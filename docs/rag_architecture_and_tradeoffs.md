# 🩺 MediKiosk RAG Architecture & Chunking Strategy Trade-offs

> **Document Version:** 1.0  
> **Target System:** MediKiosk AI Clinical History Software Platform  
> **Primary Scope:** Scoped Cross-Visit Doctor Ad-Hoc RAG Assistant & Historical Document Search  

---

## 📌 Executive Summary

In **MediKiosk**, Retrieval-Augmented Generation (RAG) is specifically reserved for **cross-visit doctor ad-hoc Q&A** (e.g., *"Has this patient ever been prescribed penicillin?"* or *"Compare current creatinine levels with 2024 lab results"*). Single-visit intake summaries do not use RAG because a single visit's transcript and documents fit comfortably within the primary LLM context window (direct context-stuffing).

Because medical records consist of highly structured, tabular, and heterogenous documents (lab reports, prescriptions, discharge summaries, and AYUSH Prakriti assessments), **the chunking strategy directly determines retrieval precision and clinical safety.**

This document details the evaluation of chunking strategies, architectural trade-offs, model selection, and the chosen hybrid JSON-to-Markdown pipeline.

---

## ⚖️ Chunking Strategy Evaluation & Trade-offs

| Strategy | Description | Key Pros | Major Cons / Risks | Verdict |
|---|---|---|---|---|
| **1. Direct Raw OCR Text Chunking** | Fixed sliding window (e.g., 500 chars) on raw OCR output | • Zero setup complexity<br>• Fast upfront processing | ❌ Jumbles lab tables (separates test name from result/units)<br>❌ Separates drug names from dosage/warnings<br>❌ Includes OCR noise/headers | **Rejected** |
| **2. Whole Document as 1 Chunk** | Embedding the entire document JSON/text into 1 vector | • Preserves complete context<br>• Simple storage | ❌ Dilutes vector similarity scores<br>❌ Exceeds embedding model token limits<br>❌ Impairs specific metric lookup | **Rejected** |
| **3. Atomic Field-Level Chunking** | Every key-value pair gets its own standalone vector | • Extremely granular search | ❌ Loses entity relationships (e.g., drug name detached from dosage)<br>❌ Exponentially inflates vector DB size | **Rejected** |
| **4. JSON-to-Markdown Entity Chunking** *(Selected)* | Extract structured JSON via LLM $\rightarrow$ Convert to Markdown $\rightarrow$ Chunk by `##` headers | ✅ Keeps test/result/units bound in 1 block<br>✅ Eliminates OCR noise upfront<br>✅ Generates JSON for UI/ABDM + Markdown for RAG<br>✅ High cosine similarity with open-source models | ⚠️ Requires 1 LLM extraction call per document during upload | **SELECTED** |

---

## 🏗️ Selected RAG Architecture & Pipeline Flow

```
                      ┌─────────────────────────────────┐
                      │ Photo / PDF of Medical Record   │
                      └────────────────┬────────────────┘
                                       │
                      ┌────────────────▼────────────────┐
                      │ OCR Engine (Vision / PaddleOCR) │
                      └────────────────┬────────────────┘
                                       │ Raw Text
                      ┌────────────────▼────────────────┐
                      │ LLM Extraction (Module B)       │
                      └────────────────┬────────────────┘
                                       │ Structured JSON
         ┌─────────────────────────────┴─────────────────────────────┐
         │                                                           │
┌────────▼────────────────────────┐               ┌──────────────────▼──────────────────┐
│ Primary Database & React UI     │               │ Python JSON-to-Markdown Converter   │
│ (Patient Record / ABDM FHIR)    │               └──────────────────┬──────────────────┘
└─────────────────────────────────┘                                  │ Markdown Text
                                                  ┌──────────────────▼──────────────────┐
                                                  │ Header Splitter (`##` Sections)     │
                                                  └──────────────────┬──────────────────┘
                                                                     │ Text Chunks
                                                  ┌──────────────────▼──────────────────┐
                                                  │ Open-Source Embedding Model         │
                                                  │ (`BAAI/bge-small-en-v1.5`)          │
                                                  └──────────────────┬──────────────────┘
                                                                     │ 384-dim Vectors
                                                  ┌──────────────────▼──────────────────┐
                                                  │ Supabase pgvector Storage           │
                                                  │ (`WHERE patient_id = X`)            │
                                                  └─────────────────────────────────────┘
