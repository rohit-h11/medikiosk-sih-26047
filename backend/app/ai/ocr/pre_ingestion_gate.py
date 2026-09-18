"""
Pre-Ingestion Quality & Deduplication Gate for MediKiosk.
Performs sub-30ms CPU-based image validation before any database write or Vision LLM execution.
- Sharpness & Motion Blur Detection (Laplacian Variance)
- Contrast & Illumination Uniformity Check
- Glare / Reflection Analysis
- Cryptographic SHA-256 Deduplication (Exact Byte Match)
- Dual Perceptual Hashing (dHash + pHash) for Robust Visual Duplicate Detection
"""

import hashlib
import io
import logging
from typing import Tuple, Optional, Dict, Any, List, Union
import cv2
import numpy as np
from PIL import Image
import imagehash

from app.schemas.document import PreIngestionCheckResult

logger = logging.getLogger("medikiosk.ocr.gate")


def compute_sha256(file_bytes: bytes) -> str:
    """Calculates cryptographic SHA-256 checksum of raw image bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def _to_pil_grayscale(image_input: Union[bytes, Image.Image, np.ndarray]) -> Image.Image:
    """Converts bytes, NumPy ndarray, or PIL Image into a normalized PIL Grayscale Image."""
    if isinstance(image_input, bytes):
        return Image.open(io.BytesIO(image_input)).convert("L")
    elif isinstance(image_input, np.ndarray):
        if len(image_input.shape) == 3:
            gray_arr = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        else:
            gray_arr = image_input
        return Image.fromarray(gray_arr)
    else:
        return image_input.convert("L")


def compute_perceptual_dhash(image_input: Union[bytes, Image.Image, np.ndarray], hash_size: int = 8) -> str:
    """
    Computes a 64-bit Perceptual Difference Hash (dHash) using horizontal gradient comparison.
    Captures text layout, line boundaries, and structural alignment in < 1.5ms.
    """
    pil_img = _to_pil_grayscale(image_input)
    try:
        h = imagehash.dhash(pil_img, hash_size=hash_size)
        return str(h)
    except Exception as e:
        logger.warning(f"imagehash.dhash fallback: {e}")
        resized = pil_img.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixels = np.asarray(resized, dtype=np.int32)
        diff = pixels[:, 1:] > pixels[:, :-1]
        decimal_val = 0
        for bit in diff.flatten():
            decimal_val = (decimal_val << 1) | int(bit)
        return f"{decimal_val:016x}"


def compute_perceptual_phash(image_input: Union[bytes, Image.Image, np.ndarray], hash_size: int = 8) -> str:
    """
    Computes a 64-bit DCT-based Perceptual Hash (pHash).
    Invariant to lighting shifts, flash glare, shadows, and minor camera perspective tilts.
    """
    pil_img = _to_pil_grayscale(image_input)
    h = imagehash.phash(pil_img, hash_size=hash_size)
    return str(h)


def compute_dual_perceptual_hashes(image_input: Union[bytes, Image.Image, np.ndarray], hash_size: int = 8) -> Tuple[str, str]:
    """Computes both (dHash, pHash) fingerprints for composite two-factor visual verification."""
    pil_img = _to_pil_grayscale(image_input)
    dhash_val = str(imagehash.dhash(pil_img, hash_size=hash_size))
    phash_val = str(imagehash.phash(pil_img, hash_size=hash_size))
    return dhash_val, phash_val


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


def is_perceptual_duplicate(hash1: str, hash2: str, max_distance: int = 6) -> bool:
    """Returns True if two visual fingerprints are within the duplicate threshold."""
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
    dhash_fingerprint: Optional[str] = None,
    phash_fingerprint: Optional[str] = None,
    document_type: Optional[str] = None,
    supabase_client: Any = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    High-Performance Multi-Tier Duplicate Check:
    1. Direct $O(1)$ SQL Index Hit for exact SHA-256 matches.
    2. Document-Type Scoped query in PostgreSQL.
    3. C-Speed Vectorized NumPy Bitwise XOR for dHash (gradient) and pHash (DCT frequency) comparison.
    
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

        # ── OPTIMIZATION 2: DUAL PERCEPTUAL (dHash + pHash) LOOKUP ───────────────
        if not dhash_fingerprint and not phash_fingerprint:
            return False, None, None

        fields_to_select = "id, perceptual_hash_dhash"
        # We also select perceptual_hash_phash if available
        try:
            hash_query = supabase_client.table("patient_medical_documents") \
                .select("id, perceptual_hash_dhash, perceptual_hash_phash") \
                .eq("patient_id", patient_id)
            if document_type:
                hash_query = hash_query.eq("document_type", document_type)
            hash_rows = hash_query.execute().data or []
        except Exception:
            # Fallback if perceptual_hash_phash column is not yet migrated in DB schema
            hash_query = supabase_client.table("patient_medical_documents") \
                .select("id, perceptual_hash_dhash") \
                .eq("patient_id", patient_id)
            if document_type:
                hash_query = hash_query.eq("document_type", document_type)
            hash_rows = hash_query.execute().data or []

        if not hash_rows:
            return False, None, None

        # ── OPTIMIZATION 3: VECTORIZED NUMPY DUAL COMPARISON ─────────────────────
        # Check dHash (Threshold <= 5)
        if dhash_fingerprint:
            valid_dhash_rows = [r for r in hash_rows if r.get("perceptual_hash_dhash")]
            if valid_dhash_rows:
                try:
                    target_int = np.uint64(int(dhash_fingerprint, 16))
                    doc_ids = [r["id"] for r in valid_dhash_rows]
                    hashes_arr = np.array([int(r["perceptual_hash_dhash"], 16) for r in valid_dhash_rows], dtype=np.uint64)
                    
                    if hasattr(np, "bitwise_count"):
                        diffs = np.bitwise_count(hashes_arr ^ target_int)
                    else:
                        xor_arr = hashes_arr ^ target_int
                        diffs = np.array([bin(int(x)).count("1") for x in xor_arr], dtype=np.int32)
                    
                    match_indices = np.where(diffs <= 5)[0]
                    if len(match_indices) > 0:
                        best_idx = match_indices[np.argmin(diffs[match_indices])]
                        matched_doc_id = doc_ids[best_idx]
                        min_dist = int(diffs[best_idx])
                        logger.info(f"Vectorized dHash hit: Duplicate detected for patient {patient_id} (Doc ID: {matched_doc_id}, distance={min_dist})")
                        return True, "VISUAL_DHASH", matched_doc_id
                except Exception as e:
                    logger.warning(f"dHash vectorized check error: {e}")
                    for row in valid_dhash_rows:
                        if is_perceptual_duplicate(dhash_fingerprint, row.get("perceptual_hash_dhash", ""), max_distance=5):
                            return True, "VISUAL_DHASH", row.get("id")

        # Check pHash (Threshold <= 6)
        if phash_fingerprint:
            valid_phash_rows = [r for r in hash_rows if r.get("perceptual_hash_phash")]
            if valid_phash_rows:
                try:
                    target_int_p = np.uint64(int(phash_fingerprint, 16))
                    doc_ids_p = [r["id"] for r in valid_phash_rows]
                    hashes_arr_p = np.array([int(r["perceptual_hash_phash"], 16) for r in valid_phash_rows], dtype=np.uint64)
                    
                    if hasattr(np, "bitwise_count"):
                        diffs_p = np.bitwise_count(hashes_arr_p ^ target_int_p)
                    else:
                        xor_arr_p = hashes_arr_p ^ target_int_p
                        diffs_p = np.array([bin(int(x)).count("1") for x in xor_arr_p], dtype=np.int32)
                    
                    match_indices_p = np.where(diffs_p <= 6)[0]
                    if len(match_indices_p) > 0:
                        best_idx_p = match_indices_p[np.argmin(diffs_p[match_indices_p])]
                        matched_doc_id_p = doc_ids_p[best_idx_p]
                        min_dist_p = int(diffs_p[best_idx_p])
                        logger.info(f"Vectorized pHash hit: Duplicate detected for patient {patient_id} (Doc ID: {matched_doc_id_p}, distance={min_dist_p})")
                        return True, "VISUAL_PHASH", matched_doc_id_p
                except Exception as e:
                    logger.warning(f"pHash vectorized check error: {e}")
                    for row in valid_phash_rows:
                        if is_perceptual_duplicate(phash_fingerprint, row.get("perceptual_hash_phash", ""), max_distance=6):
                            return True, "VISUAL_PHASH", row.get("id")

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
    1. Computes forensic SHA-256, visual dHash (gradient), and pHash (DCT) fingerprints.
    2. Assesses image sharpness, blur, contrast, and glare.
    3. Checks for existing duplicates in DB (Direct SQL index + Vectorized Dual dHash/pHash).
    4. Returns a typed PreIngestionCheckResult.
    """
    # 1. Forensic & Perceptual Hashes
    sha256_hash = compute_sha256(image_bytes)
    try:
        dhash_val, phash_val = compute_dual_perceptual_hashes(image_bytes)
    except Exception:
        dhash_val, phash_val = None, None

    # 2. Quality & Blur Assessment
    clarity_report = assess_image_clarity(image_bytes)
    
    if not clarity_report.get("is_valid_image", False):
        return PreIngestionCheckResult(
            is_acceptable=False,
            is_duplicate=False,
            sha256_hash=sha256_hash,
            dhash_fingerprint=dhash_val,
            phash_fingerprint=phash_val,
            quality_score=0.0,
            reasons=clarity_report.get("reasons", ["Invalid image file."]),
            suggested_action="REJECT"
        )

    # 3. Duplicate Detection Check (Optimized Dual Check)
    is_dup, dup_reason, existing_id = False, None, None
    if not bypass_duplicate_check and supabase_client:
        is_dup, dup_reason, existing_id = check_existing_duplicates(
            patient_id=patient_id,
            sha256_hash=sha256_hash,
            dhash_fingerprint=dhash_val,
            phash_fingerprint=phash_val,
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
        phash_fingerprint=phash_val,
        sharpness=clarity_report.get("sharpness", 0.0),
        contrast_std=clarity_report.get("contrast_std", 0.0),
        glare_ratio=clarity_report.get("glare_ratio", 0.0),
        quality_score=clarity_report.get("quality_score", 100.0),
        reasons=reasons,
        suggested_action=suggested_action
    )
