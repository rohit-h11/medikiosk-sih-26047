# backend/app/ai/asr/sarvam_tts_client.py
import base64
import logging
import httpx
from typing import Optional, Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)

class SarvamTTSClient:
    """
    Client for Sarvam AI Text-to-Speech (Bulbul models) and Translation (Mayura model).
    Supports 11 Indian languages: Hindi (hi-IN), Bengali (bn-IN), Gujarati (gu-IN),
    Kannada (kn-IN), Malayalam (ml-IN), Marathi (mr-IN), Odia (od-IN), Punjabi (pa-IN),
    Tamil (ta-IN), Telugu (te-IN), and Indian English (en-IN).
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.tts_model = model or "bulbul:v3"
        self.tts_url = "https://api.sarvam.ai/text-to-speech"
        self.translate_url = "https://api.sarvam.ai/translate"

    @property
    def is_configured(self) -> bool:
        """Check if Sarvam API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def _normalize_lang_code(self, lang: str) -> str:
        """Converts short ISO code ('hi') to Sarvam format ('hi-IN')."""
        if not lang or lang.lower() in ["unknown", "auto"]:
            return "hi-IN"
        lang_lower = lang.lower().strip()
        mapping = {
            "hi": "hi-IN",
            "en": "en-IN",
            "mr": "mr-IN",
            "ta": "ta-IN",
            "te": "te-IN",
            "bn": "bn-IN",
            "gu": "gu-IN",
            "kn": "kn-IN",
            "ml": "ml-IN",
            "pa": "pa-IN",
            "or": "od-IN",
            "od": "od-IN",
            "as": "bn-IN", # Assamese fallback to Bengali phonetics if needed
        }
        if lang_lower in mapping:
            return mapping[lang_lower]
        return lang if "-" in lang else f"{lang}-IN"

    async def translate_text_async(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi"
    ) -> str:
        """
        Translates text between English and Indian languages using Sarvam Mayura model.
        """
        if not text or not text.strip():
            return ""

        src_code = self._normalize_lang_code(source_lang)
        tgt_code = self._normalize_lang_code(target_lang)

        # If source and target are the same, return as is
        if src_code == tgt_code:
            return text

        if not self.is_configured:
            logger.warning("SARVAM_API_KEY not configured. Skipping translation.")
            return text

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "MediKiosk-Speech-Engine/1.0",
            "Accept": "application/json"
        }
        payload = {
            "input": text,
            "source_language_code": src_code,
            "target_language_code": tgt_code,
            "speaker_gender": "Female",
            "mode": "formal",
            "model": "mayura:v1"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
                res = await client.post(self.translate_url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("translated_text", text)
                logger.error(f"Sarvam Translation error ({res.status_code}): {res.text}")
                return text
        except Exception as e:
            logger.error(f"Sarvam translation exception: {e}")
            return text

    async def text_to_speech_async(
        self,
        text: str,
        language: str = "hi",
        speaker: str = "priya", # 'priya', 'kavya', 'shreya', 'aditya', 'rahul', 'neha'
        sample_rate: int = 16000,
        pace: float = 1.0
    ) -> Dict[str, Any]:
        """
        Synthesizes text into spoken audio using Sarvam Bulbul model.

        Returns:
            Dict with:
            - success (bool)
            - audio_base64 (str)
            - audio_bytes (bytes)
            - format ("wav")
            - language_code (str)
            - error (Optional[str])
        """
        if not text or not text.strip():
            return {
                "success": False,
                "audio_base64": None,
                "audio_bytes": None,
                "format": "wav",
                "error": "Input text is empty."
            }

        if not self.is_configured:
            logger.warning("SARVAM_API_KEY not configured. Operating in fallback mock mode.")
            return {
                "success": False,
                "audio_base64": None,
                "audio_bytes": None,
                "format": "wav",
                "error": "SARVAM_API_KEY is not configured in backend/.env."
            }

        lang_code = self._normalize_lang_code(language)
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "MediKiosk-Speech-Engine/1.0",
            "Accept": "application/json"
        }

        # Truncate to 500 characters if input is too long for single utterance
        clean_text = text.strip()[:500]

        payload = {
            "inputs": [clean_text],
            "target_language_code": lang_code,
            "speaker": speaker,
            "pace": pace,
            "speech_sample_rate": sample_rate,
            "enable_preprocessing": True,
            "model": self.tts_model
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(self.tts_url, headers=headers, json=payload)
                if res.status_code != 200:
                    logger.error(f"Sarvam TTS Error ({res.status_code}): {res.text}")
                    return {
                        "success": False,
                        "audio_base64": None,
                        "audio_bytes": None,
                        "format": "wav",
                        "error": f"Sarvam TTS API Error: {res.text}"
                    }

                data = res.json()
                audios: List[str] = data.get("audios", [])
                if not audios or not audios[0]:
                    return {
                        "success": False,
                        "audio_base64": None,
                        "audio_bytes": None,
                        "format": "wav",
                        "error": "No audio returned from Sarvam TTS."
                    }

                b64_audio = audios[0]
                audio_bytes = base64.b64decode(b64_audio)

                return {
                    "success": True,
                    "audio_base64": b64_audio,
                    "audio_bytes": audio_bytes,
                    "format": "wav",
                    "sample_rate": sample_rate,
                    "language_code": lang_code,
                    "error": None
                }

        except Exception as e:
            logger.error(f"Sarvam TTS exception: {str(e)}")
            return {
                "success": False,
                "audio_base64": None,
                "audio_bytes": None,
                "format": "wav",
                "error": f"Sarvam TTS failed: {str(e)}"
            }

sarvam_tts_service = SarvamTTSClient()
