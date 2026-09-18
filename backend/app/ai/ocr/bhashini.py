import os
import json
import base64
import requests
import numpy as np
import cv2

def run_bhashini_ocr(image_rgb: np.ndarray) -> str:
    """
    Takes an RGB image array, encodes it to base64, and calls the Bhashini OCR API.
    Returns the extracted text.
    """
    inference_api_key = os.getenv("BHASHINI_INFERENCE_API_KEY")
    
    if not inference_api_key:
        print("[BHASHINI] BHASHINI_INFERENCE_API_KEY missing in .env. Returning mock Bhashini OCR text.")
        return "MOCK BHASHINI OCR TEXT: 1. Paracetamol 500mg\n2. Azithromycin 250mg"

    # Encode image to base64
    success, encoded_jpg = cv2.imencode(".jpg", image_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not success:
        print("[BHASHINI] Failed to encode image.")
        return ""
    
    base64_img = base64.b64encode(encoded_jpg.tobytes()).decode("utf-8")

    # Bhashini Inference Endpoint
    url = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    
    headers = {
        "Authorization": inference_api_key,
        "Content-Type": "application/json"
    }

    # Standard Bhashini OCR payload for inference
    payload = {
        "pipelineTasks": [
            {
                "taskType": "ocr",
                "config": {
                    "language": {
                        "sourceLanguage": "en"
                    },
                    "serviceId": "bhashini/iiith-bhasha-ocr" 
                }
            }
        ],
        "inputData": {
            "image": [
                {
                    "imageContent": base64_img
                }
            ]
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"[BHASHINI] API request failed with status {response.status_code}. Response: {response.text}")
            return ""
        
        data = response.json()
        
        # Parse the nested response structure (Bhashini returns pipelineResponse)
        # Typically: data["pipelineResponse"][0]["output"][0]["source"]
        pipeline_res = data.get("pipelineResponse", [])
        if pipeline_res and len(pipeline_res) > 0:
            outputs = pipeline_res[0].get("output", [])
            if outputs and len(outputs) > 0:
                extracted_text = outputs[0].get("source", "")
                print(f"[BHASHINI] Successfully extracted text length: {len(extracted_text)}")
                return extracted_text
                
        return ""
    except Exception as e:
        print(f"[BHASHINI] API request failed: {e}")
        return ""
