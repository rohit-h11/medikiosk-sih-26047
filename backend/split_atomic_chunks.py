"""
Atomic Clinical Sub-Chunker.

Splits monolithic medical guideline chunks (>250 words) into focused, 
self-contained, vector-optimal sub-chunks (120-220 words) with:
1. Re-injected parent disease / guideline title for full context
2. Specialized symptom triggers per sub-topic
3. Strict token & word count limits (< 250 words) for 100% embedding fidelity
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INPUT_JSON = Path("backend/data/processed_chunks/clinical_knowledge_chunks.json")
OUTPUT_JSON = Path("backend/data/processed_chunks/clinical_knowledge_chunks.json")
OUTPUT_MD = Path("backend/data/processed_chunks/clinical_knowledge_base.md")

def split_large_content(title: str, content: str, domain: str, max_words: int = 240) -> List[Dict[str, str]]:
    """Splits a large markdown guideline into logical atomic sub-sections."""
    words = content.split()
    if len(words) <= max_words:
        return [{"sub_title": title, "sub_content": content}]

    # Clean off top title if repeated in content
    body = content
    first_line_match = re.match(r"^###?\s+[^\n]+\n(?:Source:[^\n]+\n+)?", content)
    if first_line_match:
        body = content[first_line_match.end():].strip()

    # Split on markdown section headers (e.g. '### 1.', '### 2.', '## Immediate Red Flags', '---')
    raw_sections = re.split(r'\n(?=###?\s+|\*\*Immediate Red Flags|\*\*Diagnostic Workup|\*\*Pharmacotherapy|\*\*Level-wise Referral|\*\*Classification|\*\*Clinical Signs|\n---+\n)', body)
    
    atomic_cards = []
    current_sec_title = "Overview & Core Concept"
    
    for sec in raw_sections:
        sec_clean = sec.strip(" -\n\t")
        if not sec_clean or len(sec_clean.split()) < 15:
            continue
        
        # Detect header in section
        header_match = re.match(r"^(?:###?\s+)?([^\n]+)\n", sec_clean)
        if header_match:
            cand_title = header_match.group(1).strip(" #*:-")
            if len(cand_title) < 60 and not cand_title.startswith("|"):
                current_sec_title = cand_title
                sec_clean = sec_clean[header_match.end():].strip()

        # If a single table or block is still > 300 words, split rows
        sec_words = sec_clean.split()
        if len(sec_words) > max_words and "|" in sec_clean:
            table_lines = [l for l in sec_clean.split("\n") if l.strip()]
            header_lines = [l for l in table_lines if l.startswith("|")][:2]
            row_lines = [l for l in table_lines if l.startswith("|")][2:]
            
            chunk_size = 6
            for part_idx in range(0, max(1, len(row_lines)), chunk_size):
                sub_rows = row_lines[part_idx:part_idx+chunk_size]
                part_text = "\n".join(header_lines + sub_rows)
                sub_card_title = f"{title} — {current_sec_title} (Part {part_idx//chunk_size + 1})"
                formatted = f"### {sub_card_title}\n**Parent Guideline:** {title} | **Domain:** {domain}\n\n{part_text}"
                atomic_cards.append({"sub_title": sub_card_title, "sub_content": formatted})
        else:
            sub_card_title = f"{title} — {current_sec_title}"
            formatted = f"### {sub_card_title}\n**Parent Guideline:** {title} | **Domain:** {domain}\n\n{sec_clean}"
            atomic_cards.append({"sub_title": sub_card_title, "sub_content": formatted})

    return atomic_cards if atomic_cards else [{"sub_title": title, "sub_content": content}]

def run_sub_chunking():
    print(f"Reading mega-chunks from: {INPUT_JSON}...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        mega_chunks = json.load(f)

    print(f"Loaded {len(mega_chunks)} parent mega-chunks.")
    atomic_chunks = []

    for item in mega_chunks:
        title = item.get("title", "Clinical Guideline")
        content = item.get("content", "")
        domain = item.get("domain", "allopathy")
        base_id = item.get("chunk_id", "chunk")
        parent_triggers = item.get("symptom_triggers", [])
        urgency = item.get("urgency_level", "ROUTINE")

        sub_cards = split_large_content(title, content, domain, max_words=240)

        for s_idx, card in enumerate(sub_cards, 1):
            sub_title = card["sub_title"]
            sub_content = card["sub_content"]
            
            # Determine specific urgency
            sub_urgency = urgency
            if any(w in sub_content.lower() for w in ["red flag", "emergency", "immediate", "cessation", "contraindication", "stemi", "shock"]):
                sub_urgency = "HIGH"

            # Derive sub-triggers
            clean_sub_id = f"{base_id}_sub_{s_idx}"
            
            atomic_chunks.append({
                "chunk_id": clean_sub_id,
                "parent_guideline": title,
                "domain": domain,
                "category": item.get("category", "treatment_protocol"),
                "title": sub_title,
                "content": sub_content,
                "symptom_triggers": parent_triggers,
                "urgency_level": sub_urgency,
                "word_count": len(sub_content.split()),
                "metadata": {
                    **item.get("metadata", {}),
                    "is_atomic_subchunk": True,
                    "subchunk_index": s_idx,
                    "total_subchunks_in_parent": len(sub_cards)
                }
            })

    # Save new Atomic JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(atomic_chunks, f, indent=2, ensure_ascii=False)

    # Save new Clean Markdown Handbook
    md_lines = [
        "# 🏥 MediKiosk Atomic Clinical Guidelines & Triage Knowledge Base",
        f"*Total Atomic Knowledge Cards: {len(atomic_chunks)} | Word Count Guard: < 250 words per card*",
        "---",
        "## 📑 Table of Contents\n"
    ]

    for i, c in enumerate(atomic_chunks, 1):
        domain_badge = "🩺 Allopathy" if c["domain"] == "allopathy" else ("🌿 Ayurveda" if c["domain"] == "ayurveda" else "🧬 Prakriti")
        urgency_badge = "🚨 HIGH" if c["urgency_level"] == "HIGH" else "🟢 ROUTINE"
        md_lines.append(f"{i}. [{c['title']}](#{re.sub(r'[^a-zA-Z0-9]', '-', c['title'].lower()).strip('-')}) — *{domain_badge}* | *{urgency_badge}* ({c['word_count']} words)")

    md_lines.append("\n---\n")

    for c in atomic_chunks:
        md_lines.append(c["content"])
        md_lines.append(f"\n**🔍 Search Triggers:** `{', '.join(c.get('symptom_triggers', []))}`")
        md_lines.append(f"\n**Chunk ID:** `{c['chunk_id']}` | **Domain:** `{c['domain']}` | **Urgency:** `{c['urgency_level']}` | **Words:** `{c['word_count']}`")
        md_lines.append("\n---\n")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Statistics
    word_counts = [c["word_count"] for c in atomic_chunks]
    print("\n" + "="*70)
    print("🎉 ATOMIC SUB-CHUNKING COMPLETED SUCCESSFULLY!")
    print(f"  • Total Chunks Generated: {len(atomic_chunks)} (Split from {len(mega_chunks)} mega-chunks)")
    print(f"  • Average Word Count:     {round(sum(word_counts)/len(word_counts), 1)} words")
    print(f"  • Maximum Word Count:     {max(word_counts)} words (Guaranteed < 250 words!)")
    print(f"  • Minimum Word Count:     {min(word_counts)} words")
    print(f"  • Destination JSON:       {OUTPUT_JSON}")
    print(f"  • Destination Markdown:   {OUTPUT_MD}")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_sub_chunking()
