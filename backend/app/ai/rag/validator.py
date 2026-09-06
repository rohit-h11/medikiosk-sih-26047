from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
import json
from pathlib import Path

class ExtractedData(BaseModel):
    """Validates the core extracted data from OCR"""
    document_type: str = Field(..., description="Type of the document")
    document_date: str = Field(..., description="Date of the document")
    patient_name: Optional[str] = None
    
    # Allow any other extracted clinical fields to pass through (medications, vitals, etc.)
    model_config = ConfigDict(extra='allow')

class OCRPayload(BaseModel):
    """
    Main Validator for incoming OCR JSON from the teammate.
    Ensures the payload has the required structure before processing.
    """
    success: bool
    extracted_data: ExtractedData
    rag_chunks: List[Dict[str, Any]] = Field(..., description="Pre-chunked markdown text for RAG")

if __name__ == "__main__":
    from pydantic import ValidationError

    # Path to the real OCR result file
    test_file_path = Path(__file__).parent.parent.parent.parent / "ocr-result.json"
    
    print("Testing Validator against actual OCR teammate JSON...")
    
    try:
        with open(test_file_path, 'r', encoding='utf-8') as f:
            real_data = json.load(f)
            
        doc = OCRPayload(**real_data)
        print(f"[SUCCESS] Validation passed!")
        print(f"Document Type: {doc.extracted_data.document_type}")
        print(f"Document Date: {doc.extracted_data.document_date}")
        print(f"Number of RAG Chunks ready to embed: {len(doc.rag_chunks)}")
        
    except ValidationError as e:
        print("[ERROR] Validation Failed:")
        print(e)
    except FileNotFoundError:
        print(f"[ERROR] Could not find {test_file_path}")
