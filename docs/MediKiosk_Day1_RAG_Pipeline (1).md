# MediKiosk — OCR → Markdown → Embedding → Supabase Vector Retrieval
## Day-1 RAG Pipeline: Final Methodology and Implementation Plan

**Project:** MediKiosk — AI Clinical History Software Platform  
**Scope of this document:** Day-1 implementation for OCR-extracted medical documents.  
**Primary objective:** Convert the teammate's structured OCR/entity-extraction JSON into retrieval-ready Markdown, generate embeddings, store them in Supabase/PostgreSQL with pgvector, and provide controlled, patient-isolated retrieval for downstream physician-summary generation.

---

# 1. Scope and Design Principles

## 1.1 What this pipeline does

The pipeline handles **existing physical medical documents** such as:

- prescriptions
- laboratory reports
- discharge summaries
- investigation reports
- procedure/surgery records

The teammate's OCR + entity extraction component is assumed to produce structured JSON.

This RAG component then:

1. preserves the original JSON as the structured source of truth;
2. converts the JSON into clean human-readable Markdown;
3. chunks the Markdown by clinical section;
4. prepends document context to every chunk;
5. creates a local embedding using `sentence-transformers/all-MiniLM-L6-v2`;
6. stores embeddings in Supabase PostgreSQL using pgvector;
7. retrieves patient-specific chunks using vector similarity plus optional structured filters;
8. supplies the retrieved evidence to the downstream LLM.

## 1.2 What is explicitly out of scope for Day 1

- Voice/conversational history embedding
- Multilingual ASR
- OCR itself
- FHIR/ABDM implementation
- Doctor chatbot
- Knowledge graph
- Medical embedding-model fine-tuning
- Autonomous diagnosis
- Replacing deterministic SQL with vector search

The Day-1 goal is a reliable **document-history retrieval layer**, not the entire MediKiosk system.

---

# 2. Architecture

```text
Scanned Medical Documents
          |
          v
Teammate's OCR + Entity Extraction
          |
          v
Structured JSON
     |            |
     |            +--------------------+
     v                                 |
PostgreSQL / Supabase                  |
(source of truth)                      |
     |                                 |
     v                                 |
JSON -> Human-readable Markdown        |
     |                                 |
     v                                 |
Section-based Chunking                 |
     |                                 |
     v                                 |
Contextual Header                      |
     |                                 |
     v                                 |
all-MiniLM-L6-v2                       |
     |                                 |
     v                                 |
Supabase pgvector <-------------------+
     |
     v
Patient-isolated retrieval
     |
     +--------------------+
     |                    |
     v                    v
Vector retrieval     Structured SQL
     |                    |
     +----------+---------+
                |
                v
          Retrieved evidence
                |
                v
       Downstream LLM summary
                |
                v
        Physician-ready overview
```

The important architectural decision is that **JSON and embeddings serve different purposes**.

- JSON = exact structured data
- Markdown = semantic representation for embedding
- Vector database = semantic retrieval
- SQL = deterministic filtering/querying

Do not force embeddings to solve problems that SQL can solve exactly.

---

# 3. Why Keep the JSON Unchanged?

The original JSON should be stored exactly as received from the OCR/entity-extraction pipeline.

It remains the source of truth for:

- exact medication fields
- exact laboratory values
- diagnoses
- allergies
- dates
- UI tables
- FHIR/ABDM transformation later
- deterministic numerical calculations
- deterministic SQL queries

The Markdown is a **derived retrieval representation** and must never replace the JSON.

Recommended relationship:

```text
patient_data.json
       |
       +----> PostgreSQL structured data
       |
       +----> Markdown conversion
                    |
                    +----> embeddings
```

This prevents information loss caused by transforming structured data into natural language.

---

# 4. JSON → Markdown Conversion

## 4.1 Why convert to Markdown?

Raw JSON is not the ideal text representation for semantic retrieval.

Example:

```json
{
  "medications": [
    {
      "name": "Metformin",
      "dose": "500mg",
      "frequency": "1-0-1",
      "condition": "Diabetes"
    }
  ]
}
```

