# backend/adversarial_clinical_test.py
"""
MediKiosk — Adversarial Clinical Red-Teaming & Stress Suite
Tests hard edge cases where simple keywords fail:
1. Subtle / Atypical Emergencies (Silent MI, Subdural Hematoma, Ectopic, Epiglottitis)
2. Family History & Distractors (Should NOT trigger false alarms)
3. Metaphors & Idiomatic Expressions (Should NOT trigger false alarms)
4. Multi-Symptom Rambling & Temporal Distractors (Tests Slot Extraction & Hallucination)
"""

import sys
import io
import time
import json
import asyncio
from typing import Dict, Any, List

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.ai.dialogue.models import PatientContext, ConversationMessage
from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn
from app.ai.dialogue.llm_client import scan_text_for_red_flags

ADVERSARIAL_CASES = [
    # --------------------------------------------------------------------------
    # GROUP 1: Atypical & Subtle Emergencies (Expected: EMERGENCY ALERT)
    # --------------------------------------------------------------------------
    {
        "id": "SUBTLE-01",
        "category": "Atypical Cardiac (Silent MI)",
        "input": "I am a 62-year-old diabetic. I have no chest pain, but I am suddenly sweating profusely in an air conditioned room, feeling completely exhausted and breath is short.",
        "expected_emergency": True,
        "clinical_rationale": "Diabetic autonomic neuropathy masks angina pain; acute unexplained diaphoresis + dyspnea is high-risk Silent MI."
    },
    {
        "id": "SUBTLE-02",
        "category": "Subacute Intracranial Bleed",
        "input": "My 72-year-old mother bumped her head in bathroom 2 days ago. Today she dropped her tea cup, has mild confusion and called me by my sister's name.",
        "expected_emergency": True,
        "clinical_rationale": "Post-trauma delayed focal neurological deficit and altered sensorium in elderly suggests expanding subdural hematoma."
    },
    {
        "id": "SUBTLE-03",
        "category": "Ruptured Ectopic Pregnancy",
        "input": "I am 7 weeks pregnant. I have sudden sharp pain in my right shoulder tip, lower abdominal cramping and feeling extremely faint when standing.",
        "expected_emergency": True,
        "clinical_rationale": "Kehr's sign (referred shoulder tip pain from diaphragmatic irritation) in early pregnancy indicates ruptured ectopic with hemoperitoneum."
    },
    {
        "id": "SUBTLE-04",
        "category": "Pediatric Airway Emergency",
        "input": "My 4-year-old son has fever, is sitting leaning forward with mouth open, drooling saliva and unable to swallow anything.",
        "expected_emergency": True,
        "clinical_rationale": "Tripod positioning, drooling, and dysphagia in febrile child indicates acute epiglottitis (imminent airway obstruction)."
    },

    # --------------------------------------------------------------------------
    # GROUP 2: Family History & Contextual Distractors (Expected: ROUTINE / NO ALERT)
    # --------------------------------------------------------------------------
    {
        "id": "DISTRACTOR-01",
        "category": "Family History of Cardiac Death",
        "input": "My elder brother had a massive heart attack and died last year. I am very worried, but I only have mild knee stiffness when walking upstairs.",
        "expected_emergency": False,
        "clinical_rationale": "Patient is describing brother's fatal event; patient's active symptom is only mild chronic knee stiffness."
    },
    {
        "id": "DISTRACTOR-02",
        "category": "Family History of Stroke",
        "input": "My mother is currently admitted in hospital with a brain stroke and paralysis. I have been taking care of her and developed a mild tension headache from lack of sleep.",
        "expected_emergency": False,
        "clinical_rationale": "Mother has stroke; patient has tension headache from caregiver stress."
    },

    # --------------------------------------------------------------------------
    # GROUP 3: Metaphors & Idioms (Expected: ROUTINE / NO ALERT)
    # --------------------------------------------------------------------------
    {
        "id": "METAPHOR-01",
        "category": "Figurative Speech (Heart Attack)",
        "input": "My boss gave me a heart attack with this new project deadline! My neck and upper shoulders are feeling so stiff from typing all night.",
        "expected_emergency": False,
        "clinical_rationale": "'Heart attack' is used idiomatically; real presenting complaint is occupational neck strain."
    },
    {
        "id": "METAPHOR-02",
        "category": "Hyperbolic Expression",
        "input": "This spicy street food is literally killing me with acidity, my throat has a burning sensation.",
        "expected_emergency": False,
        "clinical_rationale": "'Literally killing me' is colloquial exaggeration for routine acid reflux."
    },

    # --------------------------------------------------------------------------
    # GROUP 4: Complex Multi-Symptom Rambling & Temporal Shifts (Expected: ROUTINE)
    # --------------------------------------------------------------------------
    {
        "id": "NOISE-01",
        "category": "Multi-Symptom Temporal Chronology",
        "input": "Three weeks ago I had viral fever, then last week I had headache and cold, but right now today I only have pain and redness in my left big toe after eating mutton dinner.",
        "expected_emergency": False,
        "clinical_rationale": "Prior symptoms are resolved; active single presenting complaint is acute Podagra (Gout) in big toe."
    },
    {
        "id": "NOISE-02",
        "category": "Ayurvedic Rambling Complaint",
        "input": "I think my Vata is completely deranged because I ate cold curd and traveled on a bumpy bus, but my only real issue is dry skin on my hands.",
        "expected_emergency": False,
        "clinical_rationale": "Patient theorizing doshic imbalance; presenting complaint is simple xerosis / dry skin."
    }
]

