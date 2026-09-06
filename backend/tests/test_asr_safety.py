import io
import math
import struct
import wave
import sys
from pathlib import Path
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path so 'app' is always resolvable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.config import settings
from app.ai.asr.safety import ASRSafetyEvaluator, ASRSafetyResult, SPEAK_AGAIN_PROMPTS



def create_synthetic_wav(duration_sec: float = 1.0, frequency_hz: float = 440.0, volume: float = 0.5) -> bytes:
    """Helper to generate in-memory synthetic PCM WAV bytes."""
    buf = io.BytesIO()
    sample_rate = 16000
    n_samples = int(sample_rate * duration_sec)
    
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            if volume == 0.0:
                val = 0
            else:
                val = int(32767.0 * volume * math.sin(2.0 * math.pi * frequency_hz * i / sample_rate))
                val = max(-32768, min(32767, val))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    
    return buf.getvalue()


class TestASRSafety(unittest.TestCase):
    """Test suite for MediKiosk ASR Safety guardrail and confidence scoring."""

    def test_silence_detection(self):
        """Zero-amplitude audio must be flagged as silence with 0.0 confidence."""
        silent_audio = create_synthetic_wav(duration_sec=1.5, volume=0.0)
        res = ASRSafetyEvaluator.evaluate(
            audio_bytes=silent_audio,
            transcript="I have a headache",
            language_code="en-IN",
            threshold=0.65
        )
        self.assertFalse(res.passed)
        self.assertTrue(res.requires_retry)
        self.assertEqual(res.confidence_score, 0.0)
        self.assertEqual(res.failure_reason, "silence_detected")
        self.assertIn("speak again", res.speak_again_prompt.lower())

    def test_empty_transcription(self):
        """Audible audio with an empty transcription must be flagged for retry."""
        audible_audio = create_synthetic_wav(duration_sec=1.0, volume=0.6)
        res = ASRSafetyEvaluator.evaluate(
            audio_bytes=audible_audio,
            transcript="   ",
            model_probability=0.8,
            language_code="hi-IN",
            threshold=0.65
        )
        self.assertFalse(res.passed)
        self.assertTrue(res.requires_retry)
        self.assertEqual(res.confidence_score, 0.0)
        self.assertEqual(res.failure_reason, "empty_transcription")
        self.assertIn("दोबारा बोलें", res.speak_again_prompt)

    def test_low_confidence_below_threshold(self):
        """Uncertain model probability and short text must fail when below threshold."""
        audible_audio = create_synthetic_wav(duration_sec=0.8, volume=0.15)
        res = ASRSafetyEvaluator.evaluate(
            audio_bytes=audible_audio,
            transcript="ok",
            model_probability=0.25,
            language_code="mr-IN",
            threshold=0.70
        )
        self.assertFalse(res.passed)
        self.assertTrue(res.requires_retry)
        self.assertEqual(res.failure_reason, "low_confidence")
        self.assertLess(res.confidence_score, 0.70)
        self.assertIn("पुन्हा बोला", res.speak_again_prompt)

    def test_high_confidence_above_threshold(self):
        """Clear speech and high model probability must pass the safety guardrail."""
        audible_audio = create_synthetic_wav(duration_sec=2.0, volume=0.7)
        res = ASRSafetyEvaluator.evaluate(
            audio_bytes=audible_audio,
            transcript="मुझे दो दिन से सीने में हल्का दर्द है",
            model_probability=0.92,
            language_code="hi-IN",
            threshold=0.65
        )
        self.assertTrue(res.passed)
        self.assertFalse(res.requires_retry)
        self.assertIsNone(res.failure_reason)
        self.assertGreaterEqual(res.confidence_score, 0.65)

    def test_repetitive_hallucination_loop(self):
        """Repetitive token hallucination loops must trigger safety retry."""
        audible_audio = create_synthetic_wav(duration_sec=2.0, volume=0.5)
        res = ASRSafetyEvaluator.evaluate(
            audio_bytes=audible_audio,
            transcript="pain pain pain pain pain pain pain pain",
            model_probability=0.75,
            language_code="en-IN",
            threshold=0.65
        )
        self.assertFalse(res.passed)
        self.assertTrue(res.requires_retry)
        self.assertEqual(res.failure_reason, "repetitive_hallucination")

    def test_multilingual_retry_prompts(self):
        """All supported Indic languages resolve to polite, localized retry directives."""
        test_cases = [
            ("hi", "दोबारा बोलें"),
            ("mr-IN", "पुन्हा बोला"),
            ("bn", "আবার বলুন"),
            ("ta-IN", "மீண்டும் பேசுங்கள்"),
            ("te", "మళ్లీ మాట్లాడండి"),
            ("gu", "ફરીથી બોલો"),
            ("kn", "ಮತ್ತೆ ಮಾತನಾಡಿ"),
            ("ml", "വീണ്ടും സംസാരിക്കുക"),
            ("pa", "ਦੁਬਾਰਾ ਬੋਲੋ"),
            ("od", "ପୁଣି କୁହନ୍ତୁ"),
            ("en-IN", "speak again")
        ]
        for lang_code, expected_substr in test_cases:
            prompt = ASRSafetyEvaluator.get_speak_again_prompt(lang_code)
            self.assertIn(expected_substr, prompt, f"Failed for language: {lang_code}")


