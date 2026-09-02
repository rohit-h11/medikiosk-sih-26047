"""
Multi-factor image quality assessment and intelligent routing engine for MediKiosk.
Evaluates sharpness inside text ROIs, contrast, illumination uniformity, glare,
and document type to make precise routing decisions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

from .config import PreprocessConfig, DocumentType, RoutingDecision
from .steps import classify_handwritten_vs_printed



@dataclass
class QualityReport:
    sharpness: float                      # ROI-specific Laplacian variance (higher = sharper)
    contrast_std: float                   # Standard deviation of luminance
    text_area_ratio: float                # Ratio of estimated text pixels to image area
    glare_ratio: float                    # Specular highlight area ratio (over-exposed zones)
    illumination_uniformity: float        # 0.0 - 1.0 (1.0 = perfectly uniform lighting)
    legibility_score: float               # Composite 0 - 100 quality score
    is_acceptable: bool                   # True if clear enough for downstream processing
    document_classification: Dict[str, Any] # Detailed handwriting / printed analysis
    reasons: List[str] = field(default_factory=list) # User-facing quality flags
    suggested_route: RoutingDecision = RoutingDecision.VISION_LLM


def assess_quality(
    gray: np.ndarray,
    text_regions: List[Dict[str, Any]],
    cfg: PreprocessConfig,
    classification: Optional[Dict[str, Any]] = None
) -> QualityReport:
    """
    Evaluates image quality with clinical document safeguards:
    1. Evaluates sharpness focused strictly on text regions.
    2. Measures contrast and dynamic range.
    3. Checks for specular glare.
    4. Calculates illumination uniformity.
    5. Determines optimal route.
    """
    h, w = gray.shape
    total_pixels = float(h * w)
    reasons = []

    # 1. Text-ROI-Focused Sharpness
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    
    if text_regions:
        roi_vars = []
        for r in text_regions[:30]:
            rx, ry, rw, rh = r["x"], r["y"], r["width"], r["height"]
            roi_lap = laplacian[max(0, ry):min(h, ry + rh), max(0, rx):min(w, rx + rw)]
            if roi_lap.size > 20:
                roi_vars.append(np.var(roi_lap))
        sharpness = float(np.mean(roi_vars)) if roi_vars else float(np.var(laplacian))
    else:
        sharpness = float(np.var(laplacian))

    # 2. Contrast Standard Deviation
    contrast_std = float(np.std(gray))

    # 3. Text Area Ratio
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    text_pixels = np.count_nonzero(thresh)
    text_area_ratio = float(text_pixels / total_pixels)

    # 4. Glare / Over-exposure Detection
    # Only flag pixels at absolute saturation (255) — plain white paper is 248-253, real phone glare hits 255
    glare_pixels = np.count_nonzero(gray == 255)
    glare_ratio = float(glare_pixels / total_pixels)

    # 5. Illumination Uniformity (4x4 grid)
    grid_means = []
    gh, gw = h // 4, w // 4
    for i in range(4):
        for j in range(4):
            cell = gray[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw]
            if cell.size > 0:
                grid_means.append(np.mean(cell))
    min_mean = min(grid_means) if grid_means else 1.0
    max_mean = max(grid_means) if grid_means else 255.0
    illumination_uniformity = float(min_mean / max(1.0, max_mean))

    # 6. Classification if not provided
    if classification is None:
        classification = classify_handwritten_vs_printed(gray, text_regions, cfg)
        
    doc_type = classification.get("doc_type", DocumentType.HYBRID_MIXED)

    # 7. Quality Checks & Flags
    if sharpness < cfg.min_sharpness_laplacian_var:
        reasons.append(f"Low image sharpness / potential motion blur (sharpness: {sharpness:.1f} < {cfg.min_sharpness_laplacian_var})")

    if contrast_std < cfg.min_contrast_std:
        reasons.append(f"Low image contrast / washed out (contrast std: {contrast_std:.1f} < {cfg.min_contrast_std})")

    if text_area_ratio < cfg.min_text_area_ratio:
        reasons.append("Very little text detected on document")

    if glare_ratio > cfg.max_glare_area_ratio:
        reasons.append(f"Glare or bright reflection detected on document surface ({glare_ratio * 100:.1f}%)")

    if illumination_uniformity < 0.35:
        reasons.append("Heavy shadows or severely uneven lighting detected")

    # 8. Legibility Score Calculation (0 - 100)
    score_sharpness = min(100.0, (sharpness / 80.0) * 40.0)
    score_contrast = min(100.0, (contrast_std / 35.0) * 30.0)
    score_illum = illumination_uniformity * 20.0
    score_glare = max(0.0, (1.0 - (glare_ratio / 0.15)) * 10.0)
    
    legibility_score = round(score_sharpness + score_contrast + score_illum + score_glare, 1)
    legibility_score = max(0.0, min(100.0, legibility_score))

    # 9. Intelligent Routing Decision
    is_acceptable = (
        sharpness >= cfg.min_sharpness_laplacian_var and
        contrast_std >= cfg.min_contrast_std and
        glare_ratio <= cfg.max_glare_area_ratio and
        text_area_ratio >= cfg.min_text_area_ratio
    )

    if not is_acceptable:
        if sharpness < (cfg.min_sharpness_laplacian_var * 0.4) or glare_ratio > (cfg.max_glare_area_ratio * 2.5):
            suggested_route = RoutingDecision.RETAKE
        else:
            suggested_route = RoutingDecision.VISION_LLM_FALLBACK
    else:
        if doc_type == DocumentType.PRINTED or doc_type == DocumentType.LAB_REPORT:
            suggested_route = RoutingDecision.OCR_FAST
        elif doc_type == DocumentType.HANDWRITTEN:
            suggested_route = RoutingDecision.VISION_LLM
        else:
            suggested_route = RoutingDecision.HYBRID_FUSION

    return QualityReport(
        sharpness=round(sharpness, 1),
        contrast_std=round(contrast_std, 1),
        text_area_ratio=round(text_area_ratio, 4),
        glare_ratio=round(glare_ratio, 4),
        illumination_uniformity=round(illumination_uniformity, 3),
        legibility_score=legibility_score,
        is_acceptable=is_acceptable,
        document_classification=classification,
        reasons=reasons,
        suggested_route=suggested_route
    )
