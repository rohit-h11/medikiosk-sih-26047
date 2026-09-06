# backend/app/ai/asr/safety.py
"""
ASR Safety Guardrail & Confidence Scoring Engine for MediKiosk.

Evaluates acoustic signal quality, lexical coherence, and model probabilities.
If the confidence score falls below a clinical threshold, it flags the turn for retry
and returns localized polite prompts asking the patient to speak again.
"""

import io
import math
import wave
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Standardized clinical kiosk retry prompts across Indian languages + English
SPEAK_AGAIN_PROMPTS = {
    "en": "We couldn't hear you clearly. Please speak again closer to the microphone.",
    "hi": "आपकी आवाज़ स्पष्ट नहीं सुनाई दी। कृपया माइक्रोफ़ोन के पास आकर दोबारा बोलें।",
    "mr": "तुमचा आवाज स्पष्ट ऐकू आला नाही. कृपया मायक्रोफोनजवळ येऊन पुन्हा बोला.",
    "bn": "আপনার কথা স্পষ্ট শোনা যায়নি। অনুগ্রহ করে মাইক্রোফোনের কাছে এসে আবার বলুন।",
    "ta": "உங்கள் குரல் தெளிவாகக் கேட்கவில்லை. தயவுசெய்து மைக்ரோஃபோனுக்கு அருகில் வந்து மீண்டும் பேசுங்கள்.",
    "te": "మీ గొంతు స్పష్టంగా వినిపించలేదు. దయచేసి మైక్రోఫోన్ దగ్గరకు వచ్చి మళ్లీ మాట్లాడండి.",
    "gu": "તમારો અવાજ સ્પષ્ટ સંભળાયો નથી. કૃપા કરીને માઇક્રોફોનની નજીક આવીને ફરીથી બોલો.",
    "kn": "ನಿಮ್ಮ ಧ್ವನಿ ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮೈಕ್ರೊಫೋನ್ ಹತ್ತಿರ ಬಂದು ಮತ್ತೆ ಮಾತನಾಡಿ.",
    "ml": "നിങ്ങളുടെ ശബ്ദം വ്യക്തമായി കേൾക്കാൻ കഴിഞ്ഞില്ല. ദയവായി മൈക്രോഫോണിന് അടുത്തേക്ക് വന്ന് വീണ്ടും സംസാരിക്കുക.",
    "pa": "ਤੁਹਾਡੀ ਆਵਾਜ਼ ਸਾਫ਼ ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤੀ। ਕਿਰਪਾ ਕਰਕੇ ਮਾਈਕ੍ਰੋਫੋਨ ਦੇ ਨੇੜੇ ਆ ਕੇ ਦੁਬਾਰਾ ਬੋਲੋ।",
    "od": "ଆପଣଙ୍କ ସ୍ୱର ସ୍ପଷ୍ଟ ଶୁଣାଗଲା ନାହିଁ। ଦୟାକରି ମାଇକ୍ରୋଫୋନ ପାଖକୁ ଆସି ପୁଣି କୁହନ୍ତୁ।"
}


class ASRSafetyResult(BaseModel):
    """Result of the ASR safety and confidence evaluation."""
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Normalized confidence score [0.0 - 1.0]")
    threshold: float = Field(..., description="Applied confidence threshold")
    passed: bool = Field(..., description="True if confidence >= threshold and speech was intelligible")
    requires_retry: bool = Field(..., description="True if patient needs to be asked to speak again")
    failure_reason: Optional[str] = Field(None, description="'silence_detected', 'empty_transcription', 'low_confidence', 'repetitive_hallucination', or None")
    speak_again_prompt: str = Field(..., description="Localized retry message in patient's detected/chosen language")
    speak_again_prompt_en: str = Field(..., description="English reference retry message")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic metrics (acoustic, lexical, model)")