should become:

```markdown
## Medications
- **Metformin**: 500mg | Frequency: 1-0-1 | Condition: Diabetes
```

The Markdown is easier for both the embedding model and the downstream LLM to interpret.

## 4.2 Conversion rules

| JSON structure | Markdown representation |
|---|---|
| top-level object/key | `## Section Name` |
| nested dictionary | `- **Key**: Value` |
| list of dictionaries | one complete bullet per item |
| list of strings/numbers | one bullet per item |
| null | `(unspecified)` |
| empty string | `(unspecified)` |
| empty list | `None recorded` where clinically appropriate |
| numeric laboratory result | value + unit + reference range + computed qualitative flag |
| explicitly negative finding | explicit statement such as `Known Allergies: NONE` |

The converter must **not invent clinical facts**.

For example, if dosage is missing:

```markdown
- **Paracetamol**: Dosage: (unspecified)
```

Do not infer a dosage.

---

# 5. Handling Negation and Missing Information

This is a retrieval-critical issue.

Do not represent:

```text
allergies: []
```

only as an empty list in the semantic text.

Prefer:

```markdown
## Allergies
- Known Allergies: NONE RECORDED
```

Likewise:

```markdown
## Surgical History
- No prior surgeries recorded.
```

and:

```markdown
## Cardiac History
- Patient denies known cardiac disease.
```

The purpose is to make absence/negation explicit rather than relying on the embedding model to infer that an empty field means "none".

Important limitation:

> Explicit formatting reduces retrieval ambiguity; it does not guarantee that an embedding model will perfectly distinguish positive and negative statements.

Therefore, the final LLM prompt must also instruct the model to respect negation.

---

# 6. Laboratory Representation

Numeric values are important, but vector similarity is not a numerical reasoning engine.

Therefore, preserve the exact numeric value while also deriving a deterministic qualitative status.

Example:

```markdown
## Lab Results
- **HbA1c**: 8.2 % | Reference: 4.0–5.6 % | FLAG: HIGH
- **Serum Creatinine**: 0.9 mg/dL | Reference: 0.7–1.3 mg/dL | FLAG: NORMAL
```

Possible flags:

- NORMAL
- LOW
- HIGH
- CRITICAL LOW
- CRITICAL HIGH

The exact clinical reference/critical rules must come from the structured data/rules engine or trusted clinical configuration. Do not let the embedding model decide whether a number is medically abnormal.

The JSON remains the authoritative numeric source.

---

# 7. Temporal Information

Every document has an encounter/document date whenever available.

Every embedded chunk must retain:

```text
Patient
Document
Document type
Encounter date
Clinical status, when known
```

Example:

```markdown
[Patient: P-101 | Document: Prescription | Encounter Date: 2024-02-15 | Status: Recent]

## Medications
- **Metformin**: 500mg | Frequency: 1-0-1 | Condition: Diabetes
- **Amlodipine**: 5mg | Frequency: 0-0-1 | Condition: Hypertension
```

This prevents a chunk from becoming temporally ambiguous after it is separated from its source document.

If a medication is explicitly discontinued, represent that status:

```markdown
- **Metformin**: 500mg — DISCONTINUED on 2024-01-15
```

Do not infer discontinuation merely because a newer prescription exists.

---

# 8. Chunking Strategy

## 8.1 Primary rule

Chunk at Markdown clinical section boundaries.

For example:

```markdown
## Medications
...

## Diagnoses
...

## Lab Results
...

## Allergies
...
```

becomes separate chunks.

This is preferable to blindly using fixed-size windows because a clinical item such as:

```text
Metformin
500mg
1-0-1
```

should remain together.

## 8.2 Long sections

If a section becomes too large for the embedding model, split it at logical/sentence boundaries.

Repeat the contextual header in every resulting sub-chunk.

Example:

```text
[Patient: P-101 | Document: Discharge Summary | Date: 2024-02-15]

## Hospital Course — Part 1
...
```

and:

