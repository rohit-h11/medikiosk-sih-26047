import asyncio
import json
import base64
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets

from app.config import settings
from app.ai.asr.sarvam_asr_client import SarvamASRClient

logger = logging.getLogger("medikiosk.ws.speech")
router = APIRouter(prefix="/ws", tags=["Real-time Speech WebSocket"])
sarvam_asr = SarvamASRClient()

def normalize_lang_for_sarvam(lang: str) -> str:
    mapping = {
        "hi": "hi-IN", "en": "en-IN", "mr": "mr-IN", "ta": "ta-IN",
        "te": "te-IN", "bn": "bn-IN", "gu": "gu-IN", "kn": "kn-IN",
        "ml": "ml-IN", "pa": "pa-IN", "od": "od-IN", "as": "as-IN"
    }
    return mapping.get(lang.lower(), f"{lang}-IN" if "-" not in lang else lang)

@router.websocket("/speech")
async def speech_websocket_relay(
    websocket: WebSocket,
    language: str = "hi",
    session_id: Optional[str] = None
):
    """
    Hospital-grade Secure WebSocket Voice Streaming Relay:
    1. Client streams PCM/WAV chunks while speaking without exposing SARVAM_API_KEY.
    2. Backend proxies stream to Sarvam Realtime STT (Saaras model).
    3. Emits 'partial' transcript events in real-time to render spoken words instantly.
    4. Emits 'final' transcript + English translation the moment speaking finishes.
    5. Automatic fallback to batch transcription if realtime connection drops.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for speech stream. lang={language}, session={session_id}")

    sarvam_lang = normalize_lang_for_sarvam(language)
    sarvam_ws_url = f"wss://api.sarvam.ai/speech-to-text-realtime/ws?language_code={sarvam_lang}&model=saaras:v3-realtime"
    headers = {"api-subscription-key": settings.SARVAM_API_KEY}

    accumulated_audio_chunks = []
    latest_final_transcript = ""

    sarvam_ws = None
    try:
        # Establish upstream connection to Sarvam Realtime STT
        try:
            sarvam_ws = await websockets.connect(sarvam_ws_url, additional_headers=headers)
        except TypeError:
            sarvam_ws = await websockets.connect(sarvam_ws_url, extra_headers=headers)
        logger.info("Connected upstream to Sarvam Realtime STT WebSocket.")
    except Exception as e:
        logger.warning(f"Could not connect to Sarvam Realtime WS: {e}. Will rely on fallback batch ASR.")

    # Task to read responses from Sarvam and relay to client
    async def sarvam_listener():
        nonlocal latest_final_transcript
        if not sarvam_ws:
            return
        try:
            async for raw_msg in sarvam_ws:
                try:
                    data = json.loads(raw_msg)
                    evt = data.get("event")
                    
                    if evt == "transcript.partial" or evt == "transcript":
                        text = data.get("transcript") or data.get("text", "")
                        if text:
                            await websocket.send_json({
                                "event": "partial",
                                "transcript": text
                            })
                    elif evt == "transcript.final":
                        text = data.get("transcript") or data.get("text", "")
                        if text:
                            latest_final_transcript = text
                            # Translate final to English
                            english = text
                            if language != "en":
                                try:
                                    english = await sarvam_asr.translate_to_english_async(text, sarvam_lang)
                                except Exception:
                                    pass
                            await websocket.send_json({
                                "event": "final",
                                "native": text,
                                "english": english
                            })
                except Exception as parse_err:
                    logger.debug(f"Sarvam WS message parse error: {parse_err}")
        except asyncio.CancelledError:
            pass
        except Exception as err:
            logger.warning(f"Sarvam WS listener error: {err}")

    listener_task = asyncio.create_task(sarvam_listener()) if sarvam_ws else None

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            # Handle text JSON message
            if "text" in msg and msg["text"]:
                try:
                    payload = json.loads(msg["text"])
                    evt = payload.get("event")
                    if evt == "audio_input":
                        b64_data = payload.get("audio", "")
                        if b64_data:
                            # Forward to Sarvam
                            if sarvam_ws:
                                await sarvam_ws.send(json.dumps({
                                    "event": "audio_input",
                                    "audio": b64_data
                                }))
                            try:
                                accumulated_audio_chunks.append(base64.b64decode(b64_data))
                            except Exception:
                                pass
                    elif evt == "stop":
                        # Client indicates recording stopped
                        logger.info("Client sent stop event.")
                        break
                except json.JSONDecodeError:
                    pass

            # Handle raw binary audio bytes
            elif "bytes" in msg and msg["bytes"]:
                raw_bytes = msg["bytes"]
                accumulated_audio_chunks.append(raw_bytes)
                if sarvam_ws:
                    b64_chunk = base64.b64encode(raw_bytes).decode("utf-8")
                    await sarvam_ws.send(json.dumps({
                        "event": "audio_input",
                        "audio": b64_chunk
                    }))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.warning(f"Error in client WebSocket loop: {e}")
    finally:
        # Cancel listener
        if listener_task:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        if sarvam_ws:
            try:
                await sarvam_ws.close()
            except Exception:
                pass

        # If we didn't receive a final transcript from Sarvam Realtime, or if accumulated audio is available
        if not latest_final_transcript and accumulated_audio_chunks:
            total_audio = b"".join(accumulated_audio_chunks)
            if len(total_audio) > 1000:
                try:
                    logger.info(f"Running fallback batch ASR on {len(total_audio)} bytes...")
                    asr_res = await sarvam_asr.transcribe_async(
                        audio_bytes=total_audio,
                        filename="ws_stream.wav",
                        language=language,
                        translate_english=True
                    )
                    native_text = asr_res.get("transcript", "")
                    en_text = asr_res.get("english_transcript", native_text)
                    if native_text:
                        try:
                            await websocket.send_json({
                                "event": "final",
                                "native": native_text,
                                "english": en_text
                            })
                        except Exception:
                            pass
                except Exception as asr_err:
                    logger.warning(f"Fallback batch ASR error: {asr_err}")

        try:
            await websocket.close()
        except Exception:
            pass
