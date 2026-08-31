import logging
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

class GroqWhisperASRService:
    """
    Cloud-accelerated Whisper ASR using Groq's ultra-fast LPU engine.
    Uses 'whisper-large-v3-turbo' (1.5 Billion parameters) for extremely high accuracy in 99+ languages.
    Requires FREE GROQ_API_KEY from https://console.groq.com
    """

    @property
    def is_configured(self) -> bool:
        return bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.startswith("gsk_"))

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        task: str = "transcribe",
        audio_format: str = "wav"
    ) -> Dict[str, Any]:
        if not self.is_configured:
            return {
                "success": False,
                "transcript": "",
                "error": "GROQ_API_KEY is not configured in .env file."
            }

        try:
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}"
            }

            files = {
                "file": (f"audio.{audio_format}", audio_bytes, f"audio/{audio_format}")
            }

            data = {
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json"
            }

            if language:
                data["language"] = language

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(GROQ_AUDIO_URL, headers=headers, files=files, data=data)
                response.raise_for_status()
                res_data = response.json()

            transcript = res_data.get("text", "").strip()
            detected_lang = res_data.get("language", language or "unknown")

            return {
                "success": True,
                "transcript": transcript,
                "detected_language": detected_lang,
                "task": task,
                "is_mock": False
            }

        except httpx.HTTPStatusError as exc:
            error_details = exc.response.text
            logger.error(f"Groq HTTP Error {exc.response.status_code}: {error_details}")
            return {
                "success": False,
                "transcript": "",
                "error": f"Groq HTTP Error {exc.response.status_code}: {error_details}",
                "is_mock": False
            }
        except Exception as exc:
            logger.error(f"Error during Groq Whisper transcription: {str(exc)}")
            return {
                "success": False,
                "transcript": "",
                "error": str(exc),
                "is_mock": False
            }

groq_whisper_service = GroqWhisperASRService()
