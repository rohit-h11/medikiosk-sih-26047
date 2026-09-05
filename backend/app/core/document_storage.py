"""
Enterprise Secure Document Storage & Ingestion Pipeline for MediKiosk.
Implements the 3-Tier Storage Model (Private Object Storage + PostgreSQL Metadata + pgvector Embeddings):
1. Pre-Ingestion Quality & Blur Triage Gate
2. Forensic Cryptographic Hashing (SHA-256) & Perceptual dHash Duplicate Detection
3. Image Optimization & Multi-Variant Generation (Processed WebP + 300px Thumbnail WebP)
4. Private Encrypted Object Storage Upload (patient-medical-records bucket)
5. PostgreSQL Relational Registration & Audit Pointers
6. Short-Lived (15-min) Presigned HMAC URL Generation for Doctor View
"""

import io
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union
from PIL import Image

from app.config import settings
from app.db import get_supabase_client
from app.schemas.document import (
    DocumentType,
    OCRStatus,
    StoredDocumentResult,
    PreIngestionCheckResult
)
from app.ai.ocr.pre_ingestion_gate import (
    run_pre_ingestion_gate,
    compute_sha256,
    compute_perceptual_dhash
)

logger = logging.getLogger("medikiosk.document_storage")

DEFAULT_BUCKET = settings.STORAGE_BUCKET_DOCUMENTS or "patient-medical-records"


def create_optimized_image_variants(raw_bytes: bytes) -> Tuple[bytes, bytes]:
    """
    Transforms raw image bytes into two optimized WebP variants:
    1. Processed Image: High-resolution (max 2048x2048), WebP Q=88 (optimized for OCR & full-screen view).
    2. UI Thumbnail: Downscaled (max 300x300), WebP Q=75 (optimized for fast Doctor Dashboard timeline rendering).
    """
    with Image.open(io.BytesIO(raw_bytes)) as img:
        # Normalize color spaces (RGBA / Palette -> RGB)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # 1. Processed Master Image (Max 2048px on longest edge)
        proc_img = img.copy()
        proc_img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        proc_buffer = io.BytesIO()
        proc_img.save(proc_buffer, format="WEBP", quality=88, method=4)
        processed_bytes = proc_buffer.getvalue()

        # 2. UI Preview Thumbnail (Max 300px on longest edge)
        thumb_img = img.copy()
        thumb_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb_img.save(thumb_buffer, format="WEBP", quality=75, method=3)
        thumbnail_bytes = thumb_buffer.getvalue()

    return processed_bytes, thumbnail_bytes


def ensure_storage_bucket_exists(supabase_client: Any, bucket_name: str = DEFAULT_BUCKET) -> None:
    """
    Verifies that the private medical document bucket exists in Supabase Storage.
    Creates it with private access (public=False) if not present.
    """
    if not supabase_client:
        return

    try:
        buckets = supabase_client.storage.list_buckets()
        existing_names = [b.name if hasattr(b, "name") else b.get("name") for b in buckets]
        if bucket_name not in existing_names:
            logger.info(f"Creating private storage bucket: {bucket_name}")
            supabase_client.storage.create_bucket(bucket_name, options={"public": False})
    except Exception as e:
        logger.warning(f"Storage bucket verification check warning (non-fatal): {e}")


def generate_signed_document_url(
    file_path: Optional[str],
    expires_in_seconds: int = 900,
    bucket_name: str = DEFAULT_BUCKET,
    supabase_client: Any = None
) -> Optional[str]:
    """
    Generates a secure, temporary (default 15-minute) signed URL for clinical viewing.
    Ensures zero public access to raw medical files.
    """
    if not file_path:
        return None

    client = supabase_client or get_supabase_client()
    if not client:
        return None

    try:
        response = client.storage.from_(bucket_name).create_signed_url(file_path, expires_in_seconds)
        if isinstance(response, dict):
            return response.get("signedURL") or response.get("signedUrl")
        elif hasattr(response, "signed_url"):
            return response.signed_url
        return None
    except Exception as e:
        logger.warning(f"Could not generate signed URL for path {file_path}: {e}")
        return None


