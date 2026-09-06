"""
Production-grade NAMASTE Ayurveda Morbidity Data Cleaner & RAG Chunk Generator.

Transforms the raw Ministry of Ayush Excel dataset into pristine, human-readable, 
and vector-optimized clinical knowledge cards.

Cleans out:
- Legacy database artifacts: `^^`, `(TM1)`, `(TM2)`, `(TM3)`
- Excel formatting noise: `(a)`, `(b)`, multiple tab/whitespace padding
- Boilerplate filler: Replaced with crisp, factual clinical descriptions
- Search noise: Cleaned multi-lingual symptom triggers (English + Devanagari + Romanized Sanskrit)
"""

import os
import re
import sys
import json
import unicodedata
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def clean_val(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s in ["-", "nan", "NaN", "None"]:
        return ""
    return s

def sanitize_sanskrit(text: str) -> str:
    """Cleans Sanskrit terms, removes (a)/(b), carets, and excessive spacing."""
    if not text:
        return ""
    # Replace carets with clean dash
    text = text.replace("^^", " - ")
    # Remove item prefixes like (a), (b), (1), (2)
    text = re.sub(r"\([a-zA-Z0-9]\)", "", text)
    # Collapse multiple whitespaces into clean delimiter
    text = re.sub(r"[ \t]{2,}", " / ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" /-,;")

def sanitize_english(text: str) -> str:
    """Removes ontology codes like (TM2), prefixes, and fixes capitalization."""
    if not text:
        return ""
    # Remove (TM1), (TM2), (TM3), etc.
    text = re.sub(r"\s*\([tT][mM]\d+\)", "", text)
    # Remove item prefixes like (a), (b)
    text = re.sub(r"\([a-zA-Z0-9]\)", "", text)
    # Remove carets
    text = text.replace("^^", " - ")
    # Fix spaces
    text = re.sub(r"\s+", " ", text).strip(" /-,;")
    return text

def sanitize_definition(text: str) -> str:
    """Cleans up clinical definitions and extracts readable sentences."""
    if not text:
        return ""
    # Remove (TM2) tags
    text = re.sub(r"\s*\([tT][mM]\d+\)", "", text)
    # Clean multiple spaces and carets
    text = text.replace("^^", " - ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

def normalize_ascii(text: str) -> str:
    """Converts diacritical Sanskrit (ā, ī, ū, ś, ṣ, ḥ) to plain ascii (a, i, u, s, s, h)."""
    if not text:
        return ""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8").lower()

def build_namaste_chunks():
    excel_path = Path("backend/data/raw_guidelines/NATIONAL AYURVEDA MORBIDITY CODES.xls")
    out_path = Path("backend/data/processed_chunks/namaste_morbidity_chunks.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading dataset: {excel_path}...")
    df = pd.read_excel(excel_path)
    print(f"Total rows found: {len(df)}")

    clinical_keywords = {
        "fever", "pain", "cough", "vomiting", "burning", "swelling", "diarrhoea",
        "bleeding", "constipation", "distension", "dysuria", "headache", "weakness",
        "edema", "itching", "nausea", "jaundice", "chills", "rigors", "dyspnoea",
        "haematuria", "vertigo", "insomnia", "anorexia", "tremor", "stiffness",
        "delirium", "convulsion", "paralysis", "flatulence", "hoarseness", "dysphonia"
    }

    chunks = []

    for idx, row in df.iterrows():
        raw_code = clean_val(row.get("NAMC_CODE")) or f"AYU-{idx+1:04d}"
        code = re.sub(r"\s+", " ", raw_code).strip()
        
        devanagari = sanitize_sanskrit(clean_val(row.get("NAMC_term_DEVANAGARI")))
        diacritical = sanitize_sanskrit(clean_val(row.get("NAMC_term_diacritical")) or clean_val(row.get("NAMC_term")))
        english_name = sanitize_english(clean_val(row.get("Name English")))
        long_def = sanitize_definition(clean_val(row.get("Long_definition")))
        ontology = clean_val(row.get("Ontology_branches"))

        # Build clean title
        title_components = []
        if devanagari:
            title_components.append(devanagari)
        if diacritical:
            title_components.append(diacritical)
        
        sanskrit_header = " — ".join(title_components) if title_components else code
        if english_name:
            full_title = f"{sanskrit_header} ({english_name.title()})"
        else:
            full_title = sanskrit_header

        # Urgency classification
        urgency = "ROUTINE"
        combined_text = f"{english_name} {long_def} {diacritical}".lower()
        if any(w in combined_text for w in [
            "fatal", "emergency", "arishta", "severe hemorrhage", "perforation", 
            "coma", "shock", "abscess", "sepsis", "convulsion", "unconsciousness"
        ]):
            urgency = "HIGH"

        # Build clean, high-density Clinical Knowledge Card
        content_lines = [
            f"### AYUSH Morbidity Standard: {full_title}",
            f"- **National Morbidity Code:** `{code}`",
            f"- **Sanskrit Term:** {devanagari if devanagari else 'N/A'} ({diacritical if diacritical else 'N/A'})",
            f"- **Clinical English Translation:** {english_name.title() if english_name else 'N/A'}"
        ]

        if long_def:
            content_lines.append(f"- **Clinical Diagnostic Features & Lakshana:** {long_def}")
        
        if ontology:
            clean_ont = ontology.replace("Note: Also Classifed under", "").replace("#san@", "").replace("#[EB]", "").strip()
            content_lines.append(f"- **Ayurvedic Classification / Srotas:** {clean_ont}")

        content = "\n".join(content_lines)

        # Build pristine Symptom Trigger keywords
        triggers = set()
        if devanagari:
            # Add full devanagari name
            triggers.add(devanagari)
            # Add root devanagari term (without parenthesis)
            root_dev = re.sub(r'\(.*?\)', '', devanagari).strip()
            if root_dev and root_dev != devanagari:
                triggers.add(root_dev)

        if diacritical:
            # Add full diacritical term
            triggers.add(diacritical.lower())
            ascii_full = normalize_ascii(diacritical)
            if ascii_full:
                triggers.add(ascii_full)
            # Add individual terms if separated by /
            for s_term in diacritical.split("/"):
                s_clean = s_term.strip(" ()-").lower()
                if len(s_clean) > 2:
                    triggers.add(s_clean)
                    ascii_s = normalize_ascii(s_clean)
                    if ascii_s:
                        triggers.add(ascii_s)

        if english_name:
            norm_eng = normalize_ascii(english_name)
            # Add full clean name
            if len(norm_eng) > 3:
                triggers.add(norm_eng)
            # Add individual keywords
            for word in re.findall(r"[a-z]{3,}", norm_eng):
                if word not in {"disorder", "pattern", "syndrome", "disease", "type", "due", "and", "with", "from", "only", "the", "for"}:
                    triggers.add(word)

        if long_def:
            norm_def = normalize_ascii(long_def)
            for word in re.findall(r"\b[a-z]{4,}\b", norm_def):
                if word in clinical_keywords:
                    triggers.add(word)

        clean_code_id = re.sub(r"[^a-zA-Z0-9]", "_", code).strip("_").lower()
        chunk_id = f"namaste_{clean_code_id}_{idx}"

        chunks.append({
            "chunk_id": chunk_id,
            "domain": "ayurveda",
            "category": "morbidity_code",
            "title": full_title,
            "content": content,
            "symptom_triggers": sorted(list(triggers)),
            "urgency_level": urgency,
            "metadata": {
                "source_document": "NATIONAL AYURVEDA MORBIDITY CODES.xls",
                "morbidity_code": code,
                "devanagari_name": devanagari,
                "sanskrit_name": diacritical,
                "english_name": english_name,
                "row_index": idx + 1,
                "has_detailed_definition": bool(long_def)
            }
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned and exported {len(chunks)} NAMASTE morbidity chunks.")
    print(f"📁 Output file: {out_path}")

if __name__ == "__main__":
    build_namaste_chunks()