```text
[Patient: P-101 | Document: Discharge Summary | Date: 2024-02-15]

## Hospital Course — Part 2
...
```

## 8.3 Model input limit

`all-MiniLM-L6-v2` produces 384-dimensional embeddings and its model card states that inputs longer than 256 word pieces are truncated by default.

Therefore, do **not** assume that a 400-token chunk is safely embedded by this model.

For Day 1, target approximately **150–220 word pieces per chunk**, with an implementation-side token/length check.

If a section exceeds the target, split it.

This is a refinement of the earlier 400-token idea: the earlier design was conceptually correct about section-based chunking, but the actual selected model's documented truncation behavior makes conservative chunk sizes safer.

---

# 9. Contextual Header Design

Every chunk should contain:

```text
[Patient: <patient_id> |
 Document: <document_type> |
 Encounter Date: <date> |
 Status: <status>]
```

Example:

```markdown
[Patient: P-101 | Document: Prescription | Encounter Date: 2024-02-15 | Status: Active]

## Medications
- **Metformin**: 500mg | Frequency: 1-0-1 | Condition: Diabetes
```

## Why this is useful

It gives every vector:

- patient context
- temporal context
- document context
- clinical content

However, **patient_id is not being used as the security mechanism**. Patient isolation must be enforced by SQL/database access controls.

The header is contextual information for the embedding and returned text, not an authorization mechanism.

---

# 10. Embedding Model

## Selected model

```text
sentence-transformers/all-MiniLM-L6-v2
```

Reasons for retaining the existing choice:

- free
- local
- lightweight
- fast enough for a prototype
- 384-dimensional output
- designed for semantic similarity/information retrieval
- no API cost
- simple Python integration

The model card states that it maps text to 384-dimensional dense vectors and supports semantic search/similarity use cases.

Important implementation fact:

> Inputs longer than 256 word pieces are truncated by default.

Therefore, chunk sizing must respect this behavior.

For Day 1, **do not spend time replacing this model**. Establish a working retrieval baseline first.

A better medical/domain-specific embedding model can be evaluated later if retrieval evaluation shows that the baseline is inadequate.

---

# 11. Embedding Procedure

For every chunk:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

embedding = model.encode(
    chunk_text,
    normalize_embeddings=True
)
```

Use normalized embeddings consistently.

Store:

```text
VECTOR(384)
```

in pgvector.

Normalization makes cosine similarity a natural metric and keeps the embedding pipeline consistent.

---

# 12. Supabase Database Design

## 12.1 Structured table

Keep structured patient/document information separately.

Conceptually:

```text
patient_documents
-----------------
id
patient_id
document_type
encounter_date
raw_json
created_at
```

The exact schema can be adapted to the teammate's existing database.

## 12.2 Vector table

Recommended table:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE patient_structured_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    patient_id TEXT NOT NULL,
    document_id TEXT NOT NULL,

    category TEXT NOT NULL,
    content TEXT NOT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    encounter_date DATE,

    embedding VECTOR(384) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Why add `encounter_date` as a real column?

The earlier design stored the date inside Markdown/metadata. Keep that, but also store it as a typed SQL column.

This makes:

```sql
WHERE encounter_date >= ...
```

and ordering/filtering deterministic and efficient.

Do not force SQL date filtering to parse a Markdown string or JSON value.

---

# 13. Indexes

Use the cosine-distance HNSW index:

```sql
CREATE INDEX idx_patient_vectors_embedding_hnsw
ON patient_structured_vectors
USING hnsw (embedding vector_cosine_ops);
```

Also create filtering indexes:

```sql
CREATE INDEX idx_patient_vectors_patient
ON patient_structured_vectors (patient_id);

CREATE INDEX idx_patient_vectors_patient_date
ON patient_structured_vectors (patient_id, encounter_date);

