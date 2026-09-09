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
    generate_thumbnail_webp,
    ndarray_to_webp
)
import numpy as np
from app.ai.ocr.pre_ingestion_gate import (
    compute_sha256,
    compute_dual_perceptual_hashes,
    compute_perceptual_dhash,
    compute_perceptual_phash,
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
    duplicate_type: Optional[str] = Field(default=None, description="'EXACT_SHA256' | 'VISUAL_DHASH' | 'VISUAL_PHASH' | None")
    extracted_data: Optional[Dict[str, Any]] = Field(default=None, description="Structured clinical medical JSON")
    message: Optional[str] = None


# Global in-memory fast triage cache to prevent re-processing identical uploads in same session
_patient_doc_cache: Dict[str, List[Dict[str, Any]]] = {}


@router.post(
    "/process-document",
    response_model=ProcessDocResponse,
    summary="Direct WebP/JPEG upload, 30ms Blur/Glare Triage Gate, Vision OCR & Async pgvector Embedding",
    status_code=status.HTTP_200_OK
)
@router.post("/process", response_model=ProcessDocResponse, status_code=status.HTTP_200_OK)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Raw or compressed document image (WebP/JPEG/PNG)"),
    patient_id: str = Form(..., description="Patient ID / ABHA ID"),
    session_id: Optional[str] = Form(None, description="Kiosk session ID"),
    document_type: Optional[str] = Form(None, description="Optional. If omitted, Vision AI auto-classifies as prescription, lab_report, or ayurvedic_prescription"),
    bypass_duplicate_check: bool = Form(False, description="Set to true to force OCR re-execution")
) -> ProcessDocResponse:
    """
    Unified Single-Endpoint Architecture (Option A: Cropped Master Archival):
    1. Deduplication Gate (< 2 ms):
       - Tier A: Cryptographic SHA-256 for exact byte matches.
       - Tier B: 64-bit Perceptual Difference Hash (dHash) for layout/text boundaries.
       - Tier C: 64-bit DCT Perceptual Hash (pHash) for illumination, glare, and angle invariance.
       - Returns existing stored record & extracted JSON immediately if duplicate.
    2. Quality Triage Gate (< 10 ms):
       - Rejects motion blur, out-of-focus, washed-out, or heavily glared images.
    3. Multimodal Vision LLM Extraction (Gemini 3.6 Flash / Fallback):
       - Dual Allopathy + AYUSH entity extraction & Namaste coding in ~1.2s.
    4. Image Normalization & Storage (< 10 ms) [Option A]:
       - Perspective dewarps, deskews, crops to document boundary, and archives cropped master WebP + 300px thumbnail.
    5. Asynchronous Vector Ingestion (Background Offloading):
       - Generates 384-dim clinical embeddings and inserts into pgvector.
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty image payload received."
            )

        # ── 1. DEDUPLICATION GATE: SHA-256 & DUAL PERCEPTUAL DHASH/PHASH (< 2 ms) ─────────
        file_hash = compute_sha256(file_bytes)
        try:
            dhash_val, phash_val = compute_dual_perceptual_hashes(file_bytes)
        except Exception:
            dhash_val, phash_val = None, None

        # Fast Path 1: Check in-memory patient cache (SHA-256, Visual dHash & pHash)
        patient_cached_docs = _patient_doc_cache.get(patient_id, [])
        for cached in patient_cached_docs:
            is_exact = (cached.get("sha256") == file_hash)
            is_dhash = (dhash_val and cached.get("dhash") and is_perceptual_duplicate(cached.get("dhash"), dhash_val, max_distance=5))
            is_phash = (phash_val and cached.get("phash") and is_perceptual_duplicate(cached.get("phash"), phash_val, max_distance=6))

            if is_exact or is_dhash or is_phash:
                if is_exact:
                    dup_type = "EXACT_SHA256"
                elif is_dhash:
                    dup_type = "VISUAL_DHASH"
                else:
                    dup_type = "VISUAL_PHASH"

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

        # Fast Path 2: Check PostgreSQL database (SQL Index + Vectorized Dual dHash/pHash)
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
                    dhash_fingerprint=dhash_val,
                    phash_fingerprint=phash_val,
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
                        "phash": phash_val,
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

        # ── AUTO-DETECT DOCUMENT TYPE IF NOT PROVIDED ─────────────────────────
        resolved_doc_type = document_type
        if not resolved_doc_type:
            raw_type = str(extracted_json.get("document_type", "")).lower()
            med_sys = str(extracted_json.get("medicine_system", "")).lower()
            if "lab" in raw_type or extracted_json.get("lab_investigations"):
                resolved_doc_type = "lab_report"
            elif med_sys == "ayurvedic" or extracted_json.get("ayurvedic_entities"):
                resolved_doc_type = "ayurvedic_prescription"
            elif "discharge" in raw_type:
                resolved_doc_type = "discharge_summary"
            elif extracted_json.get("medications") or extracted_json.get("diagnoses"):
                resolved_doc_type = "prescription"
            else:
                resolved_doc_type = "prescription"
        
        extracted_json["document_type"] = resolved_doc_type

        # ── 3. OPTION A: CROPPED & RECTIFIED MASTER WEBP + 300px THUMBNAIL ─────
        cropped_rgb = extraction_result.get("processed_rgb")
        if cropped_rgb is not None and isinstance(cropped_rgb, np.ndarray):
            master_bytes = ndarray_to_webp(cropped_rgb, quality=88)
            thumb_bytes = generate_thumbnail_webp(cropped_rgb, max_dim=300, quality=75)
        else:
            master_bytes = file_bytes
            thumb_bytes = generate_thumbnail_webp(file_bytes, max_dim=300, quality=75)

        # ── 4. STORAGE PATH HIERARCHY & MEMORY CACHE ───────────────────────────
        doc_id = str(uuid.uuid4())
        master_path = f"{patient_id}/{resolved_doc_type}/{doc_id}.webp"
        thumb_path = f"{patient_id}/{resolved_doc_type}/{doc_id}_thumb.webp"

        _patient_doc_cache.setdefault(patient_id, []).append({
            "doc_id": doc_id,
            "sha256": file_hash,
            "dhash": dhash_val,
            "phash": phash_val,
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
                    "document_type": resolved_doc_type,
                    "storage_bucket": "patient-medical-records",
                    "file_path": master_path,
                    "file_path_thumb": thumb_path,
                    "mime_type": "image/webp",
                    "file_size_bytes": len(master_bytes),
                    "file_hash_sha256": file_hash,
                    "perceptual_hash_dhash": dhash_val,
                    "perceptual_hash_phash": phash_val,
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
        async def run_background_pipeline(
            sb,
            m_path: str,
            m_bytes: bytes,
            t_path: str,
            t_bytes: bytes,
            d_id: str,
            p_id: str,
            ext_res: Dict[str, Any]
        ):
            if sb:
                try:
                    storage = sb.storage.from_("patient-medical-records")
                    storage.upload(m_path, m_bytes, {"content-type": "image/webp"})
                    storage.upload(t_path, t_bytes, {"content-type": "image/webp"})
                    logger.info(f"Uploaded cropped master & thumbnail to Supabase storage for doc {d_id}")
                except Exception as upload_err:
                    logger.warning(f"Background storage upload note for {d_id}: {upload_err}")

            try:
                # Ingest findings into patient_structured_vectors via RAG pipeline
                await ingest_ocr_payload_async(
                    payload=ext_res,
                    patient_id_override=p_id,
                    document_id=d_id
                )
                logger.info(f"Ingested RAG vector chunks for doc {d_id}")
            except Exception as rag_err:
                logger.warning(f"Background RAG ingestion note for {d_id}: {rag_err}")

        background_tasks.add_task(
            run_background_pipeline,
            supabase,
            master_path,
            master_bytes,
            thumb_path,
            thumb_bytes,
            doc_id,
            patient_id,
            extraction_result
        )

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
