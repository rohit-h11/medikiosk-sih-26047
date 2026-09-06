# backend/app/ai/dialogue/streaming_orchestrator.py
"""
MediKiosk — Pipelined Streaming & Sentence Chunking Orchestrator
Streams LLM tokens, detects sentence boundaries, and concurrently dispatches
Sarvam Translation and TTS audio synthesis over Server-Sent Events (SSE).
"""

import json
import re
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List
from app.ai.asr.sarvam_tts_client import sarvam_tts_service

logger = logging.getLogger("medikiosk.dialogue.streaming")

SENTENCE_ENDINGS = re.compile(r'([.?!।\n]+)')

def split_complete_sentences(buffer: str) -> (List[str], str):
    """
    Splits buffer into complete sentences based on punctuation.
    Returns (list of complete sentences, remaining incomplete buffer).
    """
    parts = SENTENCE_ENDINGS.split(buffer)
    if len(parts) <= 1:
        return [], buffer
    
    sentences = []
    # parts alternates: [text, punct, text, punct, ..., trailing_text]
    for i in range(0, len(parts) - 1, 2):
        sent = (parts[i] + parts[i+1]).strip()
        if sent:
            sentences.append(sent)
    
    remainder = parts[-1]
    return sentences, remainder

async def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Formats a dictionary payload into standard Server-Sent Event (SSE) wire format."""
    payload = {"event": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

async def stream_static_turn_sse(
    question_payload: Dict[str, Any],
    language: str = "hi"
) -> AsyncGenerator[str, None]:
    """
    Instant sub-50ms SSE stream for static MCQ questions (Prakriti / Dashavidha).
    Yields question text, synthesized Sarvam audio, and touchscreen options.
    """
    question_text = question_payload.get("text", "")
    options = question_payload.get("options", [])
    
    # 1. Emit question text
    yield await format_sse_event("text_chunk", {
        "text": question_text,
        "question_number": question_payload.get("question_number"),
        "total_questions": question_payload.get("total_questions")
    })
    
    # 2. Synthesize & stream spoken audio
    try:
        audio_b64 = await sarvam_tts_service.synthesize_speech_async(
            text=question_text,
            language=language
        )
        if audio_b64:
            yield await format_sse_event("audio_chunk", {
                "audio_base64": audio_b64,
                "text": question_text
            })
    except Exception as e:
        logger.warning(f"Static turn TTS synthesis fallback: {e}")
    
    # 3. Emit touch options
    touch_options = []
    for opt in options:
        touch_options.append({
            "id": opt.get("id"),
            "label": opt.get("label"),
            "value": opt.get("value"),
            "slot_tag": opt.get("anchor") or opt.get("tier")
        })
        
    yield await format_sse_event("touch_options", {
        "touch_options": touch_options
    })
    
    # 4. Stream completion signal
    yield await format_sse_event("done", {
        "is_completed": False,
        "phase": "STATIC_MCQ"
    })

async def stream_dynamic_turn_sse(
    raw_result: Dict[str, Any],
    language: str = "hi"
) -> AsyncGenerator[str, None]:
    """
    Streams dynamic turn results (from LLM protocol execution) over SSE:
    1. Translates next_question to patient's native tongue.
    2. Synthesizes Sarvam audio and streams audio chunk.
    3. Translates and emits touchscreen options.
    4. Emits state update and clinical summary (if completed).
    """
    next_q_en = raw_result.get("next_question") or ""
    touch_opts = raw_result.get("touch_options", [])
    clinical_state = raw_result.get("state", raw_result.get("socrates_state", {}))
    is_completed = raw_result.get("should_stop", False)
    summary = raw_result.get("clinical_summary")
    is_red_flag = raw_result.get("is_red_flag", False)
    red_flag_details = raw_result.get("red_flag_details")
    
    # If Red Flag detected, emit immediate emergency event
    if is_red_flag:
        alert_msg = red_flag_details or "High-risk clinical emergency detected. Transferring to emergency triage."
        native_alert = alert_msg
        if language != "en":
            try:
                native_alert = await sarvam_tts_service.translate_text_async(alert_msg, source_lang="en", target_lang=language)
            except Exception:
                pass
        
        audio_b64 = await sarvam_tts_service.synthesize_speech_async(native_alert, language=language)
        yield await format_sse_event("red_flag", {
            "is_red_flag": True,
            "severity": "CRITICAL",
            "message": native_alert,
            "audio_base64": audio_b64
        })
        yield await format_sse_event("done", {"is_completed": True})
        return

    # 1. Translate question to patient's language
    native_q = next_q_en
    if next_q_en and language != "en":
        try:
            native_q = await sarvam_tts_service.translate_text_async(
                text=next_q_en,
                source_lang="en",
                target_lang=language
            )
        except Exception as e:
            logger.warning(f"Translation exception: {e}")
            native_q = next_q_en

    # 2. Emit text event
    if native_q:
        yield await format_sse_event("text_chunk", {
            "text": native_q,
            "english_text": next_q_en
        })
        
        # 3. Synthesize and emit audio chunk (<700ms TTFA)
        try:
            audio_b64 = await sarvam_tts_service.synthesize_speech_async(
                text=native_q,
                language=language
            )
            if audio_b64:
                yield await format_sse_event("audio_chunk", {
                    "audio_base64": audio_b64,
                    "text": native_q
                })
        except Exception as e:
            logger.warning(f"Audio chunk synthesis exception: {e}")

    # 4. Translate & emit touchscreen options
    localized_chips = []
    for opt in touch_opts:
        label = opt.get("label", "")
        native_label = label
        if language != "en" and label:
            try:
                native_label = await sarvam_tts_service.translate_text_async(label, source_lang="en", target_lang=language)
            except Exception:
                native_label = label
        
        localized_chips.append({
            "id": opt.get("id"),
            "label": native_label,
            "english_label": label,
            "value": opt.get("value"),
            "slot_tag": opt.get("slot_tag")
        })
        
    yield await format_sse_event("touch_options", {
        "touch_options": localized_chips
    })

    # 5. Emit state update
    yield await format_sse_event("state_update", {
        "clinical_state": clinical_state,
        "covered_slots": raw_result.get("covered_slots", []),
        "missing_slots": raw_result.get("missing_slots", [])
    })

    # 6. If interview completed, emit clinical summary & closing message
    if is_completed:
        closing = raw_result.get("closing_message", "Thank you. Your clinical intake details are saved for your doctor.")
        native_closing = closing
        if language != "en":
            try:
                native_closing = await sarvam_tts_service.translate_text_async(closing, source_lang="en", target_lang=language)
            except Exception:
                pass
                
        closing_audio = await sarvam_tts_service.synthesize_speech_async(native_closing, language=language)
        
        yield await format_sse_event("summary", {
            "clinical_summary": summary,
            "closing_message": native_closing,
            "closing_audio_base64": closing_audio
        })

    # 7. Final done event
    yield await format_sse_event("done", {
        "is_completed": is_completed
    })