CREATE INDEX idx_patient_vectors_patient_category
ON patient_structured_vectors (patient_id, category);
```

The pgvector documentation supports HNSW with cosine distance and recommends indexing filter columns when filtering vector searches.

For a small SIH prototype, exact search may be perfectly adequate. HNSW is useful when the dataset grows.

---

# 14. Cosine Similarity

pgvector's:

```sql
embedding <=> query_embedding
```

returns cosine **distance**, where lower is better.

Convert to similarity:

```sql
1 - (embedding <=> query_embedding)
```

So:

```text
distance = 0.10
similarity = 0.90
```

and:

```text
distance = 0.40
similarity = 0.60
```

Use one convention consistently throughout the project.

---

# 15. Minimum Similarity Threshold

Do not claim that a universal value such as 0.75 is medically meaningful.

Similarity thresholds depend on:

- embedding model
- chunk format
- query wording
- corpus
- domain

For the first implementation, use:

```text
SIMILARITY_THRESHOLD = 0.40
```

as an **initial experimental value**, not a scientifically validated threshold.

Then evaluate it using representative queries.

Example:

```text
Query:
"previous cardiovascular history"

Candidate:
"History of hypertension and coronary artery disease..."

Similarity:
0.72 → retain

Candidate:
"Routine ophthalmology prescription..."

Similarity:
0.24 → reject
```

The final threshold should be chosen from retrieval evaluation rather than intuition.

---

# 16. Top-K

Initial value:

```text
TOP_K = 5
```

Reason:

- the output is an overview, not a complete document reproduction;
- section-level chunks contain substantial information;
- excessive context increases irrelevant information sent to the LLM;
- 5 gives a manageable initial retrieval budget.

Keep it configurable.

Recommended testing:

```text
K = 3
K = 5
K = 8
K = 10
```

Do not permanently hardcode 5 until evaluation confirms it.

---

# 17. Category Filtering

Category filtering should be **optional**.

Example categories:

```text
medication
lab
diagnosis
allergy
surgery
procedure
hospitalization
other
```

If:

```text
category = NULL
```

search all categories.

If:

```text
category = 'medication'
```

restrict retrieval to medication chunks.

This filter belongs inside the database retrieval function.

---

# 18. Date Filtering

Date filtering should also be optional.

Examples:

### Recent history

```text
start_date = 2025-01-01
```

### Specific period

```text
start_date = 2024-01-01
end_date   = 2024-12-31
```

### Entire history

```text
start_date = NULL
end_date = NULL
```

Do not automatically discard old records just because they are old.

A five-year-old surgery can be more clinically important than a two-week-old minor prescription.

---

# 19. Similarity + Recency

This is useful as a **secondary ranking signal**, not as a replacement for semantic relevance.

Define:

```text
S = semantic similarity, 0 to 1
R = recency score, 0 to 1
```

Use:

```text
FINAL_SCORE = 0.80 * S + 0.20 * R
```

Initial weights:

```text
semantic = 80%
recency  = 20%
```

This preserves the fundamental principle:

> Clinical relevance should dominate freshness.

## Recency function

Use a simple deterministic decay:

```text
R = 1 / (1 + age_in_years)
```

Examples:

| Age | R |
|---:|---:|
| 0 years | 1.00 |
| 1 year | 0.50 |
| 2 years | 0.33 |
| 4 years | 0.20 |

This is deliberately simple and easy to explain in an SIH presentation.

### Important limitation

Recency must not override explicit clinical status.

For example:

```text
Metformin — DISCONTINUED
```

must not become current merely because another ranking mechanism scores that chunk highly.

Structured status/date logic should remain authoritative.

---

# 20. When NOT to Use Similarity + Recency

Some requests should be handled primarily by deterministic SQL.

Examples:

### "What are the latest medications?"

Use:

```text
category = medication
ORDER BY encounter_date DESC
```

plus medication status.

### "Show abnormal lab results."

Use structured lab values/reference ranges/flags.

### "What allergies are recorded?"

Use structured allergy data.

### "Show the most recent discharge summary."

Use:

```text
document_type = discharge_summary
ORDER BY encounter_date DESC
LIMIT 1
```

Vector retrieval is best for semantic questions, not every database operation.

---

# 21. Hybrid Retrieval Architecture

Final Day-1 design:

```text
                  Doctor Query / Retrieval Task
                              |
                +-------------+-------------+
                |                           |
                v                           v
        Structured SQL                Vector Search
        exact facts                  semantic relevance
                |                           |
                |                           |
                +-------------+-------------+
                              |
                              v
                    Evidence assembly
                              |
                              v
                         LLM prompt
                              |
                              v
                 Physician-ready overview
