# backend/app/api/v1/endpoints/kiosk.py
"""
MediKiosk — Kiosk Terminal & Active Session Controller
Enables database-backed patient state hydration without browser localStorage.
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any
import logging

from app.db.kiosk_db import (
    get_active_kiosk_session,
    create_or_resume_kiosk_session,
    close_kiosk_session
)

logger = logging.getLogger("medikiosk.kiosk.endpoint")

router = APIRouter(prefix="/kiosk", tags=["Kiosk Terminal Session"])

@router.get("/session", summary="Rehydrate active kiosk session & dialogue history on page load")
async def get_current_kiosk_session():
    """
    Returns the active patient profile, language, and complete dialogue history from SQLite/DB.
    Called by React frontend on initial mount and page refresh (F5) to eliminate localStorage.
    """
    session_data = get_active_kiosk_session()
    if not session_data:
        return {
            "authenticated": False,
            "session_id": None,
            "patient": None,
            "language": "hi",
            "messages": [],
            "socrates_state": {}
        }

    return {
        "authenticated": True,
        **session_data
    }

@router.post("/session/start", summary="Start or activate a kiosk session for an authenticated patient")
async def start_kiosk_session(payload: Dict[str, Any] = Body(...)):
    """
    Activates a new session on the kiosk terminal for the given patient profile.
    """
    patient = payload.get("patient") or payload
    language = payload.get("language", "hi")
    session_id = payload.get("session_id")

    session = create_or_resume_kiosk_session(
        patient_dict=patient,
        language=language,
        session_id=session_id
    )
    return {
        "success": True,
        "session": session
    }

@router.post("/session/logout", summary="Close active session and reset kiosk for next patient")
async def logout_kiosk_session(payload: Optional[Dict[str, Any]] = Body(default={})):
    """
    Marks the current active session completed so the terminal returns to the welcome/QR screen.
    """
    sid = payload.get("session_id") if payload else None
    close_kiosk_session(sid)
    return {
        "success": True,
        "message": "Kiosk terminal session closed."
    }
