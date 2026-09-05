# MediKiosk RAG Pipeline: Architectural Enhancements & Optimization Guide

**Project:** MediKiosk (Smart India Hackathon 2026 · Problem Statement 26047)  
**Module:** RAG (Retrieval-Augmented Generation) & Clinical History Vector Engine  
**Target Architecture:** FastAPI Backend + Supabase `pgvector` + Bhashini Multilingual Intake  

---

## 1. Executive Summary

MediKiosk processes patient prescriptions, lab reports, and voice intakes in high-volume Indian Outpatient Departments (OPDs). While the baseline RAG pipeline successfully implements OCR JSON validation, Markdown chunk formatting, vector embedding, and similarity retrieval, several key enhancements are recommended to make the system **clinical-grade**, **multilingual-ready**, and **resilient under high concurrency**.

This document outlines all recommended improvements, architectural rationale, and concrete implementation patterns.

---

## 2. Architecture & Pipeline Overview

```
[ OCR Vision LLM / Voice Intake ]
               │
               ▼
[ Structured JSON / ExtractedDocumentData ]
               │
               ▼
[ Markdown Chunking & Contextual Headers ]
  - clinical_summary, medications, lab_reports, ayurvedic_assessment
               │
               ▼
[ Vector Embedding Engine (Multilingual) ]
               │
               ▼
[ Supabase pgvector Store (patient_structured_vectors) ]
  - Idempotent Upsert + Temporal Decay + Category Filtering
               │
               ▼
[ Context-Aware Retrieval (Interview Engine) ]
  - Sub-10ms Scoped Query for Clinical Intake & Doctor Summaries
```

---

## 3. Recommended Enhancements

### 3.1 Multilingual Embedding Support

#### Current Limitation
- Currently uses `sentence-transformers/all-MiniLM-L6-v2`.
- `all-MiniLM-L6-v2` is an **English-only** model.
- Because MediKiosk takes voice and text input across regional Indian languages (Hindi, Tamil, Telugu, Marathi, Bengali, Gujarati, Kannada, and Hinglish transliterations), cross-lingual semantic search suffers with an English-only model.

#### Proposed Solution
Upgrade to a compact, high-performance multilingual model such as:
- **`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** (384 dimensions — drop-in replacement with no SQL schema change needed)
- **`BAAI/bge-m3`** (1024 dimensions, state-of-the-art multilingual & multi-granularity)
- **`intfloat/multilingual-e5-small`** (384 dimensions)

```python
# app/ai/rag/retriever.py
MULTILINGUAL_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(MULTILINGUAL_MODEL_NAME)
    return _embedding_model
```

---

### 3.2 SQL Date Normalization for PostgreSQL `DATE`

#### Current Limitation
- OCR extracted dates come in varied formats: `"26/01/2024"`, `"26-Jan-2024"`, `"2024.01.26"`, or `"Unknown Date"`.
- The database schema defines `encounter_date DATE`.
- Inserting non-ISO date strings directly causes Postgres runtime execution errors (`date/time field value out of range`).

#### Proposed Solution
Implement a robust date parsing utility to normalize all dates to standard `YYYY-MM-DD` (ISO-8601) format or `None`.

```python
# app/ai/rag/utils.py
import re
from datetime import datetime
from typing import Optional

def normalize_clinical_date(raw_date: Optional[str]) -> Optional[str]:
    """
    Normalizes varied clinical date formats into standard ISO YYYY-MM-DD for PostgreSQL DATE.
    """
    if not raw_date or not isinstance(raw_date, str):
        return None
        
    cleaned = raw_date.strip()
    if cleaned.lower() in ("unknown", "unknown date", "n/a", "none", ""):
        return None

    # Supported common Indian clinical date formats
    patterns = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y"
    ]
    for fmt in patterns:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    return None
```

---

### 3.3 Non-Blocking CPU Embeddings in FastAPI

#### Current Limitation
- `model.encode()` in `retriever.py` is synchronous PyTorch code.
- Calling synchronous CPU inference inside `async def retrieve_patient_history_async()` blocks FastAPI's asyncio event loop, preventing all concurrent requests from being processed during inference.

#### Proposed Solution
Offload CPU-bound inference and synchronous database calls to thread pools using `asyncio.to_thread`.

```python
# app/ai/rag/retriever.py
import asyncio
from typing import List

async def generate_embedding_async(text: str) -> List[float]:
    """Runs vector embedding inference in a background thread to prevent event loop blocking."""
    model = get_embedding_model()
    if model is None:
        return [0.0] * 384
    
    # Offload CPU compute
    embedding = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
    return embedding.tolist()
