-- 1. Enable the pgvector extension to work with embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the main table to store the RAG chunks and their vector embeddings
CREATE TABLE patient_structured_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    patient_id TEXT NOT NULL,
    document_id TEXT, -- Made optional since our OCR JSON might not always have one
    
    category TEXT, -- Example: 'clinical_summary', 'medications', 'ayurvedic_assessment'
    content TEXT NOT NULL, -- The actual markdown chunk with the header attached
    
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb, -- Store the original raw chunk metadata
    
    encounter_date DATE, -- Stored as an actual SQL Date for efficient filtering/recency decay
    
    -- The actual vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding VECTOR(384) NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Create Vector Index (HNSW with Cosine Distance) for fast similarity search
CREATE INDEX idx_patient_vectors_embedding_hnsw
ON patient_structured_vectors
USING hnsw (embedding vector_cosine_ops);

-- 4. Create standard indexes to make filtering lightning fast before vector search
CREATE INDEX idx_patient_vectors_patient ON patient_structured_vectors (patient_id);
CREATE INDEX idx_patient_vectors_patient_date ON patient_structured_vectors (patient_id, encounter_date);
CREATE INDEX idx_patient_vectors_patient_category ON patient_structured_vectors (patient_id, category);

-- 5. Create the Hybrid Retrieval Function (RPC) that Supabase/PostgREST can call directly
CREATE OR REPLACE FUNCTION match_patient_history(
    p_patient_id TEXT,
    p_query_embedding VECTOR(384),
    p_top_k INT DEFAULT 5,
    p_similarity_threshold REAL DEFAULT 0.40,
    p_category TEXT DEFAULT NULL,
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL,
    p_use_recency BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    id UUID,
    patient_id TEXT,
    category TEXT,
    content TEXT,
    metadata JSONB,
    encounter_date DATE,
    similarity REAL,
    recency REAL,
    final_score REAL
)
LANGUAGE SQL
AS $$
WITH candidates AS (
    -- Step A: Filter by patient and optional filters, and calculate semantic similarity
    SELECT
        v.*,
        1 - (v.embedding <=> p_query_embedding) AS similarity
    FROM patient_structured_vectors v
    WHERE v.patient_id = p_patient_id
      AND (p_category IS NULL OR v.category = p_category)
      AND (p_start_date IS NULL OR v.encounter_date >= p_start_date)
      AND (p_end_date IS NULL OR v.encounter_date <= p_end_date)
),
scored AS (
    -- Step B: Keep only chunks that pass the similarity threshold and calculate temporal decay (recency)
    SELECT
        c.*,
        CASE
            WHEN c.encounter_date IS NULL THEN 0.0
            ELSE
                1.0 / (
                    1.0 +
                    GREATEST(
                        0.0,
                        ((CURRENT_DATE - c.encounter_date)::REAL / 365.25)
                    )
                )
        END::REAL AS recency
    FROM candidates c
    WHERE c.similarity >= p_similarity_threshold
)
-- Step C: Combine the semantic similarity and recency into a final score, sort, and return Top K
SELECT
    s.id,
    s.patient_id,
    s.category,
    s.content,
    s.metadata,
    s.encounter_date,
    s.similarity::REAL,
    s.recency::REAL,
    (
        CASE
            WHEN p_use_recency
            THEN (0.80 * s.similarity + 0.20 * s.recency)
            ELSE s.similarity
        END
    )::REAL AS final_score
FROM scored s
ORDER BY final_score DESC
LIMIT GREATEST(1, LEAST(p_top_k, 20));
$$;
