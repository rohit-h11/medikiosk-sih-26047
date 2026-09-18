import os
import sys
import json
import asyncio
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from app.db import get_supabase_client
from app.ai.rag.retriever import (
    retrieve_patient_history_async,
    retrieve_clinical_guidelines_async
)
from app.ai.dialogue.models import (
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    TouchOption
)
from app.ai.dialogue.protocols.registry import get_protocol
from app.ai.dialogue.dialogue_manager import (
    _format_conversation_history_text,
    detect_inquired_axes
)
from app.ai.dialogue.llm_client import call_gemini_llm, call_groq_llm, parse_llm_json_response

DEMO_PATIENT_ID = "PAT-DEMO-RAG-01"

def simulate_patient_answer(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["pantoprazole", "medication", "medicine", "pill", "tablet", "miss"]):
        return "I actually forgot to take my Pantoprazole for the past 2 days because I was traveling. The burning gets much worse after dinner."
    elif any(k in q for k in ["spread", "radiat", "arm", "shoulder", "jaw", "back", "sweat", "breath"]):
        return "No, it does not spread to my arm or jaw, and I am not sweating or breathless. It stays in my upper chest and throat."
    elif any(k in q for k in ["when", "start", "began", "onset", "how long"]):
        return "It started 2 days ago in the evening and has been getting worse, especially after I eat dinner."
    elif any(k in q for k in ["feel like", "character", "sharp", "dull", "type of"]):
        return "It feels like a harsh sour burning sensation coming up into my food pipe with acidic burps."
    elif any(k in q for k in ["anything else", "other symptom", "before i prepare", "finalize", "add", "wrap"]):
        return "No, that is all. Nothing else."
    elif any(k in q for k in ["scale", "severe", "severity", "1 to 10", "1-10"]):
        return "It is about a 6 or 7 out of 10, very uncomfortable when trying to sleep."
    else:
        return "It is mainly an acidic burning feeling that gets worse after heavy food and when lying flat."

async def call_resilient_llm(sys_p: str, usr_p: str):
    """Uses the exact same Groq model (openai/gpt-oss-120b) as Strategy A."""
    for attempt in range(5):
        out = await call_groq_llm(sys_p, usr_p)
        if out:
            return out
        print(f"   [Groq TPM rate buffer, pausing 5s before retry (attempt {attempt+1}/5)...]", flush=True)
        await asyncio.sleep(5.0)
    return None


