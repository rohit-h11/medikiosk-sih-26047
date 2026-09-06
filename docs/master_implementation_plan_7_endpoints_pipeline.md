# Master Technical Implementation Plan: 5-Endpoint Pipeline
**MediKiosk AI Clinical Intake, Dual-RAG Dialogue, & Automated Doctor EHR Summary**

> **Document Version:** 4.2 (Production RAG & Async PyTorch Offloading)  
> **Target Audience:** Autonomous Coding Agents & Senior Backend Engineers  
> **Problem Statement:** SIH 26047 — Ministry of Ayush / All India Institute of Ayurveda (AIIA)  
> **Instruction for Implementation:** Read this document and execute the implementation steps in sequential order (Steps 1 through 5).

---

## 1. Executive Summary & Architectural Invariants

This document contains the complete, production-ready implementation plan for the **Unified 5-Endpoint MediKiosk Backend Architecture**. All document scanning, deduplication, thumbnailing, OCR extraction, and **asynchronous pgvector RAG embedding** are consolidated into **exactly one endpoint**.

```
+===================================================================================================+
|                               MEDIKIOSK FINALIZED 5-ENDPOINT SUITE                                |
+===================================================================================================+
| 📂 DOCUMENT & VISION OCR (Only 1 Single Endpoint for all Document Operations)                     |
+------------------------------------+--------+-----------------------------------------------------+
| 1. /api/v1/ocr/process-document    | POST   | Direct WebP Upload -> Deduplication -> Gemini OCR   |
|                                    |        | -> Auto-Thumbnail -> Async pgvector RAG Ingestion   |
+------------------------------------+--------+-----------------------------------------------------+
| 🗣️ DUAL-RAG DIALOGUE & STREAMING TRIAGE (Screen 2: Voice & Touch Dialogue)                         |
+------------------------------------+--------+-----------------------------------------------------+
| 2. /api/v1/dialogue/stream-turn    | POST   | Real-time SSE Token Stream -> Voice TTS (Primary)   |
| 3. /api/v1/dialogue/turn           | POST   | Discrete REST turn handler for touchscreen taps     |
| 4. /api/v1/dialogue/session/{id}   | GET    | Session status, SOCRATES slot state & telemetry     |
+------------------------------------+--------+-----------------------------------------------------+
| 👨‍⚕️ DOCTOR OPD STATION & CONSULTATION PASS (Doctor Dashboard & Thermal QR)                          |
+------------------------------------+--------+-----------------------------------------------------+
| 5. /api/v1/doctor/ticket/{id}      | GET    | Doctor OPD pre-populated EHR ticket & QR pass       |
+===================================================================================================+
```

