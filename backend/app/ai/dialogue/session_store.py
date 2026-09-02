"""
MediKiosk — In-Memory Session Store for Clinical Dialogue Sessions
Tracks active kiosk dialogue sessions, history, and accumulated SOCRATES state.
"""

import uuid
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from app.ai.dialogue.models import (
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState
)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class DialogueSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_context: PatientContext
    history: List[ConversationMessage] = Field(default_factory=list)
    socrates_state: SocratesState = Field(default_factory=SocratesState)
    last_result: Optional[DialogueTurnResult] = None
    turn_count: int = 0
    max_turns: int = 6
    is_completed: bool = False
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)

_SESSIONS: Dict[str, DialogueSession] = {}

def create_session(patient_context: PatientContext, max_turns: int = 6) -> DialogueSession:
    session = DialogueSession(
        patient_context=patient_context,
        max_turns=max_turns
    )
    _SESSIONS[session.session_id] = session
    return session

def get_session(session_id: str) -> Optional[DialogueSession]:
    return _SESSIONS.get(session_id)

def save_session(session: DialogueSession) -> None:
    session.updated_at = _utc_now_iso()
    _SESSIONS[session.session_id] = session

def delete_session(session_id: str) -> bool:
    if session_id in _SESSIONS:
        del _SESSIONS[session_id]
        return True
    return False

def clear_all_sessions() -> None:
    _SESSIONS.clear()
