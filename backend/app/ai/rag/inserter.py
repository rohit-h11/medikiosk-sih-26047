import asyncio
import json
import os
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from dotenv import load_dotenv

try:
    from app.ai.rag.validator import OCRPayload
    from app.ai.rag.utils import normalize_clinical_date
    from app.ai.rag.retriever import generate_embeddings_batch_async
    from app.db import get_supabase_client
except ImportError:
    from validator import OCRPayload  # type: ignore
    from utils import normalize_clinical_date  # type: ignore
    from retriever import generate_embeddings_batch_async  # type: ignore
    get_supabase_client = None

from pydantic import ValidationError

# Load credentials from .env file (project root is 4 levels up from this file)
root_dir = Path(__file__).resolve().parents[4]
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")


def create_contextual_header(patient_id: str, document_type: str, date: str) -> str:
    """Creates the contextual header as per Section 9 of the methodology."""
    return f"[Patient: {patient_id} | Document: {document_type.replace('_', ' ').title()} | Encounter Date: {date} | Status: Active]\n\n"


async def ingest_extracted_document_async(
    patient_id: str,
    document_type: str,
    document_date: Optional[str],
    rag_chunks: List[Dict[str, Any]],
    document_id: Optional[str] = None
) -> int:
    """
    Directly transforms, formats with contextual headers, embeds, and inserts
    RAG chunks from memory into Supabase pgvector table (patient_structured_vectors).
    
    Returns the count of successfully ingested chunks.
    """
    if not rag_chunks:
        return 0

    client = None
    if get_supabase_client:
        try:
            client = get_supabase_client()
        except Exception:
            client = None

    if not client:
        try:
            from supabase import create_client
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("[ERROR] SUPABASE_URL or SUPABASE_KEY not found in environment.")
                return 0
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except ImportError:
            print("[ERROR] supabase library not installed. Run: pip install supabase")
            return 0

    normalized_date = normalize_clinical_date(document_date)
    display_date = normalized_date or document_date or "Recent"

    chunks_to_embed = []
    texts_to_embed = []

    for i, chunk in enumerate(rag_chunks):
        p_id = chunk.get("metadata", {}).get("patient_id") or patient_id or "UNKNOWN-PATIENT"
        header = create_contextual_header(p_id, document_type, display_date)
        full_text = header + chunk.get("content", "").strip()

        texts_to_embed.append(full_text)
        chunks_to_embed.append({
            "patient_id": p_id,
            "document_id": document_id,
            "category": chunk.get("chunk_type", "clinical_summary"),
            "content": full_text,
            "metadata": chunk.get("metadata", {}),
            "encounter_date": normalized_date,
            "chunk_index": chunk.get("chunk_index", i),
        })

    # Generate embeddings asynchronously in a single batch (non-blocking)
    embeddings = await generate_embeddings_batch_async(texts_to_embed)

    rows = []
    for i, meta in enumerate(chunks_to_embed):
        rows.append({
            "patient_id": meta["patient_id"],
            "document_id": meta["document_id"],
            "category": meta["category"],
            "content": meta["content"],
            "metadata": meta["metadata"],
            "encounter_date": meta["encounter_date"],
            "embedding": embeddings[i],
        })

    # Insert into Supabase table offloaded to background thread
    await asyncio.to_thread(
        lambda: client.table("patient_structured_vectors").insert(rows).execute()
    )
    return len(rows)


async def ingest_ocr_payload_async(
    payload: Union[OCRPayload, Dict[str, Any]],
    patient_id_override: Optional[str] = None,
    document_id: Optional[str] = None
) -> int:
    """
    Validates and ingests an in-memory OCR payload (dictionary or OCRPayload instance)
    directly into Supabase pgvector without touching the disk.
    """
    if isinstance(payload, dict):
        validated = OCRPayload(**payload)
    elif isinstance(payload, OCRPayload):
        validated = payload
    else:
        raise TypeError("payload must be a dict or OCRPayload instance")

    patient_id = (
        patient_id_override
        or validated.extracted_data.patient_name
        or "UNKNOWN-PATIENT"
    )
    doc_type = validated.extracted_data.document_type
    doc_date = validated.extracted_data.document_date
    chunks = validated.rag_chunks

    return await ingest_extracted_document_async(
        patient_id=patient_id,
        document_type=doc_type,
        document_date=doc_date,
        rag_chunks=chunks,
        document_id=document_id
    )


def run_pipeline(json_path: str):
    """
    CLI / Local Testing runner:
    Loads an OCR JSON file from disk and triggers the in-memory ingestion pipeline.
    """
    print(f"[INFO] Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    try:
        print("[INFO] Ingesting document into Supabase in-memory...")
        count = asyncio.run(ingest_ocr_payload_async(raw_data))
        print(f"[SUCCESS] Ingested {count} chunks into Supabase patient_structured_vectors!")
    except Exception as e:
        print(f"[ERROR] Ingestion failed: {e}")


if __name__ == "__main__":
    test_file = Path(__file__).parent.parent.parent.parent / "ocr-result.json"
    run_pipeline(str(test_file))