### 🏛️ Core Architectural Invariants:
1. **Direct In-Memory OCR & Auto-RAG Ingestion:** `POST /api/v1/ocr/process-document` runs Gemini 3.6 Flash Vision directly on in-memory WebP bytes ($0$ Supabase downloads). Extracted clinical findings are asynchronously ingested via `ingest_ocr_payload_async` into **`patient_structured_vectors` in Supabase `pgvector`** with normalized dates and contextual headers.
2. **Asynchronous Batch Vector Inference:** PyTorch MiniLM embedding generation is offloaded to background threads via `generate_embeddings_batch_async` using `asyncio.to_thread`, keeping the FastAPI event loop $100\%$ non-blocking.
3. **Client-Side WebP Compression (Zero Backend Memory Bloat):** Kiosk camera photos are compressed to lightweight $2048\text{px}$ WebP (Q=88, $\sim 250\text{ KB}$) on HTML5 Canvas in $< 15\text{ms}$. Heavy $5\text{ MB}$ raw files never touch backend memory or network.
4. **Sub-15ms Pre-Ingestion Deduplication Gate:** The backend computes the SHA-256 hash in $< 1\text{ms}$ and queries PostgreSQL. If duplicate $\rightarrow$ skips all storage uploads, RAG embeddings, and LLM calls, returning cached clinical JSON in $< 20\text{ms}$.
5. **Dual-Variant Storage (Master WebP + 30KB Thumbnail):** New documents generate a 300px thumbnail in $2\text{ms}$ (Pillow). Both the master WebP ($250\text{ KB}$ for OCR and full-screen doctor zoom) and thumbnail ($30\text{ KB}$ for fast doctor timeline feeds) are archived to Supabase Storage in the background.
6. **Vector-Driven Red Flags (No Regex):** Patient utterances are embedded via `MiniLM-L6-v2` and matched against **ICMR Emergency STWs** in Supabase `pgvector` in **$< 10\text{ms}$**. If similarity exceeds `0.82`, an immediate emergency triage pass is issued.
7. **Parallel Dual-Vector RAG:** Dialogue turns execute `asyncio.gather()` to fetch (A) Static National Clinical Guidelines (NAMASTE / ICMR) and (B) Patient-Specific OCR Medical History from `patient_structured_vectors` simultaneously (with automatic chronological SQL fallback).
8. **Sub-250ms Streaming Voice Dialogue (Phase 1):** Real-time conversational turns are streamed token-by-token via **Server-Sent Events (SSE)** using **Groq Qwen-27B** on LPUs directly to the Kiosk TTS buffer.
9. **Automatic Doctor EHR Summary (Phase 2):** When `should_stop == True` on the final dialogue turn, **Google Gemini 3.6 Flash** automatically synthesizes all dialogue turns, OCR meds, vitals, and RAG guidelines into a strictly validated `ClinicalSummaryTicket` Pydantic payload in $\sim 1.2\text{s}$ and saves it to PostgreSQL `clinical_summary_tickets`.

---

## 2. Complete File Modification & Creation Manifest

```
backend/
├── app/
│   ├── ai/
│   │   ├── dialogue/
│   │   │   ├── models.py               [MODIFY] Add ClinicalSummaryTicket & update DialogueTurnResult
│   │   │   ├── prompts.py              [MODIFY] Inject Dual-RAG context & strict summary prompts
│   │   │   ├── llm_client.py           [MODIFY] Add Groq SSE streaming & Gemini Flash summary generator
│   │   │   ├── dialogue_manager.py     [MODIFY] Add parallel RAG, vector red flags, & auto-summary
│   │   │   └── db_logger.py            [VERIFIED] Async DB logger for dialogue turns and sessions
│   │   ├── ocr/
│   │   │   ├── image_utils.py          [NEW]    Generate 30KB WebP thumbnails in-memory (Pillow)
│   │   │   └── vision_llm.py           [MODIFY] Gemini 3.6 Flash structured clinical JSON extraction
│   │   └── rag/
│   │       ├── inserter.py             [VERIFIED] Ingests in-memory OCR JSON to pgvector (ingest_ocr_payload_async)
│   │       ├── retriever.py            [VERIFIED] Batch async embeddings & patient RAG with chronological SQL fallback
│   │       ├── utils.py                [VERIFIED] Clinical date normalization (normalize_clinical_date)
│   │       └── validator.py            [VERIFIED] Strong Pydantic v2 schemas (OCRPayload, ExtractedData, RAGChunk)
│   └── api/
│       └── v1/
│           ├── api.py                  [MODIFY] Register ocr, dialogue, and doctor routers
│           └── endpoints/
│               ├── ocr.py              [MODIFY] Endpoint 1: Direct WebP upload, deduplication, OCR, RAG ingestion & storage
│               ├── dialogue.py         [MODIFY] Endpoints 2, 3, 4: SSE stream-turn, REST turn, & session telemetry
│               └── doctor.py           [NEW]    Endpoint 5: Doctor OPD consultation ticket
docs/
└── master_implementation_plan_7_endpoints_pipeline.md  [MODIFY] Updated to 5-Endpoint Architecture with auto-RAG
```

---

## 3. Database Schema & Storage Setup

Ensure the following tables and buckets are configured in Supabase:

### A. Storage Bucket:
* **Bucket Name:** `patient-medical-records` (Private Bucket, RLS enabled).
* **Directory Structure:** `{patient_id}/{document_type}/{doc_uuid}.webp` and `{doc_uuid}_thumb.webp`

