# MediKiosk — AI Clinical History Software Platform

**Problem Statement:** 26047 — Patient Case-Taking Software
**Organization:** Ministry of Ayush / All India Institute of Ayurveda (AIIA)
**Category:** Software · Theme: MedTech / BioTech / HealthTech
**Timeline:** 6-day MVP/demo build · Team: 5 ML + 1 Dev

---

## 1. Problem Summary

Indian OPDs see 4,000–10,000 patients/day with only 2–5 minutes of doctor consultation time available. History-taking — the single most diagnostically valuable clinical activity — gets systematically compressed or skipped. AYUSH institutions face an even heavier burden, since Ayurvedic history-taking (Dashavidha Pariksha: Prakriti, Vikriti, Agni, Koshtha, Ahara-Vihara, Nidana, Samprapti) is far more extensive than allopathic intake.

Patients also arrive with fragmented paper records (prescriptions, lab reports, discharge summaries) that doctors must manually parse mid-consultation, wasting further time.

**Existing solutions fall short** because they either only capture demographic data (hospital kiosks), require smartphone literacy (health apps), don't scale (nurse-led triage), or don't extract/structure content (basic scanners).

## 2. Solution Overview

MediKiosk is a kiosk/software platform patients use **before** seeing the doctor:

1. **Identify** — ABHA ID login + consent (audio-guided)
2. **Converse** — AI conducts adaptive voice + touch history interview (chief complaint, HPI, past/drug/family/personal history, ROS); red flags trigger priority alerts
3. **Scan** — Patient uploads prior documents; AI OCRs and digitizes them
4. **Summarize & Route** — AI generates a structured, physician-ready summary, links to ABHA, pushes to HIS
5. **Consult** — Physician reviews the pre-built summary in seconds, edits/confirms, spends the consult on examination and reasoning

## 3. Architecture

### 3.1 Voice/Language Pipeline (accuracy-first, translate-then-reason)

```
Patient speech (Hindi/Tamil/Assamese/etc.)
  → IndicConformer or IndicWhisper (ASR)
  → IndicTrans2 (translate to English)
  → LLM reasons in English (follow-up questions, SOCRATES branching, red-flag detection)
  → IndicTrans2 (translate response back to patient's language)
  → TTS (Bhashini / Indic TTS) → spoken back to patient
```

Chosen over native multilingual LLM reasoning — English-language reasoning is far more reliable for medical follow-up logic; the extra translation hop is worth the accuracy gain. Batch-per-utterance (not live streaming translation) for demo reliability. Patient selects language upfront rather than auto-detection.

### 3.2 Document Digitization (Module B)

```
Photo of document → OCR (Cloud Vision / PaddleOCR) → raw text
  → LLM extraction → structured JSON (diagnosis, meds, labs, date)
  → store in DB + embed for RAG
  → feed into summary generator
```

Handwriting recognition is hard — demo focus on printed/typed documents, claim handwriting as future scope if needed. Abnormal lab values flagged against reference ranges.

### 3.3 Summary Generation (Module C) — no RAG needed

Single visit's transcript + extracted documents fit in one LLM context window — direct context-stuffing, not retrieval. Output: standard clinical format (Chief complaint → HPI → Past medical/surgical → Drug & allergy → Family → Personal → ROS → Prior investigations), editable by physician, bilingual (patient audio confirmation local language / physician summary English/Hindi), exported as FHIR-shaped JSON.

### 3.4 RAG — scoped to doctor ad-hoc Q&A only (in MVP)

Used only when doctor asks something not in the summary (e.g., "did this patient ever mention a penicillin allergy?"), querying across the patient's **full historical** record.

```
Doctor question → embed → pgvector similarity search (WHERE patient_id = X) 
  → top-k chunks → LLM generates answer with source/date citation
```

- Vector DB: **pgvector** (via Supabase) — avoids a second data store, native SQL filtering by `patient_id`, sufficient at hackathon scale
- Retrieval always scoped to one patient — never searches across patients (correctness + privacy)
- LLM never queries the DB directly — backend does nearest-neighbor search, then hands retrieved text to the LLM as context

### 3.5 AYUSH/Ayurveda-Specific Handling (differentiation focus)

Ayurvedic history-taking is **person-centered, not just disease-centered** — two patients with the same complaint can need different treatment based on constitution. This is structurally different from allopathic intake, not just "extra questions," and is treated as a key differentiator for this build (see Section 8).

**Dashavidha Pariksha (tenfold examination)** — the ten parameters: Prakriti (constitution), Vikriti (current imbalance), Sara (tissue quality), Samhanana (structural integrity), Pramana (anthropometry), Satmya (adaptability), Satva (mental strength), Ahara Shakti (digestive capacity), Vyayama Shakti (exercise capacity), Vaya (age).

