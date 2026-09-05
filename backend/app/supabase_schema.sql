-- ==============================================================================
-- MediKiosk — Master Supabase Database Schema & pgvector Setup
-- Execute this script in your Supabase Dashboard: SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------------------------
-- 2. Patients Table (Demographic Registry & ABHA Linkage)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY, -- Can be 'PAT-101', UUID, or ABHA address
    name TEXT NOT NULL,
    age INT,
    gender TEXT, -- 'male', 'female', 'other'
    phone TEXT,
    abha_number TEXT UNIQUE,
    abha_address TEXT UNIQUE,
    prakriti TEXT, -- 'Vata', 'Pitta', 'Kapha', 'Vata-Pitta', etc. (AYUSH)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 3. Clinical Visits Table (Encounter Records)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clinical_visits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_date DATE NOT NULL DEFAULT CURRENT_DATE,
    department TEXT DEFAULT 'General Medicine', -- or 'Ayurveda / Kayachikitsa'
    status TEXT NOT NULL DEFAULT 'in_progress', -- 'in_progress', 'completed', 'cancelled'
    triage_level TEXT DEFAULT 'normal', -- 'normal', 'priority', 'emergency_red_flag'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 4. Dialogue Sessions Table (Kiosk Interview Session Metadata)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dialogue_sessions (
    id TEXT PRIMARY KEY, -- Session ID string (e.g. 'sess_98432a10')
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_id UUID REFERENCES clinical_visits(id) ON DELETE SET NULL,
    language TEXT NOT NULL DEFAULT 'hi', -- 'hi', 'ta', 'te', 'mr', 'en', etc.
    turn_count INT NOT NULL DEFAULT 1,
    max_turns INT NOT NULL DEFAULT 6,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    chief_complaint TEXT,
    socrates_state JSONB NOT NULL DEFAULT '{}'::jsonb, -- Covered/missing slots
    red_flag_alert JSONB, -- Stores emergency alert details if detected
    last_question TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 5. Dialogue Messages Table (Conversation History Logs)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dialogue_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE CASCADE,
    turn_number INT NOT NULL,
    role TEXT NOT NULL, -- 'assistant' or 'patient'
    content_native TEXT NOT NULL, -- Spoken/rendered in patient's language
    content_english TEXT, -- Translated to English for clinical reasoning
    slot_tag TEXT, -- Optional touch button ID (e.g. 'opt_left_arm')
    audio_url TEXT, -- Link to stored audio file if uploaded
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 6. Patient Structured Vectors (RAG pgvector Embeddings Table)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patient_structured_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL,
    document_id TEXT, -- Optional (for OCR documents)
    category TEXT NOT NULL, -- 'clinical_interview', 'ocr_prescription', 'lab_report', 'ayurvedic_assessment'
    content TEXT NOT NULL, -- Markdown content chunk with contextual header
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    encounter_date DATE DEFAULT CURRENT_DATE,
    embedding VECTOR(384) NOT NULL, -- 384 dimensions for all-MiniLM-L6-v2
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 7. Performance Indexes
-- ------------------------------------------------------------------------------
-- Vector HNSW Index for sub-10ms Cosine Similarity search
CREATE INDEX IF NOT EXISTS idx_patient_vectors_embedding_hnsw
ON patient_structured_vectors
USING hnsw (embedding vector_cosine_ops);

-- Standard relational query indexes
CREATE INDEX IF NOT EXISTS idx_patient_vectors_patient ON patient_structured_vectors (patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_vectors_patient_date ON patient_structured_vectors (patient_id, encounter_date);
CREATE INDEX IF NOT EXISTS idx_patient_vectors_category ON patient_structured_vectors (patient_id, category);
CREATE INDEX IF NOT EXISTS idx_dialogue_messages_session ON dialogue_messages (session_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_sessions_patient ON dialogue_sessions (patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_visits_patient ON clinical_visits (patient_id);

-- ------------------------------------------------------------------------------
-- 8. Hybrid RAG Search RPC Function (Semantic Similarity + Temporal Decay)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_patient_history(
    p_patient_id TEXT,
    p_query_embedding VECTOR(384),
    p_top_k INT DEFAULT 5,
    p_similarity_threshold REAL DEFAULT 0.35,
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

-- ------------------------------------------------------------------------------
-- 9. Insert Demo Patient Record for Instant Testing
-- ------------------------------------------------------------------------------
INSERT INTO patients (id, name, age, gender, phone, abha_address)
VALUES ('PAT-DEMO-01', 'Ramesh Kumar', 52, 'male', '+919876543210', 'ramesh.kumar@abdm')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------------------------
-- 10. Patient Medical Documents Table (Storage Pointers & Pre-Ingestion Metadata)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patient_medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
    
    -- Categorization
    document_type TEXT NOT NULL DEFAULT 'prescription',
    -- Options: 'prescription', 'lab_report', 'discharge_summary', 'ayurvedic_record', 'other'
    
    -- Private Storage Bucket Paths
    storage_bucket TEXT NOT NULL DEFAULT 'patient-medical-records',
    file_path_raw TEXT,                  -- Untouched original upload (_raw.jpg/.pdf)
    file_path_processed TEXT NOT NULL,   -- Normalized, contrast-boosted WebP (_processed.webp)
    file_path_thumbnail TEXT NOT NULL,   -- 300px lightweight preview (_thumb.webp)
    
    -- Forensic Hashes & Technical Attributes
    file_hash_sha256 TEXT NOT NULL,      -- Exact byte-level cryptographic checksum
    perceptual_hash_dhash TEXT,          -- 64-bit structural visual fingerprint
    mime_type TEXT NOT NULL,             -- 'image/jpeg', 'image/png', 'image/webp', 'application/pdf'
    file_size_bytes BIGINT NOT NULL,
    page_count INT NOT NULL DEFAULT 1,
    
    -- Pre-Ingestion Quality Assessment Scores
    quality_score REAL DEFAULT 100.0,    -- Composite 0-100 score
    sharpness_score REAL DEFAULT 0.0,    -- Laplacian variance
    contrast_std REAL DEFAULT 0.0,
    glare_ratio REAL DEFAULT 0.0,
    
    -- Pipeline Lifecycle & Review
    ocr_status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'quality_rejected'
    is_reviewed_by_doctor BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by_doctor_id TEXT,
    doctor_notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 11. Document OCR Extracted Clinical Entities Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_ocr_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES patient_medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    raw_extracted_text TEXT NOT NULL,
    structured_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score REAL DEFAULT 0.95,
    abnormal_flags_detected JSONB DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance & Deduplication Query Indexes
CREATE INDEX IF NOT EXISTS idx_med_docs_patient ON patient_medical_documents (patient_id);
CREATE INDEX IF NOT EXISTS idx_med_docs_sha256 ON patient_medical_documents (patient_id, file_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_med_docs_dhash ON patient_medical_documents (patient_id, perceptual_hash_dhash);
CREATE INDEX IF NOT EXISTS idx_med_docs_status ON patient_medical_documents (ocr_status);
CREATE INDEX IF NOT EXISTS idx_ocr_extract_doc ON document_ocr_extractions (document_id);
CREATE INDEX IF NOT EXISTS idx_ocr_extract_patient ON document_ocr_extractions (patient_id);
