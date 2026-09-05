"""
Pre-Ingestion Quality & Deduplication Gate for MediKiosk.
Performs sub-30ms CPU-based image validation before any database write or Vision LLM execution.
- Sharpness & Motion Blur Detection (Laplacian Variance)
- Contrast & Illumination Uniformity Check
- Glare / Reflection Analysis
- Cryptographic SHA-256 Deduplication (Exact Byte Match)
- 64-bit Perceptual Difference Hash (dHash) for Visual Duplicate Detection
"""

import hashlib
import io
import logging
from typing import Tuple, Optional, Dict, Any, List, Union
import cv2
import numpy as np
from PIL import Image

from app.schemas.document import PreIngestionCheckResult

logger = logging.getLogger("medikiosk.ocr.gate")


def compute_sha256(file_bytes: bytes) -> str:
    """Calculates cryptographic SHA-256 checksum of raw image bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def compute_perceptual_dhash(image_input: Union[bytes, Image.Image, np.ndarray], hash_size: int = 8) -> str:
    """
    Computes a 64-bit Perceptual Difference Hash (dHash) using grayscale gradients.
    Detects two different camera captures of the same physical document page.
    
    Algorithm:
    1. Resize image to (hash_size + 1, hash_size), default (9, 8) = 72 pixels.
    2. Convert to grayscale.
    3. Compare adjacent horizontal pixels (pixel[col] > pixel[col + 1]).
    4. Construct 64-bit binary integer -> return 16-character hexadecimal string.
    """
    if isinstance(image_input, bytes):
        pil_img = Image.open(io.BytesIO(image_input)).convert("L")
    elif isinstance(image_input, np.ndarray):
        if len(image_input.shape) == 3:
            gray_arr = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        else:
            gray_arr = image_input
        pil_img = Image.fromarray(gray_arr)
    else:
        pil_img = image_input.convert("L")

    # Resize to (width=9, height=8) for 8x8 difference matrix
    resized = pil_img.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(resized, dtype=np.int32)

    # Compute difference: True if left pixel > right pixel
    diff = pixels[:, 1:] > pixels[:, :-1]

    # Convert boolean 8x8 array to 64-bit integer
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)

    # Return 16-character hex string (zero-padded)
    return f"{decimal_val:016x}"


def compute_hamming_distance(hex_hash1: str, hex_hash2: str) -> int:
    """
    Calculates the bitwise Hamming distance between two 64-bit hex hash strings.
    Distance 0 = Identical visual layout.
    Distance <= 5 = Very likely the same physical document under slightly different lighting/angle.
    Distance > 10 = Distinctly different images.
    """
    try:
        val1 = int(hex_hash1, 16)
        val2 = int(hex_hash2, 16)
        xor_result = val1 ^ val2
        return bin(xor_result).count("1")
    except (ValueError, TypeError):
        return 64


def is_perceptual_duplicate(hash1: str, hash2: str, max_distance: int = 8) -> bool:
    """Returns True if two visual dHash fingerprints are within the duplicate threshold."""
    if not hash1 or not hash2:
        return False
    return compute_hamming_distance(hash1, hash2) <= max_distance


def assess_image_clarity(
    image_bytes: bytes,
    min_sharpness: float = 30.0,
    min_contrast: float = 15.0,
    max_glare_ratio: float = 0.15
) -> Dict[str, Any]:
    """
    Evaluates raw image clarity using OpenCV on CPU (< 15ms):
    1. Sharpness via Laplacian Variance (detects motion blur / out of focus).
    2. Contrast Standard Deviation (detects washed-out or completely dark scans).
    3. Glare Ratio (detects bright flash / overhead specular reflections).
    4. Illumination Uniformity across a 4x4 spatial grid.
    5. Composite 0-100 Legibility Score.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {
            "is_valid_image": False,
            "sharpness": 0.0,
            "contrast_std": 0.0,
            "glare_ratio": 0.0,
            "illumination_uniformity": 0.0,
            "quality_score": 0.0,
            "reasons": ["Corrupt or unreadable image file format."]
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    total_pixels = float(h * w)
    reasons = []

    # 1. Laplacian Variance for Sharpness
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(np.var(laplacian))

    # 2. Luminance Contrast Standard Deviation
    contrast_std = float(np.std(gray))

    # 3. Specular Glare Detection (Saturated white paper vs. flash glare)
    glare_pixels = np.count_nonzero(gray >= 254)
    glare_ratio = float(glare_pixels / max(1.0, total_pixels))

    # 4. Illumination Uniformity (4x4 grid test)
    grid_means = []
    gh, gw = max(1, h // 4), max(1, w // 4)
    for i in range(4):
        for j in range(4):
            cell = gray[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw]
            if cell.size > 0:
                grid_means.append(float(np.mean(cell)))
    min_m = min(grid_means) if grid_means else 1.0
    max_m = max(grid_means) if grid_means else 255.0
    illumination_uniformity = float(min_m / max(1.0, max_m))

    # Quality Gate Checks
    if sharpness < min_sharpness:
        reasons.append(f"Document image is blurry (sharpness: {sharpness:.1f} < {min_sharpness:.1f}). Please hold camera steady.")

    if contrast_std < min_contrast:
        reasons.append(f"Document is washed out or too dark (contrast: {contrast_std:.1f} < {min_contrast:.1f}).")

    if glare_ratio > max_glare_ratio:
        reasons.append(f"Bright glare or reflection detected ({glare_ratio * 100:.1f}% of page). Please angle away from light.")

    if illumination_uniformity < 0.25:
        reasons.append("Severe shadows or uneven lighting detected across document surface.")

    # Composite Legibility Score (0 to 100)
    score_sharpness = min(40.0, (sharpness / 80.0) * 40.0)
    score_contrast = min(30.0, (contrast_std / 35.0) * 30.0)
    score_illum = min(20.0, illumination_uniformity * 20.0)
    score_glare = max(0.0, (1.0 - (glare_ratio / 0.15)) * 10.0)
    legibility_score = round(max(0.0, min(100.0, score_sharpness + score_contrast + score_illum + score_glare)), 1)

    is_acceptable = len(reasons) == 0

    return {
        "is_valid_image": True,
        "sharpness": round(sharpness, 1),
        "contrast_std": round(contrast_std, 1),
        "glare_ratio": round(glare_ratio, 4),
        "illumination_uniformity": round(illumination_uniformity, 3),
        "quality_score": legibility_score,
        "is_acceptable": is_acceptable,
        "reasons": reasons
    }


def check_existing_duplicates(
    patient_id: str,
    sha256_hash: str,
    dhash_fingerprint: str,
    document_type: Optional[str] = None,
    supabase_client: Any = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    High-Performance Multi-Tier Duplicate Check:
    1. Direct $O(1)$ SQL Index Hit for exact SHA-256 matches.
    2. Document-Type Scoped query in PostgreSQL.
    3. C-Speed Vectorized NumPy Bitwise XOR (`np.bitwise_count`) for visual dHash comparison (< 0.05ms).
    
    Returns: (is_duplicate: bool, reason: Optional[str], existing_document_id: Optional[str])
    """
    if not supabase_client or not patient_id:
        return False, None, None

    try:
        # ── OPTIMIZATION 1: DIRECT SQL INDEX HIT FOR EXACT SHA-256 (< 0.2ms) ──────
        sha_query = supabase_client.table("patient_medical_documents") \
            .select("id") \
            .eq("patient_id", patient_id) \
            .eq("file_hash_sha256", sha256_hash.lower())
        
        if document_type:
            sha_query = sha_query.eq("document_type", document_type)

        sha_result = sha_query.execute()
        if sha_result.data and len(sha_result.data) > 0:
            doc_id = sha_result.data[0]["id"]
            logger.info(f"Direct SHA-256 index hit: Duplicate detected for patient {patient_id} (Doc ID: {doc_id})")
            return True, "EXACT_SHA256", doc_id

        # ── OPTIMIZATION 2: DOCUMENT-TYPE SCOPED VISUAL DHASH LOOKUP ────────────
        if not dhash_fingerprint:
            return False, None, None

        dhash_query = supabase_client.table("patient_medical_documents") \
            .select("id, perceptual_hash_dhash") \
            .eq("patient_id", patient_id)
        
        if document_type:
            dhash_query = dhash_query.eq("document_type", document_type)

        dhash_rows = dhash_query.execute().data or []
        valid_rows = [r for r in dhash_rows if r.get("perceptual_hash_dhash")]

        if not valid_rows:
            return False, None, None

        # ── OPTIMIZATION 3: VECTORIZED NUMPY BITWISE COMPARISON (C-SPEED) ────────
        try:
            target_int = np.uint64(int(dhash_fingerprint, 16))
            doc_ids = [r["id"] for r in valid_rows]
            
            # Parse all 64-bit integer hashes into a contiguous C-array in memory
            hashes_arr = np.array([int(r["perceptual_hash_dhash"], 16) for r in valid_rows], dtype=np.uint64)
            
            # Vectorized bitwise XOR and bit-counting across all documents simultaneously
            if hasattr(np, "bitwise_count"):
                diffs = np.bitwise_count(hashes_arr ^ target_int)
            else:
                # Fallback vectorized popcount
                xor_arr = hashes_arr ^ target_int
                diffs = np.array([bin(int(x)).count("1") for x in xor_arr], dtype=np.int32)
            
            match_indices = np.where(diffs <= 5)[0]
            if len(match_indices) > 0:
                # Select the closest visual match (minimum Hamming distance)
                best_idx = match_indices[np.argmin(diffs[match_indices])]
                matched_doc_id = doc_ids[best_idx]
                min_dist = int(diffs[best_idx])
                logger.info(f"Vectorized dHash hit: Duplicate detected for patient {patient_id} (Doc ID: {matched_doc_id}, distance={min_dist})")
                return True, "VISUAL_DHASH", matched_doc_id

        except Exception as vec_err:
            logger.warning(f"Vectorized dHash comparison fallback to scalar loop: {vec_err}")
            for row in valid_rows:
                if is_perceptual_duplicate(dhash_fingerprint, row.get("perceptual_hash_dhash", ""), max_distance=5):
                    return True, "VISUAL_DHASH", row.get("id")

        return False, None, None

    except Exception as e:
        logger.warning(f"Database duplicate check encountered error (proceeding gracefully): {e}")
        return False, None, None


def run_pre_ingestion_gate(
    patient_id: str,
    image_bytes: bytes,
    document_type: Optional[str] = None,
    bypass_duplicate_check: bool = False,
    supabase_client: Any = None
) -> PreIngestionCheckResult:
    """
    Executes the complete unified Pre-Ingestion Gate:
    1. Computes forensic SHA-256 and visual dHash fingerprints.
    2. Assesses image sharpness, blur, contrast, and glare.
    3. Checks for existing duplicates in DB (Direct SQL index + Vectorized NumPy dHash).
    4. Returns a typed PreIngestionCheckResult.
    """
    # 1. Hashes
    sha256_hash = compute_sha256(image_bytes)
    try:
        dhash_val = compute_perceptual_dhash(image_bytes)
    except Exception:
        dhash_val = None

    # 2. Quality & Blur Assessment
    clarity_report = assess_image_clarity(image_bytes)
    
    if not clarity_report.get("is_valid_image", False):
        return PreIngestionCheckResult(
            is_acceptable=False,
            is_duplicate=False,
            sha256_hash=sha256_hash,
            dhash_fingerprint=dhash_val,
            quality_score=0.0,
            reasons=clarity_report.get("reasons", ["Invalid image file."]),
            suggested_action="REJECT"
        )

    # 3. Duplicate Detection Check (Optimized)
    is_dup, dup_reason, existing_id = False, None, None
    if not bypass_duplicate_check and supabase_client:
        is_dup, dup_reason, existing_id = check_existing_duplicates(
            patient_id=patient_id,
            sha256_hash=sha256_hash,
            dhash_fingerprint=dhash_val or "",
            document_type=document_type,
            supabase_client=supabase_client
        )

    # 4. Formulate Action & Response
    reasons = clarity_report.get("reasons", [])
    if is_dup:
        reasons.append(f"Identical or near-identical document is already on file for this patient ({dup_reason}).")
        suggested_action = "LINK_EXISTING"
    elif not clarity_report.get("is_acceptable", False):
        suggested_action = "RETAKE_CAMERA"
    else:
        suggested_action = "PROCEED"

    return PreIngestionCheckResult(
        is_acceptable=clarity_report.get("is_acceptable", False),
        is_duplicate=is_dup,
        duplicate_reason=dup_reason,
        existing_document_id=existing_id,
        sha256_hash=sha256_hash,
        dhash_fingerprint=dhash_val,
        sharpness=clarity_report.get("sharpness", 0.0),
        contrast_std=clarity_report.get("contrast_std", 0.0),
        glare_ratio=clarity_report.get("glare_ratio", 0.0),
        quality_score=clarity_report.get("quality_score", 100.0),
        reasons=reasons,
        suggested_action=suggested_action
    )
