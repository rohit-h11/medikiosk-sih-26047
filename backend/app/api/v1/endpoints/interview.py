# backend/app/api/v1/endpoints/interview.py
"""
MediKiosk — Unified Multi-Paradigm Clinical Interview & SSE Streaming Engine
Handles the complete patient journey across Allopathy (SOCRATES) and Ayurveda
(Prakriti -> Dashavidha -> Vikriti) with voice/touch multimodality, DB caching,
Tri-Source RAG retrieval, and Server-Sent Events (SSE) streaming.
"""

import json
import logging
import uuid
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.ai.asr.sarvam_asr_client import SarvamASRClient
from app.ai.asr.sarvam_tts_client import sarvam_tts_service
from app.ai.rag.retriever import retrieve_patient_history_async, store_dialogue_summary_in_rag_async
from app.ai.dialogue import (
    get_next_dialogue_turn,
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState,
    TouchOption,
    RedFlagAlert,
    scan_text_for_red_flags,
    store_full_dialogue_session_async,
    create_session,
    get_session,
    save_session,
    DialogueSession
)
from app.ai.ayurveda import (
    get_prakriti_question,
    get_dashavidha_question,
    score_prakriti,
    score_dashavidha,
    PrakritiResult,
    DashavidhaState
)
from app.ai.dialogue.streaming_orchestrator import (
    format_sse_event,
    stream_static_turn_sse,
    stream_dynamic_turn_sse
)
from app.db import get_supabase_client

logger = logging.getLogger("medikiosk.interview.endpoint")

router = APIRouter(prefix="/interview", tags=["Unified Multi-Paradigm Interview & SSE Stream"])

sarvam_asr = SarvamASRClient()

class UtterancePair(BaseModel):
    native: str
    english: str

class TouchOptionResponse(BaseModel):
    id: str
    label: str
    label_native: Optional[str] = None
    value: str
    slot_tag: Optional[str] = None

class AudioResponse(BaseModel):
    audio_base64: Optional[str] = None
    audio_format: str = "wav"
    sample_rate: int = 16000
    language: str = "hi"

class InterviewTurnResponse(BaseModel):
    session_id: str
    turn_number: int
    phase: str = Field(default="DYNAMIC", description="'PRAKRITI' | 'DASHAVIDHA' | 'DYNAMIC_VIKRITI' | 'DYNAMIC_SOCRATES'")
    patient_utterance: UtterancePair
    next_question: Optional[UtterancePair] = None
    audio_response: Optional[AudioResponse] = None
    touch_options: List[TouchOptionResponse] = Field(default_factory=list)
    clinical_state: Dict[str, Any] = Field(default_factory=dict)
    socrates_state: Dict[str, Any] = Field(default_factory=dict)
    covered_slots: List[str] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    is_completed: bool = False
    clinical_summary: Optional[str] = None
    closing_message: Optional[UtterancePair] = None
    red_flag_alert: Optional[RedFlagAlert] = None
    prakriti_result: Optional[Dict[str, Any]] = None
    rag_context_used: List[str] = Field(default_factory=list)

