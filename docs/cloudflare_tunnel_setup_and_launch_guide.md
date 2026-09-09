# MediKiosk — Cloudflare Tunnel Exposing & Server Launch Guide

> **Target Audience:** Hackathon Judges, Deployment Engineers, and Developers  
> **Purpose:** Exposing both MediKiosk Frontend (React/Vite) and Backend (FastAPI) securely over public HTTPS using **Cloudflare Tunnel (`cloudflared`)** for remote access, mobile camera QR uploads, and live demonstrations.

---

## 1. Why MediKiosk Needs Cloudflare Tunnel

1. **Smartphone Camera & Mobile Upload**:
   - Patients scan a QR code on the kiosk screen to upload prescriptions from their smartphones.
   - Mobile browsers (iOS Safari, Android Chrome) strictly block camera access (`getUserMedia`) on unencrypted HTTP.
   - Cloudflare Tunnel provides an instant, trusted **`https://*.trycloudflare.com`** certificate for zero-hassle phone camera uploads.
2. **Zero Port Forwarding & Firewall Traversal**:
   - Operates seamlessly through strict hospital Wi-Fi networks, 4G/5G mobile hotspots, and CGNAT without configuring router ports.
3. **Unified Single-Port Ingress**:
   - Because Vite's dev server (`vite.config.ts`) automatically proxies `/api` requests to the FastAPI backend on port `8000`, **exposing just the Vite frontend port (`3000`) exposes both Frontend and Backend together** with zero CORS errors.

---

## 2. Zero-Installation Setup (Already Included!)

> [!TIP]
> **Good news!** `cloudflared.exe` is **already included** directly in your project root directory (`f:\Coding\projects\midiosk SIH hackathon\cloudflared.exe`). You do **not** need to install anything or configure system PATHs!

### Quick Verification:
From the project root directory, run:
```powershell
.\cloudflared.exe --version
```
*(Output: `cloudflared version 2026.8.3 ...`)*

*(Optional: If you ever want to install it system-wide in Windows PATH, you can run `winget install Cloudflare.cloudflared`)*

---

## 3. Step-by-Step Manual Startup Sequence

### Step 1: Start the Backend (FastAPI Uvicorn)
Open **Terminal 1**:
```powershell
cd "f:\Coding\projects\midiosk SIH hackathon\backend"
.\venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
*Verify: Visit `http://localhost:8000/docs` in your browser. You should see the interactive Swagger API documentation.*

---

### Step 2: Start the Frontend (Vite React App)
Open **Terminal 2**:
```powershell
cd "f:\Coding\projects\midiosk SIH hackathon\frontend"
npm run dev
```
*Verify: Vite should output `Local: http://localhost:3000/`.*

---

### Step 3: Launch the Cloudflare Tunnel
Open **Terminal 3**:
```powershell
cloudflared tunnel --url http://localhost:3000
```

Cloudflare will initialize and print an output similar to:
```text
2026-09-08T11:55:00Z INF +--------------------------------------------------------------------------------------------+
2026-09-08T11:55:00Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-09-08T11:55:00Z INF |  https://clinical-kiosk-sample-domain.trycloudflare.com                                    |
2026-09-08T11:55:00Z INF +--------------------------------------------------------------------------------------------+
```

Copy the **`https://<random-name>.trycloudflare.com`** URL!

---

### Step 4: Connecting the Mobile Upload QR Code

MediKiosk has **auto-detection built-in**:
* If you open the kiosk on your laptop using the Cloudflare URL (e.g. `https://clinical-kiosk-sample-domain.trycloudflare.com`), the screen **automatically** generates QR codes pointing to that public tunnel!
* If you run the kiosk locally on `http://localhost:3000` but want the QR code to point to your Cloudflare tunnel, update [frontend/.env](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/.env):
  ```bash
  VITE_NGROK_URL=https://clinical-kiosk-sample-domain.trycloudflare.com
  ```

---

## 4. One-Click Automated Startup (Windows Scripts)

To start everything simultaneously in one command, double-click **`start_all_with_tunnel.bat`** in the project root, or run it in PowerShell:

```powershell
.\start_all_with_tunnel.bat
```

This launches three separate terminal windows:
1. **Window 1 (MediKiosk Backend)**: Uvicorn FastAPI on `http://127.0.0.1:8000`
2. **Window 2 (MediKiosk Frontend)**: Vite Dev Server on `http://localhost:3000`
3. **Window 3 (Cloudflare Tunnel)**: Exposes `http://localhost:3000` to the public web and displays your live HTTPS link.

---

## 5. Advanced: Named Persistent Tunnel (Custom Domain)

If you own a domain on Cloudflare (e.g. `medikiosk.in`), you can create a permanent URL that never changes on restart:

### 1. Authenticate with Cloudflare:
```powershell
cloudflared tunnel login
```

### 2. Create the Named Tunnel:
```powershell
cloudflared tunnel create medikiosk-tunnel
```
*(This creates a credentials file in `~/.cloudflared/<tunnel-id>.json`)*

### 3. Create Configuration File (`config.yml`):
Create `~/.cloudflared/config.yml`:
```yaml
tunnel: medikiosk-tunnel
credentials-file: C:\Users\<Username>\.cloudflared\<tunnel-id>.json

ingress:
  # Route 1: Kiosk UI & Proxied API
  - hostname: kiosk.medikiosk.in
    service: http://localhost:3000
  # Route 2: Standalone Direct Backend Access (Optional)
  - hostname: api.medikiosk.in
    service: http://localhost:8000
  # Catch-all rule (Required)
  - service: http_status:404
```

### 4. Route DNS Traffic:
```powershell
cloudflared tunnel route dns medikiosk-tunnel kiosk.medikiosk.in
cloudflared tunnel route dns medikiosk-tunnel api.medikiosk.in
```

### 5. Run Persistent Tunnel:
```powershell
cloudflared tunnel run medikiosk-tunnel
```

---

## 6. Verification Checklist

| Test Item | Expected Result | Verified Status |
| :--- | :--- | :---: |
| **Frontend Public Load** | `https://*.trycloudflare.com` loads the Welcome / QR login screen | ✅ |
| **API Proxy** | `https://*.trycloudflare.com/api/v1/dialogue/stream-turn` reaches FastAPI | ✅ |
| **Real-time SSE Streaming** | Consultation screen streams text and Sarvam voice audio over HTTPS | ✅ |
| **Mobile Upload QR** | Scanning QR code on phone camera opens `/mobile-upload?session=...` | ✅ |
| **Prescription Photo Upload** | Smartphone captures photo, uploads WebP, and triggers Gemini Vision OCR | ✅ |

---

## 7. Troubleshooting & FAQs

### Q1: `cloudflared : The term 'cloudflared' is not recognized`
**Fix**: Install it using `winget install Cloudflare.cloudflared` and restart your terminal. Alternatively, place `cloudflared.exe` directly in the project root folder.

### Q2: Phone camera shows a black screen or permission error
**Fix**: Mobile browsers require HTTPS. Ensure you are accessing the page via `https://*.trycloudflare.com` rather than an unencrypted `http://` IP address.

### Q3: The Vite frontend is running on port 3001 instead of 3000
**Fix**: If port 3000 was in use by another app, Vite picks 3001. Simply run:
```powershell
cloudflared tunnel --url http://localhost:3001
```

### Q4: Are Server-Sent Events (SSE) buffered by Cloudflare?
**Fix**: No. Cloudflare supports real-time HTTP streaming and WebSockets out of the box. MediKiosk sets `text/event-stream` headers with chunked transfer encoding, ensuring sub-second voice and text token delivery to the frontend.
