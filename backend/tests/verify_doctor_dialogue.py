import os
import sys
import json
import asyncio
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from app.ai.dialogue.models import PatientContext, ConversationMessage
from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn
from app.ai.rag.retriever import retrieve_patient_history_async, retrieve_clinical_guidelines_async

async def main():
    print("="*85)
    print("🩺 LIVE VERIFICATION: PRODUCTION DIALOGUE ENGINE (DOCTOR-GRADE SOCRATES)")
    print("="*85)

    ctx = PatientContext(
        patient_id="PAT-DEMO-RAG-01",
        name="Ramesh Kumar",
        age=52,
        gender="male",
        hospital_type="allopathy",
        chief_complaint="Severe burning in chest and upper abdomen",
        language="en"
    )

    # 1. Fetch RAG context snippets
    print("\n[Step 1: Fetching RAG context for patient...]")
    patient_res = await retrieve_patient_history_async(
        patient_id=ctx.patient_id, query_text=ctx.chief_complaint, top_k=3, similarity_threshold=0.35
    )
    guidelines_res = await retrieve_clinical_guidelines_async(
        query_text=ctx.chief_complaint, top_k=2, similarity_threshold=0.35, domain="allopathy"
    )

    rag_snippets = []
    for g in (guidelines_res or []):
        rag_snippets.append(f"[GUIDELINE: {g.get('title')}] {g.get('content', '')[:200]}")
    for p in (patient_res or []):
        clean = p.get('content', '').split("]\n\n")[-1] if "]\n\n" in p.get('content', '') else p.get('content', '')
        rag_snippets.append(f"[PATIENT RECORD ({p.get('category', '').upper()})] {clean[:200]}")

    print(f"Loaded {len(rag_snippets)} RAG snippets into context.")

    history = []
    current_state = {}

    patient_utterances = [
        # Turn 1: Patient volunteers Site, Character, Onset, Severity in one breath
        "I have severe burning in my chest and upper stomach that started 2 days ago after dinner. It's about a 7 out of 10.",
        # Turn 2: Patient answers cardiac rule-out
        "No sweating or breathlessness, and the pain does not go to my jaw or left arm. It stays in my upper chest and throat.",
        # Turn 3: Patient answers medication inquiry
        "I forgot to take my Pantoprazole for the past 2 days because I was traveling.",
        # Turn 4: Final closure answer
        "No, that is all. Nothing else."
    ]

    for turn_idx, utt in enumerate(patient_utterances, 1):
        print("\n" + "-"*85)
        print(f"📍 TURN {turn_idx}: PATIENT UTTERANCE")
        print(f"Patient: \"{utt}\"")
        print("-"*85)

        history.append(ConversationMessage(role="patient", content=utt))

        result = await get_next_dialogue_turn(
            patient_context=ctx,
            conversation_history=history,
            max_turns=14,
            current_state=current_state,
            rag_context_snippets=rag_snippets
        )

        current_state = result.state

        print(f"\n🧠 Clinical Rationale: {result.reasoning}")
        print(f"🎯 Impression: {result.primary_impression}")
        print(f"💡 Differentials: {result.provisional_differentials}")
        print(f"🚨 Red Flag Detected: {result.red_flag_alert.is_red_flag if result.red_flag_alert else False}")
        print(f"\n📥 Current SOCRATES State: {json.dumps(current_state, indent=2)}")
        print(f"   Covered Slots: {result.covered_slots}")
        print(f"   Missing Slots: {result.missing_slots}")

        if result.should_stop:
            print("\n" + "="*85)
            print(f"🛑 CLINICAL INTAKE DYNAMICALLY COMPLETED AT TURN {turn_idx}!")
            print("="*85)
            print(f"💬 Closing Spoken Message: \"{result.closing_message}\"")
            print(f"\n📋 Doctor's Final SOAP Summary Note:\n{result.clinical_summary}")
            break
        else:
            q = result.next_question or ""
            word_count = len(q.split())
            qmark_count = q.count("?")
            print(f"\n🩺 Doctor AI Question: \"{q}\"")
            print(f"   [Verification: Question Marks = {qmark_count} | Word Count = {word_count}]")
            assert qmark_count == 1, f"Expected 1 question mark, got {qmark_count} in: {q}"
            assert word_count <= 35, f"Question too long ({word_count} words): {q}"
            print(f"   Touch Options ({len(result.touch_options)}): {[o.label for o in result.touch_options]}")
            history.append(ConversationMessage(role="assistant", content=q))

        # Pacing sleep to allow Groq TPM window to reset
        print("\n   [Waiting 6s for Groq TPM rate buffer...]")
        await asyncio.sleep(6.0)

    print("\n" + "="*85)
    print("✅ VERIFICATION PASSED SUCCESSFULLY!")
    print("="*85)

if __name__ == "__main__":
    asyncio.run(main())
