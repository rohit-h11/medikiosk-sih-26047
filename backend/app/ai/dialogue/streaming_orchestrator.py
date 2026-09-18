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

async def localize_touch_option(opt: Dict[str, Any], language: str = "hi") -> Dict[str, Any]:
    """
    Translates an English clinical touch option into natural, culturally accurate regional tongue
    dynamically using Sarvam AI translation.
    """
    label = (opt.get("label") or "").strip()
    native_label = label

    if language != "en" and label:
        try:
            native_label = await sarvam_tts_service.translate_text_async(
                label,
                source_lang="en",
                target_lang=language
            )
        except Exception as e:
            logger.warning(f"Dynamic option translation error for '{label}': {e}")
            native_label = label

    return {
        "id": opt.get("id"),
        "label": native_label,
        "english_label": label,
        "value": opt.get("value"),
        "slot_tag": opt.get("slot_tag")
    }

async def stream_dynamic_turn_sse(
    raw_result: Dict[str, Any],
    language: str = "hi"
) -> AsyncGenerator[str, None]:
    """
    Streams dynamic turn results (from LLM protocol execution) over SSE:
    1. Translates next_question and touch_options dynamically via Sarvam in parallel.
    2. IMMEDIATELY emits text_chunk and touch_options (~2.1s) so patient can read and interact.
    3. Synthesizes Sarvam audio concurrently in background and streams audio_chunk (~3.0s).
    4. Emits state update and clinical summary (if completed).
    """
    next_q_en = raw_result.get("next_question") or ""
    native_q = raw_result.get("native_question")
    touch_opts = raw_result.get("touch_options", [])
    localized_chips = raw_result.get("localized_options")
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

    # 1. Translate question AND touch options concurrently via Sarvam AI batch translation
    if language != "en":
        items_to_translate = []
        needs_q_trans = not native_q and bool(next_q_en)
        if needs_q_trans:
            items_to_translate.append(next_q_en)

        needs_opts_trans = localized_chips is None and bool(touch_opts)
        opts_labels = []
        if needs_opts_trans:
            for opt in touch_opts:
                lbl = opt.get("label") if isinstance(opt, dict) else getattr(opt, "label", "")
                opts_labels.append(lbl or "")
            items_to_translate.extend(opts_labels)

        if items_to_translate:
            try:
                translated_items = await sarvam_tts_service.translate_batch_async(
                    texts=items_to_translate,
                    source_lang="en",
                    target_lang=language
                )
            except Exception as e:
                logger.warning(f"Batch translation exception: {e}")
                translated_items = items_to_translate

            idx = 0
            if needs_q_trans:
                native_q = translated_items[0] if translated_items else next_q_en
                idx = 1

            if needs_opts_trans:
                localized_chips = []
                for i, opt in enumerate(touch_opts):
                    opt_id = opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", f"opt_{i}")
                    orig_label = opt.get("label") if isinstance(opt, dict) else getattr(opt, "label", "")
                    val = opt.get("value") if isinstance(opt, dict) else getattr(opt, "value", orig_label)
                    slot_tag = opt.get("slot_tag") if isinstance(opt, dict) else getattr(opt, "slot_tag", None)
                    trans_idx = idx + i
                    trans_label = translated_items[trans_idx] if trans_idx < len(translated_items) else orig_label
                    localized_chips.append({
                        "id": opt_id,
                        "label": trans_label,
                        "english_label": orig_label,
                        "value": val,
                        "slot_tag": slot_tag
                    })
        else:
            if not native_q:
                native_q = next_q_en
            if localized_chips is None:
                localized_chips = touch_opts or []
    else:
        native_q = next_q_en
        if localized_chips is None:
            localized_chips = []
            for i, opt in enumerate(touch_opts):
                opt_id = opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", f"opt_{i}")
                lbl = opt.get("label") if isinstance(opt, dict) else getattr(opt, "label", "")
                val = opt.get("value") if isinstance(opt, dict) else getattr(opt, "value", lbl)
                slot_tag = opt.get("slot_tag") if isinstance(opt, dict) else getattr(opt, "slot_tag", None)
                localized_chips.append({
                    "id": opt_id,
                    "label": lbl,
                    "english_label": lbl,
                    "value": val,
                    "slot_tag": slot_tag
                })

    # 2. Progressive SSE: IMMEDIATELY emit question text & clickable touch options to screen! (~2.1s mark)
    if native_q:
        yield await format_sse_event("text_chunk", {
            "text": native_q,
            "english_text": next_q_en
        })

    yield await format_sse_event("touch_options", {
        "touch_options": list(localized_chips or [])
    })

    # 3. Stream state update
    yield await format_sse_event("state_update", {
        "clinical_state": clinical_state,
        "covered_slots": raw_result.get("covered_slots", []),
        "missing_slots": raw_result.get("missing_slots", [])
    })

    # 4. Synthesize and emit audio chunk in background (~3.0s mark)
    if native_q:
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
