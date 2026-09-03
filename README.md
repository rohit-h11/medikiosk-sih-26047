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
- **Node.js 18+ (LTS)** & **npm** (for Frontend)

---

### ⚡ Option A: 1-Command Automated Setup (Recommended Fast-Track)

Run the automated setup script from the root directory:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

**Mac / Linux / Git Bash (Terminal):**
```bash
chmod +x ./scripts/setup.sh && ./scripts/setup.sh
```

*This automatically creates `backend/venv`, installs dependencies, and creates `backend/.env` from `.env.example`.*

> 💡 **Troubleshooting / Rebuilding Environment:**
> If your virtual environment becomes corrupted or missing `python.exe`, force a fresh rebuild using:
> - Windows: `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Clean`
> - Mac / Linux: `./scripts/setup.sh --clean`

---

## 📦 Managing Python Packages in `venv`

When adding new libraries or dependencies to the backend, follow these steps so the entire team stays in sync:

### 1. Activating the Virtual Environment
Always activate your virtual environment before installing packages:
* **Windows (PowerShell):**
  ```powershell
  cd backend
  .\venv\Scripts\Activate.ps1
  ```
* **Windows (CMD):**
  ```cmd
  cd backend
  .\venv\Scripts\activate.bat
  ```
* **Mac / Linux / Git Bash:**
  ```bash
  cd backend
  source venv/bin/activate
  ```

### 2. Installing a New Package & Updating `requirements.txt`
After installing a new package into your venv:
```bash
# Example: installing a new package
pip install package-name

# Freeze and update requirements.txt
pip freeze > requirements.txt
```
*(Or manually add `package-name>=version` into `backend/requirements.txt` to keep the file clean).*

### 3. Syncing `venv` when Teammates Add New Packages
Whenever you pull new changes from git that update `requirements.txt`:
```bash
cd backend
pip install -r requirements.txt
```

---

## 💻 Frontend Setup Guide (React)

The MediKiosk frontend is structured as a modular React application designed for high-contrast kiosk touchscreens and doctor dashboards.

### 1. Setup & Install Dependencies
Navigate into the `frontend` folder from the root directory:
```bash
cd frontend
npm install
```

### 2. Configure Environment Variables
Create a `.env` file in the `frontend/` directory (or copy from `.env.example`):
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Start Frontend Development Server
```bash
npm run dev
```
Once started, the React app will be live at `http://localhost:5173` (or the port displayed in your terminal).

### 4. Build for Production
```bash
npm run build
```

---

## 🏃 How to Start Frontend & Backend for Live Testing

### ⚡ Option A: Start Both with a Single Command (Recommended)
From the root project directory, run:
```bash
npm run dev
```
*(Or on Windows PowerShell: `.\scripts\dev.ps1` or double-click `dev.bat`)*

This concurrently starts:
* **FastAPI Backend (Port 8000):** [http://localhost:8000/docs](http://localhost:8000/docs) (Cyan logs)
* **React Frontend (Port 5173 / 3000):** [http://localhost:5173](http://localhost:5173) (Magenta logs)
* Press `Ctrl + C` once to stop both servers simultaneously.

---

### 🖥️ Option B: Start in Separate Terminals
If you prefer dedicated terminal windows:

#### 1️⃣ Terminal 1: Backend
```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Unified Interview Route:** `POST /api/v1/interview/turn`

#### 2️⃣ Terminal 2: Frontend
```powershell
cd frontend
npm install
npm run dev
```
- **Frontend Kiosk UI:** [http://localhost:5173](http://localhost:5173)

---

### 🧪 Live Testing Walkthrough:
1. Open [http://localhost:3000](http://localhost:3000) in Chrome/Edge.
2. Choose your language from the top-right dropdown (**Hindi, Tamil, Telugu, Marathi, Bengali, or English**).
3. **Press & hold the large microphone button (or Spacebar)** and describe your symptoms:
   * *Example:* *"मुझे 2 दिन से पेट में बहुत तेज जलन और दर्द है"*
4. **Release the button**:
   * Client-side Web Audio DSP removes fan noise & AC rumble.
   * **Sarvam AI (Saaras ASR)** transcribes it into English.
   * **Supabase pgvector** retrieves prior medical records for that patient.
   * **Groq Llama-3.3-70b (SOCRATES Engine)** evaluates the clinical turn.
   * **Sarvam Bulbul:v3 TTS** synthesizes and **speaks the next question back to you out loud**!
   * 4 dynamic touch options appear on screen for one-tap answering.
5. Tap an option or speak again to continue the intake until the final clinical summary is generated!

---

## 👥 Team & Task Split (5 ML + 1 Dev)

| Team Member | Primary Responsibility | Key Deliverables |
|---|---|---|
| **ML 1 + Dev** | ASR & Audio Processing | Browser WebAudio (Push-to-Talk) → HTTP POST → IndicConformer/Whisper ASR pipeline |
| **ML 2** | Translation & Voice Synth | IndicTrans2 bidirectional translation engine & Bhashini TTS integration |
| **ML 3** | Clinical Dialogue Manager | Adaptive SOCRATES engine, CCRAS-PAS AYUSH module, Red-flag alert rules |
| **ML 4** | Document OCR & Extraction | Prescription OCR pipeline, structured JSON parsing, abnormal lab flagging |
| **ML 5** | RAG & Clinical Summarizer | pgvector index & doctor Q&A engine, single-visit FHIR summary generator |
| **Full-Stack Dev** | Platform Infrastructure | FastAPI backend, React (Vite) Kiosk & Doctor UI, Supabase Auth/DB, ABDM wiring |

---

## 📄 License & Standards

Developed under **Smart India Hackathon (SIH 2026)** for Problem Statement 26047.  
Designed in accordance with **ABDM (Ayushman Bharat Digital Mission)** standards and **DPDP Act 2023** data privacy requirements.
