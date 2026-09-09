"""
Mobile Upload Session API
--------------------------
Provides 3 endpoints for the QR-based mobile upload flow:
  POST /mobile-upload/session        → create a session, get session_id back
  GET  /mobile-upload/session/{id}   → poll for result (kiosk polls this)
  POST /mobile-upload/session/{id}/file → receive file from patient's phone, run OCR
"""

import uuid
import time
import asyncio
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

import socket

# ---------------------------------------------------------------------------
# In-memory session store (demo-grade; swap for Redis/Supabase in production)
# Session TTL: 15 minutes
# ---------------------------------------------------------------------------
_SESSION_TTL_SECONDS = 15 * 60
_sessions: dict[str, dict] = {}

router = APIRouter(prefix="/mobile-upload", tags=["mobile-upload"])

@router.get("/ip")
async def get_local_ip():
    """Returns the local network IP address dynamically."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
        s.close()
        return {"ip": IP}
    except Exception:
        return {"ip": "localhost"}

def _cleanup_expired():
    """Remove sessions older than TTL."""
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > _SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


# ---------------------------------------------------------------------------
# 1. Create Session
# ---------------------------------------------------------------------------
@router.post("/session")
async def create_session(patient_id: Optional[str] = Form(None)):
    """
    Kiosk calls this to get a fresh session_id.
    Returns {session_id, expires_in_seconds}.
    """
    _cleanup_expired()
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "created_at": time.time(),
        "status": "pending",   # pending | processing | complete | error
        "patient_id": patient_id,
        "result": None,
        "error": None,
    }
    return {"session_id": session_id, "expires_in_seconds": _SESSION_TTL_SECONDS}


# ---------------------------------------------------------------------------
# 2. Poll Session (kiosk polls this every 2s)
# ---------------------------------------------------------------------------
@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    Returns the current session status + result when available.
    Status flow:  pending → processing → complete | error
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {
        "session_id": session_id,
        "status": session["status"],
        "result": session["result"],
        "error": session["error"],
    }


# ---------------------------------------------------------------------------
# 3. Upload File from Patient's Phone
# ---------------------------------------------------------------------------
@router.post("/session/{session_id}/file")
async def upload_file_for_session(
    session_id: str,
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
):
    """
    Mobile page calls this with the selected/photographed document.
    Runs the same OCR pipeline as the kiosk camera capture, then stores result.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session["status"] not in ("pending",):
        raise HTTPException(status_code=409, detail=f"Session is already {session['status']}")

    # Mark as processing immediately so mobile shows spinner
    session["status"] = "processing"

    try:
        # Read uploaded bytes
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Empty file received")

        # Reuse the existing OCR pipeline
        from app.ai.ocr.ocr import process_document_image
        from app.ai.ocr.extractor import DocumentExtractor

        # Run OCR → structured data
        ocr_result = await asyncio.get_event_loop().run_in_executor(
            None,
            process_document_image,
            image_bytes,
            file.filename or "mobile_upload.jpg",
        )

        # Store to vector DB if patient_id available
        pid = patient_id or session.get("patient_id")
        if pid and ocr_result:
            extractor = DocumentExtractor()
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    extractor.store_document,
                    ocr_result,
                    pid,
                )
            except Exception as store_err:
                # Non-fatal: log but don't fail the session
                print(f"[mobile_upload] Vector store warning: {store_err}")

        session["status"] = "complete"
        session["result"] = ocr_result
        return {"status": "complete", "message": "Document processed successfully"}

    except Exception as exc:
        session["status"] = "error"
        session["error"] = str(exc)
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {exc}")
