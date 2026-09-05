-- ============================================================================
-- MediKiosk — Clinical Knowledge & Guidelines Vector Schema (Collection 1)
-- Stores static, authoritative government medical guidelines (CCRAS, WHO, ICMR, NAMASTE)
-- ============================================================================

-- 1. Ensure the pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the Clinical Reference Vectors Table
CREATE TABLE IF NOT EXISTS clinical_reference_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Deterministic unique ID to prevent duplicates (e.g., 'icmr_stw_v1_acs_p42', 'namaste_ayu_dis_0412')
    chunk_id TEXT UNIQUE NOT NULL,
    
    -- Clinical domain
    domain TEXT NOT NULL, -- 'ayurveda' | 'allopathy' | 'morbidity_code' | 'prakriti_assessment'
    
    -- Clinical category for filtered vector search
    category TEXT, -- 'treatment_protocol' | 'red_flag' | 'diagnostic_criteria' | 'socrates_exploration' | 'pathya_apathya'
    
    -- Title of the disease, syndrome, or protocol
    title TEXT NOT NULL,
    
    -- Rich contextual Markdown text chunk with citation header
    content TEXT NOT NULL,
    
    -- Search keywords / trigger terms for hybrid matching
    symptom_triggers TEXT[] DEFAULT '{}',
    
    -- Triage urgency level
    urgency_level TEXT DEFAULT 'ROUTINE', -- 'CRITICAL' | 'HIGH' | 'ROUTINE'
    
    -- Rich metadata (source_document, page_number, namaste_code, icd11_code, dosage, etc.)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- 384-dimensional vector embedding (all-MiniLM-L6-v2)
    embedding VECTOR(384) NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Create Vector Index (HNSW with Cosine Distance) for lightning-fast similarity search
CREATE INDEX IF NOT EXISTS idx_clinical_ref_embedding_hnsw
ON clinical_reference_vectors
USING hnsw (embedding vector_cosine_ops);

-- 4. Create Standard B-Tree Indexes for fast pre-filtering by domain & category
CREATE INDEX IF NOT EXISTS idx_clinical_ref_domain ON clinical_reference_vectors (domain);
CREATE INDEX IF NOT EXISTS idx_clinical_ref_category ON clinical_reference_vectors (category);
CREATE INDEX IF NOT EXISTS idx_clinical_ref_urgency ON clinical_reference_vectors (urgency_level);
CREATE INDEX IF NOT EXISTS idx_clinical_ref_chunk_id ON clinical_reference_vectors (chunk_id);

-- 5. Create the Hybrid Clinical Match RPC Function
CREATE OR REPLACE FUNCTION match_clinical_guidelines(
    p_query_embedding VECTOR(384),
    p_top_k INT DEFAULT 5,
    p_similarity_threshold REAL DEFAULT 0.35,
    p_domain TEXT DEFAULT NULL,
    p_category TEXT DEFAULT NULL,
    p_urgency_level TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    chunk_id TEXT,
    domain TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    symptom_triggers TEXT[],
    urgency_level TEXT,
    metadata JSONB,
    similarity REAL
)
LANGUAGE SQL
AS $$
WITH candidates AS (
    SELECT
        v.id,
        v.chunk_id,
        v.domain,
        v.category,
        v.title,
        v.content,
        v.symptom_triggers,
        v.urgency_level,
        v.metadata,
        (1 - (v.embedding <=> p_query_embedding))::REAL AS similarity
    FROM clinical_reference_vectors v
    WHERE (p_domain IS NULL OR v.domain = p_domain)
      AND (p_category IS NULL OR v.category = p_category)
      AND (p_urgency_level IS NULL OR v.urgency_level = p_urgency_level)
)
SELECT
    c.id,
    c.chunk_id,
    c.domain,
    c.category,
    c.title,
    c.content,
    c.symptom_triggers,
    c.urgency_level,
    c.metadata,
    c.similarity
FROM candidates c
WHERE c.similarity >= p_similarity_threshold
ORDER BY c.similarity DESC
LIMIT GREATEST(1, LEAST(p_top_k, 25));
$$;
