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

## 🏗️ Architecture & Backend Structure

```
backend/
├── .env
├── .env.example
├── requirements.txt
└── app/
    ├── main.py                   # FastAPI initialization, middlewares, /healthz
    ├── config.py                 # Pydantic BaseSettings & Environment config
    ├── db.py                     # Supabase DB client connection setup
    ├── core/
    │   ├── security.py           # JWT auth tokens, password hashing & RBAC
    │   └── middleware.py         # CORS, Request logging, Security headers, Exceptions
    ├── api/
    │   ├── deps.py               # FastAPI dependency injection (Current User, DB)
    │   └── v1/
    │       ├── router.py         # Master API v1 router
    │       └── endpoints/
    │           ├── auth.py       # /api/v1/auth (Login, Register, Profiles)
    │           ├── interview.py  # /api/v1/interview (Voice/Text Intake, SOCRATES, AYUSH PAS)
    │           ├── ocr.py        # /api/v1/ocr (Document upload & OCR extraction)
    │           ├── summary.py    # /api/v1/summary (FHIR Clinical Summary & Doctor RAG)
    │           └── abdm.py       # /api/v1/abdm (ABHA Sandbox Auth & Linkage)
    ├── schemas/                  # Pydantic data validation schemas
    └── ai/                       # Isolated AI package subdirectories
        ├── asr/                  # 🎧 Member 1: Audio-to-Text & Speech Synthesis
        ├── translation/          # 🌐 Member 2: Text-to-Text Translation
        ├── dialogue/             # 🧠 Member 3: Prompt Engineering & SOCRATES Engine
        ├── ocr/                  # 📄 Member 4: Document OCR & Extraction
        └── rag/                  # 🔍 Member 5: pgvector Vector Store & Clinical RAG
```

---

## 🔌 API Routes Overview

| Route Module | Prefix | Description |
|---|---|---|
| **Health Check** | `/healthz` | System health check (DB connection, AI model service connectivity) |
| **Authentication** | `/api/v1/auth` | User login, doctor/staff registration, JWT token generation |
| **Clinical Interview** | `/api/v1/interview` | Adaptive voice/text intake sessions, SOCRATES branching & CCRAS PAS |
| **Document OCR** | `/api/v1/ocr` | Upload prescriptions/lab reports, run OCR & extract structured JSON |
| **Clinical Summary & RAG** | `/api/v1/summary` | Generate 30-second FHIR summaries & doctor Q&A assistant |
| **ABDM Integration** | `/api/v1/abdm` | ABHA OTP verification, patient health ID link & consent records |

---

## 🚀 Quickstart & Developer Setup Guide

### 📋 Prerequisites
- **Git**
- **Python 3.10+**

---

### ⚡ Option A: 1-Command Automated Setup (Recommended Fast-Track)

Run the automated setup script from the root directory:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

**Mac / Linux (Terminal):**
```bash
chmod +x ./scripts/setup.sh && ./scripts/setup.sh
```

*This automatically creates `backend/venv`, installs dependencies, and creates `backend/.env` from `.env.example`.*

#### Launch Development Server:
- **Windows:** `powershell .\scripts\run_backend.ps1`
- **Mac / Linux:** `./scripts/run_backend.sh`

---

### 🛠️ Option B: Manual Setup

#### Step 1: Clone the Repository
```bash
git clone https://github.com/rohit-h11/medikiosk-sih-26047.git
cd medikiosk-sih-26047
```

#### Step 2: Backend Virtual Environment Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment:
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Mac / Linux:
source venv/bin/activate

# Install all backend dependencies
pip install -r requirements.txt
```

#### Step 3: Configure Environment Variables
Copy `.env.example` to create your local `.env` file:
```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```
*Fill in your Supabase credentials, JWT secret, and API keys in `.env`.*

#### Step 4: Run the Backend Development Server
From inside the `backend/` directory:
```bash
uvicorn app.main:app --reload
```

---

### 🌐 Access Interactive API Documentation
Open your browser and navigate to:
- 📖 **Swagger UI Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 📑 **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- 🩺 **Health Check:** [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)

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

## 📄 License & Standards

Developed under **Smart India Hackathon (SIH 2026)** for Problem Statement 26047.  
Designed in accordance with **ABDM (Ayushman Bharat Digital Mission)** standards and **DPDP Act 2023** data privacy requirements.
