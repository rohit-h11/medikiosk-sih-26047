"""
Master Medical Guideline Processing & Clinical Knowledge Base Generator.

Extracts, cleans, and structures:
1. CCRAS Standardized Prakriti Assessment Tool (Physical, Metabolic, Behavioral, Scoring)
2. WHO Ayurveda Practice Benchmarks (Panchakarma, Safety, Diagnosis, Preventive)
3. ICMR Standard Treatment Workflows Vol 1 & 3 (Emergency, Cardiology, Medicine, Triage)

Outputs:
- `backend/data/processed_chunks/clinical_knowledge_base.md` (Human-readable Handbook)
- `backend/data/processed_chunks/clinical_knowledge_chunks.json` (Structured RAG Chunks)
"""

import os
import sys
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pymupdf as fitz
from dotenv import load_dotenv
from google import genai

load_dotenv("backend/.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in backend/.env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.6-flash"

PROCESSED_DIR = Path("backend/data/processed_chunks")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

MD_OUT_PATH = PROCESSED_DIR / "clinical_knowledge_base.md"
JSON_OUT_PATH = PROCESSED_DIR / "clinical_knowledge_chunks.json"

def call_llm_json(prompt: str, max_retries: int = 3) -> Dict[str, Any]:
    """Calls Gemini 3.6 Flash to extract structured clinical JSON."""
    for attempt in range(max_retries):
        try:
            resp = gemini_client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            raw = resp.text.strip()
            # Clean possible markdown code fence wrappers
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?", "", raw).strip()
                raw = re.sub(r"```$", "", raw).strip()
            return json.loads(raw)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                print(f"LLM call failed after {max_retries} attempts: {e}", flush=True)
                return {}

def process_ccras_prakriti(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extracts the 40-item Prakriti Assessment Scale from CCRAS research paper."""
    print(f"\n--- [1/3] Processing CCRAS Prakriti Guidelines ({pdf_path.name}) ---", flush=True)
    doc = fitz.open(pdf_path)
    chunks = []

    scale_text = ""
    for page_idx in range(5, min(38, len(doc))):
        text = doc[page_idx].get_text("text").strip()
        if "Table" in text or "Predictor" in text or "Prakriti" in text:
            scale_text += f"\n--- Page {page_idx+1} ---\n" + text

    sections = [
        ("Physical & Anatomical Predictors", "Body frame, skin texture, hair characteristics, complexion, teeth, joints, nails, forehead, eyes"),
        ("Physiological & Metabolic Predictors", "Digestive fire (Agni), appetite, bowel evacuation, sleep pattern, perspiration, physical endurance (Bala), taste preferences"),
        ("Psychological & Behavioral Predictors", "Memory retention, emotional stability, speech velocity, anger threshold, grasping power, dream patterns, spiritual inclination"),
        ("Standard Clinical Scoring & Diagnostic Triage Matrix", "Mathematical weighting, scoring thresholds for Vataja, Pittaja, Kaphaja, and Dwandwaja Prakriti classification in Kiosk")
    ]

    for sec_title, sec_desc in sections:
        print(f"  Generating knowledge card: '{sec_title}'...", flush=True)
        prompt = f"""You are a Senior Ayurvedic Clinical Informatics Specialist.
From the CCRAS Standardized Prakriti Assessment Tool literature, create a definitive, high-density Clinical Knowledge Card for '{sec_title}'.
Focus areas: {sec_desc}.

Source Text Extract:
{scale_text[:15000]}

You MUST output ONLY valid JSON without markdown fences matching this schema:
{{
  "title": "CCRAS Standardized Prakriti Assessment: {sec_title}",
  "category": "diagnostic_criteria",
  "urgency_level": "ROUTINE",
  "clean_markdown": "Structured markdown with: (1) Core Classical Clinical Concept, (2) Diagnostic Assessment Table with columns [Trait, Sanskrit Term (Devanagari/Roman), Clinical Indicator, Primary Dosha Correlation (Vata/Pitta/Kapha)], and (3) Examination Guidelines for Automated Kiosk Scoring",
  "symptom_triggers": ["8-12 search keywords in English, Sanskrit, and Hindi"]
}}"""

        res = call_llm_json(prompt)
        if res and "clean_markdown" in res:
            chunk_id = f"ccras_prakriti_{re.sub(r'[^a-zA-Z0-9]', '_', sec_title).lower()}"
            chunks.append({
                "chunk_id": chunk_id,
                "domain": "prakriti_assessment",
                "category": "diagnostic_criteria",
                "title": res.get("title", f"CCRAS Prakriti Assessment: {sec_title}"),
                "content": f"### 🌿 {res.get('title', f'CCRAS Prakriti Assessment: {sec_title}')}\n**Source:** CCRAS Standardized Prakriti Assessment Guidelines | **Domain:** Ayurvedic Constitutional Diagnosis\n\n{res['clean_markdown']}",
                "symptom_triggers": res.get("symptom_triggers", []),
                "urgency_level": "ROUTINE",
                "metadata": {
                    "source_document": pdf_path.name,
                    "guideline_body": "Central Council for Research in Ayurvedic Sciences (CCRAS)",
                    "system": "ayurvedic"
                }
            })
            print(f"  ✓ Finished: {res.get('title')}", flush=True)
        time.sleep(1)

    return chunks

def process_who_ayurveda(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extracts WHO safety benchmarks, panchakarma indications and contraindications."""
    print(f"\n--- [2/3] Processing WHO Ayurveda Practice Benchmarks ({pdf_path.name}) ---", flush=True)
    doc = fitz.open(pdf_path)
    chunks = []

    key_topics = [
        ("Panchakarma Procedures, Indications & Strict Contraindications", ["vamana", "virechana", "basti", "nasya", "raktamokshana", "contraindications", "indications"]),
        ("Ayurvedic Diagnostic Assessment Principles (Trividha, Ashtavidha Pariksha)", ["darshana", "sparshana", "prashna", "nadi", "mutra", "mala", "jihva", "shabda"]),
        ("Safety, Pharmacovigilance & Herb-Drug Interaction Protocols", ["adverse events", "precautions", "toxic", "dosage", "anupana", "safety benchmarks", "interaction"]),
        ("Promotive, Preventive and Curative Health Interventions (Swasthavritta)", ["svasthavrutta", "dinacharya", "ritucharya", "rasayana", "ahara", "vihara"])
    ]

    for topic_title, keywords in key_topics:
        print(f"  Generating WHO benchmark card: '{topic_title}'...", flush=True)
        matching_text = ""
        matched_pages = []
        for page_idx in range(len(doc)):
            text = doc[page_idx].get_text("text").strip()
            if any(kw in text.lower() for kw in keywords):
                matching_text += f"\n--- Page {page_idx+1} ---\n" + text[:2500]
                matched_pages.append(page_idx + 1)
                if len(matching_text) > 12000:
                    break

        prompt = f"""You are a World Health Organization (WHO) Traditional Medicine Expert.
From the WHO Benchmarks for the Practice of Ayurveda, construct a comprehensive, authoritative Clinical Knowledge Card for '{topic_title}'.

Extracted Text:
{matching_text[:15000]}

You MUST output ONLY valid JSON without markdown fences matching this schema:
{{
  "title": "WHO Benchmark: {topic_title}",
  "category": "treatment_protocol",
  "urgency_level": "HIGH" if "Safety" in topic_title or "Contraindications" in topic_title else "ROUTINE",
  "clean_markdown": "Structured markdown with: (1) International Benchmark Principles, (2) Clinical Indications & Contraindications Matrix, (3) Operative Safety Guidelines, (4) Immediate Red Flags / Discontinuation Protocols",
  "symptom_triggers": ["8-12 search keywords in English, Sanskrit, and Hindi"]
}}"""

        res = call_llm_json(prompt)
        if res and "clean_markdown" in res:
            chunk_id = f"who_ayurveda_{re.sub(r'[^a-zA-Z0-9]', '_', topic_title).lower()[:32]}"
            chunks.append({
                "chunk_id": chunk_id,
                "domain": "ayurveda",
                "category": res.get("category", "treatment_protocol"),
                "title": res.get("title", f"WHO Benchmark: {topic_title}"),
                "content": f"### 🌐 {res.get('title', f'WHO Benchmark: {topic_title}')}\n**Source:** WHO Benchmarks for the Practice of Ayurveda | **Relevant Pages:** {matched_pages[:4]}\n\n{res['clean_markdown']}",
                "symptom_triggers": res.get("symptom_triggers", []),
                "urgency_level": res.get("urgency_level", "ROUTINE"),
                "metadata": {
                    "source_document": pdf_path.name,
                    "guideline_body": "World Health Organization (WHO)",
                    "system": "ayurvedic"
                }
            })
            print(f"  ✓ Finished: {res.get('title')}", flush=True)
        time.sleep(1)

    return chunks

def process_icmr_stws(pdf_path: Path, volume_label: str, max_workflows: int = 12) -> List[Dict[str, Any]]:
    """Extracts core emergency and chronic disease treatment workflows from ICMR STW PDF."""
    print(f"\n--- [3/3] Processing ICMR Standard Treatment Workflows ({volume_label}) ---", flush=True)
    doc = fitz.open(pdf_path)
    chunks = []

    clinical_pages = []
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text("text").strip()
        if len(text) < 200:
            continue
        lower = text.lower()
        if any(kw in lower for kw in ["standard treatment workflow", "stw", "icd-10", "management of", "immediate intervention", "investigations", "level 1", "level 2"]):
            if not any(skip in lower for skip in ["editorial board", "table of contents", "acknowledgements", "diary no.", "suggested citation"]):
                clinical_pages.append((page_idx + 1, text))

    print(f"  Found {len(clinical_pages)} clinical workflow pages. Processing top {min(len(clinical_pages), max_workflows)} workflows...", flush=True)

    for page_num, raw_text in clinical_pages[:max_workflows]:
        first_line = raw_text.split('\n')[0].strip()
        print(f"  Processing Page {page_num} ({first_line[:40]})...", flush=True)
        prompt = f"""You are a Senior Clinical Guideline Specialist for an AI Medical Kiosk Emergency & Primary Triage system.
Transform this raw ICMR Standard Treatment Workflow page ({volume_label}, Page {page_num}) into an expert Clinical Knowledge Card.

Raw Text:
{raw_text[:4500]}

You MUST output ONLY valid JSON without markdown fences matching this schema:
{{
  "title": "Exact clinical condition title (e.g. ICMR Protocol: Acute Coronary Syndrome / STEMI)",
  "category": "treatment_protocol",
  "urgency_level": "HIGH" if any emergency/critical condition else "ROUTINE",
  "clean_markdown": "Structured markdown with:\\n- **ICD-10 Code & Definition**\\n- **Immediate Red Flags & Emergency Triage Indicators**\\n- **Diagnostic Workup (Basic vs Desirable vs Optional)**\\n- **Pharmacotherapy & Step-by-Step Management**\\n- **Level-wise Referral Protocol (PHC/CHC -> District Hospital -> Tertiary Centre)**",
  "symptom_triggers": ["6-10 clinical search keywords in English"]
}}"""

        res = call_llm_json(prompt)
        if res and "title" in res and "clean_markdown" in res:
            clean_code_id = re.sub(r"[^a-zA-Z0-9]", "_", pdf_path.stem).lower()
            chunk_id = f"{clean_code_id}_p{page_num}"
            chunks.append({
                "chunk_id": chunk_id,
                "domain": "allopathy",
                "category": res.get("category", "treatment_protocol"),
                "title": res["title"],
                "content": f"### 📋 {res['title']}\n**Source:** ICMR Standard Treatment Workflows ({volume_label}) | **Page:** {page_num} | **Urgency:** {res.get('urgency_level', 'ROUTINE')}\n\n{res['clean_markdown']}",
                "symptom_triggers": res.get("symptom_triggers", []),
                "urgency_level": res.get("urgency_level", "ROUTINE"),
                "metadata": {
                    "source_document": pdf_path.name,
                    "page_number": page_num,
                    "guideline_body": "Indian Council of Medical Research (ICMR)",
                    "system": "allopathic"
                }
            })
            print(f"  ✓ Finished Page {page_num}: {res['title']}", flush=True)
        time.sleep(1)

    return chunks

def compile_and_save(all_chunks: List[Dict[str, Any]]):
    """Compiles all chunks into a beautiful human-readable .md handbook and .json file."""
    print(f"\n=======================================================", flush=True)
    print(f"Compiling {len(all_chunks)} Clinical Knowledge Chunks...", flush=True)

    # 1. Save JSON
    with open(JSON_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Structured JSON: {JSON_OUT_PATH}", flush=True)

    # 2. Save Markdown Handbook
    md_lines = [
        "# 🏥 MediKiosk Clinical Guidelines & Triage Knowledge Base",
        "*Integrated Allopathy (ICMR STWs) + Ayurveda (CCRAS, WHO Benchmarks)*\n",
        "---",
        "## 📑 Table of Contents\n"
    ]

    for i, c in enumerate(all_chunks, 1):
        domain_badge = "🩺 Allopathy" if c["domain"] == "allopathy" else ("🌿 Ayurveda" if c["domain"] == "ayurveda" else "🧬 Prakriti")
        urgency_badge = "🚨 HIGH" if c["urgency_level"] == "HIGH" else "🟢 ROUTINE"
        md_lines.append(f"{i}. [{c['title']}](#{re.sub(r'[^a-zA-Z0-9]', '-', c['title'].lower()).strip('-')}) — *{domain_badge}* | *{urgency_badge}*")

    md_lines.append("\n---\n")

    for c in all_chunks:
        md_lines.append(c["content"])
        md_lines.append(f"\n**🔍 Search Triggers:** `{', '.join(c.get('symptom_triggers', []))}`")
        md_lines.append(f"\n**Chunk ID:** `{c['chunk_id']}` | **Domain:** `{c['domain']}` | **Category:** `{c['category']}`")
        md_lines.append("\n---\n")

    with open(MD_OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"✅ Saved Markdown Clinical Handbook: {MD_OUT_PATH}", flush=True)
    print(f"=======================================================\n", flush=True)

def main():
    guidelines_dir = Path("backend/data/raw_guidelines")
    all_chunks = []

    # 1. CCRAS Prakriti Assessment
    prakriti_pdf = guidelines_dir / "DevelopmentofStandardizedPrakritiAssessmentToolAnOverviewof0AOngoingCCRASInitiatives.pdf"
    if prakriti_pdf.exists():
        all_chunks.extend(process_ccras_prakriti(prakriti_pdf))

    # 2. WHO Ayurveda Benchmarks
    who_pdf = guidelines_dir / "WHO-Ayurveda.pdf"
    if who_pdf.exists():
        all_chunks.extend(process_who_ayurveda(who_pdf))

    # 3. ICMR STW Vol 1 & Vol 3
    stw1_pdf = guidelines_dir / "STW_Manual_v1.pdf"
    if stw1_pdf.exists():
        all_chunks.extend(process_icmr_stws(stw1_pdf, "Vol 1", max_workflows=10))

    stw3_pdf = guidelines_dir / "STW_Vol_3_2022.pdf"
    if stw3_pdf.exists():
        all_chunks.extend(process_icmr_stws(stw3_pdf, "Vol 3", max_workflows=10))

    compile_and_save(all_chunks)

if __name__ == "__main__":
    main()
