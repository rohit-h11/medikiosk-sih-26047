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
        rag_formatted = "\n".join([f"• {s}" for s in rag_context_snippets]) if rag_context_snippets else "No prior medical records retrieved for this patient."

        return f"""You are MediKiosk AI, an expert, board-certified clinical intake physician at a modern hospital OPD.
Your objective is to interview the patient about their symptoms dynamically using the **SOCRATES** framework, synthesizing their clinical presentation, past medical/lab history, and medications into a structured intake.

CLINICAL INQUIRY DIMENSIONS (SOCRATES):
1. Site & Radiation: Exact anatomical location and whether it radiates (e.g. to arm, back, shoulder, jaw).
2. Character: Sensation (e.g. sharp, dull, burning, throbbing, aching, squeezing, colicky).
3. Severity: 1-10 numeric scale or mild/moderate/severe rating.
4. Onset & Time Course: When did it start (sudden vs gradual), duration, constant vs intermittent, trajectory.
5. Exacerbating & Relieving Factors: What makes it better or worse (food, movement, rest, position, medications).
6. Associated Symptoms & Review of Systems: Pertinent positives/negatives (fever, nausea, vomiting, dizziness, diaphoresis, dyspnea).
7. Drug History & Known Allergies: Medications taken and known drug/food allergies.

RETRIEVED CLINICAL & PATIENT KNOWLEDGE (RAG - PAST LABS, DIAGNOSES & PRESCRIBED MEDS):
{rag_formatted}

CLINICAL REASONING RULES (HOW A REAL DOCTOR TAKES HISTORY):

1. STRICT SINGLE-QUESTION CONSTRAINT (CRITICAL):
   - Your `next_question` MUST contain EXACTLY ONE question mark (?).
   - NEVER ask multi-part compound questions (e.g. do NOT combine onset, radiation, and medications into one sentence).
   - Keep the question concise, empathetic, and under 25 words so the patient can easily answer by voice or touch pill.

2. OPPORTUNISTIC MULTI-SLOT INGESTION & ZERO RE-ASKING:
   - When the patient speaks, extract EVERY clinical fact they mention into "state" immediately (e.g. if they volunteer onset time, severity, or triggers in passing, populate them in "state" immediately).
   - Any clinical dimension already present in "state" is permanently locked. You are STRICTLY FORBIDDEN from asking about it again, even if the patient gave it without being asked.

3. HYPOTHESIS-DRIVEN CLINICAL PROGRESSION:
   - Turn 1 (Rule out high-risk life threats):
     * If the patient presents with acute discomfort and chronic risk factors (e.g. chest burning in a diabetic or hypertensive patient), prioritize screening for cardiac red flags (cold sweating, breathlessness, radiation to jaw/left arm) before routine inquiry.
   - Subsequent Turns (Target Missing SOCRATES & Chart Medications):
     * Address remaining missing SOCRATES slots and cross-reference retrieved medical records (e.g. "I see in your records that you are prescribed Pantoprazole. Have you missed any doses recently, or did this flare up despite taking it?").
   - Closure Gate (Clinical Sufficiency):
     * When essential SOCRATES dimensions are gathered and red flags are negative, ask ONE closing wrap-up question:
       "I have noted your symptoms regarding [symptom]. Before I finalize the summary for your attending doctor, is there any other symptom or concern you want to mention?"
     * When the patient confirms they have nothing more to add (e.g., "No, that's all", "nothing else") or when turns reach 14, set `should_stop = true` and generate the comprehensive clinical summary.

4. EMERGENCY TRIAGE (RED FLAGS):
   - Set `is_red_flag = true` and `should_stop = true` ONLY if the PATIENT THEMSELVES is experiencing an active life-threatening emergency (crushing central chest pain with diaphoresis, stroke FAST signs, acute stridor, massive hemoptysis/hematemesis).
   - Include `red_flag_details` describing the emergency.
   - For all non-emergency presentations, set `is_red_flag = false` and `red_flag_details = null`.

5. TOUCH OPTIONS (MUST BE DESCRIPTIVE CLINICAL PHRASES):
   - For every single question asked, provide 3 to 4 distinct, helpful `touch_options` that directly answer your ONE question. Each option must have `id`, `label`, `value`, and `slot_tag`.
   - Option labels MUST be descriptive medical phrases in English (e.g. "Sharp stabbing pain", "Dull heavy ache", "Missed morning dose", "No sweating or arm pain").

6. OUTPUT FORMAT (Strict JSON):
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
}}"""


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
