# backend/app/ai/rag/__init__.py
from app.ai.rag.retriever import (
    retrieve_patient_history_async,
    store_dialogue_summary_in_rag_async,
    generate_embedding,
    generate_embedding_async,
    generate_embeddings_batch_async,
    get_embedding_model
)
from app.ai.rag.utils import normalize_clinical_date
from app.ai.rag.validator import OCRPayload
from app.ai.rag.inserter import (
    ingest_extracted_document_async,
    ingest_ocr_payload_async
)

__all__ = [
    "retrieve_patient_history_async",
    "store_dialogue_summary_in_rag_async",
    "generate_embedding",
    "generate_embedding_async",
    "generate_embeddings_batch_async",
    "get_embedding_model",
    "normalize_clinical_date",
    "OCRPayload",
    "ingest_extracted_document_async",
    "ingest_ocr_payload_async"
]
