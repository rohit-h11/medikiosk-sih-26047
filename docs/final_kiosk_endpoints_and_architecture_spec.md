# MediKiosk Comprehensive API Endpoints Specification & Architecture Plan
**Finalized Technical Architecture & Protocol Reference Manual**

---

## 1. Finalized Endpoints Suite Summary

We have streamlined the entire MediKiosk backend down to **7 clean, high-performance endpoints** across 3 decoupled subsystems:

```
+===================================================================================================+
|                                  MEDIKIOSK FINALIZED 7-ENDPOINT SUITE                             |
+===================================================================================================+
| SUBSYSTEM A: SECURE DOCUMENT INGESTION & VISION OCR (Screen 1: Document Upload)                   |
+------------------------------------+--------+-----------------------------------------------------+
| 1. /api/v1/documents/upload-url    | POST   | Generates 60s cryptographically signed upload URL   |
| 2. /api/v1/ocr/process-document    | POST   | Triggers Gemini 3.6 Flash Vision OCR on WebP        |
| 3. /api/v1/documents/patient/{id}  | GET    | Retrieves patient's document history & OCR JSON     |
+------------------------------------+--------+-----------------------------------------------------+
| SUBSYSTEM B: DUAL-RAG DIALOGUE & STREAMING TRIAGE (Screen 2: Voice & Touch Dialogue)              |
+------------------------------------+--------+-----------------------------------------------------+
| 4. /api/v1/dialogue/stream-turn    | POST   | Real-time SSE Token Stream -> Voice TTS (Primary)   |
| 5. /api/v1/dialogue/turn           | POST   | Discrete REST turn handler for touchscreen taps     |
+------------------------------------+--------+-----------------------------------------------------+
| SUBSYSTEM C: SESSION TELEMETRY & DOCTOR EMR (Doctor OPD Station & Thermal Pass)                   |
+------------------------------------+--------+-----------------------------------------------------+
| 6. /api/v1/dialogue/session/{id}   | GET    | Session status, SOCRATES slot state & debug info    |
| 7. /api/v1/doctor/ticket/{id}      | GET    | Doctor OPD pre-populated EHR ticket & QR pass       |
+===================================================================================================+
```

---

## 2. End-to-End System Architecture

```
[SCREEN 1: DOCUMENT SCANNING]
  Patient scans Prescription / Lab Report
               │
               ▼
  1. POST /api/v1/documents/upload-url ──> Backend returns temporary Signed Upload URL (No credentials on Frontend)
  2. Direct Upload (Frontend -> Supabase Storage): Binary raw image uploaded directly to private bucket
  3. Client-Side WebP Conversion: Canvas converts image to lightweight 250KB WebP
  4. POST /api/v1/ocr/process-document ──> Gemini Vision OCR extracts structured Meds, Diagnoses, Vitals
               │
               ▼
[SCREEN 2: REAL-TIME VOICE & TOUCH DIALOGUE]
  Patient speaks or taps touchscreen options
               │
               ▼
  5. POST /api/v1/dialogue/stream-turn (Server-Sent Events)
     ├── Parallel RAG Search (8.4 ms): Supabase Vector Search on NAMASTE & ICMR Guidelines
     ├── Vector-Driven Red Flag Interceptor: Matches ICMR STW Emergency Protocols in < 10 ms
     ├── Groq LPU (Qwen-27B): Streams conversational inquiry tokens in < 250 ms TTFT
     └── EdgeTTS / ElevenLabs: Speaks out voice tokens on Kiosk Speaker
               │
          [Turns 1 to 5]
               │
               ▼ (When all SOCRATES slots filled / should_stop == True)
     Automatic Summary Generation (Gemini 3.6 Flash):
     Synthesizes full dialogue + OCR records into `ClinicalSummaryTicket`
               │
               ▼
[SCREEN 3: CONSULTATION PASS & DOCTOR EMR DISPATCH]
  6. Kiosk displays Summary Card & prints Thermal QR Pass
  7. GET /api/v1/doctor/ticket/{session_id} pushes pre-populated EHR to Doctor's desk
```

---

## 3. Comprehensive Endpoint Specifications

### 📂 Subsystem A: Document Ingestion & OCR

#### 1. `POST /api/v1/documents/upload-url`
* **Purpose**: Issues a 60-second, cryptographically signed pre-signed URL allowing the frontend to upload a multi-megabyte raw photo directly to Supabase Storage without burdening backend memory.
* **Request (`GetUploadUrlRequest`)**:
```json
{
  "patient_id": "PAT-98421",
  "document_type": "prescription",
  "file_extension": "jpg"
}
```
* **Response (`GetUploadUrlResponse`)**:
```json
{
  "doc_id": "d8f3b2a1-6c4e-4f11-9a7b-8e2d4c6a1b3f",
  "storage_path_raw": "patient-medical-records/PAT-98421/prescriptions/d8f3b2a1_raw.jpg",
  "signed_upload_url": "https://xyz.supabase.co/storage/v1/object/upload/sign/patient-medical-records/PAT-98421/d8f3b2a1_raw.jpg?token=eyJhbGciOi...",
  "expires_in_seconds": 60
}
```

