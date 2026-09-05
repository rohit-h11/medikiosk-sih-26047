# backend/app/ai/rag/retriever.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.db import get_supabase_client
try:
    from app.ai.rag.utils import normalize_clinical_date
except ImportError:
    from utils import normalize_clinical_date  # type: ignore

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
    """Generates a 384-dimensional vector embedding for given text (synchronous)."""
    model = get_embedding_model()
    if model is None:
        # Return dummy 384-dim zero vector if model is uninstalled
        return [0.0] * 384
    emb = model.encode(text, normalize_embeddings=True)
    return emb.tolist()

async def generate_embedding_async(text: str) -> List[float]:
    """
    Asynchronously generates a 384-dimensional vector embedding for given text,
    offloading CPU-bound PyTorch inference to a background thread to keep FastAPI non-blocking.
    """
    model = get_embedding_model()
    if model is None:
        return [0.0] * 384
    emb = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
    return emb.tolist()

async def generate_embeddings_batch_async(texts: List[str]) -> List[List[float]]:
    """
    Asynchronously generates 384-dimensional vector embeddings for a list of texts in a single batch,
    offloading CPU-bound PyTorch inference to a background thread to keep FastAPI non-blocking.
    """
    if not texts:
        return []
    model = get_embedding_model()
    if model is None:
        return [[0.0] * 384 for _ in texts]
    embs = await asyncio.to_thread(model.encode, texts, normalize_embeddings=True)
    return embs.tolist()

async def retrieve_patient_history_async(
    patient_id: str,
    query_text: str,
    top_k: int = 5,
    similarity_threshold: float = 0.35,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs patient-scoped vector similarity search via Supabase pgvector RPC.
    If the embedding model is unavailable or vector search encounters an error,
    it gracefully falls back to a chronological SQL query for the patient's records.
    
    Returns a list of relevant medical context records (past diagnoses, medications, labs, etc.).
    """
    if not patient_id or not query_text or not query_text.strip():
        return []

    try:
        supabase = get_supabase_client()
    except Exception as e:
        logger.warning(f"Could not get Supabase client: {e}")
        return []

    def _chronological_fallback() -> List[Dict[str, Any]]:
        """Fallback: retrieves patient's most recent structured clinical records by date."""
        try:
            logger.info(f"Executing chronological SQL fallback for patient {patient_id}...")
            query = supabase.table("patient_structured_vectors") \
                .select("id, patient_id, category, content, metadata, encounter_date") \
                .eq("patient_id", patient_id)
            if category:
                query = query.eq("category", category)
            res = query.order("encounter_date", desc=True).limit(top_k).execute()
            return res.data or []
        except Exception as sql_err:
            logger.error(f"SQL fallback also failed: {sql_err}")
            return []

    # Check if embedding model is available
    model = get_embedding_model()
    if model is None:
        logger.warning(f"Embedding model unavailable. Using chronological SQL fallback for patient {patient_id}.")
        return await asyncio.to_thread(_chronological_fallback)

    try:
        query_vector = await generate_embedding_async(query_text)

        rpc_params = {
            "p_patient_id": patient_id,
            "p_query_embedding": query_vector,
            "p_top_k": top_k,
            "p_similarity_threshold": similarity_threshold,
            "p_category": category,
            "p_use_recency": True
        }

        response = await asyncio.to_thread(
            lambda: supabase.rpc("match_patient_history", rpc_params).execute()
        )
        results = response.data or []
        logger.info(f"Retrieved {len(results)} relevant RAG chunks for patient {patient_id}")
        return results
    except Exception as e:
        logger.warning(f"RAG vector search encountered error: {e}. Executing chronological SQL fallback...")
        return await asyncio.to_thread(_chronological_fallback)

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
        iso_date = normalize_clinical_date(encounter_date)
        header = f"[Patient: {patient_id} | Document: Clinical Intake Interview | Encounter Date: {iso_date or 'Recent'} | Status: Completed]\n\n"
        full_content = header + clinical_summary.strip()

        embedding = await generate_embedding_async(full_content)

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
            "encounter_date": iso_date,
            "embedding": embedding
        }

        supabase.table("patient_structured_vectors").insert(row).execute()
        logger.info(f"Stored completed interview summary in RAG vector store for patient {patient_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to store interview summary in RAG: {e}")
        return False
