# scripts/test_sarvam_asr.py
import os
import sys
import httpx

# 1. Provide your key directly or via environment
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "sk_y5p0h22s_jzClDL7O2V6TjXxhvHxKpQBo")

def translate_to_english(text: str, source_language_code: str = "hi-IN") -> str:
    """
    Translates transcript text into English using Sarvam AI's Mayura translation model.
    """
    if not text or not text.strip():
        return ""
    
    # If already English, skip translation
    if source_language_code.lower().startswith("en"):
        return text

    url = "https://api.sarvam.ai/translate"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    payload = {
        "input": text,
        "source_language_code": source_language_code,
        "target_language_code": "en-IN",
        "speaker_gender": "Male",
        "mode": "formal",
        "model": "mayura:v1"
    }

    try:
        with httpx.Client(timeout=30.0, verify=True) as client:
            res = client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                result = res.json()
                return result.get("translated_text", text)
            else:
                return f"[Translation Error {res.status_code}: {res.text}]"
    except Exception as e:
        return f"[Translation Failed: {str(e)}]"


def test_sarvam_stt_with_file(audio_path: str, language_code: str = "unknown"):
    print(f"\n=======================================================")
    print(f"🎙️  Testing Sarvam STT + English Translation")
    print(f"📁  File: {audio_path}")
    print(f"🌐  Language Hint: {language_code}")
    print(f"=======================================================")

    if not os.path.exists(audio_path):
        print(f"❌ Error: File {audio_path} does not exist.")
        return

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    files = {
        "file": (os.path.basename(audio_path), audio_bytes, "audio/wav")
    }
    data = {
        "model": "saarika:v2.5",
        "language_code": language_code,
        "with_diarization": "false"
    }

    print("⏳ Transcribing audio via Sarvam STT (saarika:v2.5)...")
    raw_transcript = ""
    detected_lang = language_code

    try:
        with httpx.Client(timeout=45.0, http2=False, verify=True) as client:
            res = client.post(url, headers=headers, files=files, data=data)
            if res.status_code == 200:
                result = res.json()
                raw_transcript = result.get("transcript", "").strip()
                detected_lang = result.get("language_code", language_code)
            else:
                print(f"❌ STT Error ({res.status_code}): {res.text}")
                return
    except httpx.ConnectError:
        # Fallback using requests
        try:
            import requests
            res = requests.post(url, headers=headers, files=files, data=data, timeout=45)
            if res.status_code == 200:
                result = res.json()
                raw_transcript = result.get("transcript", "").strip()
                detected_lang = result.get("language_code", language_code)
            else:
                print(f"❌ STT Error ({res.status_code}): {res.text}")
                return
        except Exception as fallback_err:
            print(f"❌ Connection failed: {fallback_err}")
            return

    # Translate to English
    print("⏳ Translating transcript to English (mayura:v1)...")
    english_translation = translate_to_english(
        text=raw_transcript,
        source_language_code=detected_lang if detected_lang != "unknown" else "hi-IN"
    )

    print("\n✅ --- FINAL RESULTS ---")
    print(f"🗣️  Detected Language : {detected_lang}")
    print(f"📝  Original Transcript: {raw_transcript}")
    print(f"🇬🇧  English Translation: {english_translation}")
    print("-------------------------------------------------------\n")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        # User passed both file path and language: python scripts/test_sarvam_asr.py audio.wav en-IN
        test_sarvam_stt_with_file(sys.argv[1], language_code=sys.argv[2])
    elif len(sys.argv) > 1:
        # User passed file path: defaults to "unknown" for automatic language detection
        test_sarvam_stt_with_file(sys.argv[1], language_code="unknown")
    else:
        print("Usage: python scripts/test_sarvam_asr.py <path_to_audio_file.wav> [language_code]")
        print("Examples:")
        print("  python scripts/test_sarvam_asr.py sample.wav          (Auto-detect language)")
        print("  python scripts/test_sarvam_asr.py sample.wav en-IN    (Force English)")
        print("  python scripts/test_sarvam_asr.py sample.wav hi-IN    (Force Hindi)")
