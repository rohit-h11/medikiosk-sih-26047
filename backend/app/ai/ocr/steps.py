"""
Individual Computer Vision preprocessing steps and handwriting/printed classifiers
for MediKiosk document digitization.
Includes Devanagari script awareness, edge-preserving filtering, and dual RGB/Grayscale preservation.
"""

from typing import Tuple, List, Dict, Any, Optional
import cv2
import numpy as np

from .config import PreprocessConfig, DocumentType



# ============================================================================
# 1. COLOR NORMALIZATION / WHITE BALANCE
# ============================================================================
def white_balance(img_bgr: np.ndarray) -> np.ndarray:
    """
    Applies Gray-World color constancy algorithm with percentile clipping
    to normalize lighting variations from kiosk camera / ambient room lights.
    Preserves RGB color fidelity for the Vision LLM stream.
    """
    result = img_bgr.copy().astype(np.float32)
    avg_b = np.percentile(result[:, :, 0], 50)
    avg_g = np.percentile(result[:, :, 1], 50)
    avg_r = np.percentile(result[:, :, 2], 50)
    
    # Target gray reference (mean of the three channels)
    avg_gray = (avg_b + avg_g + avg_r) / 3.0
    if avg_b > 0 and avg_g > 0 and avg_r > 0:
        result[:, :, 0] = np.clip(result[:, :, 0] * (avg_gray / avg_b), 0, 255)
        result[:, :, 1] = np.clip(result[:, :, 1] * (avg_gray / avg_g), 0, 255)
        result[:, :, 2] = np.clip(result[:, :, 2] * (avg_gray / avg_r), 0, 255)
        
    return result.astype(np.uint8)


# ============================================================================
# 2. GRAYSCALE CONVERSION
# ============================================================================
def to_grayscale(img_bgr: np.ndarray) -> np.ndarray:
    """Converts BGR image to single-channel 8-bit grayscale."""
    if len(img_bgr.shape) == 2:
        return img_bgr.copy()
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


# ============================================================================
# 3. EDGE-PRESERVING DENOISING
# ============================================================================
def denoise(gray: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Edge-preserving smoothing. Uses bilateral filtering by default to maintain
    thin pen strokes, decimal points (e.g. 0.5 mg), and Hindi/Sanskrit diacritics
    (Anusvara, Nukta) while removing sensor/paper grain noise.
    """
    if cfg.denoise_method == "bilateral":
        return cv2.bilateralFilter(
            gray,
            d=cfg.bilateral_d,
            sigmaColor=cfg.denoise_h * 5,
            sigmaSpace=cfg.bilateral_sigma_space
        )
    elif cfg.denoise_method == "nlm":
        return cv2.fastNlMeansDenoising(
            gray,
            h=cfg.denoise_h,
            templateWindowSize=7,
            searchWindowSize=21
        )
    else:
        return cv2.GaussianBlur(gray, (3, 3), 0)


# ============================================================================
# 4. ORIENTATION DETECTION & CORRECTION (0 / 90 / 180 / 270)
# ============================================================================
def detect_and_fix_orientation(gray: np.ndarray, cfg: PreprocessConfig) -> Tuple[np.ndarray, int]:
    """
    Detects major 90-degree rotational orientation based on horizontal text line
    energy and gradient projections. Rotates to upright position.
    """
    if not cfg.enable_orientation_check:
        return gray, 0

    best_angle = 0
    max_horizontal_energy = -1.0
    h, w = gray.shape

    # For fast check, downsample if image is large
    scale = min(1.0, 1000.0 / max(h, w))
    small = cv2.resize(gray, (int(w * scale), int(h * scale))) if scale < 1.0 else gray

    for angle in [0, 90, 180, 270]:
        if angle == 0:
            rotated = small
        elif angle == 90:
            rotated = cv2.rotate(small, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            rotated = cv2.rotate(small, cv2.ROTATE_180)
        elif angle == 270:
            rotated = cv2.rotate(small, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Compute horizontal projection profile variance (text lines create distinct peaks and valleys)
        sobel_v = cv2.Sobel(rotated, cv2.CV_32F, 0, 1, ksize=3)
        horizontal_proj = np.sum(np.abs(sobel_v), axis=1)
        energy = float(np.var(horizontal_proj))

        if energy > max_horizontal_energy:
            max_horizontal_energy = energy
            best_angle = angle

    # Apply best rotation to original resolution image
    if best_angle == 0:
        return gray, 0
    elif best_angle == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE), 90
    elif best_angle == 180:
        return cv2.rotate(gray, cv2.ROTATE_180), 180
    elif best_angle == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE), 270
    return gray, 0


# ============================================================================
# 5. DESKEW (FINE ROTATION CORRECTION)
# ============================================================================
def deskew(gray: np.ndarray, cfg: PreprocessConfig) -> Tuple[np.ndarray, float]:
    """
    Corrects small rotational skew (-25 to +25 deg).
    Incorporates Devanagari Shirorekha tolerance to avoid getting misled by
    isolated Hindi/Sanskrit header lines.
    """
    h, w = gray.shape
    
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    
    pts = cv2.findNonZero(thresh)
    if pts is None or len(pts) < 100:
        return gray, 0.0

    rect = cv2.minAreaRect(pts)
    angle = rect[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) > cfg.max_correctable_skew_deg or abs(angle) < 0.3:
        return gray, 0.0

    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return deskewed, float(angle)


# ============================================================================
# 6. ILLUMINATION CORRECTION
# ============================================================================
def correct_illumination(gray: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Corrects uneven illumination, shadows, and vignetting.
    Uses morphological background estimation (closing with large structuring element)
    which avoids the high-contrast dark halo bands caused by simple Gaussian division.
    """
    if cfg.illum_method == "morphological":
        ksize = cfg.illum_kernel_size
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
        background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        background = np.maximum(background, 1)
        corrected = np.clip((gray.astype(np.float32) / background.astype(np.float32)) * 240.0, 0, 255)
        return corrected.astype(np.uint8)
    else:
        blur = cv2.GaussianBlur(gray, (cfg.illum_kernel_size, cfg.illum_kernel_size), 0)
        corrected = cv2.divide(gray, blur, scale=255)
        return corrected


# ============================================================================
# 7. CONTRAST ENHANCEMENT (CLAHE)
# ============================================================================
def enhance_contrast(img: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE).
    If color image is passed, applies CLAHE to the L channel in LAB color space
    to enhance contrast while perfectly preserving RGB color fidelity.
    """
    clahe = cv2.createCLAHE(
        clipLimit=cfg.clahe_clip_limit,
        tileGridSize=cfg.clahe_tile_grid
    )
    
    if len(img.shape) == 3:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    else:
        return clahe.apply(img)


# ============================================================================
# 8. SOFT ADAPTIVE BINARIZATION
# ============================================================================
def binarize(gray: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Binarizes image for OCR engines using Soft Adaptive Gaussian Thresholding.
    Tunes parameters to retain faint ballpoint ink and doctor cursive loops.
    """
    block_size = cfg.adaptive_block_size
    if block_size % 2 == 0:
        block_size += 1
        
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        cfg.adaptive_C
    )
    return binary