```

This is the preferred architecture.

Examples:

| Request | Preferred method |
|---|---|
| Latest medications | SQL |
| Abnormal labs | SQL |
| Known allergies | SQL |
| Most recent document | SQL |
| Relevant cardiovascular history | Vector |
| Relevant diabetes history | Vector |
| Important prior hospitalization related to current context | Vector |
| Overall history overview | Hybrid |

---

# 22. Retrieval RPC

Recommended conceptual API:

```text
match_patient_history(
    p_patient_id,
    p_query_embedding,
    p_top_k,
    p_similarity_threshold,
    p_category,
    p_start_date,
    p_end_date,
    p_use_recency
)
```

Suggested defaults:

```text
top_k = 5
similarity_threshold = 0.40
category = NULL
start_date = NULL
end_date = NULL
use_recency = TRUE
```

---

# 23. Retrieval Algorithm

The logical sequence should be:

```text
1. Identify patient
       ↓
2. Restrict candidate rows to that patient
       ↓
3. Apply optional category filter
       ↓
4. Apply optional date filter
       ↓
5. Calculate cosine similarity
       ↓
6. Reject results below similarity threshold
       ↓
7. Calculate recency score when enabled
       ↓
8. Calculate final combined score
       ↓
9. Sort by final score
       ↓
10. Return top K
```

Patient isolation is a security requirement.

Do not retrieve globally and then filter patient records in application code.

---

# 24. Example SQL Function

The following is a prototype pattern and should be adapted to the actual Supabase schema and security model.

```sql
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
    document_id TEXT,
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
                        EXTRACT(
                            EPOCH FROM (CURRENT_DATE - c.encounter_date)
                        ) / (365.25 * 24 * 60 * 60)
                    )
                )
        END::REAL AS recency
    FROM candidates c
    WHERE c.similarity >= p_similarity_threshold
)
SELECT
    s.id,
    s.patient_id,
    s.document_id,
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
```

## Important production note

For a larger corpus with HNSW and selective filters, benchmark the query plan and pgvector filtering behavior. Approximate vector indexes can interact with filtering differently from exact search, and pgvector provides iterative scans for filtered ANN searches.

For the SIH prototype, correctness and evaluation should come before premature performance tuning.

---

# 25. Security

At minimum:

- patient ID must be supplied as a required retrieval constraint;
- vector retrieval must never be global across patients;
- application users must only be authorized to access the relevant patient;
- Supabase Row Level Security should be considered as an additional database-level protection;
- service-role credentials must never be exposed to the browser/client;
- retrieved context should contain only information authorized for the current encounter/user.

The `patient_id` filter in the RPC is part of the retrieval design, but it is **not by itself a complete authorization system**.

---

# 26. Metadata

Recommended metadata:

```json
{
  "patient_id": "P-101",
  "document_id": "DOC-123",
  "document_type": "Prescription",
  "encounter_date": "2024-02-15",
  "category": "medication",
  "source": "scanned_document",
  "chunk_index": 0
}
```

Do not put the entire raw JSON into every vector row if it becomes large.

Better:

- store authoritative raw JSON in the structured document table;
- store lightweight retrieval metadata in the vector row;
- use `document_id` to fetch the original structured record when needed.

This keeps vector rows focused on retrieval.

---

# 27. End-to-End Implementation

## Stage A — Input validation

Input:

```text
patient_data.json
```

Validate:

- valid JSON
- required patient/document identifiers
- valid date formats where available
- expected top-level categories
- correct types for lists/dictionaries

Do not silently corrupt malformed data.

---

## Stage B — JSON preservation

Store the original JSON unchanged.

```text
raw JSON
   ↓
