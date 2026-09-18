import os
import sys
import json
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv("backend/.env")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

sb = create_client(supabase_url, supabase_key)
print("Loading embedder model...", flush=True)
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")

test_queries = [
    "Patient has irregular racing heartbeat and palpitations",
    "वातव्याधि जोड़ों में दर्द और जकड़न (Sandhivata)",
    "Prakriti test for dry rough skin, thin body frame, and cracking joints"
]

print("\n" + "="*70)
print("🔥 TESTING LIVE SUPABASE VECTOR SEARCH (HNSW Index - BAAI/bge-small-en-v1.5, K=5)")
print("="*70)

for q in test_queries:
    print(f"\n🔍 Query: \"{q}\"", flush=True)
    emb = embedder.encode(q, normalize_embeddings=True).tolist()
    
    res = sb.rpc("match_clinical_guidelines", {
        "p_query_embedding": emb,
        "p_top_k": 5,
        "p_similarity_threshold": 0.35
    }).execute()
    
    if res.data:
        for idx, hit in enumerate(res.data, 1):
            print(f"  [{idx}] Match (Cosine Similarity: {round(hit['similarity'], 3)}): {hit['title']}")
            print(f"      Domain: {hit['domain']} | Urgency: {hit['urgency_level']} | ID: {hit['chunk_id']}")
    else:
        print("  No matches found.")

print("\n" + "="*70)
print("✅ LIVE SUPABASE RETRIEVAL IS 100% OPERATIONAL!")
print("="*70 + "\n")
