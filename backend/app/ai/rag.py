from typing import List, Dict, Any
from app.db import get_supabase_client

async def store_document_embedding(
    document_id: str,
    patient_id: str,
    chunk_index: int,
    content: str,
    embedding: List[float],
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Store text chunk embedding into Supabase pgvector table (document_embeddings).
    """
    supabase = get_supabase_client()
    data = {
        "document_id": document_id,
        "patient_id": patient_id,
        "chunk_index": chunk_index,
        "content": content,
        "embedding": embedding,
        "metadata": metadata or {}
    }
    response = supabase.table("document_embeddings").insert(data).execute()
    return response.data

async def search_patient_documents(
    patient_id: str,
    query_embedding: List[float],
    match_count: int = 5,
    similarity_threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Perform pgvector similarity search scoped exclusively to a specific patient.
    Invokes the RPC function `match_document_chunks`.
    """
    supabase = get_supabase_client()
    
    rpc_params = {
        "query_embedding": query_embedding,
        "match_patient_id": patient_id,
        "match_count": match_count,
        "similarity_threshold": similarity_threshold
    }
    
    response = supabase.rpc("match_document_chunks", rpc_params).execute()
    return response.data
