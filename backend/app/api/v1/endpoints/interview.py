# backend/app/api/v1/endpoints/interview.py
import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
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
    store_full_dialogue_session_async
)
from app.db import get_supabase_client

logger = logging.getLogger("medikiosk.interview.endpoint")

router = APIRouter(prefix="/interview", tags=["Unified Clinical Interview & Voice Turn"])

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
    patient_utterance: UtterancePair
    next_question: Optional[UtterancePair] = None
    audio_response: Optional[AudioResponse] = None
    touch_options: List[TouchOptionResponse] = Field(default_factory=list)
    socrates_state: Dict[str, Any] = Field(default_factory=dict)
    covered_slots: List[str] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    is_completed: bool = False
    clinical_summary: Optional[str] = None
    closing_message: Optional[UtterancePair] = None
    red_flag_alert: Optional[RedFlagAlert] = None
    rag_context_used: List[str] = Field(default_factory=list)

@router.post("/turn", response_model=InterviewTurnResponse)
async def process_interview_turn(
    audio_file: Optional[UploadFile] = File(None, description="Patient 16kHz audio from Push-to-Talk"),
    text_response: Optional[str] = Form(None, description="Typed text or touchscreen response"),
    selected_option_id: Optional[str] = Form(None, description="Selected touchscreen option ID"),
    session_id: Optional[str] = Form(None, description="Active session ID (auto-generated if empty)"),
    patient_id: str = Form("PAT-DEMO-01", description="Patient ID in Supabase"),
    language: str = Form("hi", description="Patient language ISO code ('hi', 'ta', 'te', 'mr', 'bn', 'en')"),
    conversation_history: Optional[str] = Form("[]", description="JSON array of previous turns from frontend"),
    max_turns: int = Form(10, description="Target safety maximum turns for comprehensive intake"),
    chief_complaint_hint: Optional[str] = Form(None, description="Initial chief complaint hint")
):
    """
    Unified All-in-One Clinical Interview Turn Endpoint:
    1. Receives 16kHz preprocessed audio OR text from frontend Push-to-Talk.
    2. Runs ASR & translation to English (Sarvam AI / Bhashini / Whisper).
    3. Runs Sub-ms Emergency Red Flag screening.
    4. Retrieves relevant past patient history from Supabase pgvector (RAG).
    5. Evaluates SOCRATES clinical inquiry & slot completion via LLM reasoning.
    6. Translates the next question & synthesizes spoken 16kHz WAV audio via Sarvam TTS.
    7. Embeds completed interview into Supabase RAG store when session finishes.
    8. Returns bilingual text, audio base64, touch buttons, and SOCRATES state to frontend.
    """
    active_session_id = session_id or f"sess_{uuid.uuid4().hex[:10]}"
    
    # --------------------------------------------------------------------------
    # Step 1: Parse Input & Extract Native + English Utterance
    # --------------------------------------------------------------------------
    patient_utterance_native = ""
    patient_utterance_english = ""

    if audio_file is not None and audio_file.filename:
        audio_bytes = await audio_file.read()
        if len(audio_bytes) > 0:
            logger.info(f"Processing patient audio payload ({len(audio_bytes)} bytes) in language: {language}")
            try:
                asr_result = await sarvam_asr.transcribe_async(
                    audio_bytes=audio_bytes,
                    filename=audio_file.filename or "patient_audio.wav",
                    language=language,
                    translate_english=True
                )
                patient_utterance_native = asr_result.get("transcript", "").strip()
                patient_utterance_english = asr_result.get("english_transcript", patient_utterance_native).strip()
            except Exception as e:
                logger.error(f"ASR transcription failed: {e}. Falling back to default.")
                patient_utterance_native = text_response or "Audio received"
                patient_utterance_english = patient_utterance_native

    if not patient_utterance_native and text_response:
        patient_utterance_native = text_response.strip()
        if language != "en":
            try:
                patient_utterance_english = await sarvam_tts_service.translate_text_async(
                    patient_utterance_native,
                    source_lang=language,
                    target_lang="en"
                )
            except Exception as e:
                logger.warning(f"Translation to English failed: {e}")
                patient_utterance_english = patient_utterance_native
        else:
            patient_utterance_english = patient_utterance_native

    if not patient_utterance_native:
        # If both audio and text are empty, default to greeting / initial inquiry
        patient_utterance_native = "नमस्ते"
        patient_utterance_english = "Hello"

    # --------------------------------------------------------------------------
    # Step 2: Emergency Red-Flag Screening (Sub-1ms rule-based safety check)
    # --------------------------------------------------------------------------
    red_flag_alert = scan_text_for_red_flags(patient_utterance_english + " " + patient_utterance_native)

    # --------------------------------------------------------------------------
    # Step 3: RAG Retrieval from Supabase pgvector
    # --------------------------------------------------------------------------
    rag_context_snippets = []
    try:
        rag_query = patient_utterance_english if patient_utterance_english else chief_complaint_hint or "symptoms"
        rag_results = await retrieve_patient_history_async(
            patient_id=patient_id,
            query_text=rag_query,
            top_k=3,
            similarity_threshold=0.35
        )
        for r in rag_results:
            content = r.get("content", "")
            if content:
                # Clean header if present
                clean_snippet = content.split("]\n\n")[-1] if "]\n\n" in content else content
                rag_context_snippets.append(clean_snippet.strip()[:200])
    except Exception as e:
        logger.warning(f"RAG context retrieval exception: {e}")

    # --------------------------------------------------------------------------
    # Step 4: Parse Conversation History and Evaluate Next Turn via LLM
    # --------------------------------------------------------------------------
    history_list: List[Dict[str, Any]] = []
    if conversation_history:
        try:
            parsed = json.loads(conversation_history)
            if isinstance(parsed, list):
                history_list = parsed
        except Exception:
            history_list = []

    # Append current patient response to conversation history
    history_list.append({
        "role": "patient",
        "content": patient_utterance_english,
        "slot_tag": selected_option_id
    })

    # Prepare Patient Context for LLM reasoning
    patient_ctx = PatientContext(
        patient_id=patient_id,
        chief_complaint=chief_complaint_hint or patient_utterance_english,
        past_medical_history=rag_context_snippets,
        language="en"
    )

    # If Red Flag detected, immediately conclude with emergency triage
    if red_flag_alert:
        turn_result = DialogueTurnResult(
            should_stop=True,
            next_question=None,
            touch_options=[],
            socrates_state=SocratesState(),
            clinical_summary=f"CRITICAL MEDICAL EMERGENCY: {red_flag_alert.emergency_message}",
            closing_message="A critical medical symptom has been detected. Please proceed immediately to the Emergency / Triage room.",
            red_flag_alert=red_flag_alert,
            reasoning="Emergency triage rule triggered."
        )
    else:
        # Call SOCRATES Dialogue Manager (LLM reasoning in English)
        turn_result = await get_next_dialogue_turn(
            patient_context=patient_ctx,
            conversation_history=history_list,
            max_turns=max_turns
        )

    # --------------------------------------------------------------------------
    # Step 5: Translate Question / Closing Message & Synthesize Native Speech via Sarvam TTS
    # --------------------------------------------------------------------------
    next_question_english = turn_result.next_question
    next_question_native = None
    closing_message_english = turn_result.closing_message
    closing_message_native = None
    audio_base64 = None

    if next_question_english:
        # 1. Translate question to patient's native language
        if language != "en":
            try:
                next_question_native = await sarvam_tts_service.translate_text_async(
                    next_question_english,
                    source_lang="en",
                    target_lang=language
                )
            except Exception as e:
                logger.warning(f"Failed to translate question to {language}: {e}")
                next_question_native = next_question_english
        else:
            next_question_native = next_question_english

        # 2. Synthesize 16kHz speech audio using Sarvam Bulbul TTS
        try:
            tts_res = await sarvam_tts_service.text_to_speech_async(
                text=next_question_native,
                language=language,
                sample_rate=16000
            )
            if tts_res.get("success"):
                audio_base64 = tts_res.get("audio_base64")
        except Exception as e:
            logger.warning(f"TTS synthesis exception: {e}")

    elif turn_result.should_stop:
        # If interview is complete, translate and speak the closing farewell message
        if not closing_message_english:
            closing_message_english = "Thank you for answering all the questions. Your clinical summary has been prepared for the attending doctor. Please proceed to the waiting area."

        if language != "en":
            try:
                closing_message_native = await sarvam_tts_service.translate_text_async(
                    closing_message_english,
                    source_lang="en",
                    target_lang=language
                )
            except Exception as e:
                logger.warning(f"Failed to translate closing message to {language}: {e}")
                closing_message_native = closing_message_english
        else:
            closing_message_native = closing_message_english

        # Synthesize spoken closing audio in native language
        try:
            tts_res = await sarvam_tts_service.text_to_speech_async(
                text=closing_message_native,
                language=language,
                sample_rate=16000
            )
            if tts_res.get("success"):
                audio_base64 = tts_res.get("audio_base64")
        except Exception as e:
            logger.warning(f"Closing TTS synthesis exception: {e}")

    # Process and translate touch options in parallel for high speed
    touch_options_response: List[TouchOptionResponse] = []
    if turn_result.touch_options:
        if language != "en":
            try:
                import asyncio
                translated_labels = await asyncio.gather(*[
                    sarvam_tts_service.translate_text_async(opt.label, source_lang="en", target_lang=language)
                    for opt in turn_result.touch_options
                ])
                for idx, opt in enumerate(turn_result.touch_options):
                    touch_options_response.append(TouchOptionResponse(
                        id=opt.id,
                        label=opt.label,
                        label_native=translated_labels[idx] if idx < len(translated_labels) else opt.label,
                        value=opt.value,
                        slot_tag=opt.slot_tag
                    ))
            except Exception as e:
                logger.warning(f"Parallel translation of touch options failed: {e}")
                for opt in turn_result.touch_options:
                    touch_options_response.append(TouchOptionResponse(
                        id=opt.id, label=opt.label, label_native=opt.label, value=opt.value, slot_tag=opt.slot_tag
                    ))
        else:
            for opt in turn_result.touch_options:
                touch_options_response.append(TouchOptionResponse(
                    id=opt.id, label=opt.label, label_native=opt.label, value=opt.value, slot_tag=opt.slot_tag
                ))

    # --------------------------------------------------------------------------
    # Step 6: Post-Interview RAG Storage & DB Sync (when completed)
    # --------------------------------------------------------------------------
    is_completed = bool(turn_result.should_stop)

    if is_completed:
        # 1. Batch store the entire conversation (all turns + closing) in Supabase
        try:
            await store_full_dialogue_session_async(
                patient_id=patient_id,
                session_id=active_session_id,
                history=history_list,
                language=language,
                chief_complaint=chief_complaint_hint or (history_list[0].get("content") if history_list else None),
                socrates_state=turn_result.socrates_state.model_dump() if turn_result.socrates_state else {},
                red_flag_alert=turn_result.red_flag_alert.model_dump() if turn_result.red_flag_alert else None,
                last_question=turn_result.next_question,
                closing_message_english=closing_message_english,
                closing_message_native=closing_message_native
            )
        except Exception as e:
            logger.error(f"Failed to batch-store full conversation in Supabase: {e}")

        # 2. Store finished interview summary into Supabase RAG table for future encounters
        if turn_result.clinical_summary:
            try:
                await store_dialogue_summary_in_rag_async(
                    patient_id=patient_id,
                    session_id=active_session_id,
                    clinical_summary=turn_result.clinical_summary,
                    socrates_state=turn_result.socrates_state.model_dump() if turn_result.socrates_state else {}
                )
            except Exception as e:
                logger.error(f"Failed to store completed dialogue in RAG: {e}")

    # --------------------------------------------------------------------------
    # Step 7: Build & Return Unified Response Payload
    # --------------------------------------------------------------------------
    current_turn_count = len([m for m in history_list if m.get("role") == "patient"])

    socrates_dict = turn_result.socrates_state.model_dump() if turn_result.socrates_state else {}
    covered = turn_result.covered_slots or []
    missing = turn_result.missing_slots or []

    closing_utterance = None
    if closing_message_native or closing_message_english:
        closing_utterance = UtterancePair(
            native=closing_message_native or closing_message_english or "",
            english=closing_message_english or ""
        )

    return InterviewTurnResponse(
        session_id=active_session_id,
        turn_number=current_turn_count,
        patient_utterance=UtterancePair(
            native=patient_utterance_native,
            english=patient_utterance_english
        ),
        next_question=UtterancePair(
            native=next_question_native or "",
            english=next_question_english or ""
        ) if next_question_english else None,
        audio_response=AudioResponse(
            audio_base64=audio_base64,
            audio_format="wav",
            sample_rate=16000,
            language=language
        ) if audio_base64 else None,
        touch_options=touch_options_response,
        socrates_state=socrates_dict,
        covered_slots=covered,
        missing_slots=missing,
        is_completed=is_completed,
        clinical_summary=turn_result.clinical_summary,
        closing_message=closing_utterance,
        red_flag_alert=turn_result.red_flag_alert,
        rag_context_used=rag_context_snippets
    )