### B. PostgreSQL DDL:
```sql
-- 1. Document Registry Table
CREATE TABLE IF NOT EXISTS patient_medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    session_id TEXT,
    document_type TEXT NOT NULL DEFAULT 'prescription', -- 'prescription' | 'lab_report' | 'ayurvedic_record'
    storage_bucket TEXT NOT NULL DEFAULT 'patient-medical-records',
    file_path TEXT NOT NULL,                            -- Master 2048px WebP (~250 KB)
    file_path_thumb TEXT,                               -- UI Thumbnail 300px WebP (~30 KB)
    mime_type TEXT NOT NULL DEFAULT 'image/webp',
    file_size_bytes BIGINT DEFAULT 0,
    file_hash_sha256 TEXT NOT NULL,                     -- Cryptographic deduplication & Section 63 BSA compliance
    ocr_status TEXT NOT NULL DEFAULT 'completed',       -- 'pending' | 'completed' | 'failed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. OCR Extracted Clinical Data Table
CREATE TABLE IF NOT EXISTS document_ocr_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES patient_medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL,
    structured_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Patient Structured Vector Store (pgvector for cross-visit RAG)
CREATE TABLE IF NOT EXISTS patient_structured_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    document_id TEXT,
    category TEXT,                                      -- 'medications', 'diagnoses', 'lab_findings', 'clinical_summary'
    content TEXT NOT NULL,                              -- Markdown chunk with contextual header
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    encounter_date DATE,
    embedding VECTOR(384) NOT NULL,                     -- all-MiniLM-L6-v2 384 dimensions
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Clinical Summary Tickets Table (For Doctor OPD Desk)
CREATE TABLE IF NOT EXISTS clinical_summary_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id TEXT UNIQUE NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    patient_id TEXT NOT NULL,
    triage_urgency TEXT NOT NULL DEFAULT 'ROUTINE_GREEN', -- 'ROUTINE_GREEN' | 'PRIORITY_YELLOW' | 'EMERGENCY_RED'
    ticket_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance & Deduplication Indexes
CREATE INDEX IF NOT EXISTS idx_med_docs_patient ON patient_medical_documents (patient_id);
CREATE INDEX IF NOT EXISTS idx_med_docs_hash ON patient_medical_documents (file_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_ocr_extract_patient ON document_ocr_extractions (patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_vectors_patient ON patient_structured_vectors (patient_id);
CREATE INDEX IF NOT EXISTS idx_summary_tickets_session ON clinical_summary_tickets (session_id);
```

---

## 4. Subsystem 1: Document Ingestion, Vision OCR & RAG Ingestion

### 🔄 The Exact 6-Step Ingestion, OCR & Vector RAG Pipeline:

```
1. KIOSK FRONTEND (Captures Prescription)
   └── Sends single HTTP POST (Multipart: file + patient_id) to FastAPI backend.

2. PRE-INGESTION GATE (< 15 ms on CPU)
   ├── A. Compute Cryptographic SHA-256 Hash of incoming image bytes (0.8 ms).
   ├── B. Fast SQL Query:
   │      `SELECT * FROM patient_medical_documents WHERE file_hash_sha256 = :hash AND patient_id = :patient_id`
   │
   └── 🚨 IF DUPLICATE FOUND:
          ├── Skip Supabase Storage upload (saves bandwidth & cost).
          ├── Skip Gemini Vision LLM call (saves API tokens).
          └── ✅ RETURN IMMEDIATELY: Fetch and return existing cached JSON (< 20 ms)!

3. IN-MEMORY MULTI-VARIANT GENERATION (10 ms with Python Pillow)
   ├── Master WebP (`processed.webp`): Max 2048px width, Q=88 (~250 KB) -> For OCR & Doctor Zoom.
   └── Thumbnail WebP (`thumb.webp`): Max 300px width, Q=75 (~30 KB) -> For Doctor Timeline Gallery.

4. MULTIMODAL VISION OCR EXTRACTION (~1.2 s)
   └── Backend passes the in-memory Master WebP bytes directly to Gemini 3.6 Flash Vision (NO Supabase download!).
       └── Returns structured medical JSON:
           • Doctor Name, Clinic, & Consultation Date
           • Diagnoses (Allopathic & Ayurvedic/NAMASTE terms)
           • Active Medications (Name, Dosage, Frequency, Duration)
           • Abnormal Lab Values & Flagged Allergies

5. PERSISTENCE, STORAGE & ASYNC RAG INGESTION (Concurrent / Non-Blocking)
   ├── A. Supabase Storage: Uploads 2 files to private bucket `patient-medical-records`:
   │      • `{patient_id}/prescriptions/{doc_id}.webp`
   │      • `{patient_id}/prescriptions/{doc_id}_thumb.webp`
   │
   ├── B. PostgreSQL Metadata: Inserts row into `patient_medical_documents`.
   │
   ├── C. PostgreSQL Clinical JSON: Inserts into `document_ocr_extractions`.
   │
   └── D. Ingest via `ingest_ocr_payload_async`: Normalizes date, creates contextual headers,
          batch-embeds (MiniLM 384-dim on background thread), and inserts into `patient_structured_vectors`.

6. RESPONSE SENT TO KIOSK (< 1.4 s Total)
   └── Returns clean JSON to Kiosk UI to display the digitized medicines and diagnoses on screen.
```

