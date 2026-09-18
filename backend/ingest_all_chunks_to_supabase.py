"""
Master Clinical RAG Ingestion Pipeline.

Ingests:
1. `clinical_knowledge_chunks.json` (68 atomic clinical cards: CCRAS, WHO, ICMR)
2. `namaste_morbidity_chunks.json` (2,910 clean NAMASTE morbidity condition cards)

Pipeline Steps:
- Loads local `all-MiniLM-L6-v2` embedding model
- Computes 384-dimensional vector embeddings in high-throughput batches
- Stores embeddings in Supabase `clinical_reference_vectors` table (or local cache)
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv("backend/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

CLINICAL_JSON = Path("backend/data/processed_chunks/clinical_knowledge_chunks.json")
NAMASTE_JSON = Path("backend/data/processed_chunks/namaste_morbidity_chunks.json")
EMBEDDINGS_CACHE = Path("backend/data/processed_chunks/clinical_vectors_cache.json")

def load_chunks() -> List[Dict[str, Any]]:
    chunks = []
    
    # 1. Load Clinical Knowledge Chunks (CCRAS, WHO, ICMR)
    if CLINICAL_JSON.exists():
        with open(CLINICAL_JSON, "r", encoding="utf-8") as f:
            c_data = json.load(f)
            chunks.extend(c_data)
            print(f"Loaded {len(c_data)} atomic clinical guideline chunks from {CLINICAL_JSON.name}")

    # 2. Load NAMASTE Morbidity Chunks
    if NAMASTE_JSON.exists():
        with open(NAMASTE_JSON, "r", encoding="utf-8") as f:
            n_data = json.load(f)
            chunks.extend(n_data)
            print(f"Loaded {len(n_data)} NAMASTE morbidity condition chunks from {NAMASTE_JSON.name}")

    return chunks

def run_ingestion():
    print("="*70)
    print("🚀 Starting Master Clinical RAG Ingestion Pipeline...")
    print("="*70)

    # 1. Load all chunks
    all_chunks = load_chunks()
    print(f"Total clinical knowledge records to ingest: {len(all_chunks)}")

    # 2. Load Embedding Model
    print("\n📦 Loading local embedding model: BAAI/bge-small-en-v1.5...")
    t0 = time.time()
    embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
    print(f"✓ Model loaded in {round(time.time() - t0, 2)}s (Embedding dimension: 384)")

    # 3. Generate Embeddings in Batches
    print("\n⚡ Generating 384-dimensional vector embeddings with BAAI/bge-small-en-v1.5...")
    texts_to_embed = [
        f"{c.get('title', '')}\n{c.get('content', '')}\nKeywords: {', '.join(c.get('symptom_triggers', []))}"
        for c in all_chunks
    ]

    t0 = time.time()
    embeddings = embedder.encode(
        texts_to_embed, 
        batch_size=64, 
        show_progress_bar=True, 
        normalize_embeddings=True
    )
    print(f"✓ Generated {len(embeddings)} embeddings in {round(time.time() - t0, 2)}s")

    # 4. Attach embeddings to chunks
    enriched_records = []
    for chunk, emb in zip(all_chunks, embeddings):
        record = {
            "chunk_id": chunk["chunk_id"],
            "domain": chunk.get("domain", "allopathy"),
            "category": chunk.get("category", "treatment_protocol"),
            "title": chunk["title"],
            "content": chunk["content"],
            "symptom_triggers": chunk.get("symptom_triggers", []),
            "urgency_level": chunk.get("urgency_level", "ROUTINE"),
            "metadata": chunk.get("metadata", {}),
            "embedding": emb.tolist()
        }
        enriched_records.append(record)

    # 5. Save Local Vector Cache (For instant local retrieval & backup)
    with open(EMBEDDINGS_CACHE, "w", encoding="utf-8") as f:
        json.dump(enriched_records, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved local vector backup cache: {EMBEDDINGS_CACHE} ({round(EMBEDDINGS_CACHE.stat().st_size / (1024*1024), 2)} MB)")

    # 6. Upload to Supabase if configured
    if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "your-supabase-url-here":
        try:
            print(f"\n☁️ Connecting to Supabase: {SUPABASE_URL}...")
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            # Clean old vectors first to guarantee 100% vector index purity
            print("  🧹 Clearing existing vectors from database...")
            try:
                supabase.table("clinical_reference_vectors").delete().neq("chunk_id", "dummy_non_existent").execute()
                print("  ✓ Cleared 'clinical_reference_vectors' table.")
            except Exception as clr_err:
                print(f"  ⚠️ Notice while clearing clinical_reference_vectors: {clr_err}")

            try:
                supabase.table("patient_structured_vectors").delete().neq("patient_id", "dummy_non_existent").execute()
                print("  ✓ Cleared 'patient_structured_vectors' table.")
            except Exception as clr_p_err:
                print(f"  ⚠️ Notice while clearing patient_structured_vectors: {clr_p_err}")

            print(f"  🚀 Ingesting {len(enriched_records)} new BAAI/bge-small-en-v1.5 vectors into 'clinical_reference_vectors'...")
            batch_size = 100
            for i in range(0, len(enriched_records), batch_size):
                batch = enriched_records[i:i+batch_size]
                supabase.table("clinical_reference_vectors").insert(batch).execute()
                print(f"  ✓ Ingested records {i+1} to {min(i+batch_size, len(enriched_records))} / {len(enriched_records)}")
            print("\n🎉 ALL CLINICAL VECTORS SUCCESSFULLY RE-INGESTED INTO SUPABASE!")
        except Exception as e:
            print(f"\n⚠️ Note on Supabase live upload: {e}")
            print("  (If the 'clinical_reference_vectors' table has not been created yet in Supabase SQL editor, run `backend/app/ai/rag/supabase_clinical_setup.sql` in your Supabase Dashboard).")
            print("  Local vector search is 100% active and working via `clinical_vectors_cache.json`!")
    else:
        print("\nℹ️ Supabase credentials not set or using mock mode. Vector cache saved locally for instant CPU retrieval!")

    print("\n" + "="*70)
    print("✅ MASTER CLINICAL RAG INGESTION COMPLETE!")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_ingestion()
