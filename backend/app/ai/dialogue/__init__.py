"""
MediKiosk — AI Clinical Dialogue Package
SOCRATES Adaptive Clinical Intake Module
"""

from app.ai.dialogue.models import (
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState,
    TouchOption,
    RedFlagAlert
)
from app.ai.dialogue.dialogue_manager import (
    get_next_dialogue_turn,
    start_dialogue
)
from app.ai.dialogue.llm_client import (
    scan_text_for_red_flags
)
from app.ai.dialogue.session_store import (
    DialogueSession,
    create_session,
    get_session,
    save_session,
    delete_session,
    clear_all_sessions
)
from app.ai.dialogue.db_logger import (
    store_full_dialogue_session_async,
    get_session_transcript_async
)

__all__ = [
    "get_next_dialogue_turn",
    "start_dialogue",
    "PatientContext",
    "ConversationMessage",
    "DialogueTurnResult",
    "SocratesState",
    "TouchOption",
    "RedFlagAlert",
    "scan_text_for_red_flags",
    "DialogueSession",
    "create_session",
    "get_session",
    "save_session",
    "delete_session",
    "clear_all_sessions",
    "store_full_dialogue_session_async",
    "get_session_transcript_async"
]