---

### File: `backend/app/ai/ocr/image_utils.py` [NEW]
```python
import io
from PIL import Image

def generate_thumbnail_webp(image_bytes: bytes, max_dim: int = 300, quality: int = 75) -> bytes:
    """
    Generates an ultra-lightweight WebP thumbnail (max 300px, ~30 KB) in < 3ms on CPU.
    Used for instant loading in Doctor Dashboard patient timeline grids.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality)
        return buf.getvalue()
```

---

### File: `backend/app/api/v1/endpoints/ocr.py` [MODIFY]
* **Endpoint 1: `POST /api/v1/ocr/process-document`**

```python
import hashlib
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from app.config import get_supabase_client
from app.ai.ocr.vision_llm import extract_clinical_data_from_image
from app.ai.ocr.image_utils import generate_thumbnail_webp
from app.ai.rag.inserter import ingest_ocr_payload_async

logger = logging.getLogger("medikiosk.api.ocr")
router = APIRouter(prefix="/ocr", tags=["Document Ingestion & Vision OCR"])

class ProcessDocResponse(BaseModel):
    status: str
    doc_id: str
    patient_id: str
    file_path: str
    file_path_thumb: Optional[str] = None
    is_duplicate: bool = False
    extracted_data: Dict[str, Any]

@router.post("/process-document", response_model=ProcessDocResponse, status_code=status.HTTP_200_OK)
async def process_document_ocr(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="2048px WebP compressed prescription image (~250 KB)"),
    patient_id: str = Form(..., description="Patient ID or ABHA ID"),
    document_type: str = Form("prescription", description="'prescription' | 'lab_report' | 'ayurvedic_record'"),
    session_id: Optional[str] = Form(None, description="Optional active dialogue session ID")
):
    """
    The Single Unified Document Ingestion & Vision OCR Endpoint:
    1. Receives 250KB WebP image from Kiosk frontend.
    2. Computes SHA-256 hash (<1ms) and checks PostgreSQL for duplicates.
       - IF duplicate: Skips storage & Gemini OCR, returning cached clinical JSON in <20ms!
    3. IF new document:
       - Generates 30KB thumbnail in-memory (2ms).
       - Passes in-memory bytes directly to Gemini 3.6 Flash Vision OCR (~1.2s). (Zero Supabase downloads!)
       - Persists structured JSON & metadata to PostgreSQL.
       - Asynchronously ingests findings into `patient_structured_vectors` via RAG pipeline.
       - Asynchronously uploads Master WebP + Thumbnail to Supabase Storage in the background.
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty image payload received.")

        # 1. SHA-256 Cryptographic Hash Check
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        supabase = get_supabase_client()

        existing_doc = supabase.table("patient_medical_documents") \
            .select("id, file_path, file_path_thumb") \
            .eq("patient_id", patient_id) \
            .eq("file_hash_sha256", file_hash) \
            .execute()

        if existing_doc.data and len(existing_doc.data) > 0:
            doc_id = existing_doc.data[0]["id"]
            logger.info(f"Duplicate document detected for patient {patient_id} (doc_id: {doc_id}). Returning cached JSON.")
            existing_extraction = supabase.table("document_ocr_extractions") \
                .select("structured_data") \
                .eq("document_id", doc_id) \
                .execute()
            
            cached_json = existing_extraction.data[0]["structured_data"] if existing_extraction.data else {}
            return ProcessDocResponse(
                status="completed",
                doc_id=doc_id,
                patient_id=patient_id,
                file_path=existing_doc.data[0]["file_path"],
                file_path_thumb=existing_doc.data[0].get("file_path_thumb"),
                is_duplicate=True,
                extracted_data=cached_json
            )

        # 2. In-Memory Thumbnail Generation (300px WebP, ~30KB)
        thumb_bytes = generate_thumbnail_webp(file_bytes)

        # 3. Vision LLM Clinical Extraction (Gemini 3.6 Flash - in-memory bytes, ZERO download)
        extracted_json = await extract_clinical_data_from_image(file_bytes)

        # 4. Storage Path Hierarchy
        doc_id = str(uuid.uuid4())
        master_path = f"{patient_id}/{document_type}/{doc_id}.webp"
        thumb_path = f"{patient_id}/{document_type}/{doc_id}_thumb.webp"

        # 5. Insert Database Records
        supabase.table("patient_medical_documents").insert({
            "id": doc_id,
            "patient_id": patient_id,
            "session_id": session_id,
            "document_type": document_type,
            "storage_bucket": "patient-medical-records",
            "file_path": master_path,
            "file_path_thumb": thumb_path,
            "mime_type": "image/webp",
            "file_size_bytes": len(file_bytes),
            "file_hash_sha256": file_hash,
            "ocr_status": "completed"
        }).execute()

        supabase.table("document_ocr_extractions").insert({
            "document_id": doc_id,
            "patient_id": patient_id,
            "structured_data": extracted_json
        }).execute()

        # 6. Background Tasks: Storage Upload & Vector RAG Ingestion
        async def background_pipeline():
            try:
                # A. Upload files to Supabase Storage
                storage = supabase.storage.from_("patient-medical-records")
                storage.upload(master_path, file_bytes, {"content-type": "image/webp"})
                storage.upload(thumb_path, thumb_bytes, {"content-type": "image/webp"})
            except Exception as upload_err:
                logger.error(f"Background storage upload error for {doc_id}: {upload_err}")

            try:
                # B. Ingest into patient_structured_vectors via RAG pipeline
                await ingest_ocr_payload_async(
                    payload=extracted_json,
                    patient_id_override=patient_id,
                    document_id=doc_id
                )
            except Exception as rag_err:
                logger.error(f"Background RAG ingestion error for {doc_id}: {rag_err}")

        background_tasks.add_task(background_pipeline)

        return ProcessDocResponse(
            status="completed",
            doc_id=doc_id,
            patient_id=patient_id,
            file_path=master_path,
            file_path_thumb=thumb_path,
            is_duplicate=False,
            extracted_data=extracted_json
        )

    except Exception as e:
        logger.error(f"OCR Processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR Extraction failed: {str(e)}")
```