# ------------------------------------------------------------------------------
# DB Helpers for Prakriti Permanence
# ------------------------------------------------------------------------------
async def _get_stored_prakriti_from_db(patient_id: str) -> Optional[str]:
    """Checks if patient has an existing Prakriti record in Supabase."""
    if not patient_id or patient_id == "PAT-DEMO-01":
        return None
    try:
        supabase = get_supabase_client()
        res = supabase.table("patients").select("prakriti").eq("id", patient_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("prakriti")
    except Exception as e:
        logger.warning(f"Could not fetch patient prakriti from db: {e}")
    return None

async def _save_prakriti_to_db(patient_id: str, prakriti_type: str) -> None:
    """Permanently stores calculated Prakriti against patient record."""
    if not patient_id:
        return
    try:
        supabase = get_supabase_client()
        supabase.table("patients").update({"prakriti": prakriti_type}).eq("id", patient_id).execute()
        logger.info(f"Permanently saved Prakriti '{prakriti_type}' to patient {patient_id}.")
    except Exception as e:
        logger.warning(f"Could not save patient prakriti to db: {e}")

# ------------------------------------------------------------------------------
# Core Turn Processing Engine (Shared by /turn and /stream)
# ------------------------------------------------------------------------------
async def _execute_turn_logic(
    audio_file: Optional[UploadFile],
    text_response: Optional[str],
    selected_option_id: Optional[str],
    session_id: Optional[str],
    patient_id: str,
    hospital_type: str,
    language: str,
    conversation_history_raw: Optional[str],
    max_turns: int,
    chief_complaint_hint: Optional[str]
) -> Dict[str, Any]:
    """Unified turn controller handling ASR, session state transitions, RAG, and LLM reasoning."""
    active_session_id = session_id or f"sess_{uuid.uuid4().hex[:10]}"
    norm_hosp = (hospital_type or "allopathy").lower().strip()
    
    # 1. Retrieve or initialize session state
    session = get_session(active_session_id)
    if not session:
        stored_prakriti = await _get_stored_prakriti_from_db(patient_id)
        ctx = PatientContext(
            patient_id=patient_id,
            hospital_type=norm_hosp,
            prakriti_profile=stored_prakriti,
            chief_complaint=chief_complaint_hint,
            language=language
        )
        session = create_session(patient_context=ctx, max_turns=max_turns, session_id=active_session_id)
        
        # Determine initial phase
        if norm_hosp in ["ayurveda", "ayush"]:
            if stored_prakriti:
                session.phase = "DYNAMIC_VIKRITI"
            else:
                session.phase = "PRAKRITI"
        else:
            session.phase = "DYNAMIC_SOCRATES"
        save_session(session)

    # 2. Parse Patient Input (Speech or Text / Touch Choice)
    patient_native = ""
    patient_english = ""

    if audio_file is not None and audio_file.filename:
        audio_bytes = await audio_file.read()
        if len(audio_bytes) > 0:
            try:
                asr_result = await sarvam_asr.transcribe_async(
                    audio_bytes=audio_bytes,
                    filename=audio_file.filename or "patient_audio.wav",
                    language=language,
                    translate_english=True
                )
                patient_native = asr_result.get("transcript", "").strip()
                patient_english = asr_result.get("english_transcript", patient_native).strip()
            except Exception as e:
                logger.error(f"ASR transcription failed: {e}")
                patient_native = text_response or selected_option_id or "Audio received"
                patient_english = patient_native

    if not patient_native and text_response:
        patient_native = text_response.strip()
        if language != "en":
            try:
                patient_english = await sarvam_tts_service.translate_text_async(
                    patient_native, source_lang=language, target_lang="en"
                )
            except Exception:
                patient_english = patient_native
        else:
            patient_english = patient_native

    if not patient_native and selected_option_id:
        patient_native = selected_option_id
        patient_english = selected_option_id

    if not patient_native and not session.history:
        patient_native = "नमस्ते" if language == "hi" else "Hello"
        patient_english = "Hello"

    # 3. Handle Static Ayurveda Phases (Turns 1-15)
    # --------------------------------------------------------------------------
    is_greeting = patient_english.lower() in ["hello", "hi", "namaste", "नमस्ते", "start", "begin"] and not selected_option_id

    if session.phase == "PRAKRITI":
        # Record answer only if this is a response to an active question
        if (selected_option_id or patient_english) and not is_greeting:
            raw_val = selected_option_id or patient_english
            session.prakriti_answers.append(raw_val)

        q_idx = len(session.prakriti_answers)
        if q_idx < 12:
            # Serve next Prakriti MCQ
            q_payload = get_prakriti_question(q_idx, lang=language)
            session.turn_count = q_idx + 1
            save_session(session)
            return {
                "session_id": active_session_id,
                "phase": "PRAKRITI",
                "turn_number": q_idx + 1,
                "patient_utterance": {"native": patient_native, "english": patient_english},
                "static_question": q_payload,
                "is_completed": False
            }
        else:
            # 12 questions complete! Calculate score and advance to Dashavidha
            prakriti_res = score_prakriti(session.prakriti_answers)
            session.prakriti_result = prakriti_res.model_dump()
            session.patient_context.prakriti_profile = prakriti_res.prakriti_type
            session.phase = "DASHAVIDHA"
            save_session(session)
            
            # Persist to database in background
            asyncio.create_task(_save_prakriti_to_db(patient_id, prakriti_res.prakriti_type))
            
            # Serve Dashavidha Q1
            q_payload = get_dashavidha_question(0, lang=language)
            return {
                "session_id": active_session_id,
                "phase": "DASHAVIDHA",
                "turn_number": 13,
                "patient_utterance": {"native": patient_native, "english": patient_english},
                "static_question": q_payload,
                "prakriti_result": session.prakriti_result,
                "is_completed": False
            }

    if session.phase == "DASHAVIDHA":
        if (selected_option_id or patient_english) and not is_greeting:
            raw_val = selected_option_id or patient_english
            session.dashavidha_answers.append(raw_val)

        d_idx = len(session.dashavidha_answers)
        if d_idx < 3:
            q_payload = get_dashavidha_question(d_idx, lang=language)
            session.turn_count = 12 + d_idx + 1
            save_session(session)
            return {
                "session_id": active_session_id,
                "phase": "DASHAVIDHA",
                "turn_number": 12 + d_idx + 1,
                "patient_utterance": {"native": patient_native, "english": patient_english},
                "static_question": q_payload,
                "prakriti_result": session.prakriti_result,
                "is_completed": False
            }
        else:
            # 3 Dashavidha questions done! Advance to Dynamic Vikriti Dialogue
            dash_state = score_dashavidha(session.dashavidha_answers, age=session.patient_context.age)
            session.dashavidha_state = dash_state.model_dump()
            session.patient_context.dashavidha_state = session.dashavidha_state
            session.phase = "DYNAMIC_VIKRITI"
            save_session(session)


    # 4. Handle Dynamic LLM Dialogue (Allopathy or Ayurveda Vikriti)
    # --------------------------------------------------------------------------
    # Sub-millisecond Emergency Red Flag screening
    red_flag_alert = scan_text_for_red_flags(patient_english + " " + patient_native)

    # Tri-Source RAG Context Retrieval
    rag_context_snippets = []
    try:
        rag_query = patient_english if patient_english else chief_complaint_hint or "symptoms"
        rag_results = await retrieve_patient_history_async(
            patient_id=patient_id,
            query_text=rag_query,
            top_k=3,
            similarity_threshold=0.35
        )
        for r in rag_results:
            content = r.get("content", "")
            if content:
                clean_snippet = content.split("]\n\n")[-1] if "]\n\n" in content else content
                rag_context_snippets.append(clean_snippet.strip()[:200])
    except Exception as e:
        logger.warning(f"RAG context retrieval exception: {e}")

    # Build history list
    history_list: List[Dict[str, Any]] = [m.model_dump() for m in session.history]
    if patient_english:
        history_list.append({
            "role": "patient",
            "content": patient_english,
            "slot_tag": selected_option_id
        })

    session.patient_context.chief_complaint = chief_complaint_hint or session.patient_context.chief_complaint or patient_english

    # Call Dialogue Manager
    if red_flag_alert:
        turn_result = DialogueTurnResult(
            should_stop=True,
            next_question=None,
            touch_options=[],
            state=session.clinical_state,
            clinical_summary=f"CRITICAL MEDICAL EMERGENCY: {red_flag_alert.emergency_message}",
            closing_message="A critical medical symptom has been detected. Please proceed immediately to the Emergency Room / Triage Desk.",
            red_flag_alert=red_flag_alert,
            reasoning="Emergency red-flag screening triggered."
        )
    else:
        turn_result = await get_next_dialogue_turn(
            patient_context=session.patient_context,
            conversation_history=history_list,
            max_turns=max_turns,
            current_state=session.clinical_state,
            rag_context_snippets=rag_context_snippets
        )

    # Update session
    session.clinical_state = turn_result.state
    session.is_completed = turn_result.should_stop
    if patient_english:
        session.history.append(ConversationMessage(role="patient", content=patient_english, slot_tag=selected_option_id))
    if turn_result.next_question:
        session.history.append(ConversationMessage(role="assistant", content=turn_result.next_question))
    save_session(session)

    # If completed, store summary in RAG in background
    if turn_result.should_stop:
        asyncio.create_task(store_dialogue_summary_in_rag_async(
            patient_id=patient_id,
            session_id=active_session_id,
            clinical_summary=turn_result.clinical_summary or "Intake completed",
            socrates_state=turn_result.state
        ))

    return {
        "session_id": active_session_id,
        "phase": session.phase,
        "turn_number": len([m for m in session.history if m.role == "patient"]),
        "patient_utterance": {"native": patient_native, "english": patient_english},
        "dynamic_turn_result": turn_result,
        "prakriti_result": session.prakriti_result,
        "rag_context_used": rag_context_snippets,
        "is_completed": turn_result.should_stop
    }

# ------------------------------------------------------------------------------
# 1. Server-Sent Events (SSE) Streaming Route (POST /stream)
# ------------------------------------------------------------------------------
@router.post("/stream")
async def stream_interview_turn(
    audio_file: Optional[UploadFile] = File(None, description="16kHz audio from Push-to-Talk"),
    text_response: Optional[str] = Form(None, description="Typed text or touchscreen response"),
    selected_option_id: Optional[str] = Form(None, description="Selected option ID"),
    session_id: Optional[str] = Form(None, description="Active session ID"),
    patient_id: str = Form("PAT-DEMO-01", description="Patient ID in Supabase"),
    hospital_type: str = Form("allopathy", description="'allopathy' | 'ayurveda'"),
    language: str = Form("hi", description="Patient language ISO code ('hi', 'ta', 'te', 'mr', 'bn', 'en')"),
    conversation_history: Optional[str] = Form("[]", description="JSON history"),
    max_turns: int = Form(10, description="Max questions limit"),
    chief_complaint_hint: Optional[str] = Form(None, description="Chief complaint hint")
):
    """
    Ultra-Low Latency Server-Sent Events (SSE) Streaming Endpoint (<700ms TTFA):
    Streams question chunks, synthesized voice audio, touch options, and state updates.
    """
    turn_data = await _execute_turn_logic(
        audio_file, text_response, selected_option_id, session_id,
        patient_id, hospital_type, language, conversation_history, max_turns, chief_complaint_hint
    )

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        # 1. Emit transcription event immediately
        patient_utt = turn_data.get("patient_utterance", {})
        yield await format_sse_event("transcription", {
            "session_id": turn_data.get("session_id"),
            "phase": turn_data.get("phase"),
            "turn_number": turn_data.get("turn_number"),
            "native": patient_utt.get("native"),
            "english": patient_utt.get("english")
        })

        # 2. If static MCQ turn (Prakriti or Dashavidha)
        if "static_question" in turn_data:
            async for sse_chunk in stream_static_turn_sse(turn_data["static_question"], language=language):
                yield sse_chunk
            return

        # 3. If dynamic LLM turn
        if "dynamic_turn_result" in turn_data:
            turn_res: DialogueTurnResult = turn_data["dynamic_turn_result"]
            async for sse_chunk in stream_dynamic_turn_sse(turn_res.model_dump(), language=language):
                yield sse_chunk

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

# ------------------------------------------------------------------------------
# 2. Standard JSON Fallback Route (POST /turn)
# ------------------------------------------------------------------------------
@router.post("/turn", response_model=InterviewTurnResponse)
async def process_interview_turn(
    audio_file: Optional[UploadFile] = File(None, description="16kHz audio from Push-to-Talk"),
    text_response: Optional[str] = Form(None, description="Typed text or touchscreen response"),
    selected_option_id: Optional[str] = Form(None, description="Selected option ID"),
    session_id: Optional[str] = Form(None, description="Active session ID"),
    patient_id: str = Form("PAT-DEMO-01", description="Patient ID in Supabase"),
    hospital_type: str = Form("allopathy", description="'allopathy' | 'ayurveda'"),
    language: str = Form("hi", description="Patient language ISO code ('hi', 'ta', 'te', 'mr', 'bn', 'en')"),
    conversation_history: Optional[str] = Form("[]", description="JSON history"),
    max_turns: int = Form(10, description="Max questions limit"),
    chief_complaint_hint: Optional[str] = Form(None, description="Chief complaint hint")
):
    """
    Standard All-in-One Turn Endpoint returning complete JSON payload with synthesized audio base64.
    """
    turn_data = await _execute_turn_logic(
        audio_file, text_response, selected_option_id, session_id,
        patient_id, hospital_type, language, conversation_history, max_turns, chief_complaint_hint
    )

    active_session_id = turn_data.get("session_id")
    phase = turn_data.get("phase", "DYNAMIC")
    turn_number = turn_data.get("turn_number", 1)
    patient_utt = turn_data.get("patient_utterance", {})
    
    # Handle Static MCQ Response
    if "static_question" in turn_data:
        sq = turn_data["static_question"]
        q_text = sq.get("text", "")
        audio_b64 = await sarvam_tts_service.synthesize_speech_async(q_text, language=language)
        
        touch_opts = [
            TouchOptionResponse(
                id=opt.get("id"),
                label=opt.get("label"),
                label_native=opt.get("label"),
                value=opt.get("value"),
                slot_tag=opt.get("anchor") or opt.get("tier")
            )
            for opt in sq.get("options", [])
        ]
        
        return InterviewTurnResponse(
            session_id=active_session_id,
            turn_number=turn_number,
            phase=phase,
            patient_utterance=UtterancePair(native=patient_utt.get("native", ""), english=patient_utt.get("english", "")),
            next_question=UtterancePair(native=q_text, english=q_text),
            audio_response=AudioResponse(audio_base64=audio_b64, language=language) if audio_b64 else None,
            touch_options=touch_opts,
            clinical_state={},
            covered_slots=[],
            missing_slots=[],
            is_completed=False,
            prakriti_result=turn_data.get("prakriti_result")
        )

    # Handle Dynamic Turn Response
    turn_res: DialogueTurnResult = turn_data.get("dynamic_turn_result")
    next_q_en = turn_res.next_question
    next_q_native = next_q_en
    audio_b64 = None

    if next_q_en:
        if language != "en":
            try:
                next_q_native = await sarvam_tts_service.translate_text_async(next_q_en, source_lang="en", target_lang=language)
            except Exception:
                next_q_native = next_q_en
        audio_b64 = await sarvam_tts_service.synthesize_speech_async(next_q_native, language=language)

    # Touch options translation
    touch_options_resp: List[TouchOptionResponse] = []
    if turn_res.touch_options:
        for opt in turn_res.touch_options:
            native_lbl = opt.label
            if language != "en" and opt.label:
                try:
                    native_lbl = await sarvam_tts_service.translate_text_async(opt.label, source_lang="en", target_lang=language)
                except Exception:
                    pass
            touch_options_resp.append(TouchOptionResponse(
                id=opt.id, label=opt.label, label_native=native_lbl, value=opt.value, slot_tag=opt.slot_tag
            ))

    closing_utt = None
    if turn_res.closing_message:
        native_closing = turn_res.closing_message
        if language != "en":
            try:
                native_closing = await sarvam_tts_service.translate_text_async(turn_res.closing_message, source_lang="en", target_lang=language)
            except Exception:
                pass
        closing_utt = UtterancePair(native=native_closing, english=turn_res.closing_message)

    return InterviewTurnResponse(
        session_id=active_session_id,
        turn_number=turn_number,
        phase=phase,
        patient_utterance=UtterancePair(native=patient_utt.get("native", ""), english=patient_utt.get("english", "")),
        next_question=UtterancePair(native=next_q_native, english=next_q_en) if next_q_en else None,
        audio_response=AudioResponse(audio_base64=audio_b64, language=language) if audio_b64 else None,
        touch_options=touch_options_resp,
        clinical_state=turn_res.state,
        covered_slots=turn_res.covered_slots,
        missing_slots=turn_res.missing_slots,
        is_completed=turn_res.should_stop,
        clinical_summary=turn_res.clinical_summary,
        closing_message=closing_utt,
        red_flag_alert=turn_res.red_flag_alert,
        prakriti_result=turn_data.get("prakriti_result"),
        rag_context_used=turn_data.get("rag_context_used", [])
    )