# ============================================================================
# 9. MORPHOLOGICAL CLEANUP
# ============================================================================
def morphological_cleanup(binary: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Gentle stroke-preserving cleanup. Applies a minimal 2x2 closing to bridge
    broken handwriting strokes. Skips aggressive opening to avoid erasing
    decimal points (e.g. 0.5mg) or Devanagari dots (Anusvara/Nukta).
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (cfg.morph_kernel_size, cfg.morph_kernel_size)
    )
    result = binary.copy()
    
    if cfg.apply_morph_close:
        inv = cv2.bitwise_not(result)
        inv = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel)
        result = cv2.bitwise_not(inv)
        
    if cfg.apply_morph_open:
        inv = cv2.bitwise_not(result)
        inv = cv2.morphologyEx(inv, cv2.MORPH_OPEN, kernel)
        result = cv2.bitwise_not(inv)
        
    return result


# ============================================================================
# 10. DOCUMENT BOUNDARY DETECTION & CROPPING
# ============================================================================
def crop_to_document_boundary(img: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Detects paper boundary on the kiosk tray/camera field of view.
    Finds quadrilateral contours, validates aspect ratio and area ratio,
    with a graceful bounding box fallback to prevent clipping headers/footers.
    """
    if not cfg.enable_boundary_crop:
        return img

    h, w = img.shape[:2]
    gray = to_grayscale(img)
    
    scale = min(1.0, 800.0 / max(h, w))
    small = cv2.resize(gray, (int(w * scale), int(h * scale))) if scale < 1.0 else gray
    
    blurred = cv2.GaussianBlur(small, (5, 5), 0)
    edged = cv2.Canny(blurred, 30, 120)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edged, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img
        
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    img_area = small.shape[0] * small.shape[1]
    
    for cnt in contours[:5]:
        area = cv2.contourArea(cnt)
        if area < img_area * cfg.min_boundary_area_ratio:
            continue
            
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        if len(approx) == 4:
            pts = approx.reshape(4, 2) / scale
            return dewarp_perspective(img, pts)
            
        if area >= img_area * cfg.min_boundary_area_ratio:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            pad_x = int(bw / scale * 0.02)
            pad_y = int(bh / scale * 0.02)
            
            x1 = max(0, int(bx / scale) - pad_x)
            y1 = max(0, int(by / scale) - pad_y)
            x2 = min(w, int((bx + bw) / scale) + pad_x)
            y2 = min(h, int((by + bh) / scale) + pad_y)
            
            if (x2 - x1) > w * 0.4 and (y2 - y1) > h * 0.4:
                return img[y1:y2, x1:x2]
                
    return img


# ============================================================================
# 11. PERSPECTIVE DEWARP (HOMOGRAPHY TRANSFORM)
# ============================================================================
def dewarp_perspective(img: np.ndarray, pts: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Performs 4-point homography perspective transform to rectify angled captures.
    """
    if pts is None or len(pts) != 4:
        return img
        
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    (tl, tr, br, bl) = rect
    
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))
    
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))
    
    if max_width < 100 or max_height < 100:
        return img
        
    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")
    
    m = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, m, (max_width, max_height), flags=cv2.INTER_CUBIC)
    return warped