class TestVoiceASREndpoint(unittest.TestCase):
    """Integration test suite for /api/v1/voice/asr endpoint with FastAPI TestClient."""

    def setUp(self):
        self.client = TestClient(app)

    def test_empty_audio_upload(self):
        """Uploading empty audio bytes must return retry_required status with localized prompt."""
        response = self.client.post(
            "/api/v1/voice/asr",
            files={"audio": ("empty.wav", b"", "audio/wav")},
            data={"language": "hi-IN"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "retry_required")
        self.assertFalse(data["success"])
        self.assertTrue(data["requires_retry"])
        self.assertEqual(data["failure_reason"], "silence_detected")
        self.assertIn("दोबारा बोलें", data["speak_again_prompt"])

    @patch("app.api.v1.endpoints.voice.sarvam_asr.transcribe_async")
    def test_endpoint_low_confidence_retry(self, mock_transcribe):
        """When ASR returns low confidence, endpoint must instruct user to speak again."""
        mock_safety = ASRSafetyResult(
            confidence_score=0.42,
            threshold=0.65,
            passed=False,
            requires_retry=True,
            failure_reason="low_confidence",
            speak_again_prompt="आपकी आवाज़ स्पष्ट नहीं सुनाई दी। कृपया माइक्रोफ़ोन के पास आकर दोबारा बोलें।",
            speak_again_prompt_en="We couldn't hear you clearly. Please speak again closer to the microphone.",
            metrics={"test": True}
        )
        mock_transcribe.return_value = {
            "transcript": "दर्द",
            "english_transcript": "pain",
            "language_code": "hi-IN",
            "language_probability": 0.40,
            "safety": mock_safety
        }

        audio_bytes = create_synthetic_wav(duration_sec=1.0, volume=0.3)
        response = self.client.post(
            "/api/v1/voice/asr",
            files={"audio": ("voice.wav", audio_bytes, "audio/wav")},
            data={"language": "hi-IN", "threshold": "0.65"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "retry_required")
        self.assertFalse(data["success"])
        self.assertTrue(data["requires_retry"])
        self.assertEqual(data["confidence_score"], 0.42)
        self.assertEqual(data["failure_reason"], "low_confidence")
        self.assertIsNotNone(data["speak_again_prompt"])
        self.assertIn("दोबारा बोलें", data["speak_again_prompt"])

    @patch("app.api.v1.endpoints.voice.sarvam_asr.transcribe_async")
    def test_endpoint_high_confidence_success(self, mock_transcribe):
        """When ASR returns high confidence, endpoint returns success without retry."""
        mock_safety = ASRSafetyResult(
            confidence_score=0.91,
            threshold=0.65,
            passed=True,
            requires_retry=False,
            failure_reason=None,
            speak_again_prompt="We couldn't hear you clearly. Please speak again closer to the microphone.",
            speak_again_prompt_en="We couldn't hear you clearly. Please speak again closer to the microphone.",
            metrics={"test": True}
        )
        mock_transcribe.return_value = {
            "transcript": "पेट में बहुत तेज दर्द हो रहा है",
            "english_transcript": "I am having severe pain in my stomach",
            "language_code": "hi-IN",
            "language_probability": 0.95,
            "safety": mock_safety
        }

        audio_bytes = create_synthetic_wav(duration_sec=2.0, volume=0.8)
        response = self.client.post(
            "/api/v1/voice/asr",
            files={"audio": ("voice.wav", audio_bytes, "audio/wav")},
            data={"language": "hi-IN"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["success"])
        self.assertFalse(data["requires_retry"])
        self.assertIsNone(data["failure_reason"])
        self.assertIsNone(data["speak_again_prompt"])
        self.assertEqual(data["transcription"], "पेट में बहुत तेज दर्द हो रहा है")
        self.assertEqual(data["english_transcription"], "I am having severe pain in my stomach")


if __name__ == "__main__":
    unittest.main()
