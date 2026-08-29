import subprocess

issues = {
    1: {
        "title": "[Setup] Initialize Repository Scaffold & Configuration Templates",
        "body": """### 🎯 Objective
Establish the core repository layout, environment configuration templates, dependency manifests, and database initialization scripts.

### 📋 Scope & Requirements
- **Directory Hierarchy Setup**:
  - `backend/`: FastAPI application code, router modules, AI pipelines, DB models.
  - `frontend/`: React + Vite application, components, state management, CSS tokens.
  - `docs/`: Architecture diagrams, FHIR schemas, API specs.
  - `scripts/`: DB migration scripts, model setup, demo seed data.
- **Environment Templates**:
  - Create `.env.example` containing placeholders for:
    - OpenAI / Anthropic / Gemini API keys
    - AI4Bharat ASR & Translation model URLs
    - Cloud Vision / PaddleOCR credentials
    - Supabase Postgres URL, Anon Key, Service Role Key
    - ABDM Sandbox Client ID & Secret
- **Database Initialization**:
  - Setup Supabase Postgres database.
  - Enable `pgvector` extension: `CREATE EXTENSION IF NOT EXISTS vector;`.

### ✅ Acceptance Criteria
- [x] Directory structure established and tracked in Git.
- [x] `.env.example` committed with all required service keys documented.
- [x] Supabase project connected with `pgvector` extension verified active."""
    },
    2: {
        "title": "[Clinical Ontology] Draft Clinical Ontology & CCRAS-PAS Question Battery",
        "body": """### 🎯 Objective
Freeze the clinical data model schemas for both Allopathic SOCRATES intake and Ayurvedic Dashavidha Pariksha / CCRAS Prakriti Assessment Scale (PAS).

### 📋 Scope & Requirements
- **Allopathic Schema**:
  - Standard SOCRATES framework: Site, Onset, Character, Radiation, Associations, Timecourse, Exacerbating/relieving factors, Severity.
  - Core clinical history blocks: Chief Complaint, HPI, Past Medical, Drug & Allergy, Family History, ROS.
- **Ayurvedic CCRAS-PAS Schema**:
  - Digitize the government-validated **CCRAS Prakriti Assessment Scale (PAS)** battery.
  - Group questions into the 4 primary domains: Physical, Physiological, Psychological, Behavioral.
  - Define dosha scoring mechanisms (Vata, Pitta, Kapha weighting).
- **Unified JSON Schema**:
```json
{
  "patient_id": "string",
  "visit_id": "string",
  "history_type": "allopathic | ayurvedic",
  "standard_history": { "chief_complaint": "", "hpi": "", "past_history": "" },
  "ayurvedic_assessment": { "prakriti": {}, "vikriti": {}, "agni": "", "koshtha": "" }
}
```

### ✅ Acceptance Criteria
- [ ] Frozen JSON schema files committed in `/docs/schemas/`.
- [ ] CCRAS-PAS question dataset saved as `ccras_pas_battery.json` for deterministic engine consumption."""
    },
    3: {
        "title": "[ABDM & Auth] Register ABDM Sandbox & FastAPI Backend Skeleton",
        "body": """### 🎯 Objective
Bootstrap the FastAPI backend web application and initiate the official ABDM (Ayushman Bharat Digital Mission) sandbox access registration.

### 📋 Scope & Requirements
- **FastAPI Infrastructure**:
  - Initialize FastAPI app with CORS middleware, request logging, and async event loop.
  - Create router modules: `/api/v1/auth`, `/api/v1/interview`, `/api/v1/ocr`, `/api/v1/summary`.
  - Add `/healthz` endpoint returning DB and service connectivity status.
- **ABDM Sandbox Registration**:
  - Submit sandbox registration on ABDM portal (https://sandbox.abdm.gov.in/).
  - Prepare a local mock ABHA auth fallback service (`/api/v1/mock/abha/otp`) in case sandbox approval lags past Day 4.

### ✅ Acceptance Criteria
- [ ] FastAPI app boots locally with `/healthz` passing.
- [ ] ABDM sandbox registration submitted; mock ABHA authentication service implemented as fallback."""
    },
    4: {
        "title": "[ASR Prototype] IndicConformer / IndicWhisper Local Baseline Test",
        "body": """### 🎯 Objective
Validate AI4Bharat IndicConformer or IndicWhisper ASR models on local sample Indian language audio files.

### 📋 Scope & Requirements
- **Model Setup**:
  - Download or connect to open-source IndicConformer / IndicWhisper weights.
  - Create test harness in `scripts/test_asr.py`.
- **Audio Validation**:
  - Test speech-to-text accuracy against sample audio files in Hindi, Tamil, and Assamese.
  - Benchmark word error rate (WER) and transcription latency per utterance.

### ✅ Acceptance Criteria
- [ ] Script successfully transcribes sample audio files into regional text.
- [ ] Latency per 5-second audio chunk benchmarked under 1.5 seconds."""
    },
    5: {
        "title": "[Voice Pipeline] Browser WebAudio Streaming & WebSocket ASR Integration",
        "body": """### 🎯 Objective
Build a real-time browser WebAudio capture module streaming raw PCM/WAV chunks over WebSockets to the FastAPI ASR engine.

### 📋 Scope & Requirements
- **Frontend Audio Capture**:
  - Use HTML5 MediaRecorder / AudioContext API to capture microphone stream.
  - Stream 16kHz mono audio chunks over WebSocket (`ws://localhost:8000/api/v1/ws/audio`).
- **Backend Streaming Pipeline**:
  - FastAPI WebSocket endpoint buffering audio chunks per utterance.
  - Pass audio buffer to IndicConformer / IndicWhisper inference worker.
  - Return transcribed text frame back to the client over WebSocket.

### ✅ Acceptance Criteria
- [ ] WebAudio capture working in browser without UI freeze.
- [ ] Continuous speech transcribed into text frames within 1 second of pause."""
    },
    6: {
        "title": "[Translation & TTS] IndicTrans2 Bidirectional Translation & Bhashini TTS",
        "body": """### 🎯 Objective
Implement the "translate-then-reason" translation loop (IndicTrans2) and regional speech synthesis (Bhashini TTS).

### 📋 Scope & Requirements
- **IndicTrans2 Integration**:
  - Input Translation: Regional Patient Language (Hindi/Tamil/etc.) ➔ English (for LLM reasoning).
  - Output Translation: LLM English Response ➔ Regional Patient Language.
- **Bhashini / Indic TTS**:
  - Synthesize translated regional text into audio stream/file for voice response playback on the kiosk.

### ✅ Acceptance Criteria
- [ ] Regional patient input translated accurately into medical English.
- [ ] LLM English response translated back to regional language and converted to audio output."""
    },
    7: {
        "title": "[Dialogue Manager] SOCRATES Adaptive LLM Dialogue Engine & Dual-Mode Controller",
        "body": """### 🎯 Objective
Construct the core LLM-driven dialogue manager supporting both adaptive SOCRATES Allopathic history taking and AYUSH CCRAS-PAS intake.

### 📋 Scope & Requirements
- **SOCRATES Adaptive Branching**:
  - LLM receives current conversation transcript + extracted document context.
  - Dynamically formulates relevant follow-up questions following SOCRATES clinical principles.
- **Dual-Mode Controller**:
  - Route dialogue dynamically based on `history_type` (`allopathic` vs `ayurvedic`).
  - Enforce max question depth (e.g., 6-8 turns) to keep interview time under 3 minutes per patient.

### ✅ Acceptance Criteria
- [ ] Dialogue engine generates logical clinical follow-up questions based on patient responses.
- [ ] Switching between Allopathic and Ayurvedic modes follows respective clinical logic."""
    },
    8: {
        "title": "[Document OCR] Prescription Scanning & Structured JSON Parsing",
        "body": """### 🎯 Objective
Build document OCR scanner (Cloud Vision / PaddleOCR) and LLM-powered extraction engine for paper medical records.

### 📋 Scope & Requirements
- **OCR Ingestion**:
  - Ingest photos/PDFs of physical prescriptions, lab reports, and discharge summaries.
  - Extract raw text using Google Cloud Vision API or PaddleOCR.
- **Structured JSON Extraction**:
  - LLM parses raw text into standardized schema:
    - `medications`: name, dosage, frequency, formulation (`vati`, `churna`, `mg`).
    - `diagnoses`: condition, system, coding.
    - `lab_results`: test_name, value, unit, reference_range.
- **Abnormal Flagging**:
  - Automatically flag lab values outside normal reference ranges.

### ✅ Acceptance Criteria
- [ ] Sample prescription images parsed into structured JSON schema with high accuracy.
- [ ] Abnormal lab values highlighted with warning flags."""
    },
    9: {
        "title": "[Vector Store] pgvector Schema & Document Embedding Pipeline",
        "body": """### 🎯 Objective
Configure Supabase `pgvector` index and build historical document embedding pipeline with strict patient SQL isolation.

### 📋 Scope & Requirements
- **Schema & Indexing**:
  - Create table `patient_document_vectors` with columns: `id`, `patient_id`, `document_id`, `content_chunk`, `embedding (vector(1536))`.
  - Add IVFFlat or HNSW index for fast cosine distance similarity search.
- **Embedding Pipeline**:
  - Generate embeddings for extracted document chunks using `text-embedding-3-small` / open-source embeddings.
- **Strict Tenant Isolation**:
  - Always enforce `WHERE patient_id = :patient_id` in vector search queries.

### ✅ Acceptance Criteria
- [ ] Document chunks embedded and indexed in `pgvector`.
- [ ] Vector search returns relevant chunks strictly filtered by `patient_id`."""
    },
    10: {
        "title": "[Voice Expansion] Multilingual ASR Support & Audio Noise Filtering",
        "body": """### 🎯 Objective
Expand ASR language capabilities to Hindi, Tamil, Assamese, and Bengali while adding background audio noise reduction.

### 📋 Scope & Requirements
- **Multilingual Support**:
  - Support language selection at kiosk onset (Hindi, Tamil, Assamese, Bengali, English).
  - Load appropriate ASR language acoustic model dynamically.
- **Noise Cancellation**:
  - Implement WebRTC / NoiseSuppressor audio pre-filter to handle noisy OPD environment background chatter.

### ✅ Acceptance Criteria
- [ ] Kiosk accurately transcribes audio across 4+ Indian languages.
- [ ] Background OPD noise effectively suppressed without clipping speech."""
    },
    11: {
        "title": "[AYUSH Engine] CCRAS Prakriti Assessment Scale (PAS) Fixed Question Battery",
        "body": """### 🎯 Objective
Implement the government-validated CCRAS-PAS Prakriti evaluation module for Ayurvedic clinical intake.

### 📋 Scope & Requirements
- **Battery Engine**:
  - Implement deterministic question flow across the 4 domains: Physical, Physiological, Psychological, Behavioral (91 predictors across 30 domains).
- **Prakriti Scoring Matrix**:
  - Calculate Vata, Pitta, and Kapha constitution percentages based on patient selections.
  - Store score summary in `ayurvedic_assessment.prakriti`.

### ✅ Acceptance Criteria
- [ ] CCRAS-PAS questions presented smoothly in voice/touch format.
- [ ] Output accurately computes Vata-Pitta-Kapha Prakriti breakdown."""
    },
    12: {
        "title": "[Red-Flag Triage] Emergency Symptom Detection Rules",
        "body": """### 🎯 Objective
Build a deterministic rule-based triage system to detect medical emergencies and alert OPD staff instantly.

### 📋 Scope & Requirements
- **Emergency Symptom Rules**:
  - Detect high-risk keyphrases (e.g., acute chest pain + radiating arm pain, sudden facial drooping, severe shortness of breath).
- **Priority Alert Action**:
  - Instantly halt non-urgent interview.
  - Trigger high-priority red alert badge on Doctor Dashboard queue.
  - Play emergency voice guidance instructing patient to report directly to emergency triage.

### ✅ Acceptance Criteria
- [ ] Red-flag symptoms trigger immediate alert badge in under 500ms.
- [ ] Emergency workflow overrides standard interview flow predictably."""
    },
    13: {
        "title": "[Frontend UI] React Kiosk Patient Interface & Doctor Dashboard Skeletons",
        "body": """### 🎯 Objective
Develop modern, accessible React (Vite) user interfaces for both the Patient Kiosk and the Doctor Consultation Dashboard.

### 📋 Scope & Requirements
- **Patient Kiosk UI**:
  - High-contrast, large touch targets designed for non-tech-literate patients.
  - Language selection screen, ABHA auth modal, animated voice visualizer (mic activity), document photo capture widget.
- **Doctor Dashboard UI**:
  - Patient queue list with red-flag priority badges.
  - High-density clinical summary view with interactive edit/confirm buttons.

### ✅ Acceptance Criteria
- [ ] Responsive, polished UI components rendered with smooth micro-animations.
- [ ] Both Patient Kiosk and Doctor Dashboard views fully navigable."""
    },
    14: {
        "title": "[Pipeline Integration] End-to-End Multilingual Voice & Document Processing",
        "body": """### 🎯 Objective
Connect all standalone microservices into a continuous, real-time end-to-end processing pipeline.

### 📋 Scope & Requirements
- **Full Voice Flow**:
  - Browser Microphone ➔ WebSocket ➔ ASR ➔ IndicTrans2 ➔ LLM Dialogue Manager ➔ IndicTrans2 ➔ TTS Audio ➔ Kiosk Speaker.
- **Full Document Flow**:
  - Document Photo ➔ Cloud Vision OCR ➔ LLM Structured JSON ➔ Supabase DB ➔ pgvector Index.

### ✅ Acceptance Criteria
- [ ] Patient can complete full voice interview with active audio feedback.
- [ ] Document photo uploaded during interview is processed and available for summary generation."""
    },
    15: {
        "title": "[Clinical Summary] FHIR R4 JSON Export & Single-Visit Context-Stuffed Summary",
        "body": """### 🎯 Objective
Generate concise, physician-ready clinical summaries in FHIR R4 standard JSON format using direct context-stuffing.

### 📋 Scope & Requirements
- **Summary Generation**:
  - Pass full visit dialogue transcript + extracted document JSON into LLM context window (no RAG needed for single visit).
  - Format output into standard sections: Chief Complaint, HPI, Past Medical, Medications, ROS, Assessment.
- **FHIR R4 Export**:
  - Map summary JSON into FHIR R4 `Composition` and `Condition` resource models for HIS/EMR export.

### ✅ Acceptance Criteria
- [ ] Clinical summary generated in under 5 seconds.
- [ ] FHIR R4 JSON valid against standard FHIR validator schemas."""
    },
    16: {
        "title": "[AYUSH Interoperability] NAMASTE Diagnostic Coding Lookup Bridge",
        "body": """### 🎯 Objective
Integrate the National AYUSH Morbidity & Standardized Terminologies Electronic (NAMASTE) portal coding mapped to WHO ICD-11 (TM2).

### 📋 Scope & Requirements
- **Terminology Lookup**:
  - Implement NAMASTE disease code search endpoint (`/api/v1/ayush/namaste-lookup`).
  - Map Ayurvedic diagnostic terms (e.g., *Amavata*, *Kaphaja Kasa*) to official NAMASTE codes and WHO ICD-11 Chapter 26 Module 2 (TM2) equivalents.

### ✅ Acceptance Criteria
- [ ] Search query returns correct NAMASTE code and ICD-11 TM2 mapping.
- [ ] Generated Ayurvedic clinical summaries include standardized NAMASTE codes."""
    },
    17: {
        "title": "[Authentication & Security] Supabase Auth RBAC & ABDM Sandbox Integration",
        "body": """### 🎯 Objective
Finalize patient authentication via ABDM ABHA sandbox and staff authentication via Supabase Auth RBAC.

### 📋 Scope & Requirements
- **Patient Auth**:
  - ABDM Sandbox OTP / Aadhaar authentication flow for ABHA ID verification.
  - Active fallback to mock ABHA auth service if sandbox credentials are offline.
- **Staff Auth**:
  - Supabase Auth with Role-Based Access Control (`doctor`, `receptionist`, `admin`).

### ✅ Acceptance Criteria
- [ ] Patient successfully logs in via ABHA OTP / Mock ABHA flow.
- [ ] Doctor access protected by Supabase Auth token middleware."""
    },
    18: {
        "title": "[Testing & Simulation] End-to-End Clinical Journey Validation",
        "body": """### 🎯 Objective
Execute comprehensive end-to-end clinical journey simulations covering all patient personas and clinical edge cases.

### 📋 Scope & Requirements
- **Test Personas**:
  - Persona A: Allopathic elderly patient with chest pain (triggers Red-Flag triage).
  - Persona B: Ayurvedic patient completing CCRAS-PAS Prakriti assessment + chronic joint pain history + prescription photo scan.
- **Validation**:
  - Measure total interview duration (target < 3 minutes).
  - Verify zero data loss between Kiosk intake and Doctor Dashboard review.

### ✅ Acceptance Criteria
- [ ] All persona test runs complete end-to-end without unhandled exceptions.
- [ ] Doctor Dashboard displays accurate summaries for all simulated visits."""
    },
    19: {
        "title": "[Doctor Workspace] Interactive Summary Edit & Ad-Hoc RAG Patient Q&A",
        "body": """### 🎯 Objective
Enhance the Doctor Dashboard with interactive summary confirmation and scoped ad-hoc RAG Q&A over historical records.

### 📋 Scope & Requirements
- **Interactive Editing**:
  - Doctor can edit, add notes, or confirm pre-generated clinical summary prior to pushing to HIS.
- **Ad-Hoc Doctor RAG Assistant**:
  - Doctor search bar allowing freeform questions (e.g., "Has patient ever had penicillin allergy?").
  - Query `pgvector` strictly scoped by `patient_id` and generate answered citations with dates.

### ✅ Acceptance Criteria
- [ ] Doctor edits save directly to Postgres and update FHIR record.
- [ ] Ad-hoc RAG accurately answers historical questions with document citations."""
    },
    20: {
        "title": "[Security & Compliance] DPDP Act 2023 Compliance & Data Encryption",
        "body": """### 🎯 Objective
Implement privacy guardrails and data protection measures in accordance with the Digital Personal Data Protection (DPDP) Act 2023.

### 📋 Scope & Requirements
- **Encryption**:
  - AES-256 encryption at rest for patient documents and PII fields.
- **Consent & Audit**:
  - SHA-256 immutable consent hash recorded in DB log during ABHA login.
- **Right to Erasure**:
  - Endpoint `/api/v1/patient/forget` destroying encryption keys and scrubbing PII records.

### ✅ Acceptance Criteria
- [ ] Database fields containing PII encrypted with AES-256.
- [ ] SHA-256 consent hash generated for every session and verifiable."""
    },
    21: {
        "title": "[Code Freeze & Optimization] Performance Tuning & Latency Cutoff",
        "body": """### 🎯 Objective
Execute code freeze, resolve lingering performance bottlenecks, and optimize WebSocket audio streaming latency.

### 📋 Scope & Requirements
- **Performance Cutoffs**:
  - WebSocket audio-to-text latency < 1.0 second.
  - Summary generation context-stuffing < 4.0 seconds.
- **Stability**:
  - Fix any UI memory leaks during long-running kiosk sessions.

### ✅ Acceptance Criteria
- [ ] Code base frozen with zero unhandled runtime exceptions.
- [ ] Latency targets met across all critical path endpoints."""
    },
    22: {
        "title": "[Demo Deliverables] Pre-record High-Res Backup Demo Video & Presentation Script",
        "body": """### 🎯 Objective
Prepare high-impact live demonstration materials and record a high-resolution fallback demo video to eliminate stage risks.

### 📋 Scope & Requirements
- **Backup Demo Video**:
  - Record 1080p video demonstrating full patient kiosk intake (voice + touch + OCR) and doctor dashboard review.
- **Presentation Script**:
  - Rehearse live pitch script emphasizing AYUSH differentiation (CCRAS-PAS, NAMASTE/ICD-11 mapping) and OPD time savings.

### ✅ Acceptance Criteria
- [ ] High-definition backup video recorded and uploaded to repository docs.
- [ ] Live demo pitch rehearsed and timed under allotted presentation limit."""
    }
}

for issue_num, data in issues.items():
    print(f"Updating Issue #{issue_num}: {data['title']}...")
    gh_exe = r"C:\Program Files\GitHub CLI\gh.exe"
    cmd = [
        gh_exe, "issue", "edit", str(issue_num),
        "--title", data["title"],
        "--body", data["body"]
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  [OK] Issue #{issue_num} updated successfully.")
    else:
        print(f"  [FAIL] Failed to update Issue #{issue_num}: {res.stderr}")

print("All issues updated successfully!")
