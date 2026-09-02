import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from app.schemas.dialogue import (
    DialogueSessionState,
    HistoryType,
    InterviewPhase,
    UnifiedClinicalHistory,
    StandardHistory,
    AyurvedicAssessment
)

# In-memory fast session registry
_SESSIONS: Dict[str, DialogueSessionState] = {}

def create_session(
    patient_id: str,
    history_type: HistoryType,
    language: str = "en",
    extracted_document_context: Optional[dict] = None
) -> DialogueSessionState:
    """Create and register a new clinical intake session."""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    visit_id = f"vis_{uuid.uuid4().hex[:8]}"
    
    initial_history = UnifiedClinicalHistory(
        patient_id=patient_id,
        visit_id=visit_id,
        history_type=history_type,
        standard_history=StandardHistory(),
        ayurvedic_assessment=AyurvedicAssessment() if history_type == HistoryType.AYURVEDIC else None,
        red_flags=[]
    )
    
    session = DialogueSessionState(
        session_id=session_id,
        patient_id=patient_id,
        history_type=history_type,
        language=language,
        phase=InterviewPhase.CHIEF_COMPLAINT,
        turn_count=0,
        max_turns=8,
        turns=[],
        clinical_history=initial_history,
        extracted_document_context=extracted_document_context or {},
        active_red_flag=None,
        is_completed=False,
        ccras_battery_index=0,
        prakriti_raw_answers=[]
    )
    
    _SESSIONS[session_id] = session
    return session

def get_session(session_id: str) -> Optional[DialogueSessionState]:
    """Retrieve an existing session by ID."""
    return _SESSIONS.get(session_id)

def save_session(session: DialogueSessionState) -> None:
    """Persist session updates in memory."""
    session.updated_at = datetime.now(timezone.utc).isoformat()
    _SESSIONS[session.session_id] = session

def delete_session(session_id: str) -> bool:
    """Remove a session from registry."""
    if session_id in _SESSIONS:
        del _SESSIONS[session_id]
        return True
    return False

def list_active_sessions() -> Dict[str, DialogueSessionState]:
    """Return all active sessions."""
    return _SESSIONS