```

---

### 3.4 Direct In-Memory Ingestion (OCR $\to$ RAG)

#### Current Limitation
- `inserter.py` is written as a standalone script taking a JSON file path (`run_pipeline(json_path: str)`).
- The OCR extraction endpoint produces an in-memory dictionary/Pydantic model that cannot currently be passed directly without writing to disk.

#### Proposed Solution
Expose a clean service function `ingest_extracted_document_async` that takes Python objects and writes directly to Supabase.

```python
# app/ai/rag/inserter.py
async def ingest_extracted_document_async(
    patient_id: str,
    document_type: str,
    document_date: Optional[str],
    rag_chunks: List[Dict[str, Any]],
    document_id: Optional[str] = None
) -> int:
    """
    Directly transforms, embeds, and upserts RAG chunks into Supabase pgvector.
    """
    if not rag_chunks:
        return 0

    supabase = get_supabase_client()
    iso_date = normalize_clinical_date(document_date)

    prepared_rows = []
    for chunk in rag_chunks:
        header = f"[Patient: {patient_id} | Document: {document_type.replace('_', ' ').title()} | Encounter Date: {iso_date or 'Recent'} | Status: Active]\n\n"
        full_content = header + chunk.get("content", "").strip()
        embedding = await generate_embedding_async(full_content)

        prepared_rows.append({
            "patient_id": patient_id,
            "document_id": document_id,
            "category": chunk.get("chunk_type", "general"),
            "content": full_content,
            "metadata": chunk.get("metadata", {}),
            "encounter_date": iso_date,
            "embedding": embedding
        })

    # Perform upsert
    response = await asyncio.to_thread(
        lambda: supabase.table("patient_structured_vectors").insert(prepared_rows).execute()
    )
    return len(prepared_rows)
```

---

### 3.5 Idempotent Ingestion & Deduplication

#### Current Limitation
- Re-uploading a document or retrying an OCR call creates duplicate chunks in `patient_structured_vectors`, polluting search results.

#### Proposed Solution
Add a composite unique constraint in PostgreSQL and use Supabase upsert:

```sql
-- Migration addition in supabase_setup.sql
ALTER TABLE patient_structured_vectors 
ADD CONSTRAINT uq_patient_doc_chunk 
UNIQUE (patient_id, document_id, category, (metadata->>'chunk_index'));
```

```python
# Upsert in Python
supabase.table("patient_structured_vectors").upsert(
    rows, 
    on_conflict="patient_id,document_id,category,chunk_index"
).execute()
```

---

### 3.6 Granular Clinical Chunking & Safety Isolation

#### Current Limitation
- Medications are grouped into one single chunk. Long prescription lists with 10+ medicines can exceed optimal chunk window or dilute similarity for specific drugs.
- Drug allergies and severe contraindications are not isolated into dedicated high-priority safety chunks.

#### Proposed Solution
Add specialized chunk types in `_generate_rag_chunks`:
1. `allergies_and_warnings` (Immediate safety screening)
2. `active_medications` (Split into chunks of max 5 drugs if list is long)
3. `abnormal_labs` (Highlighted separately from normal lab values)

```python
# Chunking enhancement in extractor.py
if data.red_flags or any(lab.abnormal_flag and lab.abnormal_flag.value != "normal" for lab in data.lab_investigations):
    critical_lines = [f"ALERT: {flag}" for flag in data.red_flags]
    critical_lines += [f"CRITICAL LAB: {lab.test_name} = {lab.observed_value} ({lab.abnormal_flag})" 
                       for lab in data.lab_investigations if lab.abnormal_flag and lab.abnormal_flag.value != "normal"]
    
    chunks.append({
        "chunk_index": len(chunks),
        "chunk_type": "critical_alerts",
        "content": "CRITICAL CLINICAL ALERTS:\n" + "\n".join(critical_lines),
        "metadata": {"patient_id": patient_id, "priority": "high"}
    })
```

---

### 3.7 Graceful Zero-Vector & Network Fallback

#### Current Limitation
- In `retriever.py`, if the model is missing, it returns `[0.0] * 384`. Vector similarity on zero vectors produces meaningless results.

#### Proposed Solution
When embeddings are unavailable, gracefully fallback to a relational metadata query based on recency and category.

```python
# Fallback mechanism in retriever.py
if model is None:
    # Direct SQL fallback: return most recent records for this patient
    response = supabase.table("patient_structured_vectors") \
        .select("id, patient_id, category, content, metadata, encounter_date") \
        .eq("patient_id", patient_id) \
        .order("encounter_date", desc=True) \
        .limit(top_k) \
        .execute()
    return response.data or []
```

---

### 3.8 Codebase Organization & Cleanup

| File Path | Action | Rationale |
| :--- | :--- | :--- |
| `backend/app/ai/rag/Validator.py` | Rename $\to$ `validator.py` | Follow PEP-8 snake_case module naming standard |
| `backend/app/ai/rag/embedder.py` | Fix relative imports | Replace `from Validator import ...` with `from app.ai.rag.validator import ...` |
| `backend/app/ai/rag/inserter.py` | Fix `.env` loading & relative imports | Use `app.config` settings instead of ad-hoc parent directory climbing |
| `backend/app/ai/rag.py` | Deprecate / remove | Remove orphan file to eliminate duplicate conflicting schemas |

---

## 4. Implementation Priority Matrix

| Enhancement | Impact | Effort | Priority |
| :--- | :---: | :---: | :---: |
| **SQL Date Normalization** | High | Low | **P0 (Immediate)** |
| **Async Threading (`asyncio.to_thread`)** | High | Low | **P0 (Immediate)** |
| **Import & Filename Standardization** | High | Low | **P0 (Immediate)** |
| **In-Memory Ingestion Function** | High | Medium | **P1 (Next)** |
| **Multilingual Embedding Model** | High | Low | **P1 (Next)** |
| **Idempotent Upsert / Deduplication** | Medium | Medium | **P2** |
| **Critical Safety Chunking** | Medium | Medium | **P2** |

---

## 5. Conclusion

Implementing these improvements ensures the MediKiosk RAG pipeline operates reliably in production OPD settings, supporting regional Indian languages without blocking server concurrency or failing on variable clinical date formats.
