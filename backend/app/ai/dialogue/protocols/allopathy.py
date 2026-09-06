# backend/app/ai/dialogue/protocols/allopathy.py
"""
MediKiosk — Allopathy Clinical Protocol Strategy (SOCRATES)
Implements standard UK/Commonwealth SOCRATES inquiry axes and SOAP summaries.
"""

from typing import Dict, Any, List, Optional
import json
import logging

from app.ai.dialogue.protocols.base import ClinicalProtocol
from app.ai.dialogue.protocols.registry import register_protocol
from app.ai.dialogue.models import PatientContext, SocratesState

logger = logging.getLogger("medikiosk.protocols.allopathy")

@register_protocol("allopathy")
class AllopathyProtocol(ClinicalProtocol):
    system_name = "allopathy"
    target_slots = [
        "site", "onset", "character", "radiation",
        "associations", "time_course", "exacerbating_relieving", "severity"
    ]

    def build_system_prompt(
        self,
        patient_context: PatientContext,
        rag_context_snippets: List[str]
    ) -> str:
        rag_formatted = "\n".join([f"• {s}" for s in rag_context_snippets]) if rag_context_snippets else "No prior medical records retrieved."

        return f"""You are MediKiosk AI, an expert, empathetic clinical intake assistant deployed in a Modern Hospital OPD.
Your objective is to interview the patient about their symptoms dynamically using the **SOCRATES** framework, exploring their presenting illness, relevant past medical history, current medications, and review of systems.

CLINICAL INQUIRY DIMENSIONS (SOCRATES):
1. Site & Radiation: Exact anatomical location and whether it radiates (e.g. to arm, back, shoulder, jaw).
2. Character: Sensation (e.g. sharp, dull, burning, throbbing, aching, squeezing, colicky).
3. Severity: 1-10 numeric scale or mild/moderate/severe rating.
4. Onset & Time Course: When did it start (sudden vs gradual), duration, constant vs intermittent, trajectory.
5. Exacerbating & Relieving Factors: What makes it better or worse (food, movement, rest, position, home remedies, medications).
6. Associated Symptoms & Review of Systems: Pertinent positives/negatives (fever, nausea, vomiting, breathlessness, dizziness, sweating).
7. Drug History & Known Allergies: Medications taken and known drug/food allergies.

RETRIEVED CLINICAL & PATIENT KNOWLEDGE (RAG):
{rag_formatted}

CRITICAL RULES & CLINICAL TRIAGE PROTOCOL:
1. DYNAMIC INQUIRY & TRIAGE RULES:
   - Ask exactly ONE clear, empathetic, conversational question at a time.
   - Do NOT stop prematurely! Set `should_stop = false` until all core SOCRATES dimensions are gathered.
   - Set `should_stop = true` and `is_red_flag = true` ONLY when an Acute Medical Emergency is actively occurring in the PATIENT:
     * Acute Coronary Syndromes (classic crushing retrosternal chest pain OR atypical silent MI in elderly/diabetic presenting with sudden cold sweats, dyspnea, nausea, extreme exhaustion).
     * Acute Stroke / CVA (sudden facial drooping, arm weakness, slurred speech).
     * Intracranial Emergencies (sudden thunderclap 'worst headache of life', subacute subdural hematoma post-fall with confusion).
     * Severe Respiratory Failure / Tension Pneumothorax / Stridor / Anaphylaxis.
     * Acute Surgical Abdomen / Peritonitis / Massive GI Hemorrhage / Septic Shock.
   - SUBJECT ATTRIBUTION & FAMILY HISTORY: Do NOT flag as emergency if the patient is describing a family member's illness (e.g., "my father had a stroke", "my brother died of a heart attack"). Only triage the PATIENT's own active presenting complaint!
   - METAPHORS & IDIOMS: Do NOT flag colloquial or figurative expressions (e.g., "my boss gave me a heart attack", "this work is killing me", "my head is exploding"). Parse the actual physical presenting complaint.
2. STRICT ANTI-REPETITION:
   - NEVER ask about an aspect or dimension that has ALREADY been addressed in the conversation history or patient background.
3. TOUCH OPTIONS:
   - For every question asked, generate 3 to 4 concise, clear `touch_options` for touchscreen selection with `id`, `label`, `value`, and `slot_tag`.

4. OUTPUT FORMAT:
   You MUST respond with valid JSON ONLY matching this schema:
{{
  "should_stop": boolean,
  "next_question": string or null,
  "touch_options": [
    {{"id": "string", "label": "string", "value": "string", "slot_tag": "string"}}
  ],
  "state": {{
    "site": string or null,
    "onset": string or null,
    "character": string or null,
    "radiation": string or null,
    "associations": ["string"],
    "time_course": string or null,
    "exacerbating_relieving": string or null,
    "severity": string or null
  }},
  "covered_slots": ["string"],
  "missing_slots": ["string"],
  "primary_impression": string or null,
  "provisional_differentials": ["string", "string", "string"],
  "clinical_summary": string or null,
  "closing_message": string or null,
  "is_red_flag": boolean,
  "red_flag_details": string or null,
  "reasoning": string
}}
(Note: Provide a concise primary_impression and top 3 provisional_differentials for the attending doctor's clinical review. Set is_red_flag to true ONLY if the PATIENT themselves is experiencing an active life-threatening emergency.)
"""

    def normalize_state(
        self,
        raw_state: Optional[Dict[str, Any]],
        accumulated_text: str = ""
    ) -> Dict[str, Any]:
        state = raw_state or {}
        covered = []
        for s in self.target_slots:
            val = state.get(s)
            if val:
                if isinstance(val, list) and len(val) > 0:
                    covered.append(s)
                elif isinstance(val, str) and val.strip():
                    covered.append(s)
        
        missing = [s for s in self.target_slots if s not in covered]
        return {
            "state": state,
            "covered_slots": covered,
            "missing_slots": missing
        }

    def format_doctor_summary(
        self,
        final_state: Dict[str, Any],
        patient_context: PatientContext
    ) -> str:
        complaint = patient_context.chief_complaint or final_state.get("site") or "Presenting illness"
        onset = final_state.get("onset") or "Reported duration"
        assoc = ", ".join(final_state.get("associations", [])) if final_state.get("associations") else "None reported"
        meds = ", ".join(patient_context.current_medications) if patient_context.current_medications else "None on file"
        allergies = ", ".join(patient_context.allergies) if patient_context.allergies else "No known allergies"
        
        return (
            f"### 📋 Allopathic Clinical History Summary (for Attending Physician)\n"
            f"1. **Chief Complaint (CC):**\n"
            f"   * {complaint} (Onset: {onset})\n"
            f"2. **History of Present Illness (HPI - SOCRATES):**\n"
            f"   * **Site / Radiation:** {final_state.get('site', 'Unspecified')} | Radiation: {final_state.get('radiation', 'None reported')}\n"
            f"   * **Character & Severity:** {final_state.get('character', 'Unspecified')} | Severity: {final_state.get('severity', 'Unspecified')}\n"
            f"   * **Timing & Progression:** {final_state.get('time_course', 'Unspecified')}\n"
            f"   * **Triggers & Relievers:** {final_state.get('exacerbating_relieving', 'None identified')}\n"
            f"   * **Associated Symptoms (ROS):** {assoc}\n"
            f"3. **Past Medical & Medication History:**\n"
            f"   * Current Medications: {meds}\n"
            f"   * Known Allergies: {allergies}\n"
            f"4. **Triage Assessment & Clinical Impression:**\n"
            f"   * Triage Urgency: Routine OPD Evaluation\n"
            f"   * Clinical Impression: Patient presenting with {complaint.lower()} for physician assessment."
        )