---

## 5. Subsystem 2: Dual-RAG Dialogue, Streaming, & Auto-Summary

### File: `backend/app/ai/dialogue/models.py` [MODIFY]
Add the comprehensive `ClinicalSummaryTicket` Pydantic model:

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AyurvedicAssessment(BaseModel):
    primary_morbidity: str = Field(..., description="Disease name in Ayurveda")
    namaste_code: str = Field(..., description="Official National Morbidity Code (e.g. 'AAD-2')")
    dosha_imbalance: str = Field(..., description="e.g. 'Vata-Pitta Pradhana'")
    srotas_involved: List[str] = Field(default_factory=list, description="e.g. ['Asthivaha', 'Majjavaha']")
    agni_status: Optional[str] = Field(None, description="e.g. 'Vishamagni' | 'Mandagni'")
    ccras_prakriti_tendency: Optional[str] = Field(None, description="e.g. 'Vata-Pitta'")
    chikitsa_principles: List[str] = Field(default_factory=list)

class AllopathicDifferential(BaseModel):
    primary_icd10: str = Field(..., description="ICD-10 Code & Condition name (e.g. 'M17.0 Osteoarthritis')")
    secondary_differentials: List[str] = Field(default_factory=list)
    urgency_level: str = Field(..., description="e.g. 'Routine OPD' | 'Priority OPD within 2h'")

