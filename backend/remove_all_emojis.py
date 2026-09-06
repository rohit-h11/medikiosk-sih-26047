"""
Emoji Sanitizer for Medical Clinical Datasets & Knowledge Chunks.

Removes all UI emojis and pictographs from clinical chunk titles, content,
and markdown files to ensure clean, professional, and unpolluted vector database storage.
Preserves all Devanagari, Sanskrit diacritics, and standard medical markdown.
"""

import os
import sys
import re
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Regex pattern matching emojis, pictographs, and decorative symbols
EMOJI_REGEX = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # extended symbols
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"            # zero width joiner
    "📋🌿🌐🩺🚨🟢🧬🏥🔍💊✨🎉⚠️✅👉📇🧪📤📱📄💡🏆⚡👁️🔄⏳📚⚙️🛠️🏷️🎯📏📊"
    "]+",
    flags=re.UNICODE
)

def clean_text(text: str) -> str:
    if not text:
        return ""
    # Strip emojis
    cleaned = EMOJI_REGEX.sub("", text)
    # Clean up double spaces created by emoji removal
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # Clean up headers like '###  Title' -> '### Title'
    cleaned = re.sub(r"^(#+)\s+", r"\1 ", cleaned, flags=re.MULTILINE)
    return cleaned.strip()

def sanitize_json_file(file_path: Path):
    if not file_path.exists():
        return
    print(f"Sanitizing JSON file: {file_path.name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        if "title" in item:
            item["title"] = clean_text(item["title"])
        if "parent_guideline" in item:
            item["parent_guideline"] = clean_text(item["parent_guideline"])
        if "content" in item:
            item["content"] = clean_text(item["content"])
        if "symptom_triggers" in item and isinstance(item["symptom_triggers"], list):
            item["symptom_triggers"] = [clean_text(t) for t in item["symptom_triggers"] if clean_text(t)]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Sanitized {len(data)} chunks in {file_path.name}")

def sanitize_md_file(file_path: Path):
    if not file_path.exists():
        return
    print(f"Sanitizing Markdown file: {file_path.name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    cleaned = clean_text(text)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print(f"  ✓ Sanitized Markdown file: {file_path.name}")

def main():
    processed_dir = Path("backend/data/processed_chunks")
    
    # Sanitize all JSON chunk files
    sanitize_json_file(processed_dir / "clinical_knowledge_chunks.json")
    sanitize_json_file(processed_dir / "namaste_morbidity_chunks.json")
    
    # Sanitize Markdown knowledge base
    sanitize_md_file(processed_dir / "clinical_knowledge_base.md")
    
    print("\n✅ All clinical datasets & knowledge chunks are 100% emoji-free and pristine for Vector DB storage!")

if __name__ == "__main__":
    main()
