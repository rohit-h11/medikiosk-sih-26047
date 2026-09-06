# MediKiosk Comprehensive API Endpoints Specification & Architecture Plan
**Finalized Technical Architecture & Protocol Reference Manual**

---

## 1. Finalized Endpoints Suite Summary

We have streamlined the entire MediKiosk backend down to **5 clean, high-performance endpoints** across 3 decoupled subsystems with **zero presigned upload URLs** and **automated pgvector RAG embedding on medical documents**:

```
+===================================================================================================+
|                                  MEDIKIOSK FINALIZED 5-ENDPOINT SUITE                             |
+===================================================================================================+
| SUBSYSTEM A: DIRECT VISION OCR, STORAGE & DOCUMENT RAG EMBEDDING (Screen 1: Document Upload)      |
+------------------------------------+--------+-----------------------------------------------------+
| 1. /api/v1/ocr/process-document    | POST   | Direct WebP Upload -> Deduplication -> Gemini OCR   |
|                                    |        | -> Auto-Thumbnail -> pgvector RAG Embedding         |
+------------------------------------+--------+-----------------------------------------------------+
| SUBSYSTEM B: DUAL-RAG DIALOGUE & STREAMING TRIAGE (Screen 2: Voice & Touch Dialogue)              |
+------------------------------------+--------+-----------------------------------------------------+
| 2. /api/v1/dialogue/stream-turn    | POST   | Real-time SSE Token Stream -> Voice TTS (Primary)   |
| 3. /api/v1/dialogue/turn           | POST   | Discrete REST turn handler for touchscreen taps     |
| 4. /api/v1/dialogue/session/{id}   | GET    | Session status, SOCRATES slot state & telemetry     |
+------------------------------------+--------+-----------------------------------------------------+
| SUBSYSTEM C: DOCTOR OPD STATION & CONSULTATION PASS (Doctor OPD Station & Thermal Pass)           |
+------------------------------------+--------+-----------------------------------------------------+
| 5. /api/v1/doctor/ticket/{id}      | GET    | Doctor OPD pre-populated EHR ticket & QR pass       |
+===================================================================================================+
```

---

## 2. End-to-End System Architecture

```
[SCREEN 1: DOCUMENT SCANNING]
  Patient scans Prescription / Lab Report / Ayurvedic Paper
               │
               ▼
  1. Kiosk Canvas compresses camera capture to 2048px WebP (~250 KB) in 15ms
  2. POST /api/v1/ocr/process-document (Single Direct Multipart Upload)
     ├── Pre-Ingestion Gate: SHA-256 hash check (<1ms) -> If duplicate, returns cached JSON (<20ms)
     ├── In-Memory Thumbnail: Generates 30KB thumbnail in 2ms (Pillow)
     ├── Gemini 3.6 Flash Vision OCR: Runs directly on in-memory bytes (Zero Supabase downloads!)
     ├── Background Storage: Uploads master WebP + thumbnail to Supabase Storage concurrently
     └── Background Vector RAG: Splits extracted findings into 4 semantic chunks with contextual headers
         and embeds them into `patient_structured_vectors` (MiniLM-L6-v2, 384 dims)
               │
               ▼
[SCREEN 2: REAL-TIME VOICE & TOUCH DIALOGUE]
  Patient speaks or taps touchscreen options
               │
               ▼
  3. POST /api/v1/dialogue/stream-turn (Server-Sent Events)
     ├── Parallel Dual-RAG Search (8.4 ms):
     │   ├── (A) National Guidelines (ICMR STWs & NAMASTE Codes) via `match_clinical_guidelines`
     │   └── (B) Patient Document History (Past Meds, Allergies, Labs) via `match_patient_history`
     ├── Vector-Driven Red Flag Interceptor: Matches ICMR STW Emergency Protocols in < 10 ms
     ├── Groq LPU (Qwen-27B): Streams conversational inquiry tokens in < 250 ms TTFT
     └── EdgeTTS / ElevenLabs / Sarvam: Speaks out voice tokens on Kiosk Speaker
               │
          [Turns 1 to 5]
               │
               ▼ (When all SOCRATES slots filled / should_stop == True)
     Automatic Summary Generation (Gemini 3.6 Flash):
     Synthesizes full dialogue + OCR records into `ClinicalSummaryTicket` & saves to DB
               │
               ▼
[SCREEN 3: CONSULTATION PASS & DOCTOR EMR DISPATCH]
  4. Kiosk displays Summary Card & prints Thermal QR Pass
  5. GET /api/v1/doctor/ticket/{session_id} pushes pre-populated EHR + document preview links to Doctor's desk
```

---

## 3. Medical Document Vector RAG Subsystem

When a medical document (prescription, lab report, discharge summary) is digitized, it is automatically converted into vector embeddings for **cross-visit longitudinal intelligence**:

### A. Contextual Chunking Strategy
Every extracted entity is prefixed with a deterministic contextual header:
```
[Patient: {patient_id} | Document: {document_type} | Encounter Date: {date} | Status: Active]
```