class DrugHerbSafetyScreening(BaseModel):
    current_allopathy_ocr: List[str] = Field(default_factory=list)
    contraindications_and_warnings: List[str] = Field(default_factory=list)

class DietaryPathyaApathya(BaseModel):
    pathya_recommended: List[str] = Field(default_factory=list)
    apathya_restricted: List[str] = Field(default_factory=list)

class ClinicalSummaryTicket(BaseModel):
    ticket_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    timestamp: str
    triage_urgency: str = Field(..., description="'ROUTINE_GREEN' | 'PRIORITY_YELLOW' | 'EMERGENCY_RED'")
    emergency_red_flags: List[str] = Field(default_factory=list)
    vitals_summary: Dict[str, Any] = Field(default_factory=dict)
    chief_complaint: str
    socrates_hpi_narrative: str
    ayurvedic_assessment: AyurvedicAssessment
    allopathic_differential: AllopathicDifferential
    drug_herb_safety_screening: DrugHerbSafetyScreening
    dietary_guidelines_pathya_apathya: DietaryPathyaApathya
    suggested_investigations_for_physician: List[str] = Field(default_factory=list)
    doctor_consultation_notes: str

class DialogueTurnResult(BaseModel):
    should_stop: bool
    next_question: Optional[str] = None
    touch_options: List[TouchOption] = Field(default_factory=list)
    socrates_state: SocratesState = Field(default_factory=SocratesState)
    covered_slots: List[str] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    clinical_summary_ticket: Optional[ClinicalSummaryTicket] = None
    closing_message: Optional[str] = None
    red_flag_alert: Optional[RedFlagAlert] = None
    reasoning: Optional[str] = None
```

---

### File: `backend/app/ai/dialogue/llm_client.py` [MODIFY]
Implement (1) Groq SSE token streaming and (2) Gemini 3.6 Flash structured clinical summary generator:

```python
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional
import httpx
from google import genai
from google.genai import types
from app.ai.dialogue.models import ClinicalSummaryTicket, PatientContext

logger = logging.getLogger("medikiosk.dialogue.llm")

async def stream_groq_dialogue_tokens(
    system_prompt: str, 
    user_prompt: str
) -> AsyncGenerator[str, None]:
    """
    Streams conversational inquiry tokens from Groq (Qwen-27B) via HTTP SSE (< 250ms TTFT).
    """
    api_key = get_groq_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 512
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream("POST", "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass

async def generate_gemini_clinical_summary(
    patient_context: PatientContext,
    conversation_history: list,
    retrieved_guidelines: list
) -> ClinicalSummaryTicket:
    """
    Uses Gemini 3.6 Flash with strict Pydantic Structured Output to synthesize 
    the full 5-layer Doctor EHR Summary Ticket upon dialogue completion.
    """
    gemini_key = get_gemini_api_key()
    client = genai.Client(api_key=gemini_key)
    
    prompt = f"""Synthesize this clinical encounter into a standardized Doctor Consultation Ticket:
    
    [PATIENT CONTEXT & OCR RECORDS]:
    {patient_context.model_dump_json()}
    
    [CONVERSATION HISTORY]:
    {json.dumps(conversation_history, indent=2)}
    
    [RETRIEVED NATIONAL GUIDELINES (NAMASTE / ICMR / WHO)]:
    {json.dumps(retrieved_guidelines, indent=2)}
    """
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClinicalSummaryTicket,
            temperature=0.1
        )
    )
    
    return ClinicalSummaryTicket.model_validate_json(response.text)
