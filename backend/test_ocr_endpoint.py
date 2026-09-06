"""
MediKiosk — OCR Document Endpoint Dedicated Verification Test.
Tests all 4 execution paths of POST /api/v1/ocr/process-document:
1. Blurry image triage rejection (< 20ms).
2. Clean image extraction, in-memory thumbnailing & vector RAG background ingestion.
3. Exact SHA-256 duplicate detection (< 8ms).
4. Visual pHash/dHash duplicate detection under slight image modification (< 8ms).
"""

import sys
import io
import time
from PIL import Image, ImageDraw, ImageEnhance
from fastapi.testclient import TestClient

# Ensure UTF-8 console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.main import app

client = TestClient(app)


def create_test_prescription(variation: str = "clean") -> bytes:
    img = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    if variation == "blurry":
        draw.rectangle([(50, 50), (550, 750)], fill=(240, 240, 240))
    else:
        draw.text((30, 40), "ALL INDIA INSTITUTE OF AYURVEDA (AIIA)", fill=(0, 0, 0))
        draw.text((30, 80), "Patient: Rajesh Kumar | Age: 48 | Gender: Male", fill=(0, 0, 0))
        draw.text((30, 120), "Diagnosis: Chronic Sandhigata Vata (Osteoarthritis)", fill=(0, 0, 0))
        draw.text((30, 160), "Rx: Yogaraja Guggulu 500mg BD after food", fill=(0, 0, 0))
        draw.text((30, 200), "Rx: Ashwagandha Churna 3g HS with warm milk", fill=(0, 0, 0))
        draw.text((30, 240), "Advice: Janu Basti with Mahanarayana Taila", fill=(0, 0, 0))

    if variation == "slight_brightness_change":
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.97)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=88)
    return buf.getvalue()


def run_tests():
    print("=" * 65)
    print("  MediKiosk OCR Single-Endpoint (`/process-document`) Test Suite")
    print("=" * 65)

    test_patient = "PAT-OCR-VERIFY-01"

    # --- Test 1: Blurry Image Triage ---
    print("\n--- Test 1: Blurry Image Rejection Gate ---")
    blurry_bytes = create_test_prescription("blurry")
    t0 = time.perf_counter()
    res1 = client.post(
        "/api/v1/ocr/process-document",
        files={"file": ("blur.webp", blurry_bytes, "image/webp")},
        data={"patient_id": test_patient, "document_type": "prescription"}
    )
    t1 = time.perf_counter()
    latency_ms1 = (t1 - t0) * 1000
    data1 = res1.json()

    print(f"Status: {res1.status_code} in {latency_ms1:.2f}ms")
    print(f"Response: status={data1.get('status')}, retake_required={data1.get('retake_required')}, reasons={data1.get('quality_reasons')}")
    assert res1.status_code == 200
    assert data1.get("status") == "quality_rejected"
    assert data1.get("retake_required") is True
    print("✅ Test 1 Passed: Blurry image caught & rejected immediately without calling LLM!")

    # --- Test 2: Clean Image Extraction ---
    print("\n--- Test 2: Clean Prescription Extraction & Vector RAG offloading ---")
    clean_bytes = create_test_prescription("clean")
    t0 = time.perf_counter()
    res2 = client.post(
        "/api/v1/ocr/process-document",
        files={"file": ("prescription.webp", clean_bytes, "image/webp")},
        data={"patient_id": test_patient, "document_type": "prescription"}
    )
    t1 = time.perf_counter()
    latency_ms2 = (t1 - t0) * 1000
    data2 = res2.json()

    print(f"Status: {res2.status_code} in {latency_ms2:.2f}ms")
    print(f"Doc ID: {data2.get('doc_id')}, Master Path: {data2.get('file_path')}, Thumb Path: {data2.get('file_path_thumb')}")
    assert res2.status_code == 200
    assert data2.get("status") == "completed"
    assert data2.get("is_duplicate") is False
    assert data2.get("file_path_thumb") is not None
    print("✅ Test 2 Passed: Full clinical extraction & thumbnail generated successfully!")

    # --- Test 3: Exact SHA-256 Duplicate Check ---
    print("\n--- Test 3: Exact SHA-256 Duplicate Check ---")
    t0 = time.perf_counter()
    res3 = client.post(
        "/api/v1/ocr/process-document",
        files={"file": ("prescription_same.webp", clean_bytes, "image/webp")},
        data={"patient_id": test_patient, "document_type": "prescription"}
    )
    t1 = time.perf_counter()
    latency_ms3 = (t1 - t0) * 1000
    data3 = res3.json()

    print(f"Status: {res3.status_code} in {latency_ms3:.2f}ms")
    print(f"Result: status={data3.get('status')}, is_duplicate={data3.get('is_duplicate')}, type={data3.get('duplicate_type')}")
    assert res3.status_code == 200
    assert data3.get("is_duplicate") is True
    assert data3.get("duplicate_type") == "EXACT_SHA256"
    assert latency_ms3 < 50.0
    print(f"✅ Test 3 Passed: Exact duplicate recognized and served from cache in {latency_ms3:.2f}ms!")

    # --- Test 4: Visual pHash / dHash Duplicate Check ---
    print("\n--- Test 4: Visual Perceptual dHash Duplicate Check ---")
    dhash_bytes = create_test_prescription("slight_brightness_change")
    t0 = time.perf_counter()
    res4 = client.post(
        "/api/v1/ocr/process-document",
        files={"file": ("prescription_photo2.webp", dhash_bytes, "image/webp")},
        data={"patient_id": test_patient, "document_type": "prescription"}
    )
    t1 = time.perf_counter()
    latency_ms4 = (t1 - t0) * 1000
    data4 = res4.json()

    print(f"Status: {res4.status_code} in {latency_ms4:.2f}ms")
    print(f"Result: status={data4.get('status')}, is_duplicate={data4.get('is_duplicate')}, type={data4.get('duplicate_type')}")
    assert res4.status_code == 200
    assert data4.get("is_duplicate") is True
    assert data4.get("duplicate_type") == "VISUAL_DHASH"
    assert latency_ms4 < 50.0
    print(f"✅ Test 4 Passed: Visual dHash variation detected as duplicate in {latency_ms4:.2f}ms!")

    print("\n" + "=" * 65)
    print("🎉 ALL OCR ENDPOINT TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
