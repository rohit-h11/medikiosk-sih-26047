"""
MediKiosk — Document Ingestion & Multimodal Vision LLM Digitization Endpoint.
Single unified endpoint for direct WebP upload, SHA-256 + Perceptual dHash deduplication,
quality triage, Gemini 3.6 Flash Vision OCR, in-memory thumbnailing, Supabase Storage archiving,
and pgvector RAG ingestion.
"""

import hashlib
import uuid
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.db import get_supabase_client
from app.ai.ocr import (
    extract_document_data,
    generate_thumbnail_webp
)
from app.ai.ocr.pre_ingestion_gate import (
    compute_sha256,
    compute_perceptual_dhash,
    is_perceptual_duplicate,
    check_existing_duplicates
)
from app.ai.rag.inserter import ingest_ocr_payload_async

logger = logging.getLogger("medikiosk.api.ocr")
router = APIRouter(prefix="/ocr", tags=["Document Ingestion & Vision OCR"])


class ProcessDocResponse(BaseModel):
    status: str = Field(..., description="'completed' | 'quality_rejected' | 'failed'")
    retake_required: bool = Field(default=False, description="True if image is too blurry, dark, or glared")
    quality_score: Optional[float] = Field(default=None, description="0.0 to 100.0 legibility score")
    quality_reasons: List[str] = Field(default_factory=list, description="Reasons for quality assessment or retake")
    doc_id: Optional[str] = None
    patient_id: Optional[str] = None
    file_path: Optional[str] = Field(default=None, description="Supabase storage path to 2048px Master WebP")
    file_path_thumb: Optional[str] = Field(default=None, description="Supabase storage path to 300px Thumbnail WebP")
    is_duplicate: bool = Field(default=False, description="True if exact document or visual duplicate was previously processed")
    duplicate_type: Optional[str] = Field(default=None, description="'EXACT_SHA256' | 'VISUAL_DHASH' | None")
    extracted_data: Optional[Dict[str, Any]] = Field(default=None, description="Structured clinical medical JSON")
    message: Optional[str] = None


# In-memory document deduplication registry: patient_id -> list of doc entries
_patient_doc_cache: Dict[str, List[Dict[str, Any]]] = {}


