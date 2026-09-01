"""
End-to-end Dual-Stream Document Preprocessing and Routing Pipeline for MediKiosk.

Maintains two parallel streams:
 1. Vision LLM Stream: Preserves full-fidelity RGB color, contrast-enhanced in LAB space,
    orientation-rectified, and normalized for Multimodal ViT encoders.
 2. OCR / CV Stream: Bilateral-denoised, soft adaptive binarized, and ROI-extracted
    for fast printed OCR and handwriting classification.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, Any, List
import cv2
import numpy as np

from .config import PreprocessConfig, DocumentType, RoutingDecision
from . import steps
from .quality import assess_quality, QualityReport



@dataclass
class PipelineResult:
    final_image_binary: np.ndarray          # 1-bit / binarized image for traditional OCR
    final_image_grayscale: np.ndarray       # Contrast-enhanced grayscale image
    final_image_rgb: np.ndarray             # High-res, color-preserved RGB image for Vision LLM
    doc_type: DocumentType                  # PRINTED | HANDWRITTEN | HYBRID_MIXED | LAB_REPORT
    text_regions: List[Dict[str, Any]]       # Text bounding boxes with handwriting flags
    quality: QualityReport                  # Detailed quality metrics & reasons
    route: RoutingDecision                  # "ocr" | "vision_llm" | "hybrid_fusion" | "vision_llm_fallback" | "retake"
    debug_steps: Dict[str, np.ndarray] = field(default_factory=dict)


def run_pipeline(
    image_input: Union[str, bytes, np.ndarray],
    cfg: Optional[PreprocessConfig] = None,
    debug_dir: Optional[str] = None,
) -> PipelineResult:
    """
    Executes the complete dual-stream preprocessing pipeline on a document image.
    """
    cfg = cfg or PreprocessConfig()
    debug = {}

    def _save(name: str, img: np.ndarray, idx: int):
        if cfg.save_intermediate_steps:
            debug[f"{idx:02d}_{name}"] = img
            if debug_dir:
                os.makedirs(debug_dir, exist_ok=True)
                cv2.imwrite(os.path.join(debug_dir, f"{idx:02d}_{name}.jpg"), img)

    # 1. Load Image
    if isinstance(image_input, str):
        img_bgr = cv2.imread(image_input)
        if img_bgr is None:
            raise FileNotFoundError(f"Could not read image file at {image_input}")
    elif isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Could not decode image from provided byte stream")
    elif isinstance(image_input, np.ndarray):
        img_bgr = image_input.copy()
        if len(img_bgr.shape) == 2:
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    _save("00_original", img_bgr, 0)

    # 2. Color Normalization & White Balance (Preserves RGB Stream)
    wb_rgb = steps.white_balance(img_bgr)
    _save("01_white_balance", wb_rgb, 1)

    # 3. Grayscale Conversion (Starts OCR / CV Stream)
    gray = steps.to_grayscale(wb_rgb)
    _save("02_grayscale", gray, 2)

    # 4. Edge-Preserving Denoise (Bilateral filter keeps decimal points & diacritics)
    denoised_gray = steps.denoise(gray, cfg)
    _save("03_denoised", denoised_gray, 3)

    # 5. Orientation Detection (0 / 90 / 180 / 270)
    oriented_gray, rot_angle = steps.detect_and_fix_orientation(denoised_gray, cfg)
    if rot_angle == 90:
        oriented_rgb = cv2.rotate(wb_rgb, cv2.ROTATE_90_CLOCKWISE)
    elif rot_angle == 180:
        oriented_rgb = cv2.rotate(wb_rgb, cv2.ROTATE_180)
    elif rot_angle == 270:
        oriented_rgb = cv2.rotate(wb_rgb, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        oriented_rgb = wb_rgb
        
    _save(f"04_oriented_rot{rot_angle}", oriented_rgb, 4)

    # 6. Deskew Correction
    deskewed_gray, skew_angle = steps.deskew(oriented_gray, cfg)
    if abs(skew_angle) > 0.3:
        h, w = oriented_rgb.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        deskewed_rgb = cv2.warpAffine(
            oriented_rgb, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
    else:
        deskewed_rgb = oriented_rgb
        
    _save(f"05_deskewed_angle{skew_angle:.1f}", deskewed_rgb, 5)

    # 7. Illumination Correction (Morphological background estimation avoids shadow halos)
    illum_corrected_gray = steps.correct_illumination(deskewed_gray, cfg)
    _save("06_illumination_corrected", illum_corrected_gray, 6)

    # 8. Contrast Enhancement (CLAHE in LAB space for RGB, direct on grayscale)
    contrast_enhanced_gray = steps.enhance_contrast(illum_corrected_gray, cfg)
    contrast_enhanced_rgb = steps.enhance_contrast(deskewed_rgb, cfg)
    _save("07_contrast_enhanced_rgb", contrast_enhanced_rgb, 7)
    _save("07_contrast_enhanced_gray", contrast_enhanced_gray, 8)

    # 9. Document Boundary Detection & Cropping
    cropped_rgb = steps.crop_to_document_boundary(contrast_enhanced_rgb, cfg)
    cropped_gray = steps.to_grayscale(cropped_rgb)
    _save("08_cropped_rgb", cropped_rgb, 9)

    # 10. Resolution & Dimension Normalization (Sweet spot: ~1800px short edge)
    norm_rgb = steps.normalize_resolution(cropped_rgb, cfg)
    norm_gray = steps.to_grayscale(norm_rgb)
    _save("09_normalized_rgb", norm_rgb, 10)

    # 11. Soft Adaptive Binarization (For OCR / ROI Stream)
    final_binary = steps.binarize(norm_gray, cfg)
    final_binary = steps.morphological_cleanup(final_binary, cfg)
    _save("10_final_binary_ocr", final_binary, 11)

    # 12. Text Region (ROI) Detection
    text_regions = steps.detect_text_regions(norm_gray)

    # 13. Handwritten vs. Printed Classification
    classification = steps.classify_handwritten_vs_printed(norm_gray, text_regions, cfg)
    doc_type = classification["doc_type"]

    # 14. Quality Assessment & Routing Decision
    quality = assess_quality(norm_gray, text_regions, cfg, classification=classification)

    return PipelineResult(
        final_image_binary=final_binary,
        final_image_grayscale=norm_gray,
        final_image_rgb=norm_rgb,
        doc_type=doc_type,
        text_regions=text_regions,
        quality=quality,
        route=quality.suggested_route,
        debug_steps=debug
    )
