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
from app.ai.rag.retriever import retrieve_clinical_guidelines_async, retrieve_patient_history_async

async def main():
    print("="*85)
    print("🌿 LIVE VERIFICATION: UPGRADED AYURVEDIC CLINICAL DIALOGUE ENGINE")
    print("="*85)

    ctx = PatientContext(
        patient_id="PAT-DEMO-RAG-01",
        name="Ramesh Kumar",
        age=52,
        gender="male",
        hospital_type="ayurveda",
        prakriti_profile="Pitta-Kapha Prakriti",
        dashavidha_state={"sattva": "Pravara", "satmya": "Sarva-rasa", "vyayama_shakti": "Madhyama", "vaya_category": "Madhya"},
        chief_complaint="Severe burning in throat and upper stomach with sour burps",
        language="en"
    )

    print(f"\n[Patient Profile]: {ctx.name}, {ctx.age}M | Baseline: {ctx.prakriti_profile}")
    print(f"Chief Complaint: {ctx.chief_complaint}")

    # Fetch NAMASTE / Ayurveda clinical guidelines and Patient Records
    print("\n[Step 1: Fetching Ayurvedic NAMASTE RAG knowledge & Patient Records...]")
    guidelines_res = await retrieve_clinical_guidelines_async(
        query_text=ctx.chief_complaint, top_k=2, similarity_threshold=0.35, domain="ayurveda"
    )
    patient_res = await retrieve_patient_history_async(
        patient_id=ctx.patient_id, query_text=ctx.chief_complaint, top_k=2, similarity_threshold=0.35
    )
    rag_snippets = []
    for g in (guidelines_res or []):
        rag_snippets.append(f"[AYURVEDA GUIDELINE / NAMASTE: {g.get('title')}] {g.get('content', '')[:200]}")
    for p in (patient_res or []):
        clean = p.get('content', '').split("]\n\n")[-1] if "]\n\n" in p.get('content', '') else p.get('content', '')
        rag_snippets.append(f"[PATIENT RECORD ({p.get('category', '').upper()})] {clean[:200]}")
    if not rag_snippets:
        rag_snippets.append("[AYURVEDA GUIDELINE: Amlapitta] Characterized by sour eructations, burning sensation in chest and throat, Tikshnagni.")
    print(f"Loaded {len(rag_snippets)} snippets (Guidelines + Patient Medical Records).")

    history = []
    current_state = {}

    patient_utterances = [
        # Turn 1: Patient presents with burning & food trigger (Volunteering Vikriti + Ahara Hetu)
        "Vaidya ji, I have severe burning in my throat and stomach with sour belching since 2 days after eating spicy fried street food.",
        # Turn 2: Patient answers hunger and tongue coating (Volunteering Agni + Ama)
        "I have intense sharp hunger all the time, and in the morning my tongue has a thick white coating with bad breath.",
        # Turn 3: Patient answers bowel habit (Volunteering Koshtha)
        "My motions are loose and burning, going 2 to 3 times a day.",
        # Turn 4: Patient confirms closure
        "No Vaidya ji, that is all. Just want relief from this acidity."
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

        print(f"\n🧠 Vaidya Clinical Rationale: {result.reasoning}")
        print(f"🎯 Impression: {result.primary_impression}")
        print(f"💡 Differentials: {result.provisional_differentials}")
        print(f"🚨 Arishta Lakshana Red Flag: {result.red_flag_alert.is_red_flag if result.red_flag_alert else False}")
        print(f"\n📥 Current Ayurvedic State: {json.dumps(current_state, indent=2)}")
        print(f"   Covered Dimensions: {result.covered_slots}")
        print(f"   Missing Dimensions: {result.missing_slots}")

        if result.should_stop:
            print("\n" + "="*85)
            print(f"🛑 AYURVEDIC INTAKE DYNAMICALLY COMPLETED AT TURN {turn_idx}!")
            print("="*85)
            print(f"💬 Closing Message: \"{result.closing_message}\"")
            print(f"\n📋 Vaidya's Final Clinical Intake Summary Note:\n{result.clinical_summary}")
            break
        else:
            q = result.next_question or ""
            word_count = len(q.split())
            qmark_count = q.count("?")
            print(f"\n🩺 Vaidya AI Question: \"{q}\"")
            print(f"   [Verification: Question Marks = {qmark_count} | Word Count = {word_count}]")
            assert qmark_count == 1, f"Expected 1 question mark, got {qmark_count} in: {q}"
            assert word_count <= 35, f"Question too long ({word_count} words): {q}"
            print(f"   Touch Options ({len(result.touch_options)}): {[o.label for o in result.touch_options]}")
            history.append(ConversationMessage(role="assistant", content=q))

        # Pacing sleep for Groq TPM limit
        print("\n   [Waiting 6s for Groq TPM buffer...]")
        await asyncio.sleep(6.0)

    print("\n" + "="*85)
    print("✅ AYURVEDIC CLINICAL INTAKE VERIFICATION PASSED!")
    print("="*85)

if __name__ == "__main__":
    asyncio.run(main())