```

---

## 🔄 Technical Workflow

### Step 1: LLM Extraction to Structured JSON
When a patient or staff member uploads a document, the OCR text is processed by an LLM prompt into structured JSON:

```json
{
  "document_type": "Lab Report",
  "document_date": "2025-02-10",
  "lab_results": [
    { "test_name": "Serum Creatinine", "value": "2.1", "unit": "mg/dL", "flag": "HIGH", "reference_range": "0.6-1.2" },
    { "test_name": "Hemoglobin", "value": "11.2", "unit": "g/dL", "flag": "LOW", "reference_range": "13.5-17.5" }
  ]
}
```

### Step 2: Zero-Cost Conversion to Markdown (Python)
A deterministic Python utility converts the JSON into clean, semantic Markdown text without calling an LLM again:

```markdown
# Document: Lab Report
Date: 2025-02-10

## Laboratory Test Results
| Test Name | Result | Status | Reference Range |
|---|---|---|---|
| Serum Creatinine | 2.1 mg/dL | HIGH | 0.6-1.2 mg/dL |
| Hemoglobin | 11.2 g/dL | LOW | 13.5-17.5 g/dL |
```

### Step 3: Markdown Header Chunking & Vectorization
Using `MarkdownHeaderTextSplitter`, each `##` section is split into a self-contained chunk and embedded using Hugging Face open-source embedding models.

---

## 🤖 Open-Source Embedding Model Options

All selected models are open-weight, free, and can run locally or via Hugging Face Inference / FastEmbed:

| Model | Hugging Face ID | Vector Dim | Max Context | Highlights |
|---|---|---|---|---|
| **BGE-Small-v1.5** *(Default)* | `BAAI/bge-small-en-v1.5` | 384 | 512 tokens | High retrieval accuracy, ultra-lightweight (~130MB), fast on CPU |
| **BGE-M3** | `BAAI/bge-m3` | 1024 | 8192 tokens | Multilingual (English + Indic languages), handles long documents |
| **Nomic Embed Text** | `nomic-ai/nomic-embed-text-v1.5` | 768 | 8192 tokens | Fully open weights & open data, 8k context window |
| **MiniLM-L6-v2** | `sentence-transformers/all-MiniLM-L6-v2` | 384 | 256 tokens | Ultra-fast execution (~90MB model size) |

---

## 🔐 Database Schema & Security (Supabase pgvector)

To guarantee **patient data isolation** and prevent cross-patient data leaks, all embeddings are stored in Supabase Postgres with `patient_id` foreign keys and indexed via `pgvector`:

```sql
-- Table definition for RAG document chunks
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast similarity search
CREATE INDEX idx_document_embeddings_vector 
ON document_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- Patient-scoped similarity search function
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding VECTOR(384),
    match_patient_id UUID,
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        de.id,
        de.document_id,
        de.content,
        de.metadata,
        1 - (de.embedding <=> query_embedding) AS similarity
    FROM document_embeddings de
    WHERE de.patient_id = match_patient_id
      AND 1 - (de.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY de.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

---

## 🌿 AYUSH & Allopathic Domain Considerations

1. **Ayurvedic Formulations:**  
   Non-Western dosage forms (`churna`, `kwath`, `vati`, `taila`, `arishta`, `asava`) do not map to Western milligram dosages. The JSON-to-Markdown converter preserves vehicle (`anupana`, e.g., "warm water") and timing (`bedtime`, `before meals`) within the chunk.
2. **NAMASTE / ICD-11 Mapping:**  
   Extracted codes (e.g., NAMASTE codes for Ayurvedic diagnoses) are included directly in the Markdown chunk header to allow semantic search by both traditional condition names and diagnostic codes.
