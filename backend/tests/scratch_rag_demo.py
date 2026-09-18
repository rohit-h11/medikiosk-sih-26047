import os
import sys
import json
import asyncio
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from app.db import get_supabase_client
from app.ai.rag.retriever import (
    generate_embedding_async,
    retrieve_patient_history_async,
    retrieve_clinical_guidelines_async
)
from app.ai.dialogue.models import PatientContext, ConversationMessage
from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn

DEMO_PATIENT_ID = "PAT-DEMO-RAG-01"

DEMO_RECORDS = [
    {
        "category": "ocr_prescription",
        "encounter_date": "2024-11-10",
        "content": (
            f"[Patient: {DEMO_PATIENT_ID} | Document: Prior OPD Prescription | Encounter Date: 2024-11-10]\n"
            "Diagnoses: Type 2 Diabetes Mellitus (T2DM) & Grade-1 Reflux Esophagitis (GERD).\n"
            "Active Medications: Tab Metformin 500mg BD after meals, Cap Pantoprazole 40mg OD before breakfast.\n"
            "Clinical Notes: Patient reports episodic retrosternal burning after heavy or oily meals. Advised lifestyle modifications, head-end elevation, and avoiding late-night snacks."
        ),
        "metadata": {
            "source": "prior_prescription",
            "diagnoses": ["Type 2 Diabetes", "GERD"],
            "medications": ["Metformin 500mg", "Pantoprazole 40mg"]
        }
    },
    {
        "category": "lab_report",
        "encounter_date": "2025-01-15",
        "content": (
            f"[Patient: {DEMO_PATIENT_ID} | Document: Fasting Lab Chemistry | Encounter Date: 2025-01-15]\n"
            "Fasting Blood Glucose: 148 mg/dL (Elevated | Ref: 70-100 mg/dL).\n"
            "HbA1c: 7.7% (Uncontrolled glycemic status | Ref: < 5.7%).\n"
            "Serum Creatinine: 0.9 mg/dL (Normal).\n"
            "Total Cholesterol: 210 mg/dL (Borderline High).\n"
            "Impression: Diabetic dysglycemia with recurrent dyspepsia."
        ),
        "metadata": {
            "source": "pathology_report",
            "hba1c": 7.7,
            "fasting_glucose": 148
        }
    },
    {
        "category": "allergies_and_alerts",
        "encounter_date": "2024-06-20",
        "content": (
            f"[Patient: {DEMO_PATIENT_ID} | Document: Safety & Allergy Alert | Encounter Date: 2024-06-20]\n"
            "Confirmed Drug Allergy: Severe hypersensitivity to Penicillin and Amoxicillin (manifests as diffuse urticarial rash, pruritus, and mild bronchospasm).\n"
            "Contraindication: Strict contraindication for beta-lactam antibiotics."
        ),
        "metadata": {
            "source": "allergy_registry",
            "allergy": "Penicillin",
            "severity": "High"
        }
    }
]

async def seed_demo_patient():
    print("\n" + "="*80)
    print(f"1. SEEDING DEMO PATIENT: {DEMO_PATIENT_ID} INTO SUPABASE")
    print("="*80)
    sb = get_supabase_client()
    
    # 1. Upsert into patients table
    patient_row = {
        "id": DEMO_PATIENT_ID,
        "name": "Ramesh Kumar",
        "age": 52,
        "gender": "male",
        "phone": "9876543210",
        "prakriti": "Pitta-Kapha"
    }
    sb.table("patients").upsert(patient_row).execute()
    print(f"  [OK] Patient profile registered: {patient_row['name']}, Age {patient_row['age']}, {patient_row['gender']}")

    # 2. Clean previous test vectors for this patient to ensure clean slate
    sb.table("patient_structured_vectors").delete().eq("patient_id", DEMO_PATIENT_ID).execute()
    print("  [OK] Cleared previous test vectors for this patient.")

    # 3. Generate 384-dim embeddings & insert structured vectors
    for idx, rec in enumerate(DEMO_RECORDS, 1):
        print(f"  --> Embedding record {idx}/{len(DEMO_RECORDS)} ({rec['category']})...", flush=True)
        emb = await generate_embedding_async(rec["content"])
        row = {
            "patient_id": DEMO_PATIENT_ID,
            "document_id": f"DOC-DEMO-{idx}",
            "category": rec["category"],
            "content": rec["content"],
            "metadata": rec["metadata"],
            "encounter_date": rec["encounter_date"],
            "embedding": emb
        }
        sb.table("patient_structured_vectors").insert(row).execute()
        print(f"      Inserted vector ({len(emb)} dims) for: {rec['category']}")

    print("  [SUCCESS] All 3 historical records embedded and stored in Supabase pgvector!")