```

---

### File: `backend/app/ai/dialogue/dialogue_manager.py` [MODIFY]
Integrate parallel dual-vector retrieval, vector-driven red flags, and auto-summary generation:

```python
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.ai.dialogue.models import PatientContext, DialogueTurnResult, SocratesState, TouchOption
from app.ai.dialogue.llm_client import call_groq_llm, generate_gemini_clinical_summary
from app.ai.rag.retriever import retrieve_patient_history_async, retrieve_clinical_guidelines_async
from app.config import get_supabase_client

async def get_next_dialogue_turn(
    patient_context: PatientContext,
    conversation_history: list,
    max_turns: int = 8,
    current_socrates_state: Optional[SocratesState] = None
) -> DialogueTurnResult:
    """
    Main dialogue manager: Evaluates vector red flags, executes parallel dual-RAG,
    updates SOCRATES slot state, and automatically synthesizes Doctor Summary Ticket on completion.
    """
    latest_utterance = conversation_history[-1]["content"] if conversation_history else patient_context.chief_complaint or ""
    patient_id = patient_context.patient_id or "PAT-DEMO"
    
    # Parallel Dual-Vector Search (A: National Guidelines, B: Patient OCR Past History)
    guidelines_task = retrieve_clinical_guidelines_async(latest_utterance, top_k=4)
    patient_rag_task = retrieve_patient_history_async(patient_id=patient_id, query_text=latest_utterance, top_k=3)
    
    guidelines, patient_history_rag = await asyncio.gather(guidelines_task, patient_rag_task)
    
    # 1. Vector-Driven Emergency Red-Flag Interceptor
    emergency_matches = [
        g for g in guidelines 
        if g.get("domain") in ["ICMR_STW_EMERGENCY", "WHO_PANCHAKARMA_CONTRAINDICATION"] and g.get("similarity", 0) > 0.82
    ]
    if emergency_matches:
        top_emergency = emergency_matches[0]
        ticket = await generate_gemini_clinical_summary(patient_context, conversation_history, [top_emergency])
        ticket.triage_urgency = "EMERGENCY_RED"
        ticket.emergency_red_flags.append(top_emergency.get("title", "Acute Emergency"))
        return DialogueTurnResult(
            should_stop=True,
            closing_message="A critical medical symptom has been detected. Please proceed directly to Emergency / Casualty.",
            clinical_summary_ticket=ticket,
            reasoning="Emergency threshold matched in ICMR STW vector knowledge base."
        )

    # 2. Regular SOCRATES Dialogue Turn with Groq Qwen-27B (Dual-RAG context injected)
    combined_context = guidelines + patient_history_rag
    llm_output = await call_groq_llm(patient_context, conversation_history, combined_context)
    
    should_stop = llm_output.get("should_stop", False) or len(conversation_history) >= (max_turns * 2)
    
    summary_ticket = None
    if should_stop:
        summary_ticket = await generate_gemini_clinical_summary(patient_context, conversation_history, combined_context)
        
        # Auto-persist ticket in PostgreSQL clinical_summary_tickets table
        try:
            supabase = get_supabase_client()
            supabase.table("clinical_summary_tickets").insert({
                "ticket_id": summary_ticket.ticket_id,
                "session_id": patient_context.session_id or "ses_active",
                "patient_id": patient_context.patient_id or "UNKNOWN",
                "triage_urgency": summary_ticket.triage_urgency,
                "ticket_data": summary_ticket.model_dump()
            }).execute()
        except Exception as persist_err:
            logger.error(f"Failed to persist clinical ticket to DB: {persist_err}")
        
    return DialogueTurnResult(
        should_stop=should_stop,
        next_question=llm_output.get("next_question") if not should_stop else None,
        touch_options=[TouchOption(**opt) for opt in llm_output.get("touch_options", [])] if not should_stop else [],
        socrates_state=SocratesState(**llm_output.get("socrates_state", {})),
        clinical_summary_ticket=summary_ticket,
        closing_message=llm_output.get("closing_message") or "Thank you. Your consultation ticket is ready."
    )
