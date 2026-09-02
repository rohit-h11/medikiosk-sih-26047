"""
Tunable parameters and configurations for the MediKiosk document preprocessing,
handwritten/printed classification, and Vision LLM clinical extraction pipeline.
Designed specifically for Indian OPD prescriptions (Allopathic & AYUSH/Ayurveda).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class DocumentType(str, Enum):
    PRINTED = "printed"                # Computerized lab report, discharge summary, printed invoice
    HANDWRITTEN = "handwritten"        # Fully handwritten prescription / clinical note
    HYBRID_MIXED = "hybrid_mixed"      # Printed hospital letterhead/template with handwritten Rx & notes
    LAB_REPORT = "lab_report"          # Formatted tabular investigation report with reference ranges


class MedicineSystem(str, Enum):
    ALLOPATHIC = "allopathic"
    AYURVEDIC = "ayurvedic"
    UNANI = "unani"
    SIDDHA = "siddha"
    HOMEOPATHY = "homeopathy"
    MIXED = "mixed"


class RoutingDecision(str, Enum):
    OCR_FAST = "ocr"                               # Printed / high-contrast -> Fast OCR
    VISION_LLM = "vision_llm"                       # Handwritten / AYUSH / complex -> Vision LLM
    HYBRID_FUSION = "hybrid_fusion"                 # Printed template + handwriting -> Dual pass
    VISION_LLM_FALLBACK = "vision_llm_fallback"     # Borderline quality -> Resilient Vision LLM
    RETAKE = "retake"                               # Severely blurred / occluded -> Kiosk retake prompt


@dataclass
class PreprocessConfig:
    """Tunable parameters for computer vision preprocessing steps."""
    # --- Denoising & Filtering ---
    denoise_method: str = "bilateral"   # "bilateral" (edge-preserving, keeps decimal points) or "nlm"
    denoise_h: int = 8                  # strength for fastNlMeans / bilateral sigmaColor
    bilateral_d: int = 7                # diameter of pixel neighborhood
    bilateral_sigma_space: int = 50

    # --- Contrast Enhancement (CLAHE) ---
    clahe_clip_limit: float = 2.0
    clahe_tile_grid: Tuple[int, int] = (8, 8)

    # --- Illumination Correction ---
    illum_method: str = "morphological" # "morphological" (avoids dark shadow halos) or "gaussian_blur"
    illum_kernel_size: int = 51

    # --- Binarization (Soft Adaptive Threshold) ---
    adaptive_block_size: int = 31       # must be odd
    adaptive_C: int = 9

    # --- Morphological Cleanup ---
    morph_kernel_size: int = 2
    apply_morph_close: bool = True      # connect broken strokes (subtle, 2x2)
    apply_morph_open: bool = False      # disabled by default to avoid erasing decimal points & diacritics

    # --- Orientation & Deskew ---
    enable_orientation_check: bool = True
    max_correctable_skew_deg: float = 25.0
    devanagari_shirorekha_aware: bool = True  # ignore dominant horizontal lines if Hindi/Sanskrit header

    # --- Document Boundary Crop & Dewarp ---
    enable_boundary_crop: bool = True
    min_boundary_area_ratio: float = 0.25
    perspective_warp_aspect_ratio_range: Tuple[float, float] = (0.5, 2.0)

    # --- Resolution & Dimension Normalization ---
    target_short_edge_px: int = 1800    # sweet spot for OCR engines and Vision LLM patch tile encoders
    max_upscale_factor: float = 2.5

    # --- Handwriting vs. Printed Classifier Thresholds ---
    stroke_variance_threshold: float = 0.35    # High variance in stroke width indicates handwriting
    bounding_box_height_std_threshold: float = 8.0  # Irregular letter heights indicate handwriting
    edge_curvature_threshold: float = 0.42     # High curvilinear loops vs straight lines

    # --- Quality Check Thresholds ---
    min_sharpness_laplacian_var: float = 25.0  # Evaluated within text ROIs
    min_contrast_std: float = 12.0
    min_text_area_ratio: float = 0.005         # Relaxed for 2-line short dispensary slips
    max_glare_area_ratio: float = 0.65         # Glare cutoff: real flash glare is localised blobs; plain white paper is naturally >50% bright pixels

    # --- Output & Debugging ---
    save_intermediate_steps: bool = True


@dataclass
class VisionLLMConfig:
    """Settings for the Multimodal Vision LLM Clinical Extraction engine."""
    provider: str = "gemini"            # "gemini" | "openai" | "mock"
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.1            # low temperature for factual medical extraction
    max_output_tokens: int = 16384      # generous token limit to accommodate thinking + structured clinical JSON
    enable_ayush_detection: bool = True
    enable_abnormal_lab_flagging: bool = True
    enable_namaste_icd11_mapping: bool = True
    api_key_env_var: str = "GEMINI_API_KEY"