async def run_dialogue_turn():
    print("\n" + "="*80)
    print("2. RUNNING DIALOGUE WITH CURRENT RAG SYSTEM (ZERO CODE CHANGES)")
    print("="*80)
    
    # Patient enters Kiosk with a burning sensation
    patient_native = "मुझे सीने और पेट के ऊपरी हिस्से में बहुत तेज जलन हो रही है और खट्टी डकारें आ रही हैं।"
    patient_english = "I am having severe burning sensation in my chest and upper abdomen along with sour acid burps."
    chief_complaint_hint = "Severe chest and epigastric burning with sour belching"
    hospital_type = "allopathy"

    print(f"Patient Speaks (Hindi):  \"{patient_native}\"")
    print(f"Translated to English:   \"{patient_english}\"")
    print(f"Chief Complaint Hint:    \"{chief_complaint_hint}\"")
    
    # EXACT logic from interview.py (lines 838-839):
    primary_complaint = chief_complaint_hint
    rag_query = f"{primary_complaint} {patient_english}".strip() if (primary_complaint and patient_english) else (patient_english or primary_complaint or "symptoms")
    
    print("\n" + "-"*80)
    print(f"🔎 CURRENT SYSTEM'S GENERATED RAG QUERY:")
    print(f"   \"{rag_query}\"")
    print("-"*80)

    # Trigger both RAG searches concurrently (as interview.py does)
    guidelines_task = retrieve_clinical_guidelines_async(
        query_text=rag_query, top_k=5, similarity_threshold=0.35,
        domain="allopathy"
    )
    patient_rag_task = retrieve_patient_history_async(
        patient_id=DEMO_PATIENT_ID, query_text=rag_query, top_k=5, similarity_threshold=0.35
    )

    guidelines_results, patient_results = await asyncio.gather(guidelines_task, patient_rag_task)

    # -------------------------------------------------------------
    # DISPLAY PATIENT HISTORY CHUNKS RETRIEVED
    # -------------------------------------------------------------
    print("\n" + "="*80)
    print(f"🏥 A. PATIENT HISTORY CHUNKS RETRIEVED FROM SUPABASE (Found: {len(patient_results)})")
    print("="*80)
    if patient_results:
        for i, p in enumerate(patient_results, 1):
            sim = round(p.get("similarity", 0), 4)
            cat = p.get("category", "record")
            enc_date = p.get("encounter_date", "N/A")
            content = p.get("content", "")
            print(f"\n  [{i}] CATEGORY: {cat.upper()} | ENCOUNTER DATE: {enc_date} | COSINE SIMILARITY: {sim}")
            print(f"      CHUNK CONTENT:")
            for line in content.splitlines():
                print(f"        {line}")
    else:
        print("  [None retrieved - check similarity threshold or embeddings]")

    # -------------------------------------------------------------
    # DISPLAY CLINICAL GUIDELINE CHUNKS RETRIEVED
    # -------------------------------------------------------------
    print("\n" + "="*80)
    print(f"📚 B. MEDICAL GUIDELINE CHUNKS RETRIEVED FROM SUPABASE (Found: {len(guidelines_results)})")
    print("="*80)
    if guidelines_results:
        for i, g in enumerate(guidelines_results, 1):
            title = g.get("title", "Untitled")
            domain = g.get("domain", "allopathy")
            sim = round(g.get("similarity", 0), 4)
            content = g.get("content", "")
            print(f"\n  [{i}] TITLE: {title} | DOMAIN: {domain.upper()} | COSINE SIMILARITY: {sim}")
            print(f"      SNIPPET: {content[:280]}...")
    else:
        print("  [None retrieved from clinical_guidelines table]")

    # -------------------------------------------------------------
    # FORMAT SNIPPETS AS interview.py DOES FOR THE LLM PROMPT
    # -------------------------------------------------------------
    rag_context_snippets = []
    if isinstance(guidelines_results, list):
        for g in guidelines_results:
            title, content = g.get("title", ""), g.get("content", "")
            domain = g.get("domain", "")
            header = f"[{domain.upper()} GUIDELINE: {title}]"
            if content:
                rag_context_snippets.append(f"{header} {content[:300].replace(chr(10), ' ').strip()}")

    if isinstance(patient_results, list):
        for p in patient_results:
            content = p.get("content", "")
            category = p.get("category", "medical_record")
            if content:
                clean_snippet = content.split("]\n\n")[-1] if "]\n\n" in content else content
                rag_context_snippets.append(f"[PATIENT RECORD ({category.upper()})] {clean_snippet.strip()[:250]}")

    print("\n" + "="*80)
    print(f"🧩 C. PACKAGED RAG CONTEXT FED INTO LLM SYSTEM PROMPT ({len(rag_context_snippets)} snippets):")
    print("="*80)
    for idx, snip in enumerate(rag_context_snippets, 1):
        print(f"  [{idx}] {snip}")

    # -------------------------------------------------------------
    # INVOKE CURRENT DIALOGUE MANAGER (Groq / Gemini)
    # -------------------------------------------------------------
    print("\n" + "="*80)
    print("🧠 D. INVOKING CLINICAL DIALOGUE MANAGER (LLM INFERENCE)")
    print("="*80)
    
    ctx = PatientContext(
        patient_id=DEMO_PATIENT_ID,
        name="Ramesh Kumar",
        age=52,
        gender="male",
        hospital_type=hospital_type,
        chief_complaint=chief_complaint_hint,
        language="hi"
    )

    history = [
        {"role": "patient", "content": patient_english}
    ]

    turn_result = await get_next_dialogue_turn(
        patient_context=ctx,
        conversation_history=history,
        max_turns=6,
        current_state={},
        rag_context_snippets=rag_context_snippets
    )

    print("\n" + "-"*80)
    print("🎯 SYSTEM OUTPUT GENERATED BY LLM:")
    print("-"*80)
    print(f"Next Question (English): {turn_result.next_question}")
    print(f"\nTouch Options Generated ({len(turn_result.touch_options)} pills):")
    for opt in turn_result.touch_options:
        print(f"  * [{opt.id}] \"{opt.label}\" (slot: {opt.slot_tag})")
    
    print(f"\nSOCRATES Clinical State Extracted:")
    for k, v in turn_result.state.items():
        if v:
            print(f"  - {k}: {v}")
            
    print(f"\nClinical Reasoning / Differential:")
    print(f"  {turn_result.reasoning or 'Processed through SOCRATES protocol.'}")
    print("="*80 + "\n")

async def main():
    await seed_demo_patient()
    await run_dialogue_turn()

if __name__ == "__main__":
    asyncio.run(main())