class ASRSafetyEvaluator:
    """
    Evaluates Speech-to-Text outputs against clinical safety guardrails.
    """

    @staticmethod
    def get_speak_again_prompt(lang_code: Optional[str] = None) -> str:
        """Resolves localized speak-again prompt by language code prefix."""
        if not lang_code:
            return SPEAK_AGAIN_PROMPTS["en"]
        short_code = lang_code.split("-")[0].lower()
        return SPEAK_AGAIN_PROMPTS.get(short_code, SPEAK_AGAIN_PROMPTS["en"])

    @staticmethod
    def analyze_acoustic_signal(audio_bytes: bytes) -> Dict[str, Any]:
        """
        Analyzes raw audio bytes to assess acoustic energy and detect silence.
        Supports WAV containers directly, with graceful heuristics for other containers.
        """
        if not audio_bytes or len(audio_bytes) < 44:
            return {
                "rms": 0.0,
                "is_silent": True,
                "acoustic_score": 0.0,
                "note": "Empty or truncated audio payload"
            }

        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return {"rms": 0.0, "is_silent": True, "acoustic_score": 0.0, "note": "0 audio frames"}

                raw_frames = wf.readframes(n_frames)

                import numpy as np
                if sampwidth == 2:  # 16-bit PCM
                    samples = np.frombuffer(raw_frames, dtype=np.int16)
                elif sampwidth == 1:  # 8-bit PCM unsigned
                    samples = (np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float64) - 128) * 256
                elif sampwidth == 4:  # 32-bit int
                    samples = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float64) / 65536.0
                else:
                    samples = np.frombuffer(raw_frames, dtype=np.int16)

                if len(samples) == 0:
                    return {"rms": 0.0, "is_silent": True, "acoustic_score": 0.0, "note": "Empty samples"}

                rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
                peak = float(np.max(np.abs(samples)))

                # Silence detection: 16-bit max amplitude is 32767.
                # An RMS under 120 indicates ambient microphone hiss or pure silence.
                is_silent = rms < 120.0

                # Acoustic quality score mapped non-linearly to [0.0 - 1.0]
                # RMS 1000+ represents normal conversational push-to-talk volume
                if rms <= 100.0:
                    acoustic_score = 0.0
                elif rms < 500.0:
                    acoustic_score = round(0.3 + 0.4 * ((rms - 100.0) / 400.0), 3)
                elif rms < 3000.0:
                    acoustic_score = round(0.7 + 0.25 * ((rms - 500.0) / 2500.0), 3)
                else:
                    acoustic_score = 0.95

                return {
                    "rms": round(rms, 2),
                    "peak": round(peak, 2),
                    "is_silent": is_silent,
                    "acoustic_score": min(1.0, acoustic_score),
                    "duration_sec": round(n_frames / max(1, wf.getframerate()), 2)
                }
        except Exception as exc:
            # Fallback heuristic for WebM/MP3/Opus when wave.open cannot parse headers
            logger.debug(f"Acoustic parser non-WAV fallback: {exc}")
            import numpy as np
            raw_arr = np.frombuffer(audio_bytes[:min(len(audio_bytes), 32000)], dtype=np.uint8)
            byte_std = float(np.std(raw_arr))
            # Standard deviation of uniform random or speech compressed bytes is typically > 40
            is_silent = byte_std < 5.0
            acoustic_score = 0.85 if not is_silent else 0.0
            return {
                "rms": round(byte_std * 20.0, 2),
                "peak": 1000.0 if not is_silent else 0.0,
                "is_silent": is_silent,
                "acoustic_score": acoustic_score,
                "note": "Container heuristic used"
            }

    @staticmethod
    def analyze_lexical_quality(transcript: str) -> Dict[str, Any]:
        """
        Assesses transcript coherence, repetition, and length.
        Detects hallucination loops (e.g. repeated filler words).
        """
        cleaned = transcript.strip() if transcript else ""
        if not cleaned:
            return {
                "lexical_score": 0.0,
                "word_count": 0,
                "char_count": 0,
                "is_repetitive": False,
                "empty": True
            }

        words = cleaned.split()
        word_count = len(words)
        char_count = len(cleaned)

        # Single word or very short noise character (e.g. ".", "ah")
        if char_count <= 2:
            return {
                "lexical_score": 0.2,
                "word_count": word_count,
                "char_count": char_count,
                "is_repetitive": False,
                "empty": False
            }

        # Check for repetition hallucination loops
        is_repetitive = False
        if word_count >= 4:
            unique_ratio = len(set(w.lower() for w in words)) / word_count
            if unique_ratio < 0.4:
                is_repetitive = True

        if is_repetitive:
            lexical_score = 0.25
        elif word_count == 1:
            lexical_score = 0.70
        elif word_count in [2, 3]:
            lexical_score = 0.85
        else:
            lexical_score = 0.95

        return {
            "lexical_score": lexical_score,
            "word_count": word_count,
            "char_count": char_count,
            "is_repetitive": is_repetitive,
            "empty": False
        }

    @classmethod
    def evaluate(
        cls,
        audio_bytes: bytes,
        transcript: str,
        model_probability: Optional[float] = None,
        language_code: Optional[str] = None,
        threshold: float = 0.65
    ) -> ASRSafetyResult:
        """
        Performs full safety and confidence scoring evaluation on an ASR turn.
        """
        acoustic = cls.analyze_acoustic_signal(audio_bytes)
        lexical = cls.analyze_lexical_quality(transcript)

        # 1. Immediate Failure Case: Silence / Inaudible Audio
        if acoustic["is_silent"]:
            return ASRSafetyResult(
                confidence_score=0.0,
                threshold=threshold,
                passed=False,
                requires_retry=True,
                failure_reason="silence_detected",
                speak_again_prompt=cls.get_speak_again_prompt(language_code),
                speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
                metrics={"acoustic": acoustic, "lexical": lexical, "model_probability": model_probability}
            )

        # 2. Immediate Failure Case: Empty transcription
        if lexical["empty"]:
            return ASRSafetyResult(
                confidence_score=0.0,
                threshold=threshold,
                passed=False,
                requires_retry=True,
                failure_reason="empty_transcription",
                speak_again_prompt=cls.get_speak_again_prompt(language_code),
                speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
                metrics={"acoustic": acoustic, "lexical": lexical, "model_probability": model_probability}
            )

        # 3. Immediate Failure Case: Severe Hallucination Loop
        if lexical["is_repetitive"]:
            confidence = round(0.25 * (model_probability or 0.5) + 0.1, 3)
            return ASRSafetyResult(
                confidence_score=confidence,
                threshold=threshold,
                passed=False,
                requires_retry=True,
                failure_reason="repetitive_hallucination",
                speak_again_prompt=cls.get_speak_again_prompt(language_code),
                speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
                metrics={"acoustic": acoustic, "lexical": lexical, "model_probability": model_probability}
            )

        # 4. Multi-Factor Confidence Calculation
        # If model_probability is provided (e.g. Sarvam language_probability / Whisper probability)
        if model_probability is not None and model_probability > 0.0:
            model_score = max(0.0, min(1.0, float(model_probability)))
            # Blended: 50% model confidence + 30% acoustic quality + 20% lexical quality
            raw_confidence = (0.50 * model_score) + (0.30 * acoustic["acoustic_score"]) + (0.20 * lexical["lexical_score"])
        else:
            # Fallback when model did not return confidence: 60% acoustic + 40% lexical
            raw_confidence = (0.60 * acoustic["acoustic_score"]) + (0.40 * lexical["lexical_score"])

        confidence_score = round(max(0.0, min(1.0, raw_confidence)), 3)
        passed = confidence_score >= threshold
        requires_retry = not passed
        failure_reason = None if passed else "low_confidence"

        return ASRSafetyResult(
            confidence_score=confidence_score,
            threshold=threshold,
            passed=passed,
            requires_retry=requires_retry,
            failure_reason=failure_reason,
            speak_again_prompt=cls.get_speak_again_prompt(language_code),
            speak_again_prompt_en=SPEAK_AGAIN_PROMPTS["en"],
            metrics={
                "acoustic": acoustic,
                "lexical": lexical,
                "model_probability": model_probability,
                "calibrated_score": confidence_score
            }
        )
