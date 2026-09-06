from typing import Optional, Dict, Any
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.asr.sarvam_asr_client import SarvamASRClient
from app.ai.asr.safety import ASRSafetyEvaluator, ASRSafetyResult, SPEAK_AGAIN_PROMPTS
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice ASR / TTS"])
sarvam_asr = SarvamASRClient()


class VoiceASRResponse(BaseModel):
    """
    Standardized response for MediKiosk Voice ASR endpoint with clinical safety guardrails.
    """
    status: str = Field(..., description="'success' or 'retry_required'")
    success: bool = Field(..., description="True if transcription succeeded and passed confidence threshold")
    provider: str = Field("sarvam_ai", description="Underlying ASR provider")
    model: str = Field(..., description="Model identifier used")
    language: str = Field(..., description="Detected or provided language BCP-47 code")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score [0.0 - 1.0]")
    threshold: float = Field(..., description="Confidence threshold used for evaluation")
    requires_retry: bool = Field(..., description="True if patient should be asked to speak again")
    failure_reason: Optional[str] = Field(
        None,
        description="Reason for failure: 'silence_detected', 'empty_transcription', 'low_confidence', 'repetitive_hallucination', or None"
    )
    speak_again_prompt: Optional[str] = Field(
        None,
        description="Localized polite clinical prompt asking patient to speak again"
    )
    speak_again_prompt_en: Optional[str] = Field(
        None,
        description="English reference retry prompt"
    )
    transcription: str = Field(default="", description="Original native language transcript")
    english_transcription: Optional[str] = Field(default="", description="Translated English transcript")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic acoustic & lexical metrics")


@router.post("/asr", response_model=VoiceASRResponse)
async def speech_to_text(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, webm, etc.)"),
    language: str = Form("unknown", description="Language code: 'unknown' (auto-detect), 'en-IN', 'hi-IN', 'mr-IN', etc."),
    threshold: Optional[float] = Form(None, description="Custom confidence threshold [0.0 - 1.0]. Defaults to system ASR_CONFIDENCE_THRESHOLD.")
):
    """
    Accepts patient audio and returns transcription using Sarvam AI Saaras model.
    Includes clinical safety feature: calculates confidence score and triggers speak-again
    guardrail if confidence falls below the specified threshold or speech is inaudible.
    """
    applied_threshold = threshold if threshold is not None else settings.ASR_CONFIDENCE_THRESHOLD

    try:
        audio_bytes = await audio.read()
        if not audio_bytes or len(audio_bytes) < 44:
            # Handle empty audio recording gracefully with a speak-again directive
            return VoiceASRResponse(
                status="retry_required",
                success=False,
                provider="sarvam_ai",
                model=settings.SARVAM_STT_MODEL,
                language=language if language != "unknown" else "hi-IN",
                confidence_score=0.0,
                threshold=applied_threshold,
                requires_retry=True,
                failure_reason="silence_detected",
                speak_again_prompt=ASRSafetyEvaluator.get_speak_again_prompt(language),
                speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
                transcription="",
                english_transcription="",
                metrics={"note": "Audio file was empty or missing bytes"}
            )

        # Sanitize language form input
        if language in ["string", "", "null", "none"]:
            language = "unknown"

        result = await sarvam_asr.transcribe_async(
            audio_bytes=audio_bytes,
            filename=audio.filename or "patient_voice.wav",
            language=language,
            translate_english=True,
            threshold=applied_threshold
        )

        safety: ASRSafetyResult = result["safety"]

        return VoiceASRResponse(
            status="success" if safety.passed else "retry_required",
            success=safety.passed,
            provider="sarvam_ai",
            model=settings.SARVAM_STT_MODEL,
            language=result["language_code"],
            confidence_score=safety.confidence_score,
            threshold=safety.threshold,
            requires_retry=safety.requires_retry,
            failure_reason=safety.failure_reason,
            speak_again_prompt=safety.speak_again_prompt if safety.requires_retry else None,
            speak_again_prompt_en=safety.speak_again_prompt_en if safety.requires_retry else None,
            transcription=result["transcript"],
            english_transcription=result["english_transcript"],
            metrics=safety.metrics
        )

    except Exception as e:
        logger.error(f"Sarvam ASR execution error: {str(e)}", exc_info=True)
        # Fallback safety response so the kiosk UI can instruct patient to speak again
        return VoiceASRResponse(
            status="retry_required",
            success=False,
            provider="sarvam_ai",
            model=settings.SARVAM_STT_MODEL,
            language=language if language != "unknown" else "hi-IN",
            confidence_score=0.0,
            threshold=applied_threshold,
            requires_retry=True,
            failure_reason="asr_service_failure",
            speak_again_prompt=ASRSafetyEvaluator.get_speak_again_prompt(language),
            speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
            transcription="",
            english_transcription="",
            metrics={"error": str(e)}
        )