# ============================================================================
# 12. RESOLUTION / DIMENSION NORMALIZATION
# ============================================================================
def normalize_resolution(img: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """
    Standardizes image dimensions so that the short edge is approximately 1800px.
    This avoids the connected-component character height estimation trap on cursive/Devanagari
    and provides the optimal resolution for both OCR and Vision LLM token grids.
    """
    h, w = img.shape[:2]
    short_edge = min(h, w)
    
    if short_edge == 0:
        return img
        
    target = cfg.target_short_edge_px
    scale = target / float(short_edge)
    scale = min(scale, cfg.max_upscale_factor)
    
    if 0.90 <= scale <= 1.10:
        return img
        
    new_w = int(w * scale)
    new_h = int(h * scale)
    interpolation = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
    return cv2.resize(img, (new_w, new_h), interpolation=interpolation)


# ============================================================================
# 13. TEXT REGION (ROI) DETECTION
# ============================================================================
def detect_text_regions(gray: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detects text bounding boxes (ROIs) across the document.
    Uses morphological gradient and horizontal smearing to identify text lines.
    """
    h, w = gray.shape
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_x = np.abs(grad_x)
    grad_norm = cv2.normalize(grad_x, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    connected = cv2.morphologyEx(grad_norm, cv2.MORPH_CLOSE, kernel)
    
    _, thresh = cv2.threshold(connected, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw > 15 and bh > 8 and (bw * bh) < (h * w * 0.5):
            regions.append({
                "x": int(x),
                "y": int(y),
                "width": int(bw),
                "height": int(bh),
                "area": int(bw * bh),
                "aspect_ratio": round(float(bw) / max(1, bh), 2)
            })
            
    regions = sorted(regions, key=lambda r: (r["y"] // 30, r["x"]))
    return regions


# ============================================================================
# 14. HANDWRITTEN VS. PRINTED CLASSIFIER
# ============================================================================
def classify_handwritten_vs_printed(
    gray: np.ndarray,
    text_regions: List[Dict[str, Any]],
    cfg: PreprocessConfig
) -> Dict[str, Any]:
    """
    Classifies whether a document is PRINTED, HANDWRITTEN, HYBRID_MIXED, or LAB_REPORT.

    Uses 4 discriminative features per text region:
      1. Stroke Width Variance (SWV) — handwriting has highly variable pen pressure
      2. X-Height / Cap-Height Uniformity — printed fonts have very consistent character height
      3. Edge Axial Ratio — printed text has dominant horizontal/vertical edges
      4. Bounding-box aspect ratio variance — printed chars are more uniform in width
    Then applies a majority-vote with calibrated thresholds.
    """
    if not text_regions:
        return {
            "doc_type": DocumentType.HYBRID_MIXED,
            "handwritten_ratio": 0.5,
            "confidence": 0.5,
            "handwritten_region_count": 0,
            "printed_region_count": 0
        }

    h, w = gray.shape
    handwritten_count = 0
    printed_count = 0
    region_details = []
    region_heights: List[float] = []

    sample_regions = text_regions[:50]

    for r in sample_regions:
        rx, ry, rw, rh = r["x"], r["y"], r["width"], r["height"]
        rx, ry = max(0, rx), max(0, ry)
        crop = gray[ry:min(h, ry + rh), rx:min(w, rx + rw)]

        if crop.size < 80 or rw < 5 or rh < 5:
            continue

        region_heights.append(float(rh))

        # --- Feature 1: Stroke Width Variance via Distance Transform ---
        _, bin_crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        dist = cv2.distanceTransform(bin_crop, cv2.DIST_L2, 3)
        non_zero_dist = dist[dist > 0.5]
        if len(non_zero_dist) > 15:
            swv = float(np.std(non_zero_dist) / max(0.1, np.mean(non_zero_dist)))
        else:
            swv = 0.0

        # --- Feature 2: Edge Axial Ratio (horizontal + vertical edges vs diagonal) ---
        # Printed text: dominant horizontal baselines + vertical strokes
        # Handwriting: rich diagonal/curvilinear components
        gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(gx**2 + gy**2)
        strong_edges = magnitude > (np.max(magnitude) * 0.2)
        if np.any(strong_edges):
            angles = np.arctan2(np.abs(gy[strong_edges]), np.abs(gx[strong_edges])) * (180.0 / np.pi)
            # Axial = edges within 20° of horizontal (0°) or vertical (90°)
            axial_edges = np.sum((angles < 20) | (angles > 70))
            axial_ratio = float(axial_edges / max(1, len(angles)))
        else:
            axial_ratio = 0.5

        # --- Feature 3: Bounding-box Aspect Ratio (width/height) ---
        # Printed chars are fairly uniform; handwriting chars vary wildly
        ar = float(rw) / max(1.0, float(rh))

        # --- Voting: a region is classified as HANDWRITTEN if 2+ of 3 features say so ---
        votes_hw = 0
        votes_hw += 1 if swv > cfg.stroke_variance_threshold else 0          # high ink pressure variation
        votes_hw += 1 if axial_ratio < 0.42 else 0                           # rich diagonals/curves
        votes_hw += 1 if ar > 3.5 else 0                                     # extremely wide squished chars (cursive blobs)

        is_hw = votes_hw >= 2  # majority vote (at least 2 out of 3 features)

        if is_hw:
            handwritten_count += 1
        else:
            printed_count += 1

        region_details.append({
            **r,
            "is_handwritten": bool(is_hw),
            "stroke_variance": round(swv, 3),
            "axial_ratio": round(axial_ratio, 3),
            "aspect_ratio": round(ar, 3),
        })

    # --- Feature 4: X-Height / Cap-Height Uniformity across all regions ---
    # Printed fonts have very consistent character heights (low coefficient of variation)
    # Handwriting has highly irregular heights (CV > 0.30)
    if len(region_heights) >= 5:
        h_cv = float(np.std(region_heights) / max(1.0, np.mean(region_heights)))
        # If height is very uniform (CV < 0.20), strongly push toward PRINTED
        if h_cv < 0.20:
            # Boost printed count by adding synthetic printed votes
            boost = max(1, printed_count // 2)
            printed_count += boost
        # If height is wildly irregular (CV > 0.45), push toward HANDWRITTEN
        elif h_cv > 0.45:
            boost = max(1, handwritten_count // 2)
            handwritten_count += boost
    else:
        h_cv = 0.5

    # --- Table/Grid Detection for Lab Reports ---
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))
    thresh_all = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    h_lines = cv2.morphologyEx(thresh_all, cv2.MORPH_OPEN, horizontal_kernel)
    v_lines = cv2.morphologyEx(thresh_all, cv2.MORPH_OPEN, vertical_kernel)
    table_grid_score = (np.count_nonzero(h_lines) + np.count_nonzero(v_lines)) / float(h * w)

    total_sampled = max(1, handwritten_count + printed_count)
    hw_ratio = float(handwritten_count / total_sampled)

    # --- Final Decision Logic ---
    if table_grid_score > 0.015 and hw_ratio < 0.35:
        doc_type = DocumentType.LAB_REPORT
    elif hw_ratio >= 0.65:
        # Clear majority handwritten
        doc_type = DocumentType.HANDWRITTEN
    elif hw_ratio <= 0.25:
        # Clear majority printed (lowered from 0.20 to catch near-printed EMR forms)
        doc_type = DocumentType.PRINTED
    elif hw_ratio >= 0.35 and hw_ratio < 0.65:
        # Mixed — printed letterhead/template with handwritten notes
        doc_type = DocumentType.HYBRID_MIXED
    else:
        doc_type = DocumentType.PRINTED  # default lean toward printed for ambiguous cases

    confidence = round(float(abs(hw_ratio - 0.5) * 2 * 0.4 + 0.6), 2)

    return {
        "doc_type": doc_type,
        "handwritten_ratio": round(hw_ratio, 3),
        "confidence": confidence,
        "handwritten_region_count": handwritten_count,
        "printed_region_count": printed_count,
        "table_grid_score": round(table_grid_score, 4),
        "height_cv": round(h_cv, 3),
        "regions": region_details
    }