### B. The 4 Semantic Document Chunk Types:
1. **`medications`**: Active allopathic drugs & dosages, Ayurvedic churnas/kwaths/vatis with frequency and duration.
2. **`diagnoses`**: Primary & secondary diagnoses, chronic morbidities, ICD-10 & NAMASTE terms.
3. **`lab_findings`**: Lab investigation results, reference ranges, and flagged abnormal values.
4. **`ayush_parameters`**: Prakriti/Vikriti notes, Agni/Koshtha status, and Panchakarma treatment history.

### C. Database Vector Schema (`patient_structured_vectors`):
```sql
CREATE TABLE IF NOT EXISTS patient_structured_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    document_id TEXT,
    category TEXT NOT NULL,           -- 'medications' | 'diagnoses' | 'lab_findings' | 'ayush_parameters'
    content TEXT NOT NULL,             -- Markdown chunk with contextual header
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    encounter_date DATE,
    embedding VECTOR(384) NOT NULL,    -- all-MiniLM-L6-v2 (384 dimensions)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patient_vectors_hnsw 
ON patient_structured_vectors USING hnsw (embedding vector_cosine_ops);
```

### D. Hybrid Retrieval RPC (`match_patient_history`):
Supports patient-scoped similarity search combined with temporal recency decay:
```sql
CREATE OR REPLACE FUNCTION match_patient_history(
    p_patient_id TEXT,
    p_query_embedding VECTOR(384),
    p_top_k INT DEFAULT 5,
    p_similarity_threshold REAL DEFAULT 0.40,
    p_category TEXT DEFAULT NULL,
    p_use_recency BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    id UUID,
    patient_id TEXT,
    category TEXT,
    content TEXT,
    metadata JSONB,
    encounter_date DATE,
    similarity REAL,
    recency REAL,
    final_score REAL
) ...
```

---

## 4. Comprehensive Endpoint Specifications

### 📂 Subsystem A: Document Ingestion, Vision OCR & RAG Embedding

#### 1. `POST /api/v1/ocr/process-document`
* **Purpose**: Single unified endpoint for prescription ingestion, instant deduplication, Gemini Vision OCR extraction, background Supabase archiving, and **auto-embedding into `patient_structured_vectors` for RAG**.
* **Request (`Multipart Form Data`)**:
  * `file`: 2048px WebP image ($\sim 250\text{ KB}$)
  * `patient_id`: `"PAT-98421"`
  * `document_type`: `"prescription"`
  * `session_id`: (Optional) `"ses_7f8c9b2a"`
* **Response (`ProcessDocResponse`)**:
```json
{
  "status": "completed",
  "doc_id": "d8f3b2a1-6c4e-4f11-9a7b-8e2d4c6a1b3f",
  "patient_id": "PAT-98421",
  "file_path": "PAT-98421/prescriptions/d8f3b2a1.webp",
  "file_path_thumb": "PAT-98421/prescriptions/d8f3b2a1_thumb.webp",
  "is_duplicate": false,
  "rag_chunks_embedded": 3,
  "extracted_data": {
    "doctor_name": "Dr. V. K. Gupta, MD",
    "consultation_date": "2025-08-14",
    "diagnoses": ["Essential Hypertension", "Mild Osteoarthritis"],
    "current_medications": [
      {"name": "Telmisartan", "dosage": "40mg", "frequency": "1-0-0", "duration": "Ongoing"},
      {"name": "Paracetamol", "dosage": "650mg", "frequency": "SOS", "duration": "5 days"}
    ],
    "known_allergies": ["Sulfa drugs"],
    "vitals_recorded": {"bp": "138/86 mmHg"}
  }
}
```

---

### 🗣️ Subsystem B: Real-Time Dual-RAG Dialogue & Streaming Triage

#### 2. `POST /api/v1/dialogue/stream-turn` (Primary Dialogue Engine)
* **Protocol**: Server-Sent Events (`text/event-stream`).
* **Purpose**: Streams Groq Qwen-27B conversational tokens in real-time ($<250\text{ms}$ TTFT), checks vector red flags, executes parallel dual-vector RAG (guidelines + patient document vectors from `patient_structured_vectors`), and auto-generates Doctor Summary Ticket on completion.

#### 3. `POST /api/v1/dialogue/turn`
* **Purpose**: Discrete REST turn handler for touchscreen button taps / non-streaming fallback.

#### 4. `GET /api/v1/dialogue/session/{session_id}`
* **Purpose**: Real-time telemetry endpoint to inspect active session state and SOCRATES slot status.

---

### 👨‍⚕️ Subsystem C: Doctor OPD Station & Consultation Pass

#### 5. `GET /api/v1/doctor/ticket/{session_id}`
* **Purpose**: Fetches the pre-populated clinical summary ticket and document preview signed URLs for the physician's OPD dashboard.
