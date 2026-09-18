# backend/app/ai/dialogue/session_store.py
"""
MediKiosk — Multi-Paradigm Session Store
Tracks active kiosk dialogue sessions, phase transitions (Prakriti -> Dashavidha -> Dynamic),
history, and accumulated clinical states.
"""

import uuid
from typing import Dict, Optional, List, Any
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
    phase: str = Field(default="AUTO", description="'PRAKRITI' | 'DASHAVIDHA' | 'DYNAMIC_VIKRITI' | 'DYNAMIC_SOCRATES' | 'COMPLETED'")
    prakriti_answers: List[str] = Field(default_factory=list)
    dashavidha_answers: List[str] = Field(default_factory=list)
    prakriti_result: Optional[Dict[str, Any]] = None
    dashavidha_state: Optional[Dict[str, Any]] = None
    clinical_state: Dict[str, Any] = Field(default_factory=dict)
    socrates_state: SocratesState = Field(default_factory=SocratesState)
    last_result: Optional[DialogueTurnResult] = None
    turn_count: int = 0
    max_turns: int = 10
    is_completed: bool = False
    accumulated_rag_snippets: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)

_SESSIONS: Dict[str, DialogueSession] = {}

def create_session(patient_context: PatientContext, max_turns: int = 10, session_id: Optional[str] = None) -> DialogueSession:
    sid = session_id or str(uuid.uuid4())
    session = DialogueSession(
        session_id=sid,
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
