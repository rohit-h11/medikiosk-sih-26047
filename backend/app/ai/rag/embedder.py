import json
from pathlib import Path
from typing import List, Dict, Any
try:
    from app.ai.rag.validator import OCRPayload
    from app.ai.rag.utils import normalize_clinical_date
except ImportError:
    from validator import OCRPayload  # type: ignore
    from utils import normalize_clinical_date  # type: ignore
from pydantic import ValidationError

def create_contextual_header(patient_id: str, document_type: str, date: str) -> str:
    """
    Creates the contextual header as designed in Section 9 of the methodology.
    """
    return f"[Patient: {patient_id} | Document: {document_type.replace('_', ' ').title()} | Encounter Date: {date} | Status: Active]\n\n"

def process_ocr_result(json_path: str):
    """
    Reads the OCR result, prepends contextual headers to the pre-generated chunks,
    and (if installed) generates vector embeddings for them.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    try:
        # Validate the incoming data first
        data = OCRPayload(**raw_data)
    except ValidationError as e:
        print(f"[ERROR] Validation failed for {json_path}:\n{e}")
        return
        
    extracted_data = data.extracted_data
    rag_chunks = data.rag_chunks
    
    document_type = extracted_data.document_type
    document_date = extracted_data.document_date
    
    print(f"[SUCCESS] Loaded {len(rag_chunks)} RAG chunks from {json_path}")
    print("=" * 50)
    
    # 2. Add Contextual Headers to every chunk
    final_texts_to_embed = []
    
    for chunk in rag_chunks:
        # Get patient_id from the chunk's metadata
        patient_id = chunk.get("metadata", {}).get("patient_id", "UNKNOWN-PATIENT")
        
        # Build the contextual header
        header = create_contextual_header(patient_id, document_type, document_date)
        
        # Combine header and content
        full_text = header + chunk.get("content", "")
        final_texts_to_embed.append(full_text)
        
        # Print it out to see the result
        print(f"CHUNK {chunk.get('chunk_index')} ({chunk.get('chunk_type')}):")
        print("-" * 30)
        print(full_text)
        print("=" * 50)
        
    # 3. Attempt to embed using sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer
        
        print("\n[INFO] Loading sentence-transformers (all-MiniLM-L6-v2)...")
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        print("[INFO] Generating vector embeddings...")
        embeddings = model.encode(final_texts_to_embed, normalize_embeddings=True)
        
        for i, emb in enumerate(embeddings):
            print(f"Chunk {i} -> Vector of length {len(emb)} (e.g., {emb[0]:.4f}, {emb[1]:.4f}, ...)")
            
    except ImportError:
        print("\n[WARNING] 'sentence-transformers' is not installed.")
        print("To generate actual embeddings, run: pip install sentence-transformers torch")
        print("For now, we successfully prepared the text formatting!")

if __name__ == "__main__":
    # Pointing to the test file
    test_file_path = Path(__file__).parent.parent.parent.parent / "ocr-result.json"
    process_ocr_result(str(test_file_path))
