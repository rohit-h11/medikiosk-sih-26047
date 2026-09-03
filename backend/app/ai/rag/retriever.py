# backend/app/ai/rag/retriever.py
import logging
from typing import List, Dict, Any, Optional
from app.db import get_supabase_client

logger = logging.getLogger("medikiosk.rag.retriever")

# Global singleton for SentenceTransformer embedding model
_embedding_model = None

def get_embedding_model():
    """Loads and caches the all-MiniLM-L6-v2 model (384 dimensions)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers/all-MiniLM-L6-v2 model...")
            _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning(f"Could not load sentence-transformers: {e}. Vector RAG fallback enabled.")
            _embedding_model = None
    return _embedding_model

def generate_embedding(text: str) -> List[float]:
    """Generates a 384-dimensional vector embedding for given text."""
    model = get_embedding_model()
    if model is None:
        # Return dummy 384-dim zero vector if model is uninstalled
        return [0.0] * 384
    emb = model.encode(text, normalize_embeddings=True)
    return emb.tolist()

async def retrieve_patient_history_async(
    patient_id: str,
    query_text: str,
    top_k: int = 3,
    similarity_threshold: float = 0.35,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs patient-scoped vector similarity search via Supabase pgvector RPC.
    
    Returns a list of relevant medical context records (past diagnoses, medications, labs, etc.).
    """
    if not patient_id or not query_text or not query_text.strip():
        return []

    try:
        supabase = get_supabase_client()
        query_vector = generate_embedding(query_text)

        rpc_params = {
            "p_patient_id": patient_id,
            "p_query_embedding": query_vector,
            "p_top_k": top_k,
            "p_similarity_threshold": similarity_threshold,
            "p_category": category,
            "p_use_recency": True
        }

        response = supabase.rpc("match_patient_history", rpc_params).execute()
        results = response.data or []
        logger.info(f"Retrieved {len(results)} relevant RAG chunks for patient {patient_id}")
        return results
    except Exception as e:
        logger.warning(f"RAG retrieval skipped or encountered error: {e}")
        return []

async def store_dialogue_summary_in_rag_async(
    patient_id: str,
    session_id: str,
    clinical_summary: str,
    socrates_state: Dict[str, Any],
    encounter_date: Optional[str] = None
) -> bool:
    """
    Embeds and stores a completed clinical interview transcript into patient_structured_vectors
    for future visits and doctor Q&A RAG.
    """
    if not patient_id or not clinical_summary:
        return False

    try:
        supabase = get_supabase_client()

        # Format contextual chunk header as per MediKiosk standard
        header = f"[Patient: {patient_id} | Document: Clinical Intake Interview | Encounter Date: {encounter_date or 'Recent'} | Status: Completed]\n\n"
        full_content = header + clinical_summary.strip()

        embedding = generate_embedding(full_content)

        row = {
            "patient_id": patient_id,
            "document_id": session_id,
            "category": "clinical_interview",
            "content": full_content,
            "metadata": {
                "session_id": session_id,
                "socrates_state": socrates_state,
                "type": "interview_summary"
            },
            "embedding": embedding
        }

        supabase.table("patient_structured_vectors").insert(row).execute()
        logger.info(f"Stored completed interview summary in RAG vector store for patient {patient_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to store interview summary in RAG: {e}")
        return False