structured PostgreSQL storage
```

---

## Stage C — JSON → Markdown

Run the converter.

```text
JSON
 ↓
clean empty values
 ↓
preserve exact values
 ↓
generate explicit negative statements
 ↓
add laboratory flags
 ↓
generate Markdown sections
```

Output:

```text
patient_data.md
```

---

## Stage D — Chunking

```text
patient_data.md
       ↓
split at clinical headers
       ↓
check chunk length
       ↓
split oversized sections
       ↓
prepend contextual header
```

Output:

```text
chunk_001
chunk_002
chunk_003
...
```

---

## Stage E — Embedding

For each chunk:

```text
chunk text
   ↓
all-MiniLM-L6-v2
   ↓
384-dimensional normalized vector
```

---

## Stage F — Database insertion

Insert:

```text
patient_id
document_id
category
content
metadata
encounter_date
embedding
```

---

## Stage G — Retrieval

Doctor/query context:

```text
query text
   ↓
same embedding model
   ↓
query vector
   ↓
match_patient_history(...)
   ↓
top-k evidence
```

The **same embedding model and preprocessing assumptions** must be used for documents and queries.

---

# 28. Testing Strategy

Do not judge the system only by whether the SQL executes.

Create a small retrieval test set.

Example queries:

```text
1. What medications is the patient taking?
2. What is the patient's diabetes history?
3. Are there any known allergies?
4. What abnormal laboratory results are present?
5. What previous surgeries are recorded?
6. What cardiovascular history is documented?
7. What are the most recent important medical events?
8. Give me a general overview of the patient's prior medical history.
```

For each query manually inspect:

- Was the correct category retrieved?
- Was the correct patient retrieved?
- Was the correct date retrieved?
- Were old records incorrectly treated as current?
- Were negated findings interpreted correctly?
- Were irrelevant chunks returned?
- Was an important old record lost because of recency?
- Did the threshold eliminate useful evidence?
- Did Top-K provide enough context?

---

# 29. Threshold Evaluation

Test:

```text
0.30
0.35
0.40
0.45
0.50
```

Do not assume one value is universally correct.

For each threshold record:

```text
Relevant retrieved
Irrelevant retrieved
Relevant missed
```

The goal is high recall for clinically important information without flooding the LLM with irrelevant material.

---

# 30. Top-K Evaluation

Test:

```text
K = 3
K = 5
K = 8
K = 10
```

Compare:

- retrieval completeness
- irrelevant context
- prompt size
- latency

Initial default:

```text
K = 5
```

---

# 31. Recency Evaluation

Create a test patient with:

```text
2022: Metformin
2024: Metformin discontinued
2024: Glimepiride started
2026: latest medication list
```

Test:

```text
"current diabetes medications"
```

The system should not simply return the semantically similar old Metformin record and treat it as current.

The structured medication/status/date layer should resolve currentness.

Then test:

```text
"history of diabetes treatment"
```

where older records can legitimately be useful.

---

# 32. Failure Handling

### Missing date

Do not invent one.

Use:

```text
encounter_date = NULL
```

and:

```text
recency = 0
```

or exclude date-dependent ranking for that record.

### Missing category

Use:

```text
category = "other"
```

only if the source information is genuinely uncategorized.

Do not guess a medical category.

### Malformed JSON

Fail the document conversion with a clear error.

Do not generate partial clinical Markdown silently.

### Empty document

Do not generate embeddings for an empty chunk.

### Very long section

Split before embedding.

### No retrieval results

Return an explicit "no sufficiently relevant evidence found" state.

Do not ask the LLM to invent an answer.

---

# 33. LLM Grounding Rule

The downstream LLM should receive instructions equivalent to:

```text
Use only the supplied retrieved clinical evidence.

Do not invent diagnoses, medications, laboratory values,
allergies, surgeries, or dates.

Distinguish historical information from current information.

Respect explicit negation such as:
NONE, denies, no history of, negative for.

If the evidence is insufficient, state that the information
is not available in the retrieved records.