---

#### 2. `POST /api/v1/ocr/process-document`
* **Purpose**: Invokes Gemini 3.6 Flash Vision OCR on the optimized WebP image, parses handwriting/printed text into structured medical JSON, and saves extracted entities in PostgreSQL and `pgvector`.
* **Request (`ProcessDocRequest`)**:
```json
{
  "doc_id": "d8f3b2a1-6c4e-4f11-9a7b-8e2d4c6a1b3f",
  "patient_id": "PAT-98421",
  "storage_path_raw": "patient-medical-records/PAT-98421/prescriptions/d8f3b2a1_raw.jpg",
  "processed_image_base64": "<optional lightweight 250KB WebP>"
}
```
* **Response (`ProcessDocResponse`)**:
```json
{
  "status": "completed",
  "doc_id": "d8f3b2a1-6c4e-4f11-9a7b-8e2d4c6a1b3f",
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

#### 4. `POST /api/v1/dialogue/stream-turn` (Primary Engine)
* **Protocol**: Server-Sent Events (`text/event-stream`).
* **Purpose**: Accepts patient voice transcription or touch chip input, executes dual-vector search (guidelines + patient history), evaluates ICMR red-flag thresholds, streams conversational LLM tokens in real-time (<250ms TTFT), and **automatically attaches the final Doctor Clinical Summary Ticket on completion**.
* **Request Payload**:
```json
{
  "session_id": "ses_7f8c9b2a",
  "patient_id": "PAT-98421",
  "patient_response": "Ghutne me tez jalan aur soojan hai 3 dino se",
  "selected_option_id": "opt_burning",
  "language": "hi"
}
```
* **Streaming Event Flow**:
```
event: token
data: {"text": "नमस्ते "}

event: token
data: {"text": "रमेश जी। क्या यह दर्द "}

event: token
data: {"text": "सुबह उठने पर ज्यादा रहता है?"}

event: control
data: {
  "should_stop": false,
  "touch_options": [
    {"id": "opt_morning", "label": "हाँ, सुबह अधिक दर्द", "value": "सुबह उठते समय ज्यादा दर्द होता है", "slot_tag": "time_course"},
    {"id": "opt_constant", "label": "लगातार एक जैसा", "value": "दिन भर एक जैसा दर्द रहता है", "slot_tag": "time_course"}
  ],
  "socrates_state": {
    "site": "Right knee",
    "character": "Burning and swelling",
    "onset": "3 days",
    "covered_slots": ["site", "character", "onset"],
    "missing_slots": ["radiation", "time_course", "exacerbating_relieving", "severity"]
  }
}

event: done
data: {"status": "complete"}
```

* **When `should_stop == True` (Final Turn Event)**:
```
event: control
data: {
  "should_stop": true,
  "closing_message": "धन्यवाद रमेश जी। आपकी जानकारी दर्ज कर ली गई है और डॉक्टर पर्ची तैयार है।",
  "clinical_summary_ticket": {
    "ticket_id": "TKT-20260906-8831",
    "triage_urgency": "PRIORITY_YELLOW",
    "ayurvedic_assessment": {
      "namaste_code": "AAD-2 (Pittavrita Vata / Sandhivata)",
      "dosha_imbalance": "Vata-Pitta Pradhana",
      "prakriti_tendency": "Vata-Pitta"
    },
    "allopathic_differential": {
      "icd10": "M17.0 (Primary Osteoarthritis with acute inflammation)"
    },
    "drug_herb_safety_warnings": [
      "Patient taking Telmisartan 40mg (ARB): Avoid high-sodium herbal kashayams.",
      "Avoid hot Panchakarma fomentation (Ushna Virya) during acute inflammatory phase."
    ],
    "pathya_recommended_diet": ["Mudga Yusha", "Old Shali Rice", "Coriander seed boiled water"],
    "apathya_restricted_diet": ["Curd at night", "Excess red chili", "Deep fried oily food"]
  }
}
```

---

### 📋 Subsystem C: Session Telemetry & Doctor OPD Station

#### 7. `GET /api/v1/doctor/ticket/{session_id}`
* **Purpose**: Live endpoint for the hospital Doctor's EMR consultation terminal to fetch the pre-populated clinical intake sheet before the patient enters the OPD room.
* **Response**: Returns the complete validated `ClinicalSummaryTicket` Pydantic payload with triage badge, SOCRATES narrative, NAMASTE code, ICD-10 differential, and herb-allopathy safety warnings.
