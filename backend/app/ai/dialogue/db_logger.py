# backend/app/ai/dialogue/db_logger.py
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.db import get_supabase_client

logger = logging.getLogger("medikiosk.dialogue.db_logger")

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _store_full_dialogue_session_sync(
    patient_id: str,
    session_id: str,
    history: List[Dict[str, Any]],
    language: str = "hi",
    chief_complaint: Optional[str] = None,
    socrates_state: Optional[Dict[str, Any]] = None,
    red_flag_alert: Optional[Dict[str, Any]] = None,
    last_question: Optional[str] = None,
    closing_message_english: Optional[str] = None,
    closing_message_native: Optional[str] = None,
    patient_name: Optional[str] = None,
) -> bool:
    """
    Synchronous implementation executed in a background worker thread via asyncio.to_thread.
    Executes in a single efficient sequence at the end of the conversation:
    1. Ensures patient profile exists in 'patients' (upsert).
    2. Upserts dialogue session record in 'dialogue_sessions' as is_completed=True.
    3. Batch-inserts all conversation turns into 'dialogue_messages'.
    """
    try:
        supabase = get_supabase_client()
    except Exception as e:
        logger.warning(f"Supabase client unavailable: {e}. Skipping dialogue session persistence.")
        return False

    try:
        # Step 1: Ensure patient profile exists to satisfy foreign key constraint
        patient_row = {
            "id": patient_id,
            "name": patient_name or f"Patient {patient_id}",
            "gender": "unknown",
            "updated_at": _utc_now_iso()
        }
        try:
            supabase.table("patients").upsert(patient_row, on_conflict="id").execute()
        except Exception as e:
            logger.warning(f"Patient upsert non-critical warning: {e}")

        # Step 2: Upsert Dialogue Session Record
        session_row = {
            "id": session_id,
            "patient_id": patient_id,
            "language": language,
            "turn_count": len(history),
            "max_turns": 10,
            "is_completed": True,
            "chief_complaint": chief_complaint,
            "socrates_state": socrates_state or {},
            "red_flag_alert": red_flag_alert,
            "last_question": last_question,
            "updated_at": _utc_now_iso()
        }
        supabase.table("dialogue_sessions").upsert(session_row, on_conflict="id").execute()

        # Step 3: Batch prepare and insert all conversation messages
        message_rows = []
        turn_number = 1

        for msg in history:
            role = msg.get("role", "patient")
            content_native = msg.get("content_native") or msg.get("content") or msg.get("utterance", "")
            content_english = msg.get("content_english") or msg.get("content") or msg.get("utterance", "")
            slot_tag = msg.get("slot_tag")

            message_rows.append({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "turn_number": turn_number,
                "role": role,
                "content_native": str(content_native),
                "content_english": str(content_english),
                "slot_tag": slot_tag,
                "created_at": _utc_now_iso()
            })
            turn_number += 1

        # If there is a closing message at the end of the interview, record it as final assistant turn
        if closing_message_english or closing_message_native:
            message_rows.append({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "turn_number": turn_number,
                "role": "assistant",
                "content_native": closing_message_native or closing_message_english or "",
                "content_english": closing_message_english or closing_message_native or "",
                "slot_tag": "closing",
                "created_at": _utc_now_iso()
            })

        if message_rows:
            supabase.table("dialogue_messages").insert(message_rows).execute()
            logger.info(
                f"Successfully batch-stored {len(message_rows)} dialogue messages for session {session_id} (Patient: {patient_id})"
            )

        return True

    except Exception as e:
        logger.error(f"Failed to store dialogue session in Supabase: {e}", exc_info=True)
        return False

async def store_full_dialogue_session_async(
    patient_id: str,
    session_id: str,
    history: List[Dict[str, Any]],
    language: str = "hi",
    chief_complaint: Optional[str] = None,
    socrates_state: Optional[Dict[str, Any]] = None,
    red_flag_alert: Optional[Dict[str, Any]] = None,
    last_question: Optional[str] = None,
    closing_message_english: Optional[str] = None,
    closing_message_native: Optional[str] = None,
    patient_name: Optional[str] = None,
) -> bool:
    """Non-blocking asynchronous wrapper for end-of-conversation batch storage."""
    return await asyncio.to_thread(
        _store_full_dialogue_session_sync,
        patient_id=patient_id,
        session_id=session_id,
        history=history,
        language=language,
        chief_complaint=chief_complaint,
        socrates_state=socrates_state,
        red_flag_alert=red_flag_alert,
        last_question=last_question,
        closing_message_english=closing_message_english,
        closing_message_native=closing_message_native,
        patient_name=patient_name
    )

async def get_session_transcript_async(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves full verbatim conversation turns for a given dialogue session."""
    def _fetch():
        try:
            supabase = get_supabase_client()
            res = supabase.table("dialogue_messages")\
                .select("*")\
                .eq("session_id", session_id)\
                .order("turn_number", desc=False)\
                .execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Failed to fetch dialogue transcript for session {session_id}: {e}")
            return []

    return await asyncio.to_thread(_fetch)
