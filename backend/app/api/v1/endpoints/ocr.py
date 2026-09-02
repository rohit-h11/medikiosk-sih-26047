"""
FastAPI REST endpoints for MediKiosk Document OCR and Multimodal Vision LLM Digitization.
Provides instant camera preview quality checking and complete structured clinical extraction.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel

from app.ai.ocr import (
    run_pipeline,
    extract_document_data,
    PreprocessConfig,
    VisionLLMConfig,
    RoutingDecision
)


router = APIRouter(prefix="/ocr", tags=["Document OCR & Digitization"])


class QualityCheckResponse(BaseModel):
    is_acceptable: bool
    legibility_score: float
    sharpness: float
    contrast_std: float
    illumination_uniformity: float
    document_type: str
    handwritten_ratio: float
    routing_decision: str
    reasons: list[str]
    retake_required: bool


@router.post("/quality-check", response_model=QualityCheckResponse)
async def check_document_quality(
    file: UploadFile = File(...)
):
    """
    Ultra-fast quality assessment endpoint for Kiosk camera preview.
    Evaluates sharpness, contrast, lighting uniformity, glare, and handwritten vs. printed type
    to give instant retake feedback before running full LLM extraction.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File provided must be an image (JPEG/PNG/WebP)"
        )

    try:
        contents = await file.read()
        cfg = PreprocessConfig(save_intermediate_steps=False)
        result = run_pipeline(contents, cfg=cfg)

        quality = result.quality
        doc_class = quality.document_classification

        return QualityCheckResponse(
            is_acceptable=quality.is_acceptable,
            legibility_score=quality.legibility_score,
            sharpness=quality.sharpness,
            contrast_std=quality.contrast_std,
            illumination_uniformity=quality.illumination_uniformity,
            document_type=result.doc_type.value,
            handwritten_ratio=doc_class.get("handwritten_ratio", 0.0),
            routing_decision=result.route.value,
            reasons=quality.reasons,
            retake_required=(result.route == RoutingDecision.RETAKE)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image quality check failed: {str(e)}"
        )


@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """
    Complete document digitization pipeline:
    1. Dual-stream Preprocessing (RGB + Binary)
    2. Handwritten vs. Printed Classification
    3. Multimodal Vision LLM Structured Extraction (Allopathic & Ayurvedic/AYUSH)
    4. Abnormal Lab Value Flagging
    5. Preparation of RAG Text Chunks for Supabase pgvector
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File provided must be an image (JPEG/PNG/WebP)"
        )

    try:
        contents = await file.read()
        res = extract_document_data(
            image_input=contents,
            patient_id=patient_id
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document extraction failed: {str(e)}"
        )