Do not make an autonomous diagnosis.
```

The RAG system retrieves evidence; it does not authorize the LLM to create medical facts.

---

# 34. Final Day-1 Pipeline

```text
                  SCANNED DOCUMENT
                         |
                         v
              OCR + ENTITY EXTRACTION
                         |
                         v
                 STRUCTURED JSON
                    /          \
                   /            \
                  v              v
          PostgreSQL        JSON -> Markdown
          source data             |
                                  v
                         Clean clinical text
                                  |
                                  v
                         Section-based chunks
                                  |
                                  v
                       Contextual metadata
                                  |
                                  v
                    all-MiniLM-L6-v2
                       384 dimensions
                                  |
                                  v
                         Supabase pgvector
                                  |
                                  v
                    Patient-isolated retrieval
                                  |
                  +---------------+---------------+
                  |                               |
                  v                               v
            Vector similarity               SQL filters
                  |                               |
                  +---------------+---------------+
                                  |
                                  v
                     Threshold + ranking
                                  |
                                  v
                       Top-K evidence
                                  |
                                  v
                           LLM context
                                  |
                                  v
                  Physician-ready health overview
```

---

# 35. Final Decisions

| Decision | Final choice |
|---|---|
| Structured source | Original JSON |
| Semantic representation | Human-readable Markdown |
| Markdown chunking | Clinical section boundaries |
| Oversized chunks | Sentence/logical-boundary splitting |
| Embedding model | `all-MiniLM-L6-v2` |
| Dimensions | 384 |
| Embedding normalization | Yes |
| Similarity metric | Cosine |
| Vector DB | Supabase PostgreSQL + pgvector |
| Vector index | HNSW |
| Initial Top-K | 5 |
| Initial similarity threshold | 0.40 |
| Category filter | Optional |
| Date filter | Optional |
| Recency | Optional secondary signal |
| Initial ranking | 0.80 similarity + 0.20 recency |
| Current medication/latest facts | Prefer structured SQL |
| Semantic clinical questions | Vector retrieval |
| Patient isolation | Mandatory DB-level filtering + authorization/RLS |
| LLM role | Summarization/grounding, not diagnosis |
| Multilingual processing | Handled upstream for Day 1 |
| Voice history | Deferred |
| FHIR/ABDM | Deferred |
| Fine-tuning | Deferred |

---

# 36. Important Implementation Philosophy

The system should not be described as:

> "We put medical JSON into a vector database and ask an LLM questions."

The stronger description is:

> **"We preserve structured clinical data as the authoritative source, create a semantically optimized representation for retrieval, enforce patient-level isolation and deterministic metadata filters in PostgreSQL, use vector similarity for semantic relevance, optionally incorporate temporal relevance, and provide only retrieved evidence to the downstream summarization model."**

That is the architecture to implement for Day 1.

---

# 37. Immediate Coding Order

Implement in exactly this order:

```text
1. JSON validator
        ↓
2. JSON → Markdown converter
        ↓
3. Markdown section chunker
        ↓
4. Contextual header generator
        ↓
5. Chunk length validation
        ↓
6. all-MiniLM-L6-v2 embedding generator
        ↓
7. Supabase vector table
        ↓
8. Indexes
        ↓
9. Vector insertion
        ↓
10. Basic patient-filtered similarity RPC
        ↓
11. Similarity threshold
        ↓
12. Optional category filter
        ↓
13. Optional date filter
        ↓
14. Recency score
        ↓
15. Combined ranking
        ↓
16. Retrieval evaluation
        ↓
17. Tune threshold / Top-K / weights
```

**Do not optimize the model before the retrieval pipeline works end-to-end.**

The first milestone is:

> Given one JSON file and one query, the system returns the correct clinical chunks for that patient.

Once that works reliably, tune retrieval quality.

---

# References

- Supabase pgvector documentation: https://supabase.com/docs/guides/database/extensions/pgvector
- Supabase semantic search documentation: https://supabase.com/docs/guides/ai/semantic-search
- pgvector documentation: https://github.com/pgvector/pgvector
- `sentence-transformers/all-MiniLM-L6-v2` model card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

