from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.ai.asr.sarvam_asr_client import SarvamASRClient
from app.config import settings

router = APIRouter(prefix="/voice", tags=["Voice ASR / TTS"])
sarvam_asr = SarvamASRClient()

@router.post("/asr")
async def speech_to_text(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, webm, etc.)"),
    language: str = Form("unknown", description="Language code: 'unknown' (auto-detect), 'en-IN', 'hi-IN', 'mr-IN', etc.")
):
    """
    Accepts patient audio and returns transcription using Sarvam AI Saaras model.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio recording.")

        result = await sarvam_asr.transcribe_async(
            audio_bytes=audio_bytes,
            filename=audio.filename or "patient_voice.wav",
            language=language,
            translate_english=True
        )

        return {
            "status": "success",
            "provider": "sarvam_ai",
            "model": settings.SARVAM_STT_MODEL,
            "language": result["language_code"],
            "transcription": result["transcript"],
            "english_transcription": result["english_transcript"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam ASR error: {str(e)}")
