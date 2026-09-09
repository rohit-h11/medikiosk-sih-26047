"""
MediKiosk Document OCR and Multimodal Vision LLM Package.
"""

from .config import (
    PreprocessConfig,
    VisionLLMConfig,
    DocumentType,
    MedicineSystem,
    RoutingDecision,
)
from .pipeline import run_pipeline, PipelineResult
from .quality import assess_quality, QualityReport
from .steps import classify_handwritten_vs_printed
from .vision_llm import VisionLLMClient
from .extractor import DocumentExtractor, extract_document_data
from .image_utils import generate_thumbnail_webp, ndarray_to_webp, create_optimized_image_variants
from .schemas import (
    ExtractedDocumentData,
    MedicationItem,
    DiagnosisItem,
    LabInvestigationItem,
    AyurvedicAssessment,
    AyurvedicForm,
    AyurvedicKala,
    AbnormalFlag,
)

__all__ = [
    "generate_thumbnail_webp",
    "ndarray_to_webp",
    "create_optimized_image_variants",
    "PreprocessConfig",
    "VisionLLMConfig",
    "DocumentType",
    "MedicineSystem",
    "RoutingDecision",
    "run_pipeline",
    "PipelineResult",
    "assess_quality",
    "QualityReport",
    "classify_handwritten_vs_printed",
    "VisionLLMClient",
    "DocumentExtractor",
    "extract_document_data",
    "ExtractedDocumentData",
    "MedicationItem",
    "DiagnosisItem",
    "LabInvestigationItem",
    "AyurvedicAssessment",
    "AyurvedicForm",
    "AyurvedicKala",
    "AbnormalFlag",
]
