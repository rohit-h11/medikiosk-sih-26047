import os
import tempfile
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LocalWhisperASRService:
    """
    Self-Hosted ASR Service using faster-whisper (CTranslate2 engine).
    Supports 99+ languages with built-in language auto-detection and direct translation.
    """
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[Any] = None

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading local faster-whisper model '{self.model_size}' on {self.device} ({self.compute_type})...")
                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
                logger.info("faster-whisper model loaded successfully!")
            except ImportError:
                raise RuntimeError("faster-whisper is not installed. Please install faster-whisper or use Sarvam AI / Groq Whisper.")
        return self._model

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,  # If None, automatically detects language!
        task: str = "transcribe",        # 'transcribe' or 'translate' (directly to English)
        audio_format: str = "wav"
    ) -> Dict[str, Any]:
        """
        Transcribes or translates audio bytes locally.
        
        Args:
            audio_bytes: Raw audio binary data.
            language: Optional language code (e.g. 'hi', 'ta', 'en'). If None, AUTO-DETECTS!
            task: 'transcribe' (native text) or 'translate' (translates to English).
            audio_format: Audio file format hint.
            
        Returns:
            Dict containing transcript, detected language, confidence, and segments.
        """
        temp_file_path = None
        try:
            # Create temporary file to pass to faster-whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as temp_audio:
                temp_audio.write(audio_bytes)
                temp_file_path = temp_audio.name

            model = self._get_model()

            # Perform transcription / auto-detection
            segments, info = model.transcribe(
                temp_file_path,
                language=language,  # None triggers automatic language identification
                task=task,
                beam_size=5
            )

            # Collect all text segments
            segment_list = []
            full_transcript = []
            for segment in segments:
                segment_list.append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip()
                })
                full_transcript.append(segment.text.strip())

            transcript_text = " ".join(full_transcript)

            return {
                "success": True,
                "transcript": transcript_text,
                "detected_language": info.language,
                "language_probability": round(info.language_probability, 4),
                "duration": round(info.duration, 2),
                "segments": segment_list,
                "task": task,
                "is_mock": False
            }

        except Exception as exc:
            logger.error(f"Error during local faster-whisper transcription: {str(exc)}")
            return {
                "success": False,
                "transcript": "",
                "detected_language": language or "unknown",
                "error": str(exc),
                "is_mock": False
            }
        finally:
            # Clean up temp audio file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

local_whisper_service = LocalWhisperASRService(model_size="small")