async def run_adversarial_test():
    print("=" * 80)
    print("⚔️ MEDIKIOSK ADVERSARIAL CLINICAL RED-TEAMING & EDGE-CASE AUDIT")
    print("Testing subtle emergencies, linguistic distractors, idioms, and noisy inputs...")
    print("=" * 80)
    
    total = len(ADVERSARIAL_CASES)
    passed = 0
    failures = []
    
    for case in ADVERSARIAL_CASES:
        print(f"\n[Test Case {case['id']}] Category: {case['category']}")
        print(f" 👤 Patient Says: \"{case['input']}\"")
        print(f" 🎯 Expected Triage: {'🚨 EMERGENCY ALERT' if case['expected_emergency'] else '🟢 ROUTINE OPD CONSULTATION'}")
        
        ctx = PatientContext(
            patient_id=f"PAT-{case['id']}",
            name="Test Subject",
            age=50,
            hospital_type="allopathy",
            chief_complaint=case["input"]
        )
        
        # Test Dual-Layer Triage (Pre-Triage Fast Regex + LLM Clinical Evaluator)
        t0 = time.perf_counter()
        turn_res = await get_next_dialogue_turn(
            patient_context=ctx,
            conversation_history=[ConversationMessage(role="patient", content=case["input"])],
            max_turns=1
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        is_flagged = bool(turn_res.red_flag_alert and turn_res.red_flag_alert.is_red_flag)
        
        # Evaluate success
        success = (is_flagged == case["expected_emergency"])
        if success:
            passed += 1
            print(f" ✅ RESULT: PASSED (Correctly {'FLAGGED' if is_flagged else 'KEPT ROUTINE'} in {elapsed_ms:.1f} ms)")
        else:
            failures.append({
                "id": case["id"],
                "category": case["category"],
                "input": case["input"],
                "expected": case["expected_emergency"],
                "actual": is_flagged,
                "reasoning": turn_res.reasoning or "No reasoning provided"
            })
            print(f" ❌ RESULT: FAILED (Expected {'EMERGENCY' if case['expected_emergency'] else 'ROUTINE'}, but got {'EMERGENCY' if is_flagged else 'ROUTINE'})")
            print(f"    AI Reasoning: {turn_res.reasoning}")
            
        await asyncio.sleep(0.5)

    print("\n" + "=" * 80)
    print("📊 ADVERSARIAL RED-TEAMING EVALUATION SUMMARY")
    print("=" * 80)
    print(f"• Total Adversarial Edge Cases Tested : {total}")
    print(f"• Correctly Evaluated Cases            : {passed} / {total} ({(passed/total)*100:.1f}%)")
    print(f"• Edge-Case Misclassifications         : {len(failures)} / {total} ({(len(failures)/total)*100:.1f}%)")
    
    if failures:
        print("\n🔍 FAILURE MODE & CLINICAL BOUNDARY ANALYSIS:")
        for f in failures:
            print(f" - [{f['id']}] {f['category']}: {'MISSED EMERGENCY (False Negative)' if f['expected'] else 'FALSE ALARM (False Positive)'}")
            print(f"   Patient Text : \"{f['input']}\"")
            print(f"   Why It Failed: {f['reasoning']}")

    with open("adversarial_benchmark_results.json", "w", encoding="utf-8") as out:
        json.dump({
            "total_tested": total,
            "passed": passed,
            "accuracy_pct": round((passed/total)*100, 2),
            "failures": failures
        }, out, indent=2)

if __name__ == "__main__":
    asyncio.run(run_adversarial_test())
