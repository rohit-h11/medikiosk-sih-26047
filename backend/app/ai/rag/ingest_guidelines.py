"""
MediKiosk — Automated Clinical Guidelines & Morbidity Ingestion Engine
Parses official PDFs & Excel/CSV files, generates structured Markdown chunks,
computes 384-dim vector embeddings, and stores them in Supabase (Collection 1).
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("medikiosk.rag.ingestion")

# Project directories
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent.parent
RAW_GUIDELINES_DIR = PROJECT_ROOT / "backend" / "data" / "raw_guidelines"
PROCESSED_CHUNKS_DIR = PROJECT_ROOT / "backend" / "data" / "processed_chunks"
PROCESSED_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment
from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
load_dotenv(dotenv_path=PROJECT_ROOT / "backend" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ---------------------------------------------------------------------------
# Pydantic Quality Validator for Clinical Chunks
# ---------------------------------------------------------------------------
class ClinicalChunk(BaseModel):
    chunk_id: str
    domain: str = Field(..., description="'ayurveda' | 'allopathy' | 'morbidity_code' | 'prakriti_assessment'")
    category: str = Field(..., description="'treatment_protocol' | 'red_flag' | 'diagnostic_criteria' | 'pathya_apathya'")
    title: str = Field(..., min_length=3)
    content: str = Field(..., min_length=40)
    symptom_triggers: List[str] = Field(default_factory=list)
    urgency_level: str = Field(default="ROUTINE", description="'CRITICAL' | 'HIGH' | 'ROUTINE'")
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Embedding Model Helper
# ---------------------------------------------------------------------------
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: sentence-transformers/all-MiniLM-L6-v2...")
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def compute_embedding(text: str) -> List[float]:
    model = get_embedding_model()
    emb = model.encode(text, normalize_embeddings=True)
    return emb.tolist()

# ---------------------------------------------------------------------------
# Parser 1: NAMASTE Morbidity Excel / CSV Parser (Enhanced Readability)
# ---------------------------------------------------------------------------
def parse_namaste_morbidity(file_path: Path) -> List[ClinicalChunk]:
    logger.info(f"Parsing NAMASTE Morbidity Dataset: {file_path.name}")
    chunks = []
    
    try:
        import pandas as pd
        if file_path.suffix.lower() in ['.xls', '.xlsx']:
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
            
        logger.info(f"Read {len(df)} rows from {file_path.name}")

        for idx, row in df.iterrows():
            code = str(row.get("NAMC_CODE", f"AYU-{idx+1:04d}")).strip()
            devanagari = str(row.get("NAMC_term_DEVANAGARI", "")).strip()
            english_name = str(row.get("Name English", "")).strip()
            diacritical = str(row.get("NAMC_term_diacritical", "")).strip()
            short_def = str(row.get("Short_definition", "")).strip()
            long_def = str(row.get("Long_definition", "")).strip()

            # Clean out '-' placeholders
            if devanagari == "-" or devanagari.lower() == "nan":
                devanagari = ""
            if english_name == "-" or english_name.lower() == "nan":
                english_name = ""
            if diacritical == "-" or diacritical.lower() == "nan":
                diacritical = str(row.get("NAMC_term", "")).strip()

            # Construct clean composite title
            display_title = ""
            if devanagari and english_name:
                display_title = f"{devanagari} — {diacritical} ({english_name.title()})"
            elif devanagari:
                display_title = f"{devanagari} ({diacritical})"
            elif english_name:
                display_title = f"{diacritical} ({english_name.title()})"
            else:
                display_title = diacritical or code

            # Determine clinical definition / lakshana
            clinical_desc = ""
            if long_def and long_def != "-" and long_def.lower() != "nan":
                clinical_desc = long_def
            elif short_def and short_def != "-" and short_def.lower() != "nan":
                clinical_desc = short_def
            else:
                clinical_desc = f"Standard clinical manifestation of {english_name or diacritical} as cataloged under Ministry of Ayush NAMASTE morbidity records."

            chunk_id = f"namaste_{code.replace(' ', '_').replace('-', '_').replace('.', '_').lower()}_{idx}"
            
            # Format clean, highly readable Medical Fact Card
            content = (
                f"### 🌿 NAMASTE AYUSH Morbidity Standard: {display_title}\n"
                f"- **National Morbidity Code:** `{code}`\n"
                f"- **Sanskrit / Devanagari Term:** {devanagari if devanagari else 'N/A'}\n"
                f"- **English Clinical Term:** {english_name.title() if english_name else diacritical}\n"
                f"- **Standard Clinical Lakshana & Definition:** {clinical_desc}\n"
            )

            # Build rich symptom trigger keywords
            triggers = []
            if english_name:
                triggers.extend([w.strip().lower() for w in english_name.split() if len(w) > 3])
            if diacritical:
                triggers.append(diacritical.lower())
            if clinical_desc and len(clinical_desc) > 10:
                # Extract up to 4 key phrases from description
                phrases = [p.strip().lower() for p in clinical_desc.split(',') if len(p.strip()) > 3]
                triggers.extend(phrases[:4])

            # Filter out generic or empty triggers
            clean_triggers = list(dict.fromkeys([t for t in triggers if t and t != "-"]))[:6]

            # Urgency classification
            urgency = "ROUTINE"
            combined_text = (display_title + " " + clinical_desc).lower()
            if any(term in combined_text for term in ["asadhya", "incurable", "emergency", "severe", "paralysis", "loss of consciousness", "acute"]):
                urgency = "HIGH"

            chunk = ClinicalChunk(
                chunk_id=chunk_id,
                domain="morbidity_code",
                category="diagnostic_criteria",
                title=f"{display_title} [{code}]",
                content=content,
                symptom_triggers=clean_triggers,
                urgency_level=urgency,
                metadata={
                    "source_document": file_path.name,
                    "namaste_code": code,
                    "devanagari": devanagari,
                    "english_name": english_name,
                    "diacritical": diacritical,
                    "row_index": idx
                }
            )
            chunks.append(chunk)

    except Exception as e:
        logger.error(f"Failed to parse {file_path.name}: {e}")

    logger.info(f"Generated {len(chunks)} clinical chunks from NAMASTE dataset.")
    return chunks


# ---------------------------------------------------------------------------
# Parser 2: General PDF Parser with Page-Level Metadata
# ---------------------------------------------------------------------------
def parse_pdf_guideline(file_path: Path, domain: str, default_category: str) -> List[ClinicalChunk]:
    logger.info(f"Parsing PDF document: {file_path.name} (Domain: {domain})")
    chunks = []
    
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        logger.info(f"Opened {file_path.name} ({len(doc)} pages)")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            # Skip empty or cover pages
            if len(text) < 120:
                continue
                
            # Filter out table of contents / index noise
            lower_text = text.lower()
            if "table of contents" in lower_text or "isbn:" in lower_text and len(text) < 300:
                continue

            # Detect urgency / red flags
            urgency = "ROUTINE"
            if any(term in lower_text for term in ["emergency", "red flag", "urgent referral", "acute myocardial", "severe dyspnea", "anaphylaxis"]):
                urgency = "CRITICAL"
            elif any(term in lower_text for term in ["warning", "caution", "contraindication", "high risk"]):
                urgency = "HIGH"

            # Determine Title from first few lines
            lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 3]
            title = lines[0] if lines else f"{file_path.stem} Page {page_num+1}"
            if len(title) > 60:
                title = title[:57] + "..."

            chunk_id = f"{file_path.stem.lower()[:15]}_p{page_num+1}_{hashlib.md5(text[:50].encode()).hexdigest()[:6]}"
            
            # Prepend Contextual Header
            formatted_content = (
                f"### 📋 Clinical Guideline: {title}\n"
                f"**Source Document:** {file_path.name} | **Page:** {page_num+1} | **Urgency:** {urgency}\n\n"
                f"{text}\n"
            )

            chunk = ClinicalChunk(
                chunk_id=chunk_id,
                domain=domain,
                category="red_flag" if urgency == "CRITICAL" else default_category,
                title=title,
                content=formatted_content,
                symptom_triggers=[w.lower() for w in title.split() if len(w) > 4][:5],
                urgency_level=urgency,
                metadata={
                    "source_document": file_path.name,
                    "page_number": page_num + 1,
                    "edition": "Official",
                    "total_pages": len(doc)
                }
            )
            chunks.append(chunk)

    except Exception as e:
        logger.error(f"Error parsing PDF {file_path.name}: {e}")

    logger.info(f"Generated {len(chunks)} chunks from {file_path.name}")
    return chunks

# ---------------------------------------------------------------------------
# Main Ingestion Orchestrator
# ---------------------------------------------------------------------------
def run_ingestion(dry_run: bool = False, upload: bool = True):
    all_chunks: List[ClinicalChunk] = []
    
    if not RAW_GUIDELINES_DIR.exists():
        logger.error(f"Directory {RAW_GUIDELINES_DIR} does not exist.")
        return

    files = list(RAW_GUIDELINES_DIR.iterdir())
    logger.info(f"Found {len(files)} files in raw_guidelines folder.")

    for f in files:
        if f.name.startswith("."):
            continue
            
        fname_lower = f.name.lower()
        if fname_lower.endswith((".xls", ".xlsx", ".csv")) or "morbidity" in fname_lower:
            chunks = parse_namaste_morbidity(f)
            all_chunks.extend(chunks)
        elif "who" in fname_lower or "ayurveda" in fname_lower:
            chunks = parse_pdf_guideline(f, domain="ayurveda", default_category="treatment_protocol")
            all_chunks.extend(chunks)
        elif "prakriti" in fname_lower or "assessment" in fname_lower:
            chunks = parse_pdf_guideline(f, domain="prakriti_assessment", default_category="diagnostic_criteria")
            all_chunks.extend(chunks)
        elif "stw" in fname_lower or "manual" in fname_lower:
            chunks = parse_pdf_guideline(f, domain="allopathy", default_category="red_flag")
            all_chunks.extend(chunks)
        elif f.suffix.lower() == ".pdf":
            chunks = parse_pdf_guideline(f, domain="general_clinical", default_category="treatment_protocol")
            all_chunks.extend(chunks)

    logger.info(f"TOTAL CLINICAL CHUNKS EXTRACTED: {len(all_chunks)}")

    # 1. Export Preview JSON for Inspection
    preview_file = PROCESSED_CHUNKS_DIR / "clinical_guidelines_preview.json"
    with open(preview_file, "w", encoding="utf-8") as out:
        json.dump([c.model_dump() for c in all_chunks], out, indent=2, ensure_ascii=False)
    logger.info(f"💾 Saved local preview JSON to: {preview_file}")

    if dry_run or not upload:
        logger.info("Dry run complete. Vectors not uploaded to Supabase.")
        return

    # 2. Generate Vector Embeddings and Upload to Supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("SUPABASE_URL or SUPABASE_KEY missing in .env. Skipping cloud upload.")
        return

    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    logger.info("Computing vector embeddings with all-MiniLM-L6-v2 and uploading in batches...")
    model = get_embedding_model()
    
    batch_size = 50
    total_uploaded = 0
    
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        texts = [c.content for c in batch]
        embeddings = model.encode(texts, normalize_embeddings=True)
        
        rows = []
        for j, chunk in enumerate(batch):
            rows.append({
                "chunk_id": chunk.chunk_id,
                "domain": chunk.domain,
                "category": chunk.category,
                "title": chunk.title,
                "content": chunk.content,
                "symptom_triggers": chunk.symptom_triggers,
                "urgency_level": chunk.urgency_level,
                "metadata": chunk.metadata,
                "embedding": embeddings[j].tolist()
            })
            
        try:
            # Upsert into clinical_reference_vectors (on conflict chunk_id update)
            supabase.table("clinical_reference_vectors").upsert(rows, on_conflict="chunk_id").execute()
            total_uploaded += len(rows)
            logger.info(f"Uploaded batch {i//batch_size + 1} ({total_uploaded}/{len(all_chunks)} chunks)")
        except Exception as e:
            logger.error(f"Error uploading batch {i//batch_size + 1}: {e}")

    logger.info(f"🎉 SUCCESS: Fully ingested and embedded {total_uploaded} clinical guidelines chunks into Supabase!")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    run_ingestion(dry_run=is_dry, upload=not is_dry)
