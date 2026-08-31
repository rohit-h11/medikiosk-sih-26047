import base64
import logging
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Bhashini Dhruva Pipeline Endpoint
BHASHINI_PIPELINE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

class BhashiniASRService:
    """
    Bhashini Speech-to-Text (ASR) Service Integration for Indian Languages.
    Supports 22 official Indian languages + English.
    """
    def __init__(self):
        self.pipeline_url = BHASHINI_PIPELINE_URL

    @property
    def is_configured(self) -> bool:
        """Check if Bhashini API keys are present in environment settings."""
        return bool(
            settings.BHASHINI_USER_ID 
            and settings.BHASHINI_API_KEY 
            and settings.BHASHINI_USER_ID != "your-bhashini-user-id"
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        source_language: str = "hi",
        audio_format: str = "wav",
        sampling_rate: int = 16000,
        target_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes into text.
        
        Args:
            audio_bytes: Raw binary audio content (.wav, .mp3, .webm, .flac)
            source_language: ISO language code ('hi', 'ta', 'te', 'mr', 'bn', 'en', etc.)
            audio_format: Audio container format ('wav', 'flac', 'mp3', 'webm')
            sampling_rate: Audio sampling frequency (default 16000 Hz)
            target_language: Optional target language if translation is requested simultaneously.
            
        Returns:
            Dict containing success status, transcript string, source language, and metadata.
        """
        if not self.is_configured:
            logger.warning("Bhashini API keys are not configured. Operating in fallback mode.")
            return {
                "success": False,
                "transcript": "",
                "language": source_language,
                "error": "Bhashini API keys not configured. Please add BHASHINI_USER_ID and BHASHINI_API_KEY to your backend/.env file.",
                "is_mock": True
            }

        try:
            # Step 1: Encode audio bytes to Base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # Step 2: Build HTTP Headers
            headers = {
                "userID": settings.BHASHINI_USER_ID,
                "ulcaApiKey": settings.BHASHINI_API_KEY,
                "Content-Type": "application/json"
            }
            if settings.BHASHINI_INFERENCE_API_KEY:
                headers["Authorization"] = settings.BHASHINI_INFERENCE_API_KEY

            # Step 3: Construct Dhruva Pipeline Payload
            pipeline_tasks = [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {
                            "sourceLanguage": source_language
                        },
                        "audioFormat": audio_format,
                        "samplingRate": sampling_rate
                    }
                }
            ]

            # Optional: Add translation task to pipeline if target_language is provided and different
            if target_language and target_language != source_language:
                pipeline_tasks.append({
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_language,
                            "targetLanguage": target_language
                        }
                    }
                })

            payload: Dict[str, Any] = {
                "pipelineTasks": pipeline_tasks,
                "inputData": {
                    "audio": [
                        {
                            "audioContent": audio_base64
                        }
                    ]
                }
            }

            if settings.BHASHINI_PIPELINE_ID:
                payload["pipelineRequestConfig"] = {
                    "pipelineId": settings.BHASHINI_PIPELINE_ID
                }

            # Step 4: Execute API Request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.pipeline_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Step 5: Extract transcript & translated text from Bhashini response
            transcript = ""
            translated_text = ""
            
            pipeline_responses = data.get("pipelineResponse", [])
            for task_res in pipeline_responses:
                task_type = task_res.get("taskType")
                output_list = task_res.get("output", [])
                
                if task_type == "asr" and output_list:
                    transcript = output_list[0].get("source", "")
                elif task_type == "translation" and output_list:
                    translated_text = output_list[0].get("target", "")

            return {
                "success": True,
                "transcript": transcript,
                "translated_text": translated_text if target_language else None,
                "language": source_language,
                "target_language": target_language,
                "is_mock": False
            }

        except httpx.HTTPStatusError as exc:
            error_msg = f"Bhashini HTTP Error {exc.response.status_code}: {exc.response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "transcript": "",
                "language": source_language,
                "error": error_msg,
                "is_mock": False
            }
        except Exception as exc:
            error_msg = f"Error calling Bhashini ASR API: {str(exc)}"
            logger.error(error_msg)
            return {
                "success": False,
                "transcript": "",
                "language": source_language,
                "error": error_msg,
                "is_mock": False
            }

bhashini_asr_service = BhashiniASRService()