```

---

## 6. Subsystem 3: Doctor OPD Station & Consultation Pass

### File: `backend/app/api/v1/endpoints/doctor.py` [NEW]
* **Endpoint 5: `GET /api/v1/doctor/ticket/{session_id}`**

```python
from fastapi import APIRouter, HTTPException
from app.config import get_supabase_client

router = APIRouter(prefix="/doctor", tags=["Doctor OPD Station & EMR Queue"])

@router.get("/ticket/{session_id}")
async def get_doctor_consultation_ticket(session_id: str):
    """
    Fetches the pre-populated clinical summary ticket and document preview signed URLs
    for the examining physician's OPD dashboard.
    """
    supabase = get_supabase_client()
    res = supabase.table("clinical_summary_tickets").select("*").eq("session_id", session_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Clinical consultation ticket not found for this session.")
    
    ticket = res.data[0]
    patient_id = ticket.get("patient_id")
    
    # Attach 15-minute secure signed URLs for patient documents
    if patient_id:
        docs_res = supabase.table("patient_medical_documents").select("*").eq("patient_id", patient_id).execute()
        document_previews = []
        for d in docs_res.data or []:
            master_path = d.get("file_path")
            thumb_path = d.get("file_path_thumb")
            signed_url = ""
            signed_url_thumb = ""
            if master_path:
                url_res = supabase.storage.from_("patient-medical-records").create_signed_url(master_path, 900)
                signed_url = url_res.get("signedUrl") or url_res.get("signedURL", "")
            if thumb_path:
                thumb_res = supabase.storage.from_("patient-medical-records").create_signed_url(thumb_path, 900)
                signed_url_thumb = thumb_res.get("signedUrl") or thumb_res.get("signedURL", "")
            document_previews.append({
                "id": d["id"],
                "document_type": d["document_type"],
                "signed_url": signed_url,
                "signed_url_thumb": signed_url_thumb or signed_url,
                "created_at": d.get("created_at")
            })
        ticket["document_previews"] = document_previews

    return ticket
```

---

## 7. Main API Router Registration

### File: `backend/app/api/v1/api.py` [MODIFY]
```python
from fastapi import APIRouter
from app.api.v1.endpoints.ocr import router as ocr_router
from app.api.v1.endpoints.dialogue import router as dialogue_router
from app.api.v1.endpoints.doctor import router as doctor_router

api_router = APIRouter()
api_router.include_router(ocr_router)
api_router.include_router(dialogue_router)
api_router.include_router(doctor_router)
```

---

## 8. Step-by-Step Verification & Automated Testing Plan

When executing the implementation, run the following sequential tests to verify 100% functionality:

1. **Step 1: Test Direct WebP Upload, Deduplication & pgvector RAG Ingestion**:
   * Command: `python backend/test_ocr_pipeline.py`
   * Target: Verifies 250KB WebP upload, SHA-256 duplicate bypassing in $<20\text{ms}$, 30KB thumbnail creation, Gemini Vision extraction, `patient_structured_vectors` pgvector insertion via `ingest_ocr_payload_async`, and Supabase Storage persistence.
2. **Step 2: Test Vector-Driven Red-Flag Interceptor**:
   * Command: `python backend/test_vector_red_flags.py`
   * Target: Verifies chest pain/emergency symptoms match ICMR STW in Supabase with $>0.82$ similarity in $<10\text{ms}$.
3. **Step 3: Test Real-Time SSE Dialogue Stream & Auto-Summary**:
   * Command: `python backend/test_dialogue_pipeline_live.py`
   * Target: Runs a complete 4-turn patient simulation, streams tokens via SSE, reaches `should_stop == True`, and verifies the generated `ClinicalSummaryTicket` is saved to `clinical_summary_tickets` table and conforms to NAMASTE and ICD-10 schemas.
4. **Step 4: Test Doctor OPD Ticket Retrieval**:
   * Command: `python backend/test_doctor_ticket.py`
   * Target: Verifies `GET /api/v1/doctor/ticket/{session_id}` fetches the synthesized ticket with attached document previews.