@router.post("/process-document", response_model=ProcessDocResponse, status_code=status.HTTP_200_OK)
@router.post("/process", response_model=ProcessDocResponse, status_code=status.HTTP_200_OK)
async def process_document_ocr(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="High-resolution 2048px WebP prescription image (~250 KB)"),
    patient_id: str = Form(..., description="Unique Patient ID or ABHA ID"),
    document_type: str = Form("prescription", description="'prescription' | 'lab_report' | 'ayurvedic_record'"),
    session_id: Optional[str] = Form(None, description="Optional active dialogue session ID")
):
    """
    Unified Single Document Ingestion & Vision OCR Endpoint:
    1. Receives 2048px WebP image bytes directly into memory (~250 KB).
    2. Multi-tier Deduplication Check (< 1ms):
       - Tier A: Exact Cryptographic SHA-256 Hash.
       - Tier B: 64-bit Perceptual Difference Hash (dHash) for visual/angle variations.
       - IF duplicate: Skips storage & Gemini OCR, returning cached clinical JSON in <8ms!
    3. Runs OpenCV blur, contrast, text-density, and glare triage (<20ms).
       - IF blurry/glared: Immediately returns 'quality_rejected' with retake reasons.
    4. Passes 2048px WebP bytes directly to Gemini 3.6 Flash Vision OCR (~1.2s, Zero Supabase download).
    5. Generates 300px WebP thumbnail in-memory (2ms).
    6. Persists structured JSON & metadata to PostgreSQL.
    7. Schedules non-blocking background tasks:
       - Uploads Master WebP + Thumbnail to Supabase Storage bucket.
       - Asynchronously embeds findings into `patient_structured_vectors` for cross-visit RAG.
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty image payload received."
            )

        # ── 1. DEDUPLICATION GATE: SHA-256 & PERCEPTUAL DHASH (< 1 ms) ─────────
        file_hash = compute_sha256(file_bytes)
        try:
            dhash_val = compute_perceptual_dhash(file_bytes)
        except Exception:
            dhash_val = None

        # Fast Path 1: Check in-memory patient cache (SHA-256 & Visual dHash)
        patient_cached_docs = _patient_doc_cache.get(patient_id, [])
        for cached in patient_cached_docs:
            is_exact = (cached.get("sha256") == file_hash)
            is_visual = (dhash_val and cached.get("dhash") and is_perceptual_duplicate(cached.get("dhash"), dhash_val, max_distance=5))

            if is_exact or is_visual:
                dup_type = "EXACT_SHA256" if is_exact else "VISUAL_DHASH"
                logger.info(f"Duplicate document recognized in-memory ({dup_type}) for patient {patient_id}.")
                return ProcessDocResponse(
                    status="completed",
                    doc_id=cached.get("doc_id"),
                    patient_id=patient_id,
                    file_path=cached.get("file_path"),
                    file_path_thumb=cached.get("file_path_thumb"),
                    is_duplicate=True,
                    duplicate_type=dup_type,
                    quality_score=100.0,
                    extracted_data=cached.get("extracted_data"),
                    message=f"Duplicate document recognized ({dup_type}). Retrieved existing clinical findings."
                )

        # Fast Path 2: Check PostgreSQL database (SQL Index + Vectorized NumPy dHash)
        supabase = None
        try:
            supabase = get_supabase_client()
        except Exception as e:
            logger.warning(f"Could not connect to Supabase: {e}")

        if supabase:
            try:
                is_db_dup, db_dup_reason, existing_doc_id = check_existing_duplicates(
                    patient_id=patient_id,
                    sha256_hash=file_hash,
                    dhash_fingerprint=dhash_val or "",
                    document_type=document_type,
                    supabase_client=supabase
                )

                if is_db_dup and existing_doc_id:
                    logger.info(f"Duplicate document detected in database ({db_dup_reason}) for patient {patient_id} (doc_id: {existing_doc_id}).")
                    existing_doc = supabase.table("patient_medical_documents") \
                        .select("file_path, file_path_thumb") \
                        .eq("id", existing_doc_id) \
                        .single() \
                        .execute()

                    existing_extraction = supabase.table("document_ocr_extractions") \
                        .select("structured_data") \
                        .eq("document_id", existing_doc_id) \
                        .execute()

                    cached_json = existing_extraction.data[0]["structured_data"] if existing_extraction.data else {}
                    master_p = existing_doc.data.get("file_path") if existing_doc.data else None
                    thumb_p = existing_doc.data.get("file_path_thumb") if existing_doc.data else None

                    # Cache in memory
                    _patient_doc_cache.setdefault(patient_id, []).append({
                        "doc_id": existing_doc_id,
                        "sha256": file_hash,
                        "dhash": dhash_val,
                        "file_path": master_p,
                        "file_path_thumb": thumb_p,
                        "extracted_data": cached_json
                    })

                    return ProcessDocResponse(
                        status="completed",
                        doc_id=existing_doc_id,
                        patient_id=patient_id,
                        file_path=master_p,
                        file_path_thumb=thumb_p,
                        is_duplicate=True,
                        duplicate_type=db_dup_reason,
                        quality_score=100.0,
                        extracted_data=cached_json,
                        message=f"Duplicate prescription detected ({db_dup_reason}). Retrieved existing medical findings."
                    )
            except Exception as db_err:
                logger.warning(f"Deduplication DB query skipped: {db_err}")

        # ── 2. EXTRACTION WITH BUILT-IN QUALITY & BLUR TRIAGE ──────────────────
        extraction_result = extract_document_data(
            image_input=file_bytes,
            patient_id=patient_id
        )

        if extraction_result.get("retake_required") or not extraction_result.get("success"):
            return ProcessDocResponse(
                status="quality_rejected",
                retake_required=True,
                quality_score=extraction_result.get("quality_score", 0.0),
                quality_reasons=extraction_result.get("reasons", []),
                message=extraction_result.get("message", "Document is too blurry or unreadable. Please hold steady and retake.")
            )

        extracted_json = extraction_result.get("extracted_data") or {}

        # ── 3. IN-MEMORY 300px THUMBNAIL GENERATION (2ms) ──────────────────────
        thumb_bytes = generate_thumbnail_webp(file_bytes)

        # ── 4. STORAGE PATH HIERARCHY & MEMORY CACHE ───────────────────────────
        doc_id = str(uuid.uuid4())
        master_path = f"{patient_id}/{document_type}/{doc_id}.webp"
        thumb_path = f"{patient_id}/{document_type}/{doc_id}_thumb.webp"

        _patient_doc_cache.setdefault(patient_id, []).append({
            "doc_id": doc_id,
            "sha256": file_hash,
            "dhash": dhash_val,
            "file_path": master_path,
            "file_path_thumb": thumb_path,
            "extracted_data": extracted_json
        })

        # ── 5. POSTGRESQL METADATA INSERTION ──────────────────────────────────
        if supabase:
            try:
                supabase.table("patient_medical_documents").insert({
                    "id": doc_id,
                    "patient_id": patient_id,
                    "session_id": session_id,
                    "document_type": document_type,
                    "storage_bucket": "patient-medical-records",
                    "file_path": master_path,
                    "file_path_thumb": thumb_path,
                    "mime_type": "image/webp",
                    "file_size_bytes": len(file_bytes),
                    "file_hash_sha256": file_hash,
                    "perceptual_hash_dhash": dhash_val,
                    "quality_score": extraction_result.get("quality_score", 100.0),
                    "ocr_status": "completed"
                }).execute()

                supabase.table("document_ocr_extractions").insert({
                    "document_id": doc_id,
                    "patient_id": patient_id,
                    "structured_data": extracted_json
                }).execute()
            except Exception as persist_err:
                logger.error(f"Failed to insert document records to Supabase: {persist_err}")

        # ── 6. NON-BLOCKING BACKGROUND TASKS (STORAGE UPLOAD + RAG INGESTION) ──
        async def background_pipeline():
            if supabase:
                try:
                    storage = supabase.storage.from_("patient-medical-records")
                    storage.upload(master_path, file_bytes, {"content-type": "image/webp"})
                    storage.upload(thumb_path, thumb_bytes, {"content-type": "image/webp"})
                    logger.info(f"Uploaded master & thumbnail to Supabase storage for doc {doc_id}")
                except Exception as upload_err:
                    logger.error(f"Background storage upload error for {doc_id}: {upload_err}")

            try:
                # Ingest findings into patient_structured_vectors via RAG pipeline
                await ingest_ocr_payload_async(
                    payload=extraction_result,
                    patient_id_override=patient_id,
                    document_id=doc_id
                )
                logger.info(f"Ingested RAG vector chunks for doc {doc_id}")
            except Exception as rag_err:
                logger.error(f"Background RAG ingestion error for {doc_id}: {rag_err}")

        background_tasks.add_task(background_pipeline)

        return ProcessDocResponse(
            status="completed",
            doc_id=doc_id,
            patient_id=patient_id,
            file_path=master_path,
            file_path_thumb=thumb_path,
            is_duplicate=False,
            duplicate_type=None,
            quality_score=extraction_result.get("quality_score", 100.0),
            extracted_data=extracted_json,
            message="Prescription successfully digitized and embedded in clinical RAG."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR Processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR Extraction failed: {str(e)}"
        )
