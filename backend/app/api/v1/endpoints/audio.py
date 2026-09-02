import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel
from app.ai.asr import bhashini_asr_service, local_whisper_service, groq_whisper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio & Speech Recognition"])


class TranscribeResponse(BaseModel):
    success: bool
    transcript: str
    translated_text: Optional[str] = None
    language: str
    target_language: Optional[str] = None
    is_mock: bool = False
    error: Optional[str] = None


class LocalWhisperResponse(BaseModel):
    success: bool
    transcript: str
    detected_language: str
    language_probability: float
    duration: float
    segments: List[Dict[str, Any]] = []
    task: str
    error: Optional[str] = None


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio_endpoint(
    file: UploadFile = File(..., description="Audio file binary (.wav, .mp3, .webm, .flac)"),
    language: str = Form("hi", description="Source language ISO code ('hi', 'ta', 'te', 'mr', 'bn', 'en', etc.)"),
    target_language: Optional[str] = Form(None, description="Optional target language for simultaneous translation"),
    audio_format: Optional[str] = Form(None, description="Audio format ('wav', 'webm', 'mp3'). Auto-detected if omitted.")
):
    """
    Transcribes uploaded patient Push-to-Talk audio payload.
    Pipeline priority:
    1. Bhashini ASR API (if credentials present)
    2. Groq Whisper Large v3 (if GROQ_API_KEY present)
    3. Local faster-whisper (Offline engine)
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file must have a filename.")

    audio_bytes = await file.read()
    # Sanitize inputs (Swagger UI defaults optional fields to 'string')
    if language in ["string", "", "null", "none"]:
        language = "hi"
    if target_language in ["string", "", "null", "none"]:
        target_language = None
    if audio_format in ["string", "", "null", "none"]:
        audio_format = None

    if not audio_format:
        ext = file.filename.split(".")[-1].lower()
        audio_format = ext if ext in ["wav", "webm", "mp3", "flac", "ogg"] else "wav"

    # Step 1: Try Bhashini if configured
    if bhashini_asr_service.is_configured:
        result = await bhashini_asr_service.transcribe_audio(
            audio_bytes=audio_bytes,
            source_language=language,
            audio_format=audio_format,
            target_language=target_language
        )
        if result["success"]:
            return TranscribeResponse(
                success=True,
                transcript=result["transcript"],
                translated_text=result.get("translated_text"),
                language=result["language"],
                target_language=result.get("target_language"),
                is_mock=False,
                error=None
            )

    # Step 2: Try Groq Whisper (Whisper-Large-v3-Turbo) if configured
    if groq_whisper_service.is_configured:
        logger.info("Calling Groq Whisper-Large-v3-Turbo API for high-accuracy ASR...")
        groq_res = await groq_whisper_service.transcribe_audio(
            audio_bytes=audio_bytes,
            language=language,
            audio_format=audio_format
        )
        if groq_res["success"]:
            return TranscribeResponse(
                success=True,
                transcript=groq_res["transcript"],
                translated_text=None,
                language=groq_res.get("detected_language", language),
                target_language=target_language,
                is_mock=False,
                error=None
            )

    # Step 3: Fallback to local faster-whisper (Offline engine)
    logger.info("Bhashini/Groq unconfigured. Falling back to local faster-whisper engine.")
    local_result = local_whisper_service.transcribe_audio(
        audio_bytes=audio_bytes,
        language=language if language else None,
        task="transcribe",
        audio_format=audio_format
    )

    return TranscribeResponse(
        success=local_result["success"],
        transcript=local_result["transcript"],
        translated_text=None,
        language=local_result.get("detected_language", language),
        target_language=target_language,
        is_mock=False,
        error=local_result.get("error") if not local_result["success"] else "Local whisper fallback used."
    )


@router.post("/transcribe-local", response_model=LocalWhisperResponse)
async def transcribe_local_endpoint(
    file: UploadFile = File(..., description="Audio file binary (.wav, .mp3, .webm, .flac)"),
    language: Optional[str] = Form(None, description="Optional language ISO code ('hi', 'ta', 'te', 'en'). Leave EMPTY for AUTO-DETECTION!"),
    task: str = Form("transcribe", description="'transcribe' (native spoken language text) or 'translate' (translates directly to English)"),
    audio_format: Optional[str] = Form(None, description="Audio format ('wav', 'webm', 'mp3'). Auto-detected if omitted.")
):
    """
    Transcribes audio offline using local faster-whisper.
    AUTOMATICALLY DETECTS spoken language if language parameter is omitted!
    Supports 'translate' mode to output English clinical text directly.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file must have a filename.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file is empty.")

    # Sanitize inputs (Swagger UI defaults optional fields to 'string')
    if language in ["string", "", "null", "none"]:
        language = None
    if audio_format in ["string", "", "null", "none"]:
        audio_format = None

    if not audio_format:
        ext = file.filename.split(".")[-1].lower()
        audio_format = ext if ext in ["wav", "webm", "mp3", "flac", "ogg"] else "wav"

    # Call local faster-whisper service
    result = local_whisper_service.transcribe_audio(
        audio_bytes=audio_bytes,
        language=language,
        task=task if task in ["transcribe", "translate"] else "transcribe",
        audio_format=audio_format
    )

    return LocalWhisperResponse(
        success=result["success"],
        transcript=result["transcript"],
        detected_language=result.get("detected_language", "unknown"),
        language_probability=result.get("language_probability", 0.0),
        duration=result.get("duration", 0.0),
        segments=result.get("segments", []),
        task=result.get("task", "transcribe"),
        error=result.get("error")
    )
