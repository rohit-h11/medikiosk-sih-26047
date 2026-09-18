# backend/simulate_patient_flow.py
"""
MediKiosk — Full 5-Turn Comprehensive Clinical Simulation
Executes real multi-turn Ayurvedic dialogue across all core clinical axes:
Turn 1: Chief Complaint & Onset
Turn 2: Dosha Sensation & Radiation (Vikriti)
Turn 3: Agni & Ama (Metabolism & Toxins)
Turn 4: Koshtha & Nidra (Bowel & Sleep)
Turn 5: Ahara & Vihara Hetu (Diet & Lifestyle Triggers) -> Comprehensive Vaidya Summary
"""

import sys
import io
import asyncio
import json
import logging

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.ai.dialogue.models import PatientContext, ConversationMessage
from app.ai.dialogue.protocols.registry import get_protocol
from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn
from app.ai.ayurveda import score_prakriti, score_dashavidha

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def run_live_simulation():
    print("=" * 75)
    print("[MEDIKIOSK LIVE 5-TURN COMPREHENSIVE CLINICAL INTERVIEW SIMULATION]")
    print("=" * 75)

    # --------------------------------------------------------------------------
    # STEP 1: OCR Extraction from Scanned Prescription
    # --------------------------------------------------------------------------
    print("\nSTEP 1: Scanned Document Ingestion (OCR)...")
    scanned_prescription_ocr = {
        "document_type": "prescription",
        "hospital_name": "All India Institute of Ayurveda (AIIA) OPD",
        "date": "2025-11-14",
        "diagnoses": ["Amlapitta (Hyperacidity)", "Mild Sandhivata (Knee Joint Stiffness)"],
        "medications": ["Avipattikara Churna 3g BD before meals", "Yogaraja Guggulu 500mg BD after meals"]
    }
    ocr_rag_snippet = (
        f"[OCR Prescription Record - 2025-11-14]: Diagnoses: {', '.join(scanned_prescription_ocr['diagnoses'])}. "
        f"Medications: {', '.join(scanned_prescription_ocr['medications'])}."
    )
    print(f"[OK] Extracted Diagnoses: {scanned_prescription_ocr['diagnoses']}")
    print(f"[OK] Extracted Medications: {scanned_prescription_ocr['medications']}")

    # --------------------------------------------------------------------------
    # STEP 2: Baseline Prakriti & Dashavidha
    # --------------------------------------------------------------------------
    print("\nSTEP 2: Establishing Baseline Constitution (Step A1 & A2)...")
    prakriti_answers = ["B"] * 7 + ["A"] * 3 + ["C"] * 2
    prakriti_res = score_prakriti(prakriti_answers)
    dash_state = score_dashavidha({"sattva": "Madhyama", "satmya": "Madhyama", "vyayama_shakti": "Pravara"}, age=42, prakriti_result=prakriti_res)

    print(f"[OK] Prakriti Baseline: {prakriti_res.prakriti_type} ({prakriti_res.scores.pitta}% Pitta, {prakriti_res.scores.vata}% Vata, {prakriti_res.scores.kapha}% Kapha)")
    print(f"[OK] Dashavidha Profile: Sattva={dash_state.sattva} | Satmya={dash_state.satmya} | Vyayama={dash_state.vyayama_shakti} | Vaya={dash_state.vaya_category}")

    # --------------------------------------------------------------------------
    # STEP 3: Setup Patient Context for Multi-Turn Clinical Dialogue
    # --------------------------------------------------------------------------
    patient_ctx = PatientContext(
        patient_id="PAT-RAMESH-42",
        name="Ramesh Sharma",
        age=42,
        gender="Male",
        hospital_type="ayurveda",
        prakriti_profile=prakriti_res.prakriti_type,
        dashavidha_state=dash_state.model_dump(),
        chief_complaint="Severe burning in stomach and acid reflux",
        current_medications=scanned_prescription_ocr["medications"],
        past_medical_history=scanned_prescription_ocr["diagnoses"]
    )

    history = []
    rag_snippets = [
        ocr_rag_snippet,
        "[NAMASTE Code]: EB-4 Amlapitta (Hyperacidity) - Cardinal features: Daha (burning sensation), Amlodgara (sour burps), Tikshnagni in Saama state."
    ]

    # Predefined clinical scenario turns for full clinical thoroughness
    patient_script = [
        "I have had severe epigastric burning and acid reflux after eating for 3 days.",
        "The burning starts about 1 hour after meals and travels up to my chest. It feels hot and sour.",
        "My appetite is sharp, but in the morning my tongue has a thick white coating and mouth tastes sour.",
        "My bowel movements are loose and burning twice a day, and I wake up around 2 AM feeling hot and restless.",
        "I have been working late night shifts this week, skipping meals and drinking 4 cups of black coffee daily."
    ]

    # --------------------------------------------------------------------------
    # STEP 4: Multi-Turn Conversational Dialogue Execution
    # --------------------------------------------------------------------------
    print("\nSTEP 4: Executing Multi-Turn Clinical Interview (Turns 1 to 5)...")

    for turn_idx, patient_utt in enumerate(patient_script, start=1):
        print(f"\n" + "=" * 50)
        print(f"🔹 TURN {turn_idx}")
        print("=" * 50)

        # Call the live AI dialogue engine
        turn_result = await get_next_dialogue_turn(
            patient_context=patient_ctx,
            conversation_history=history,
            max_turns=6,
            rag_context_snippets=rag_snippets
        )

        if turn_result.next_question:
            print(f"🤖 AI Asks: \"{turn_result.next_question}\"")
            print(f"📱 Touch Chips: {[opt.label for opt in turn_result.touch_options]}")
            history.append(ConversationMessage(role="assistant", content=turn_result.next_question))
        
        print(f"👤 Patient Responds: \"{patient_utt}\"")
        history.append(ConversationMessage(role="patient", content=patient_utt))

        # Check stopping condition on final turn
        if turn_idx == len(patient_script) or (turn_result.should_stop and turn_idx >= len(patient_script)):
            print(f"\n[OK] Reached clinical completeness (Turn {turn_idx})!")
            break
        
        await asyncio.sleep(1.0)

    # Final evaluation turn to get completed Vaidya Intake Summary
    print("\n" + "=" * 75)
    print("📋 GENERATING FINAL COMPREHENSIVE VAIDYA INTAKE SUMMARY")
    print("=" * 75)
    
    final_turn = await get_next_dialogue_turn(
        patient_context=patient_ctx,
        conversation_history=history,
        max_turns=len(patient_script),
        rag_context_snippets=rag_snippets
    )
    
    print(final_turn.clinical_summary)
    print("=" * 75)
    print("\n[SUCCESS] 5-Turn Comprehensive Clinical Simulation Finished!")

if __name__ == "__main__":
    asyncio.run(run_live_simulation())
