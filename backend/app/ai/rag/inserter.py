import json
import os
from pathlib import Path
from dotenv import load_dotenv
from Validator import OCRPayload  # type: ignore
from pydantic import ValidationError

# Load credentials from .env file (going up 4 levels to the project root)
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def create_contextual_header(patient_id: str, document_type: str, date: str) -> str:
    """Creates the contextual header as per Section 9 of the methodology."""
    return f"[Patient: {patient_id} | Document: {document_type.replace('_', ' ').title()} | Encounter Date: {date} | Status: Active]\n\n"

def run_pipeline(json_path: str):
    """
    Full pipeline:
    1. Validate the OCR JSON
    2. Attach contextual headers to each chunk
    3. Generate vector embeddings
    4. Insert into Supabase
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] SUPABASE_URL or SUPABASE_KEY not found in .env file.")
        return

    # --- Step 1: Load & Validate ---
    print(f"[INFO] Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    try:
        data = OCRPayload(**raw_data)
    except ValidationError as e:
        print(f"[ERROR] Validation failed:\n{e}")
        return

    print(f"[SUCCESS] Validated. Found {len(data.rag_chunks)} chunks.")

    document_type = data.extracted_data.document_type
    document_date = data.extracted_data.document_date

    # --- Step 2: Attach Contextual Headers ---
    chunks_to_embed = []
    for chunk in data.rag_chunks:
        patient_id = chunk.get("metadata", {}).get("patient_id", "UNKNOWN-PATIENT")
        header = create_contextual_header(patient_id, document_type, document_date)
        full_text = header + chunk.get("content", "")
        chunks_to_embed.append({
            "patient_id": patient_id,
            "category": chunk.get("chunk_type"),
            "content": full_text,
            "metadata": chunk.get("metadata", {}),
            "encounter_date": document_date,
            "chunk_index": chunk.get("chunk_index", 0),
        })

    # --- Step 3: Generate Embeddings ---
    print("[INFO] Generating vector embeddings with all-MiniLM-L6-v2...")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[ERROR] sentence-transformers not installed. Run: pip install sentence-transformers")
        return

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    texts = [c["content"] for c in chunks_to_embed]
    embeddings = model.encode(texts, normalize_embeddings=True)
    print(f"[SUCCESS] Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}.")

    # --- Step 4: Insert into Supabase ---
    print("[INFO] Connecting to Supabase and inserting vectors...")
    try:
        from supabase import create_client
    except ImportError:
        print("[ERROR] supabase not installed. Run: pip install supabase")
        return

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    rows = []
    for i, chunk_meta in enumerate(chunks_to_embed):
        rows.append({
            "patient_id": chunk_meta["patient_id"],
            "category": chunk_meta["category"],
            "content": chunk_meta["content"],
            "metadata": chunk_meta["metadata"],
            "encounter_date": chunk_meta["encounter_date"],
            "embedding": embeddings[i].tolist(),  # pgvector needs a plain list
        })

    response = client.table("patient_structured_vectors").insert(rows).execute()
    print(f"[SUCCESS] Inserted {len(rows)} rows into Supabase!")
    print(f"Response: {response}")


if __name__ == "__main__":
    test_file = Path(__file__).parent.parent.parent.parent / "ocr-result.json"
    run_pipeline(str(test_file))