def upload_bytes_to_storage(
    supabase_client: Any,
    bucket_name: str,
    file_path: str,
    file_bytes: bytes,
    mime_type: str = "image/webp"
) -> bool:
    """Uploads binary bytes to private Supabase Storage."""
    if not supabase_client:
        return False

    try:
        supabase_client.storage.from_(bucket_name).upload(
            file_path,
            file_bytes,
            file_options={"content-type": mime_type, "upsert": "true"}
        )
        return True
    except Exception as e:
        logger.error(f"Failed uploading {file_path} to storage bucket {bucket_name}: {e}")
        return False


async def ingest_patient_document_pipeline(
    patient_id: str,
    raw_file_bytes: bytes,
    filename: str = "document.jpg",
    document_type: Union[DocumentType, str] = DocumentType.PRESCRIPTION,
    session_id: Optional[str] = None,
    bypass_quality_check: bool = False,
    bypass_duplicate_check: bool = False,
    supabase_client: Any = None
) -> StoredDocumentResult:
    """
    Master Ingestion & Storage Pipeline:
    1. Runs Pre-Ingestion Gate (blur, contrast, glare, and multi-layer duplicate checks).
    2. If duplicate detected: returns existing document reference with fresh signed URLs.
    3. If blurry / low quality: raises ValueError with actionable retake reasons.
    4. Generates optimized WebP variants (High-Res Processed + 300px Thumbnail).
    5. Uploads files to private Supabase Object Storage in hierarchical paths.
    6. Registers forensic metadata row in PostgreSQL `patient_medical_documents`.
    7. Generates 15-minute temporary presigned viewing URLs for clinical safety.
    """
    if not patient_id or not patient_id.strip():
        raise ValueError("patient_id is required for document ingestion.")

    if not raw_file_bytes or len(raw_file_bytes) == 0:
        raise ValueError("raw_file_bytes cannot be empty.")

    # Normalize document type
    if isinstance(document_type, str):
        try:
            doc_type_enum = DocumentType(document_type.lower())
        except ValueError:
            doc_type_enum = DocumentType.OTHER
    else:
        doc_type_enum = document_type

    client = supabase_client or get_supabase_client()

    # ── STEP 1: PRE-INGESTION QUALITY & DUPLICATE GATE (< 30ms) ───────────────
    gate_result: PreIngestionCheckResult = run_pre_ingestion_gate(
        patient_id=patient_id,
        image_bytes=raw_file_bytes,
        document_type=doc_type_enum.value,
        bypass_duplicate_check=bypass_duplicate_check,
        supabase_client=client
    )

    # If duplicate detected, link and return existing record with fresh signed URLs
    if gate_result.is_duplicate and gate_result.existing_document_id and client:
        logger.info(f"Linking existing document for patient {patient_id}: {gate_result.existing_document_id}")
        existing_doc = client.table("patient_medical_documents") \
            .select("*") \
            .eq("id", gate_result.existing_document_id) \
            .single() \
            .execute()

        if existing_doc.data:
            d = existing_doc.data
            return StoredDocumentResult(
                id=d["id"],
                patient_id=d["patient_id"],
                session_id=d.get("session_id"),
                document_type=DocumentType(d.get("document_type", "prescription")),
                storage_bucket=d.get("storage_bucket", DEFAULT_BUCKET),
                file_path_raw=d.get("file_path_raw"),
                file_path_processed=d["file_path_processed"],
                file_path_thumbnail=d["file_path_thumbnail"],
                signed_url_processed=generate_signed_document_url(d["file_path_processed"], supabase_client=client),
                signed_url_thumbnail=generate_signed_document_url(d["file_path_thumbnail"], supabase_client=client),
                signed_url_raw=generate_signed_document_url(d.get("file_path_raw"), supabase_client=client),
                file_hash_sha256=d["file_hash_sha256"],
                perceptual_hash_dhash=d.get("perceptual_hash_dhash"),
                file_size_bytes=d["file_size_bytes"],
                mime_type=d["mime_type"],
                ocr_status=OCRStatus(d.get("ocr_status", "pending")),
                quality_score=float(d.get("quality_score", 100.0)),
                sharpness_score=float(d.get("sharpness_score", 0.0)),
                is_duplicate_linked=True,
                created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None
            )

    # If blurry or unreadable and not explicitly bypassed, stop immediately
    if not gate_result.is_acceptable and not bypass_quality_check:
        reasons_str = "; ".join(gate_result.reasons)
        raise ValueError(f"Document rejected at Pre-Ingestion Gate: {reasons_str}")

    # ── STEP 2: IMAGE OPTIMIZATION & VARIANT CREATION ─────────────────────────
    processed_bytes, thumb_bytes = create_optimized_image_variants(raw_file_bytes)

    # ── STEP 3: PATH DETERMINATION & OBJECT STORAGE UPLOAD ─────────────────────
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    year_month = now.strftime("%Y/%m")
    
    raw_ext = Path(filename).suffix.lower() or ".jpg"
    raw_path = f"{patient_id}/{doc_type_enum.value}/{year_month}/{doc_id}_raw{raw_ext}" if settings.STORE_RAW_ORIGINAL else None
    proc_path = f"{patient_id}/{doc_type_enum.value}/{year_month}/{doc_id}_processed.webp"
    thumb_path = f"{patient_id}/{doc_type_enum.value}/{year_month}/{doc_id}_thumb.webp"

    if client:
        ensure_storage_bucket_exists(client, DEFAULT_BUCKET)
        
        # Upload Processed WebP Master
        upload_bytes_to_storage(client, DEFAULT_BUCKET, proc_path, processed_bytes, mime_type="image/webp")
        
        # Upload UI Thumbnail
        upload_bytes_to_storage(client, DEFAULT_BUCKET, thumb_path, thumb_bytes, mime_type="image/webp")
        
        # Upload Raw Original (if enabled in settings)
        if settings.STORE_RAW_ORIGINAL and raw_path:
            mime_raw = "image/jpeg" if raw_ext in (".jpg", ".jpeg") else ("application/pdf" if raw_ext == ".pdf" else "image/png")
            upload_bytes_to_storage(client, DEFAULT_BUCKET, raw_path, raw_file_bytes, mime_type=mime_raw)

    # ── STEP 4: RELATIONAL DATABASE INSERT (POSTGRESQL) ───────────────────────
    doc_record = {
        "id": doc_id,
        "patient_id": patient_id,
        "session_id": session_id,
        "document_type": doc_type_enum.value,
        "storage_bucket": DEFAULT_BUCKET,
        "file_path_raw": raw_path,
        "file_path_processed": proc_path,
        "file_path_thumbnail": thumb_path,
        "file_hash_sha256": gate_result.sha256_hash,
        "perceptual_hash_dhash": gate_result.dhash_fingerprint,
        "mime_type": "image/webp",
        "file_size_bytes": len(raw_file_bytes),
        "page_count": 1,
        "quality_score": gate_result.quality_score,
        "sharpness_score": gate_result.sharpness,
        "contrast_std": gate_result.contrast_std,
        "glare_ratio": gate_result.glare_ratio,
        "ocr_status": "pending",
        "is_reviewed_by_doctor": False
    }

    if client:
        try:
            client.table("patient_medical_documents").insert(doc_record).execute()
            logger.info(f"Registered medical document {doc_id} in database for patient {patient_id}")
        except Exception as e:
            logger.error(f"Failed inserting document record into database: {e}")

    # ── STEP 5: GENERATE TEMPORARY SIGNED VIEWING URLS ────────────────────────
    signed_proc = generate_signed_document_url(proc_path, expires_in_seconds=900, supabase_client=client)
    signed_thumb = generate_signed_document_url(thumb_path, expires_in_seconds=900, supabase_client=client)
    signed_raw = generate_signed_document_url(raw_path, expires_in_seconds=900, supabase_client=client) if raw_path else None

    return StoredDocumentResult(
        id=doc_id,
        patient_id=patient_id,
        session_id=session_id,
        document_type=doc_type_enum,
        storage_bucket=DEFAULT_BUCKET,
        file_path_raw=raw_path,
        file_path_processed=proc_path,
        file_path_thumbnail=thumb_path,
        signed_url_processed=signed_proc,
        signed_url_thumbnail=signed_thumb,
        signed_url_raw=signed_raw,
        file_hash_sha256=gate_result.sha256_hash,
        perceptual_hash_dhash=gate_result.dhash_fingerprint,
        file_size_bytes=len(raw_file_bytes),
        mime_type="image/webp",
        ocr_status=OCRStatus.PENDING,
        quality_score=gate_result.quality_score,
        sharpness_score=gate_result.sharpness,
        is_duplicate_linked=False,
        created_at=now
    )