**Dialogue manager needs two distinct modes, not one schema with extra fields:**
```
IF history_type == "ayurvedic":
    1. Standard chief-complaint/HPI intake (same engine as allopathic)
    2. Prakriti assessment — mostly FIXED question battery, low reactivity,
       NOT complaint-driven (constitution doesn't change based on why they came in)
    3. Vikriti/Agni/Koshtha — classification-style questions constrained to
       known dosha-imbalance categories, not free-form follow-up generation
ELSE:
    Standard SOCRATES-style adaptive branching only
```

**CCRAS Prakriti Assessment Scale (PAS)** — a real, government-standardized, validated instrument (Ministry of AYUSH body CCRAS, same parent ministry as AIIA) to use as the source question set for the Prakriti module, instead of inventing questions from scratch:
- Multiple-choice, segregated into four domains: physical, physiological, psychological, behavioral
- 91 predictors grouped into 30 domains across those four traits
- Validated via multi-centric double-blinded interrater study, including AIIA New Delhi as one of the validating institutions
- Digitized reference implementation exists: CCRAS "AYUR Prakriti" web portal (ccras.res.in/ccras_pas)
- Caveat: of 64 known Prakriti assessment tools reviewed, only CCRAS-PAS and one other (ACPI) meet most scientific validation criteria — frame to judges as "CCRAS-validated," not as definitively scientifically proven

**Conversational history schema addition** (separate block, not merged into standard history):
```json
{
  "patient_id": "...", "visit_id": "...",
  "history_type": "allopathic | ayurvedic",
  "standard_history": { "chief_complaint": "...", "hpi": "...", "past_history": "...", "..." : "..." },
  "ayurvedic_assessment": {
    "prakriti": "...", "vikriti": "...", "agni": "...",
    "koshtha": "...", "ahara_vihara": "...", "nidana": "...", "samprapti": "..."
  }
}
```

**Document schema addition** (Module B) — shared schema across medicine systems, with an Ayurveda-aware extension, not a fully separate schema:
```json
{
  "medicine_system": "allopathic | ayurvedic | unani | other",
  "medications": [
    {
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "form": "string | null"   // churna, kwath, vati, taila, arishta, asava, ghrita — doesn't map to Western mg dosing
    }
  ],
  "diagnosis": [
    {
      "condition": "string",
      "system_terminology": "ayurvedic | biomedical",
      "coding_system": "NAMASTE | ICD | null",
      "code": "string | null"
    }
  ]
}
```
OCR/extraction prompt (ML4) needs explicit awareness it may be reading an Ayurvedic document — mixed English/Devanagari/Sanskrit script, non-Western formulation names (Triphala, Ashwagandha, Chyawanprash) less represented in OCR training data → expect more low-confidence flags on these terms.

**NAMASTE (National AYUSH Morbidity & Standardized Terminologies Electronic Portal)** — Ministry of AYUSH's standardized coding system for Ayurveda/Siddha/Unani diagnoses, mapped to WHO ICD-11 Chapter 26 Module 2 (TM2, officially released Feb 2025) — this is the intended real path for FHIR/ABDM semantic interoperability on the Ayurvedic side, not a workaround. An open-source bridge project (AyushSyncAPI) offers FHIR R4-compliant NAMASTE↔ICD-11 search/mapping with ABHA auth built in — worth evaluating for reuse instead of building terminology lookup from scratch. Caveat: public access to the full official NAMASTE dataset has been inconsistent in past implementation attempts — verify direct access before committing; a small representative code sample may be needed as fallback for the demo.

### 3.6 Red-Flag Detection

Rule/keyword-based (not ML classifier) for demo predictability — flags emergency symptoms (e.g., chest pain + dyspnoea, stroke symptoms) and triggers priority triage alert.

### 3.7 Consent, Privacy & ABDM Integration (Module D)

- **ABDM is federated, not a central data store** — hospital's own DB is the source of truth; ABDM only brokers consent and knows "this patient has records here" (HIP role)
- Patient auth: real ABHA sandbox OTP flow (register for sandbox access on Day 1 — 3–4 day approval lag) with a mocked fallback ready if credentials don't land in time
- Staff/doctor auth: Supabase Auth (standard email/password + role-based access) — unrelated to ABHA, don't build custom auth
- DPDP Act 2023 compliance: patient identity tokenized/encrypted (separate from document content); document content encrypted at rest (AES-256); document integrity via SHA-256 hash; consent records hashed for immutable audit trail; "right to erasure" satisfied by deleting encryption key + DB row

## 4. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python) | ML logic is all Python — one backend, native async REST endpoints for Push-to-Talk audio processing |
| Frontend | **React (Vite)** | No SSR/SEO need for kiosk or internal dashboard; lightweight REST integration for Push-to-Talk audio payloads |
| Auth (staff) | **Supabase Auth** | Standard, solved problem — don't build custom auth |
| Auth (patient) | **ABHA sandbox** (OTP/Aadhaar) | Required by the problem itself — this is what links data to the patient's real health record |
| Main DB | **Postgres (Supabase)** | Encrypted patient/document tables |
| Vector DB | **pgvector** (Supabase extension) | Same DB as main store, native filtering, sufficient scale |
| ASR | **IndicConformer / IndicWhisper** (AI4Bharat, open-source) | Purpose-built for Indian languages |
| Translation | **IndicTrans2** | Pairs with AI4Bharat ASR stack |
| TTS | **Bhashini** or Indic TTS | Free for non-commercial use, govt-aligned |
| LLM | API-based (adaptive questioning, extraction, summary, RAG answers) | No fine-tuning needed — prompt engineering + schema design |
| OCR | Cloud Vision API / PaddleOCR | Multilingual, printed + some handwriting support |

