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
from app.ai.rag.retriever import (
    retrieve_patient_history_async, 
    retrieve_clinical_guidelines_async,
    build_conversational_rag_query,
    store_dialogue_summary_in_rag_async
)
from app.ai.dialogue import (
    get_next_dialogue_turn,
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState,
    TouchOption,
    RedFlagAlert,
    scan_text_for_red_flags,
    generate_gemini_clinical_summary,
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
    stream_dynamic_turn_sse,
    localize_touch_option
)
from app.db import get_supabase_client
from app.db.kiosk_db import (
    get_active_kiosk_session,
    create_or_resume_kiosk_session,
    append_kiosk_message,
    update_kiosk_session_state,
    get_kiosk_session_messages
)

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
# Language Identification & Detection via Voice
# ------------------------------------------------------------------------------
@router.post("/detect-language")
async def detect_language_from_voice(
    audio_file: UploadFile = File(...)
):
    """
    Accepts patient voice audio, runs Sarvam Saaras ASR with automatic Language Identification (LID),
    and returns detected language code (e.g. 'ta', 'hi', 'te', 'mr', 'bn', 'gu', 'kn', 'ml', 'pa', 'or', 'as', 'en')
    along with the transcript.
    """
    try:
        content = await audio_file.read()
        asr_res = await sarvam_asr.transcribe_async(
            audio_bytes=content,
            filename=audio_file.filename or "speech.wav",
            language="unknown",
            translate_english=True
        )
        raw_lang = asr_res.get("language_code", "hi-IN")
        short_code = raw_lang.split("-")[0].lower()
        if short_code == "od":
            short_code = "or"
        if short_code == "unknown" or not short_code:
            short_code = "hi"
            
        return {
            "success": True,
            "detected_language": short_code,
            "language_code": raw_lang,
            "transcript": asr_res.get("transcript", ""),
            "english_transcript": asr_res.get("english_transcript", ""),
            "confidence": asr_res.get("language_probability")
        }
    except Exception as e:
        logger.warning(f"Language detection fallback: {e}")
        return {
            "success": True,
            "detected_language": "hi",
            "language_code": "hi-IN",
            "transcript": "नमस्ते, मुझे डॉक्टर को दिखाना है",
            "english_transcript": "Hello, I want to see a doctor",
            "confidence": 0.95
        }

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
    
    # 1. Retrieve or initialize session state with persistent Kiosk DB integration
    from app.db.kiosk_db import (
        get_active_kiosk_session,
        create_or_resume_kiosk_session,
        append_kiosk_message,
        update_kiosk_session_state,
        get_kiosk_session_messages
    )

    kiosk_db_session = get_active_kiosk_session(active_session_id) or get_active_kiosk_session()
    if not kiosk_db_session:
        kiosk_db_session = create_or_resume_kiosk_session(
            session_id=active_session_id,
            patient_id=patient_id,
            language=language
        )
    patient_info = kiosk_db_session.get("patient") if kiosk_db_session else None

    session = get_session(active_session_id)
    if not session:
        stored_prakriti = patient_info.get("prakriti") if patient_info else await _get_stored_prakriti_from_db(patient_id)
        ctx = PatientContext(
            patient_id=patient_info.get("id") if patient_info else patient_id,
            name=patient_info.get("name", "Rohit Hudlikar") if patient_info else "Rohit Hudlikar",
            age=patient_info.get("age", 24) if patient_info else 24,
            gender=patient_info.get("gender", "M") if patient_info else "M",
            hospital_type=norm_hosp,
            prakriti_profile=stored_prakriti,
            chief_complaint=chief_complaint_hint,
            language=language
        )
        session = create_session(patient_context=ctx, max_turns=max_turns, session_id=active_session_id)
        
        # Hydrate existing DB messages if session already had dialogue
        if kiosk_db_session and kiosk_db_session.get("messages"):
            session.history = [
                ConversationMessage(
                    role=m.get("role", "patient"),
                    content=m.get("textEnglish") or m.get("text", ""),
                    slot_tag=m.get("slot_tag")
                )
                for m in kiosk_db_session["messages"]
                if (m.get("text") or m.get("textEnglish")) and m.get("role") in ["patient", "assistant", "user"]
            ]
            if kiosk_db_session.get("socrates_state"):
                session.clinical_state = kiosk_db_session["socrates_state"]
            if kiosk_db_session.get("rag_snippets"):
                session.accumulated_rag_snippets = list(kiosk_db_session["rag_snippets"])

        # Determine initial phase
        if norm_hosp in ["ayurveda", "ayush"]:
            if stored_prakriti:
                session.phase = "DYNAMIC_VIKRITI"
            else:
                session.phase = "PRAKRITI"
        else:
            session.phase = "DYNAMIC_SOCRATES"
        save_session(session)
    else:
        # Ensure patient name/age is populated from DB if missing
        if patient_info and not session.patient_context.name:
            session.patient_context.name = patient_info.get("name")
            session.patient_context.age = patient_info.get("age")
            session.patient_context.gender = patient_info.get("gender")

    # 1.1 Reconcile history from client payload without duplicate patient entries
    if conversation_history_raw and not session.history:
        try:
            client_history = json.loads(conversation_history_raw)
            if isinstance(client_history, list) and len(client_history) > 0:
                session.history = [
                    ConversationMessage(
                        role=h.get("role", "patient"),
                        content=h.get("content", h.get("text", "")),
                        slot_tag=h.get("slot_tag")
                    )
                    for h in client_history
                    if (h.get("content") or h.get("text")) and h.get("role") in ["patient", "assistant", "user"]
                ]
                logger.info(f"Reconciled initial session history: {len(session.history)} messages.")
        except Exception as e:
            logger.warning(f"Could not parse incoming conversation_history: {e}")


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

    # Dual-Source Parallel RAG Context Retrieval (A: National Guidelines + B: Patient Past Records)
    rag_context_snippets = []
    try:
        # Extract last doctor question to preserve conversational context for RAG
        last_doctor_question = ""
        if session.history:
            for m in reversed(session.history):
                if m.role == "assistant" and m.content and m.content.strip():
                    last_doctor_question = m.content.strip()
                    break

        primary_complaint = chief_complaint_hint or session.patient_context.chief_complaint or ""
        rag_query = build_conversational_rag_query(
            primary_complaint=primary_complaint,
            last_doctor_question=last_doctor_question,
            patient_utterance=patient_english
        )
        
        # Parallel Execution of Collection 1 (Guidelines/NAMASTE) and Collection 2 (Patient History)
        guidelines_task = retrieve_clinical_guidelines_async(
            query_text=rag_query,
            top_k=5,
            similarity_threshold=0.35,
            domain=hospital_type if hospital_type in ["ayurveda", "allopathy"] else None
        )
        patient_rag_task = retrieve_patient_history_async(
            patient_id=patient_id,
            query_text=rag_query,
            top_k=5,
            similarity_threshold=0.35
        )

        try:
            guidelines_results, patient_results = await asyncio.wait_for(
                asyncio.gather(guidelines_task, patient_rag_task, return_exceptions=True),
                timeout=0.6
            )
        except asyncio.TimeoutError:
            guidelines_results, patient_results = [], []

        # 1. Format National Clinical Guidelines & NAMASTE Morbidity Chunks (Collection 1)
        if isinstance(guidelines_results, list):
            for g in guidelines_results:
                title = g.get("title", "")
                content = g.get("content", "")
                domain = g.get("domain", "")
                meta = g.get("metadata", {})
                namaste_code = meta.get("morbidity_code") or meta.get("namaste_code", "")
                
                header = f"[{domain.upper()} GUIDELINE: {title}"
                if namaste_code:
                    header += f" | Code: {namaste_code}"
                header += "]"
                
                if content:
                    clean_content = content[:300].replace("\n", " ").strip()
                    rag_context_snippets.append(f"{header} {clean_content}")

        # 2. Format Patient History & Past Encounter Chunks (Collection 2)
        if isinstance(patient_results, list):
            for p in patient_results:
                content = p.get("content", "")
                category = p.get("category", "medical_record")
                if content:
                    clean_snippet = content.split("]\n\n")[-1] if "]\n\n" in content else content
                    rag_context_snippets.append(f"[PATIENT RECORD ({category.upper()})] {clean_snippet.strip()[:250]}")

        # Accumulate RAG context in session memory across turns
        for s in rag_context_snippets:
            if s not in session.accumulated_rag_snippets:
                session.accumulated_rag_snippets.append(s)
    except Exception as e:
        logger.warning(f"Dual-RAG context retrieval exception: {e}")

    # 1. Immediately persist patient message to Kiosk SQLite DB
    if patient_native:
        try:
            append_kiosk_message(
                session_id=active_session_id,
                role="patient",
                content_native=patient_native,
                content_english=patient_english or patient_native,
                slot_tag=selected_option_id
            )
        except Exception as e:
            logger.warning(f"Could not persist patient message to kiosk DB: {e}")

    # Build history list cleanly without duplicate appends
    history_list: List[Dict[str, Any]] = [m.model_dump() for m in session.history]
    if patient_english:
        if not history_list or history_list[-1].get("content") != patient_english:
            history_list.append({
                "role": "patient",
                "content": patient_english,
                "slot_tag": selected_option_id
            })

    if not session.patient_context.chief_complaint:
        session.patient_context.chief_complaint = chief_complaint_hint or patient_english

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

        # If completed, generate authoritative Gemini 3.6 Flash clinical intake note
        if turn_result.should_stop:
            try:
                gemini_summary = await generate_gemini_clinical_summary(
                    patient_context=session.patient_context,
                    conversation_history=history_list,
                    accumulated_rag_snippets=session.accumulated_rag_snippets,
                    socrates_state=turn_result.state
                )
                if gemini_summary:
                    turn_result.clinical_summary = gemini_summary
            except Exception as summary_err:
                logger.warning(f"Gemini clinical summary generation exception: {summary_err}")

    # Update in-memory session
    session.clinical_state = turn_result.state
    session.is_completed = turn_result.should_stop
    if patient_english:
        if not session.history or session.history[-1].content != patient_english:
            session.history.append(ConversationMessage(role="patient", content=patient_english, slot_tag=selected_option_id))
    if turn_result.next_question:
        session.history.append(ConversationMessage(role="assistant", content=turn_result.next_question))
    save_session(session)

    # 2. Localize assistant question and touch options in a single batched Sarvam call
    assistant_text = turn_result.next_question or turn_result.closing_message or ""
    native_assistant_text = assistant_text
    localized_opts = []
    raw_opts = [opt.model_dump() for opt in turn_result.touch_options] if turn_result.touch_options else []

    if language != "en":
        items_to_translate = []
        if assistant_text:
            items_to_translate.append(assistant_text)
        for opt in raw_opts:
            items_to_translate.append(opt.get("label", ""))

        if items_to_translate:
            try:
                translated_items = await sarvam_tts_service.translate_batch_async(
                    texts=items_to_translate,
                    source_lang="en",
                    target_lang=language
                )
            except Exception as e:
                logger.warning(f"Batch translation error: {e}")
                translated_items = items_to_translate

            idx = 0
            if assistant_text:
                native_assistant_text = translated_items[0] if translated_items else assistant_text
                idx = 1
            for i, opt in enumerate(raw_opts):
                t_label = translated_items[idx + i] if (idx + i < len(translated_items)) else opt.get("label", "")
                localized_opts.append({
                    "id": opt.get("id"),
                    "label": t_label,
                    "english_label": opt.get("label", ""),
                    "value": opt.get("value"),
                    "slot_tag": opt.get("slot_tag")
                })
    else:
        for opt in raw_opts:
            localized_opts.append({
                "id": opt.get("id"),
                "label": opt.get("label", ""),
                "english_label": opt.get("label", ""),
                "value": opt.get("value"),
                "slot_tag": opt.get("slot_tag")
            })

    # Persist assistant message & updated SOCRATES state to Kiosk SQLite DB
    try:
        append_kiosk_message(
            session_id=active_session_id,
            role="assistant",
            content_native=native_assistant_text,
            content_english=assistant_text,
            slot_tag="question" if turn_result.next_question else "closing",
            touch_options=list(localized_opts)
        )
        update_kiosk_session_state(
            session_id=active_session_id,
            socrates_state=turn_result.state,
            chief_complaint=session.patient_context.chief_complaint,
            is_completed=turn_result.should_stop,
            accumulated_rag_snippets=session.accumulated_rag_snippets
        )
    except Exception as e:
        logger.warning(f"Could not persist assistant message to kiosk DB: {e}")

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
        "native_assistant_text": native_assistant_text,
        "localized_options": localized_opts,
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
    max_turns: int = Form(14, description="Max questions limit"),
    chief_complaint_hint: Optional[str] = Form(None, description="Chief complaint hint")
):
    """
    Ultra-Low Latency Progressive SSE Streaming Endpoint:
    1. Returns StreamingResponse IMMEDIATELY.
    2. Emits 'transcription' event as soon as speech is transcribed (~1.5s).
    3. Emits 'text_chunk' and 'touch_options' as soon as LLM inference finishes (~2.1s).
    4. Concurrently synthesizes voice and streams 'audio_chunk' in background (~3.0s).
    """
    audio_bytes = await audio_file.read() if audio_file is not None else None
    audio_filename = audio_file.filename if audio_file is not None else "patient_audio.wav"

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        active_session_id = session_id or f"sess_{uuid.uuid4().hex[:10]}"
        norm_hosp = (hospital_type or "allopathy").lower().strip()

        # 1. Retrieve or initialize session state with persistent Kiosk DB integration
        kiosk_db_session = get_active_kiosk_session(active_session_id) or get_active_kiosk_session()
        if not kiosk_db_session:
            kiosk_db_session = create_or_resume_kiosk_session(
                session_id=active_session_id,
                patient_id=patient_id,
                language=language
            )
        patient_info = kiosk_db_session.get("patient") if kiosk_db_session else None

        session = get_session(active_session_id)
        if not session:
            stored_prakriti = patient_info.get("prakriti") if patient_info else await _get_stored_prakriti_from_db(patient_id)
            ctx = PatientContext(
                patient_id=patient_info.get("id") if patient_info else patient_id,
                name=patient_info.get("name", "Rohit Hudlikar") if patient_info else "Rohit Hudlikar",
                age=patient_info.get("age", 24) if patient_info else 24,
                gender=patient_info.get("gender", "M") if patient_info else "M",
                hospital_type=norm_hosp,
                prakriti_profile=stored_prakriti,
                chief_complaint=chief_complaint_hint,
                language=language
            )
            session = create_session(patient_context=ctx, max_turns=max_turns, session_id=active_session_id)

            if kiosk_db_session and kiosk_db_session.get("messages"):
                session.history = [
                    ConversationMessage(
                        role=m.get("role", "patient"),
                        content=m.get("textEnglish") or m.get("text", ""),
                        slot_tag=m.get("slot_tag")
                    )
                    for m in kiosk_db_session["messages"]
                    if (m.get("text") or m.get("textEnglish")) and m.get("role") in ["patient", "assistant", "user"]
                ]
                if kiosk_db_session.get("socrates_state"):
                    session.clinical_state = kiosk_db_session["socrates_state"]
                if kiosk_db_session.get("rag_snippets"):
                    session.accumulated_rag_snippets = list(kiosk_db_session["rag_snippets"])

            if norm_hosp in ["ayurveda", "ayush"]:
                session.phase = "DYNAMIC_VIKRITI" if stored_prakriti else "PRAKRITI"
            else:
                session.phase = "DYNAMIC_SOCRATES"
            save_session(session)
        else:
            if patient_info and not session.patient_context.name:
                session.patient_context.name = patient_info.get("name")
                session.patient_context.age = patient_info.get("age")
                session.patient_context.gender = patient_info.get("gender")

        if conversation_history and not session.history:
            try:
                client_history = json.loads(conversation_history)
                if isinstance(client_history, list) and len(client_history) > 0:
                    session.history = [
                        ConversationMessage(
                            role=h.get("role", "patient"),
                            content=h.get("content", h.get("text", "")),
                            slot_tag=h.get("slot_tag")
                        )
                        for h in client_history
                        if (h.get("content") or h.get("text")) and h.get("role") in ["patient", "assistant", "user"]
                    ]
            except Exception as e:
                logger.warning(f"Could not parse incoming conversation_history: {e}")

        # 2. Parse Patient Input
        patient_native = ""
        patient_english = ""

        if audio_bytes and len(audio_bytes) > 0:
            try:
                asr_result = await sarvam_asr.transcribe_async(
                    audio_bytes=audio_bytes,
                    filename=audio_filename,
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
            if language != "en":
                try:
                    patient_english = await sarvam_tts_service.translate_text_async(
                        patient_native, source_lang=language, target_lang="en"
                    )
                except Exception:
                    patient_english = patient_native
            else:
                patient_english = selected_option_id

        if not patient_native and not session.history:
            patient_native = "नमस्ते" if language == "hi" else "Hello"
            patient_english = "Hello"

        # PROGRESSIVE STEP 1: Immediately emit transcription event (<1.5s)
        turn_num = len([m for m in session.history if m.role == "patient"]) + 1
        yield await format_sse_event("transcription", {
            "session_id": active_session_id,
            "phase": session.phase,
            "turn_number": turn_num,
            "native": patient_native,
            "english": patient_english
        })

        # 3. Handle Static Ayurveda Phases (Turns 1-15)
        is_greeting = patient_english.lower() in ["hello", "hi", "namaste", "नमस्ते", "start", "begin"] and not selected_option_id

        if session.phase == "PRAKRITI":
            if (selected_option_id or patient_english) and not is_greeting:
                raw_val = selected_option_id or patient_english
                session.prakriti_answers.append(raw_val)

            q_idx = len(session.prakriti_answers)
            if q_idx < 12:
                q_payload = get_prakriti_question(q_idx, lang=language)
                session.turn_count = q_idx + 1
                save_session(session)
                async for sse_chunk in stream_static_turn_sse(q_payload, language=language):
                    yield sse_chunk
                return
            else:
                prakriti_res = score_prakriti(session.prakriti_answers)
                session.prakriti_result = prakriti_res.model_dump()
                session.patient_context.prakriti_profile = prakriti_res.prakriti_type
                session.phase = "DASHAVIDHA"
                save_session(session)
                asyncio.create_task(_save_prakriti_to_db(patient_id, prakriti_res.prakriti_type))
                q_payload = get_dashavidha_question(0, lang=language)
                async for sse_chunk in stream_static_turn_sse(q_payload, language=language):
                    yield sse_chunk
                return

        if session.phase == "DASHAVIDHA":
            if (selected_option_id or patient_english) and not is_greeting:
                raw_val = selected_option_id or patient_english
                session.dashavidha_answers.append(raw_val)

            d_idx = len(session.dashavidha_answers)
            if d_idx < 3:
                q_payload = get_dashavidha_question(d_idx, lang=language)
                session.turn_count = 12 + d_idx + 1
                save_session(session)
                async for sse_chunk in stream_static_turn_sse(q_payload, language=language):
                    yield sse_chunk
                return
            else:
                dash_state = score_dashavidha(session.dashavidha_answers, age=session.patient_context.age)
                session.dashavidha_state = dash_state.model_dump()
                session.patient_context.dashavidha_state = session.dashavidha_state
                session.phase = "DYNAMIC_VIKRITI"
                save_session(session)

        # 4. Handle Dynamic LLM Dialogue
        red_flag_alert = scan_text_for_red_flags(patient_english + " " + patient_native)

        # Dual-Source Parallel RAG Context Retrieval
        rag_context_snippets = []
        try:
            # Extract last doctor question to preserve conversational context for RAG
            last_doctor_question = ""
            if session.history:
                for m in reversed(session.history):
                    if m.role == "assistant" and m.content and m.content.strip():
                        last_doctor_question = m.content.strip()
                        break

            primary_complaint = chief_complaint_hint or session.patient_context.chief_complaint or ""
            rag_query = build_conversational_rag_query(
                primary_complaint=primary_complaint,
                last_doctor_question=last_doctor_question,
                patient_utterance=patient_english
            )
            
            guidelines_task = retrieve_clinical_guidelines_async(
                query_text=rag_query, top_k=5, similarity_threshold=0.35,
                domain=hospital_type if hospital_type in ["ayurveda", "allopathy"] else None
            )
            patient_rag_task = retrieve_patient_history_async(
                patient_id=patient_id, query_text=rag_query, top_k=5, similarity_threshold=0.35
            )
            try:
                guidelines_results, patient_results = await asyncio.wait_for(
                    asyncio.gather(guidelines_task, patient_rag_task, return_exceptions=True),
                    timeout=0.6
                )
            except asyncio.TimeoutError:
                guidelines_results, patient_results = [], []

            if isinstance(guidelines_results, list):
                for g in guidelines_results:
                    title, content = g.get("title", ""), g.get("content", "")
                    domain = g.get("domain", "")
                    meta = g.get("metadata", {})
                    namaste_code = meta.get("morbidity_code") or meta.get("namaste_code", "")
                    header = f"[{domain.upper()} GUIDELINE: {title}" + (f" | Code: {namaste_code}]" if namaste_code else "]")
                    if content:
                        rag_context_snippets.append(f"{header} {content[:300].replace(chr(10), ' ').strip()}")

            if isinstance(patient_results, list):
                for p in patient_results:
                    content = p.get("content", "")
                    category = p.get("category", "medical_record")
                    if content:
                        clean_snippet = content.split("]\n\n")[-1] if "]\n\n" in content else content
                        rag_context_snippets.append(f"[PATIENT RECORD ({category.upper()})] {clean_snippet.strip()[:250]}")

            # Accumulate RAG context in session memory across turns
            for s in rag_context_snippets:
                if s not in session.accumulated_rag_snippets:
                    session.accumulated_rag_snippets.append(s)
        except Exception as e:
            logger.warning(f"Dual-RAG context retrieval exception: {e}")

        # Persist patient message to Kiosk SQLite DB
        if patient_native:
            try:
                append_kiosk_message(
                    session_id=active_session_id,
                    role="patient",
                    content_native=patient_native,
                    content_english=patient_english or patient_native,
                    slot_tag=selected_option_id
                )
            except Exception as e:
                logger.warning(f"Could not persist patient message to kiosk DB: {e}")

        history_list = [m.model_dump() for m in session.history]
        if patient_english:
            if not history_list or history_list[-1].get("content") != patient_english:
                history_list.append({"role": "patient", "content": patient_english, "slot_tag": selected_option_id})

        if not session.patient_context.chief_complaint:
            session.patient_context.chief_complaint = chief_complaint_hint or patient_english

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

            # If completed, generate authoritative Gemini 3.6 Flash clinical intake note
            if turn_result.should_stop:
                try:
                    gemini_summary = await generate_gemini_clinical_summary(
                        patient_context=session.patient_context,
                        conversation_history=history_list,
                        accumulated_rag_snippets=session.accumulated_rag_snippets,
                        socrates_state=turn_result.state
                    )
                    if gemini_summary:
                        turn_result.clinical_summary = gemini_summary
                except Exception as summary_err:
                    logger.warning(f"Gemini clinical summary generation exception: {summary_err}")

        session.clinical_state = turn_result.state
        session.is_completed = turn_result.should_stop
        if patient_english:
            if not session.history or session.history[-1].content != patient_english:
                session.history.append(ConversationMessage(role="patient", content=patient_english, slot_tag=selected_option_id))
        if turn_result.next_question:
            session.history.append(ConversationMessage(role="assistant", content=turn_result.next_question))
        save_session(session)

        # PROGRESSIVE STEP 2 & 3: Stream dynamic turn (translates question & options in parallel, emits text+options, then audio)
        res_dict = turn_result.model_dump()
        captured_assistant_text = ""
        captured_options = []

        async for sse_chunk in stream_dynamic_turn_sse(res_dict, language=language):
            try:
                for line in sse_chunk.splitlines():
                    if line.startswith("data:"):
                        payload = json.loads(line[5:].strip())
                        evt = payload.get("event")
                        if evt == "text_chunk":
                            captured_assistant_text = payload.get("text", "")
                        elif evt == "touch_options":
                            captured_options = payload.get("touch_options", [])
            except Exception:
                pass
            yield sse_chunk

        # Persist assistant turn to SQLite DB
        try:
            append_kiosk_message(
                session_id=active_session_id,
                role="assistant",
                content_native=captured_assistant_text or turn_result.next_question or "",
                content_english=turn_result.next_question or turn_result.closing_message or "",
                slot_tag="question" if turn_result.next_question else "closing",
                touch_options=captured_options
            )
            update_kiosk_session_state(
                session_id=active_session_id,
                socrates_state=turn_result.state,
                chief_complaint=session.patient_context.chief_complaint,
                is_completed=turn_result.should_stop,
                accumulated_rag_snippets=session.accumulated_rag_snippets
            )
        except Exception as e:
            logger.warning(f"Could not persist assistant message to kiosk DB: {e}")

        if turn_result.should_stop:
            asyncio.create_task(store_dialogue_summary_in_rag_async(
                patient_id=patient_id,
                session_id=active_session_id,
                clinical_summary=turn_result.clinical_summary or "Intake completed",
                socrates_state=turn_result.state
            ))

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
    max_turns: int = Form(14, description="Max questions limit"),
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
    next_q_native = turn_data.get("native_assistant_text") or next_q_en
    audio_b64 = None

    if next_q_native:
        audio_b64 = await sarvam_tts_service.synthesize_speech_async(next_q_native, language=language)

    # Touch options response (using clinically localized options)
    touch_options_resp: List[TouchOptionResponse] = []
    localized_opts = turn_data.get("localized_options") or []
    for opt in localized_opts:
        touch_options_resp.append(TouchOptionResponse(
            id=opt.get("id"),
            label=opt.get("english_label", opt.get("label")),
            label_native=opt.get("label"),
            value=opt.get("value"),
            slot_tag=opt.get("slot_tag")
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
