"""
Unit tests for MediKiosk Pre-Ingestion Gate & Document Storage Pipeline.
Tests:
- SHA-256 cryptographic hashing & exact duplicate detection
- Perceptual dHash computation & visual duplicate detection (Hamming distance)
- Blur & sharpness evaluation (Laplacian variance)
- Specular glare detection
- Multi-variant WebP image generation & thumbnail scaling
- Master pipeline execution & metadata extraction
"""

import io
import pytest
import numpy as np
import cv2
from PIL import Image, ImageDraw

from app.schemas.document import DocumentType, OCRStatus, PreIngestionCheckResult, StoredDocumentResult
from app.ai.ocr.pre_ingestion_gate import (
    compute_sha256,
    compute_perceptual_dhash,
    compute_hamming_distance,
    is_perceptual_duplicate,
    assess_image_clarity,
    run_pre_ingestion_gate
)
from app.core.document_storage import (
    create_optimized_image_variants,
    ingest_patient_document_pipeline
)


def create_sample_prescription_image(blur: bool = False, glare: bool = False) -> bytes:
    """Helper to generate realistic synthetic test document images in memory."""
    # Natural slightly off-white paper background (RGB: 240, 238, 230)
    img = Image.new("RGB", (800, 1000), color=(240, 238, 230))
    draw = ImageDraw.Draw(img)

    # Draw dark clinical text lines and prescription table
    draw.rectangle([(40, 40), (760, 120)], fill=(225, 225, 215), outline=(100, 100, 100))
    draw.text((60, 55), "ALL INDIA INSTITUTE OF AYURVEDA (AIIA) - OPD", fill=(10, 10, 10))
    draw.text((60, 85), "Patient: Ramesh Kumar | Age: 52 | Date: 15/08/2026", fill=(30, 30, 30))
    
    draw.text((60, 140), "Chief Complaints: Sandhivata (Joint stiffness), Mandagni", fill=(10, 10, 10))
    draw.text((60, 175), "Rx (Prescribed Formulations):", fill=(10, 10, 10))
    
    for i in range(12):
        y = 210 + (i * 50)
        draw.text((70, y), f"{i+1}. Yograj Guggulu - 2 tabs BD with warm water (30 days)", fill=(20, 20, 20))
        draw.text((70, y + 22), f"   Dashmularishta - 20ml BD after meals with equal water", fill=(40, 40, 40))
        draw.line([(50, y + 45), (750, y + 45)], fill=(180, 180, 170), width=1)

    arr = np.array(img)

    if glare:
        # Add a huge over-exposed saturated flash hotspot covering > 20% of image
        cv2.circle(arr, (400, 500), 250, (255, 255, 255), -1)

    if blur:
        # Apply heavy Gaussian blur simulating camera shake
        arr = cv2.GaussianBlur(arr, (45, 45), 0)

    # Encode to JPEG bytes
    success, encoded = cv2.imencode(".jpg", cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return encoded.tobytes()


class TestPreIngestionGate:

    def test_sha256_exact_hash(self):
        img_bytes = create_sample_prescription_image()
        hash1 = compute_sha256(img_bytes)
        hash2 = compute_sha256(img_bytes)

        assert len(hash1) == 64
        assert hash1 == hash2

    def test_perceptual_dhash_and_hamming_distance(self):
        img_bytes = create_sample_prescription_image()
        dhash1 = compute_perceptual_dhash(img_bytes)

        assert len(dhash1) == 16  # 64-bit hex is 16 chars

        # Test identical image has 0 distance
        assert compute_hamming_distance(dhash1, dhash1) == 0
        assert is_perceptual_duplicate(dhash1, dhash1, max_distance=5) is True

        # Test slightly altered image (e.g. slight brightness shift) remains a perceptual duplicate
        arr = np.frombuffer(img_bytes, np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        brightened = cv2.convertScaleAbs(decoded, alpha=1.05, beta=5)
        _, altered_bytes = cv2.imencode(".jpg", brightened)
        
        dhash2 = compute_perceptual_dhash(altered_bytes.tobytes())
        dist = compute_hamming_distance(dhash1, dhash2)
        assert dist <= 5
        assert is_perceptual_duplicate(dhash1, dhash2, max_distance=5) is True

    def test_sharp_image_passes_clarity_check(self):
        sharp_bytes = create_sample_prescription_image(blur=False)
        report = assess_image_clarity(sharp_bytes, min_sharpness=35.0)

        assert report["is_valid_image"] is True
        assert report["is_acceptable"] is True
        assert report["sharpness"] > 35.0
        assert len(report["reasons"]) == 0
        assert report["quality_score"] > 60.0

    def test_blurry_image_fails_clarity_check(self):
        blurry_bytes = create_sample_prescription_image(blur=True)
        report = assess_image_clarity(blurry_bytes, min_sharpness=35.0)

        assert report["is_valid_image"] is True
        assert report["is_acceptable"] is False
        assert report["sharpness"] < 35.0
        assert any("blurry" in r.lower() for r in report["reasons"])

    def test_glare_image_detection(self):
        glare_bytes = create_sample_prescription_image(glare=True)
        report = assess_image_clarity(glare_bytes, max_glare_ratio=0.08)

        assert report["glare_ratio"] > 0.08
        assert any("glare" in r.lower() for r in report["reasons"])

    def test_run_pre_ingestion_gate_orchestration(self):
        sharp_bytes = create_sample_prescription_image()
        result: PreIngestionCheckResult = run_pre_ingestion_gate(
            patient_id="PAT-TEST-01",
            image_bytes=sharp_bytes
        )

        assert result.is_acceptable is True
        assert result.is_duplicate is False
        assert result.suggested_action == "PROCEED"
        assert len(result.sha256_hash) == 64
        assert result.dhash_fingerprint is not None


class TestDocumentStorageService:

    def test_create_optimized_image_variants(self):
        raw_bytes = create_sample_prescription_image()
        proc_bytes, thumb_bytes = create_optimized_image_variants(raw_bytes)

        # Verify processed WebP
        proc_img = Image.open(io.BytesIO(proc_bytes))
        assert proc_img.format == "WEBP"
        assert max(proc_img.size) <= 2048

        # Verify UI Thumbnail WebP
        thumb_img = Image.open(io.BytesIO(thumb_bytes))
        assert thumb_img.format == "WEBP"
        assert max(thumb_img.size) <= 300
        # Thumbnail should be lightweight (< 50KB)
        assert len(thumb_bytes) < 50 * 1024

    @pytest.mark.asyncio
    async def test_ingest_patient_document_pipeline_success(self):
        raw_bytes = create_sample_prescription_image()
        
        # Run pipeline in offline/standalone mode (no live Supabase client required for unit test)
        result: StoredDocumentResult = await ingest_patient_document_pipeline(
            patient_id="PAT-TEST-100",
            raw_file_bytes=raw_bytes,
            filename="my_prescription.jpg",
            document_type=DocumentType.PRESCRIPTION,
            session_id="sess_demo_123"
        )

        assert result.id is not None
        assert result.patient_id == "PAT-TEST-100"
        assert result.session_id == "sess_demo_123"
        assert result.document_type == DocumentType.PRESCRIPTION
        assert "_processed.webp" in result.file_path_processed
        assert "_thumb.webp" in result.file_path_thumbnail
        assert result.ocr_status == OCRStatus.PENDING
        assert result.is_duplicate_linked is False
        assert result.quality_score > 0

    @pytest.mark.asyncio
    async def test_ingest_patient_document_pipeline_rejects_blurry(self):
        blurry_bytes = create_sample_prescription_image(blur=True)

        with pytest.raises(ValueError, match="Document rejected at Pre-Ingestion Gate"):
            await ingest_patient_document_pipeline(
                patient_id="PAT-TEST-100",
                raw_file_bytes=blurry_bytes,
                filename="blurry_photo.jpg"
            )