**No dataset collection or model training required** — every AI component is either a pretrained open-source model or an API call. Effort goes into orchestration, prompt/schema design, and integration.

## 5. Team & Task Split (5 ML + 1 Dev)

| Person | Owns |
|---|---|
| ML1 + Dev (paired) | ASR pipeline (IndicConformer/Whisper) + Push-to-Talk audio capture (browser → HTTP POST → ASR) |
| ML2 | Translation (IndicTrans2 in/out) + TTS voice-out |
| ML3 | Adaptive questioning LLM (dialogue manager, clinical ontology/SOCRATES schema, red-flag rules) |
| ML4 | OCR + document extraction (OCR API → LLM structured JSON, abnormal-value flagging) |
| ML5 | RAG pipeline (embeddings, pgvector, doctor Q&A) + summary generator (context-stuffing + FHIR export) |
| Dev (remaining time) | FastAPI backend, React frontend (kiosk + doctor dashboard), Supabase auth, DB schema, ABHA mock/sandbox wiring |

## 6. 6-Day Timeline

**Day 1 — Setup**
- API keys/model access for everyone; repo scaffold
- Team: draft clinical ontology/schema (SOCRATES + AYUSH questions) — blocks ML3, do first
- Dev: FastAPI skeleton, Supabase project, **register ABDM sandbox immediately** (3–4 day approval lag)
- Dev + ML1: get IndicConformer/Whisper running on sample audio

**Day 2 — Individual components, isolated**
- Dev + ML1: browser Push-to-Talk audio capture → HTTP POST → ASR working for 1–2 languages
- ML2: IndicTrans2 both directions + basic TTS
- ML3: prompt engineering, dual-mode (voice/touch) question format
- ML4: OCR wired, tested on sample prescriptions
- ML5: pgvector schema + embedding pipeline skeleton

**Day 3 — Depth**
- Dev + ML1: expand ASR languages, noise handling
- ML2: wire translation into dialogue manager loop
- ML3: full adaptive questioning loop + red-flag rules
- ML4: structured extraction (JSON), abnormal-value flagging
- ML5: retrieval + doctor Q&A generation; start summary generator
- Dev: React kiosk screens + doctor dashboard skeleton

**Day 4 — Integration, round 1**
- Full loop: ASR → translate → dialogue → translate → TTS
- OCR → extraction → DB → embeddings, connected end to end
- Frontend wired to real endpoints
- ABHA sandbox credentials likely land ~now — swap in if ready, keep mock as fallback
- Summary generator producing FHIR-shaped JSON

**Day 5 — Integration, round 2 + testing**
- Full patient journey tested start to finish
- Doctor dashboard: summary view + edit/confirm + ad-hoc RAG Q&A
- Bug fixes, consent screen polish

**Day 6 — Demo prep**
- UI polish, rehearse demo script
- **Record a backup demo video** — live multilingual voice on stage is the single biggest failure risk
- Buffer for last-minute fixes

**Estimated total effort:** ~350–390 person-hours across the team (~60–72 hrs/person over 6 days).

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| ABDM sandbox approval delayed past Day 4 | Mocked ABHA login/consent screens ready as fallback from Day 1 |
| Live ASR fails on stage (noise/accent) | Pre-recorded backup demo video |
| Clinical schema design drags on Day 1 | Time-box it; blocks ML3 and downstream work |
| ASR/noise tuning becomes a rabbit hole | Hard cutoff by end of Day 3 |
| Behind schedule by Day 4 | First cut candidate: doctor's ad-hoc RAG Q&A (core voice-intake → summary flow still stands without it) |

## 8. Explicit Scope Decisions (for judges)

- **No RAG for same-visit summary generation** — single visit's data fits in one LLM context window; RAG is reserved for cross-visit doctor Q&A where it's actually needed
- **No dataset training** — all AI components are pretrained/API-based; effort is orchestration and prompt/schema design
- **Red-flag detection is rule-based**, not ML — safer and more predictable for a live demo
- **Real ABDM sandbox targeted**, not just a UI mock — registered Day 1, with a fallback mock kept ready
- **AYUSH depth over shallow "Ayurveda mode" toggle** — most competing teams will likely bolt on a couple of generic Ayurveda-flavored questions; this build uses a genuinely distinct dialogue-manager branch (fixed CCRAS-validated Prakriti battery vs. adaptive SOCRATES branching) and targets real NAMASTE-coded Ayurvedic diagnoses in the FHIR export rather than leaving them unstructured
