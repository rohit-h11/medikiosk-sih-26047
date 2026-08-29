# 🩺 MediKiosk — AI Clinical History Software Platform

> **Smart India Hackathon (SIH) — Problem Statement 26047**  
> **Organization:** Ministry of Ayush / All India Institute of Ayurveda (AIIA)  
> **Category:** Software · **Theme:** MedTech / BioTech / HealthTech  

---

## 📌 Executive Summary

Indian OPDs handle 4,000–10,000 patients daily with only 2–5 minutes available per consultation. Clinical history taking—the most diagnostically critical activity—is often severely compressed or skipped. AYUSH institutions (specifically Ayurvedic hospitals) face an even greater challenge: Ayurvedic history taking (**Dashavidha Pariksha**) requires evaluating patient constitution (*Prakriti*), dosha imbalance (*Vikriti*), digestive power (*Agni*), and lifestyle (*Ahara-Vihara*), making thorough history taking impossible within standard consultation limits.

**MediKiosk** solves this by serving as an AI-powered voice & touch intake kiosk used by patients **prior** to entering the consultation room. It captures adaptive clinical history in native Indian languages, digitizes physical records, extracts structured medical data, maps AYUSH diagnoses to **NAMASTE/ICD-11** standards, and generates FHIR-compliant clinical summaries for immediate doctor review.

---

## 🌟 Key Features & Capabilities

- 🗣️ **Multilingual Voice Interview Engine:** Powered by AI4Bharat IndicConformer/IndicWhisper, IndicTrans2, and Bhashini TTS with an English reasoning core ("translate-then-reason").
- 🌿 **AYUSH-Native Dual Dialogue Engine:** Features a dedicated, government-standardized **CCRAS Prakriti Assessment Scale (PAS)** battery alongside standard allopathic SOCRATES adaptive history branching.
- 📄 **Document Digitization & Structured Extraction:** OCR extraction of handwritten/typed prescriptions, lab reports, and discharge summaries into structured JSON with abnormal lab value flagging.
- ⚡ **Instant Clinical Summarizer:** Generates direct context-stuffed, FHIR-shaped summaries formatted for 30-second physician review.
- 🔍 **Doctor Ad-Hoc RAG Assistant:** Scoped pgvector retrieval for cross-visit historical patient Q&A without cross-patient data leaks.
- 🚨 **Rule-Based Red-Flag Triage:** Instant emergency symptom detection (e.g., acute chest pain, stroke signs) triggering priority queue alerts.
- 🔐 **ABDM & DPDP Act 2023 Compliant:** ABHA authentication, tokenized/encrypted identity storage, AES-256 document encryption at rest, and cryptographic hash consent audit trails.

---

## 🏗️ Architecture Overview

```
               +-------------------------------------------------------+
               |                  MediKiosk Platform                   |
               +-------------------------------------------------------+
                                           |
    +--------------------------------------+--------------------------------------+
    |                                      |                                      |
    v                                      v                                      v
[ Patient Kiosk ]                [ AI Processing Pipeline ]              [ Doctor Dashboard ]
  - ABHA Sandbox Auth              - IndicConformer / Whisper (ASR)        - FHIR Clinical Summary
  - Voice / Touch UI               - IndicTrans2 (Translation)             - Interactive Edit / Confirm
  - Doc Photo Capture              - LLM Clinical Dialogue Manager         - Ad-hoc RAG Patient Q&A
  - Multilingual TTS               - OCR + Structured Extraction           - Emergency Triage Alerts
                                   - pgvector Context Store
```

### Voice / Language Pipeline ("Translate-Then-Reason")
```
Patient Speech (Hindi/Tamil/etc.) 
   ➔ IndicConformer / IndicWhisper (ASR) 
   ➔ IndicTrans2 (Translate to English) 
   ➔ LLM Clinical Reasoning (SOCRATES / CCRAS-PAS) 
   ➔ IndicTrans2 (Translate back) 
   ➔ Bhashini / Indic TTS (Audio Out)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend Framework** | **FastAPI (Python)** | Native async, WebSocket streaming for audio, Python ML ecosystem integration |
| **Frontend UI** | **React + Vite + Vanilla CSS** | Responsive touch/voice Kiosk interface & high-density Doctor Dashboard |
| **Database & Vector Store** | **Supabase Postgres + pgvector** | Unified relational database, encrypted storage, and fast patient-scoped vector search |
| **ASR (Speech-to-Text)** | **IndicConformer / IndicWhisper** | State-of-the-art open-source ASR for Indian regional languages |
| **Translation & Speech Synth** | **IndicTrans2 & Bhashini TTS** | Government-aligned multilingual translation and speech synthesis |
| **OCR & Extraction** | **Cloud Vision / PaddleOCR + LLM** | Printed & handwritten document OCR + structured clinical JSON mapping |
| **Clinical Coding** | **NAMASTE & WHO ICD-11 (TM2)** | Official AYUSH morbidity coding & ABDM interoperability standards |

---

## 👥 Team & Task Split (5 ML + 1 Dev)

| Team Member | Primary Responsibility | Key Deliverables |
|---|---|---|
| **ML 1 + Dev** | ASR & Audio Streaming | Browser WebAudio → WebSocket → IndicConformer/Whisper streaming pipeline |
| **ML 2** | Translation & Voice Synth | IndicTrans2 bidirectional translation engine & Bhashini TTS integration |
| **ML 3** | Clinical Dialogue Manager | Adaptive SOCRATES engine, CCRAS-PAS AYUSH module, Red-flag alert rules |
| **ML 4** | Document OCR & Extraction | Prescription OCR pipeline, structured JSON parsing, abnormal lab flagging |
| **ML 5** | RAG & Clinical Summarizer | pgvector index & doctor Q&A engine, single-visit FHIR summary generator |
| **Full-Stack Dev** | Platform Infrastructure | FastAPI backend, React (Vite) Kiosk & Doctor UI, Supabase Auth/DB, ABDM wiring |

---

## 📅 6-Day Development Roadmap

See the detailed task breakdown and execution tracking in [ROADMAP.md](ROADMAP.md).

- 🟢 **Day 1:** Environment setup, API keys, repository structure & clinical ontology design.
- 🟡 **Day 2:** Isolated component prototyping (ASR, Translation, Dialogue LLM, OCR, pgvector).
- 🔵 **Day 3:** Deep integration, AYUSH dual-mode engine, React Kiosk & Dashboard UI skeletons.
- 🟣 **Day 4:** End-to-end pipeline wiring, ABDM sandbox integration, FHIR JSON export.
- 🟠 **Day 5:** System integration testing, doctor workspace refinement, NAMASTE coding validation.
- 🔴 **Day 6:** Live demo rehearsal, UI polish, backup demo video recording & final submission.

---

## 📄 License & Standards

Developed under **Smart India Hackathon (SIH 2026)** for Problem Statement 26047.  
Designed in accordance with **ABDM (Ayushman Bharat Digital Mission)** standards and **DPDP Act 2023** data privacy requirements.
