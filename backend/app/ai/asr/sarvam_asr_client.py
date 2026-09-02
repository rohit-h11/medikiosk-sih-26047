# backend/app/ai/asr/sarvam_asr_client.py
import httpx
from typing import Optional, Dict, Any
from app.config import settings

class SarvamASRClient:
    """
    Client for Sarvam AI Speech-to-Text (Saarika model) and Translation (Mayura model) APIs.
    Supports Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu, and Indian English.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.model = model or getattr(settings, "SARVAM_STT_MODEL", "saarika:v2.5")
        self.stt_url = "https://api.sarvam.ai/speech-to-text"
        self.translate_url = "https://api.sarvam.ai/translate"

    def _normalize_lang_code(self, lang: str) -> str:
        """Converts short ISO code ('hi') to Sarvam format ('hi-IN') or 'unknown' for auto."""
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
            "od": "od-IN",
            "auto": "unknown",
            "unknown": "unknown"
        }
        return mapping.get(lang.lower(), lang if "-" in lang else f"{lang}-IN")

    def translate_to_english(self, text: str, source_language_code: str = "hi-IN") -> str:
        """Translates text to English using Sarvam's Mayura model."""
        if not text or not text.strip():
            return ""
        if source_language_code.lower().startswith("en"):
            return text

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "MediKiosk-Speech-Engine/1.0",
            "Accept": "application/json"
        }
        payload = {
            "input": text,
            "source_language_code": self._normalize_lang_code(source_language_code),
            "target_language_code": "en-IN",
            "speaker_gender": "Male",
            "mode": "formal",
            "model": "mayura:v1"
        }

        with httpx.Client(timeout=30.0, verify=True) as client:
            res = client.post(self.translate_url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json().get("translated_text", text)
            return text

    async def translate_to_english_async(self, text: str, source_language_code: str = "hi-IN") -> str:
        """Async version of translate_to_english."""
        if not text or not text.strip():
            return ""
        if source_language_code.lower().startswith("en"):
            return text

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "MediKiosk-Speech-Engine/1.0",
            "Accept": "application/json"
        }
        payload = {
            "input": text,
            "source_language_code": self._normalize_lang_code(source_language_code),
            "target_language_code": "en-IN",
            "speaker_gender": "Male",
            "mode": "formal",
            "model": "mayura:v1"
        }

        async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
            res = await client.post(self.translate_url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json().get("translated_text", text)
            return text

    async def transcribe_async(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "unknown",
        translate_english: bool = True
    ) -> Dict[str, Any]:
        """
        Async transcription + English translation for FastAPI endpoints.
        """
        if not self.api_key:
            self.api_key = settings.SARVAM_API_KEY
            if not self.api_key:
                raise ValueError("SARVAM_API_KEY is not configured.")

        lang_code = self._normalize_lang_code(language)
        headers = {
            "api-subscription-key": self.api_key,
            "User-Agent": "MediKiosk-Speech-Engine/1.0",
            "Accept": "application/json"
        }
        files = {"file": (filename, audio_bytes, "audio/wav")}
        data = {
            "model": self.model,
            "language_code": lang_code,
            "with_diarization": "false"
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(self.stt_url, headers=headers, files=files, data=data)
            if response.status_code != 200:
                raise RuntimeError(f"Sarvam API Error ({response.status_code}): {response.text}")
            
            result = response.json()
            raw_transcript = result.get("transcript", "").strip()
            detected_lang = result.get("language_code", lang_code)

            english_transcript = raw_transcript
            if translate_english and raw_transcript:
                src_lang = detected_lang if detected_lang != "unknown" else "hi-IN"
                english_transcript = await self.translate_to_english_async(raw_transcript, src_lang)

            return {
                "transcript": raw_transcript,
                "english_transcript": english_transcript,
                "language_code": detected_lang
            }