async def run_strategy_b_inspector():
    print("\n" + "="*85, flush=True)
    print("🔬 STRATEGY B (NEW HISTORY-ANCHORED & MULTI-SLOT STRATEGY) — LIVE INSPECTION", flush=True)
    print("="*85, flush=True)

    ctx = PatientContext(
        patient_id=DEMO_PATIENT_ID,
        name="Ramesh Kumar",
        age=52,
        gender="male",
        hospital_type="allopathy",
        chief_complaint="Severe chest and epigastric burning with sour belching",
        language="hi"
    )

    protocol = get_protocol("allopathy")
    current_state = {}
    history = []
    
    # Patient Initial Presentation
    patient_utterance = "I am having severe burning sensation in my chest and upper abdomen along with sour acid burps."
    history.append({"role": "patient", "content": patient_utterance})

    print(f"\n👤 [PATIENT ENTERS KIOSK]:", flush=True)
    print(f"   Name: {ctx.name} | Age: {ctx.age} | Gender: {ctx.gender}", flush=True)
    print(f"   Opening Statement: \"{patient_utterance}\"", flush=True)

    turn = 1
    while turn <= 6:
        print("\n" + "#"*85, flush=True)
        print(f"📍 TURN {turn}: LIVE SYSTEM EXECUTION PIPELINE", flush=True)
        print("#"*85, flush=True)

        # -------------------------------------------------------------
        # STEP 1: CONSTRUCT RAG QUERY & EXECUTE VECTOR RETRIEVAL
        # -------------------------------------------------------------
        rag_query = f"{ctx.chief_complaint} {patient_utterance}".strip()
        print(f"\n[Step 1: RAG Query Generated]: \"{rag_query}\"", flush=True)

        guidelines_res = await retrieve_clinical_guidelines_async(
            query_text=rag_query, top_k=3, similarity_threshold=0.35, domain="allopathy"
        )
        patient_res = await retrieve_patient_history_async(
            patient_id=DEMO_PATIENT_ID, query_text=rag_query, top_k=3, similarity_threshold=0.35
        )

        print(f"\n[Step 2: Patient History Chunks Retrieved from Supabase (Found: {len(patient_res or [])})]:", flush=True)
        if patient_res:
            for i, p in enumerate(patient_res, 1):
                sim = round(p.get("similarity", 0), 4)
                cat = p.get("category", "record")
                snip = p.get("content", "").replace("\n", " ")[:160]
                print(f"   ({i}) [{cat.upper()}] (Similarity: {sim}) -> {snip}...", flush=True)

        print(f"\n[Step 3: Medical Knowledge Chunks Retrieved from Supabase (Found: {len(guidelines_res or [])})]:", flush=True)
        if guidelines_res:
            for i, g in enumerate(guidelines_res, 1):
                sim = round(g.get("similarity", 0), 4)
                title = g.get("title", "Guideline")
                domain = g.get("domain", "allopathy")
                print(f"   ({i}) [{domain.upper()}: {title}] (Similarity: {sim})", flush=True)

        # Build combined snippets
        rag_snippets = []
        for g in (guidelines_res or []):
            rag_snippets.append(f"[ALLOPATHY GUIDELINE: {g.get('title')}] {g.get('content', '')[:250]}")
        for p in (patient_res or []):
            clean_snip = p.get('content', '').split("]\n\n")[-1] if "]\n\n" in p.get('content', '') else p.get('content', '')
            rag_snippets.append(f"[PATIENT RECORD ({p.get('category', '').upper()})] {clean_snip[:250]}")

        # -------------------------------------------------------------
        # STEP 2: BUILD SYSTEM PROMPT & TRACK COVERED/MISSING SLOTS
        # -------------------------------------------------------------
        system_prompt = protocol.build_system_prompt(ctx, rag_snippets)

        confirmed_slots = {
            k: v for k, v in current_state.items()
            if v and str(v).lower() not in ["null", "none", "[]", "{}"]
        }
        confirmed_facts_text = "\n".join([f"- {k.replace('_', ' ').title()}: {v}" for k, v in confirmed_slots.items()]) if confirmed_slots else "None confirmed yet."

        inquired_axes = detect_inquired_axes(history)
        uninquired_axes = [s for s in protocol.target_slots if s not in inquired_axes and s not in confirmed_slots]
        if not uninquired_axes:
            uninquired_axes = ["clinical wrap-up & review of systems"]

        inquired_text = ", ".join([a.title() for a in inquired_axes]) if inquired_axes else "None yet"
        uninquired_text = ", ".join([a.title() for a in uninquired_axes])
        history_text = _format_conversation_history_text(history)

        print(f"\n[Step 4: Clinical Dimension Tracking]:", flush=True)
        print(f"   Slots Already Covered: {list(confirmed_slots.keys()) or 'None'}", flush=True)
        print(f"   Remaining Uninquired Axes: [{uninquired_text}]", flush=True)

        # -------------------------------------------------------------
        # STEP 3: STRATEGY B INSTRUCTIONS (HISTORY-ANCHORED MULTI-SLOT)
        # -------------------------------------------------------------
        instructions = f"""INSTRUCTIONS:
1. HIGH-YIELD MULTI-SLOT ELICITATION:
   - Your goal is to cover remaining UNINQUIRED AXES: [{uninquired_text}].
   - Combine 2 or more related axes in one natural question (e.g. Onset + Exacerbating Factors, or Radiation + Associated Symptoms) rather than asking separate textbook questions.
2. ACTIVE HISTORY-ANCHORED ELICITATION (CRITICAL):
   - Review RETRIEVED CLINICAL & PATIENT KNOWLEDGE above. If the patient has relevant chronic diagnoses or active medications, you MUST anchor your inquiry to that chart:
     * Medication Compliance as a Trigger/Reliever: If prescribed an active drug (e.g. Pantoprazole, Metformin), ask whether the episode started after missing doses or is occurring despite taking it.
     * Risk-Stratified Screening: In patients with chronic risk factors (e.g. Diabetes, Hypertension), prioritize screening for atypical/ischemic associated symptoms (cold sweats, shortness of breath, radiating discomfort) over routine textbook questions.
3. STRICT ANTI-REPETITION:
   - Do NOT re-ask axes [{inquired_text}].
4. CLINICAL CLOSURE GATE:
   - When core clinical dimensions are gathered, ask a closing wrap-up question:
     "Before I prepare your clinical note for the attending doctor, is there any other symptom or medication you want to mention?"
   - Only set should_stop = true if the patient explicitly confirms they have nothing more to add, or if turns >= 6.
5. TOUCH OPTIONS:
   - Provide 3 to 4 distinct `touch_options` with id, label, value, slot_tag. Options should reflect both clinical choices and historical triggers (e.g. "Missed morning Pantoprazole").
6. Update "state" with all newly extracted findings.
Respond strictly in JSON format."""

        user_prompt = f"""PATIENT CONTEXT:
- Name: {ctx.name} | Age: {ctx.age} | Gender: {ctx.gender}
- Chief Complaint: {ctx.chief_complaint}

CONFIRMED CLINICAL FACTS SO FAR:
{confirmed_facts_text}

CLINICAL AXES ALREADY INQUIRED:
{inquired_text}

TARGET UNINQUIRED AXES:
{uninquired_text}

CONVERSATION TRANSCRIPT:
{history_text}

PATIENT'S LATEST STATEMENT:
"{patient_utterance}"

{instructions}"""

        # -------------------------------------------------------------
        # STEP 4: CALL LLM INFERENCE
        # -------------------------------------------------------------
        print(f"\n[Step 5: Invoking LLM Clinical Decision Engine...]", flush=True)
        llm_output = await call_resilient_llm(system_prompt, user_prompt)
        if not llm_output:
            print("  [Error: LLM returned empty response. Retrying once...]", flush=True)
            await asyncio.sleep(2.0)
            llm_output = await call_resilient_llm(system_prompt, user_prompt)

        should_stop = bool(llm_output.get("should_stop", False))
        next_q = llm_output.get("next_question") if not should_stop else None
        
        # Merge state
        raw_state = llm_output.get("state", llm_output.get("socrates_state", {}))
        merged_state = dict(current_state)
        if isinstance(raw_state, dict):
            for k, v in raw_state.items():
                if v and str(v).lower() not in ["null", "none", "[]", "{}"]:
                    merged_state[k] = v
        current_state = merged_state
        normalized = protocol.normalize_state(current_state)

        # -------------------------------------------------------------
        # STEP 5: DISPLAY TURN OUTPUTS
        # -------------------------------------------------------------
        print(f"\n🎯 [Step 6: LLM Clinical Decision Result]:", flush=True)
        print(f"   Should Stop (Intake Complete): {should_stop}", flush=True)
        print(f"   Newly Updated State: {json.dumps(normalized['state'], indent=6)}", flush=True)
        print(f"   Slots Covered So Far: {normalized['covered_slots']}", flush=True)
        print(f"   Slots Still Missing:  {normalized['missing_slots']}", flush=True)

        if should_stop:
            print("\n" + "="*85, flush=True)
            print(f"🛑 LLM DECIDED TO TERMINATE INTAKE AUTONOMOUSLY (Turn {turn})", flush=True)
            print("="*85, flush=True)
            print(f"\n💬 Closing Spoken Message to Patient:")
            print(f"   \"{llm_output.get('closing_message')}\"", flush=True)
            
            summary = llm_output.get("clinical_summary") or protocol.format_doctor_summary(normalized["state"], ctx)
            print(f"\n📋 PRE-POPULATED DOCTOR'S EHR CLINICAL INTAKE TICKET (SOAP NOTE):", flush=True)
            print("-" * 75, flush=True)
            print(summary, flush=True)
            print("-" * 75, flush=True)
            return

        print(f"\n🤖 [Kiosk Assistant Spoken Question]:", flush=True)
        print(f"   \"{next_q}\"", flush=True)

        raw_options = llm_output.get("touch_options", [])
        print(f"\n📱 [Touch Screen Option Pills Generated ({len(raw_options)} options)]:", flush=True)
        for opt in raw_options:
            print(f"   * [{opt.get('id')}] \"{opt.get('label')}\" (tag: {opt.get('slot_tag')})", flush=True)

        # -------------------------------------------------------------
        # STEP 6: PATIENT REPLIES
        # -------------------------------------------------------------
        patient_utterance = simulate_patient_answer(next_q)
        print(f"\n👤 [Patient's Spoken Answer]:", flush=True)
        print(f"   \"{patient_utterance}\"", flush=True)

        # Append to history
        history.append({"role": "assistant", "content": next_q})
        history.append({"role": "patient", "content": patient_utterance})

        turn += 1
        # 2-second breathing window between turns
        await asyncio.sleep(2.0)

    print("\n⚠️ Safety ceiling of 6 turns reached.", flush=True)

if __name__ == "__main__":
    asyncio.run(run_strategy_b_inspector())
