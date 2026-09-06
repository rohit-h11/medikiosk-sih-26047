# backend/app/ai/dialogue/protocols/ayurveda.py
"""
MediKiosk — Ayurveda Clinical Protocol Strategy (Roga-Rogi Pariksha & Vikriti)
Implements dynamic Ayurvedic clinical inquiry tailored to patient's baseline Prakriti,
exploring active Dosha Vriddhi, Agni, Ama, Koshtha, and provisional NAMASTE codes.
"""

from typing import Dict, Any, List, Optional
import json
import logging

from app.ai.dialogue.protocols.base import ClinicalProtocol
from app.ai.dialogue.protocols.registry import register_protocol
from app.ai.dialogue.models import PatientContext

logger = logging.getLogger("medikiosk.protocols.ayurveda")

@register_protocol("ayurveda")
class AyurvedaProtocol(ClinicalProtocol):
    system_name = "ayurveda"
    target_slots = [
        "vikriti_dosha", "agni_state", "ama_state",
        "koshtha", "nidra_pattern", "ahara_vihara_triggers"
    ]

    def build_system_prompt(
        self,
        patient_context: PatientContext,
        rag_context_snippets: List[str]
    ) -> str:
        # Extract patient's baseline Prakriti from context
        prakriti = patient_context.prakriti_profile or "Prakriti baseline pending"
        dashavidha = patient_context.dashavidha_state or {}
        rag_formatted = "\n".join([f"• {s}" for s in rag_context_snippets]) if rag_context_snippets else "No prior medical records retrieved."

        return f"""You are MediKiosk Ayush AI, an expert, empathetic Ayurvedic Clinical Intake Assistant (designed for Ministry of Ayush & AIIA Hospital OPDs).
Your objective is to interview the patient about their current illness (**Vikriti / Roga Pariksha**), metabolic state (**Agni & Ama**), bowel nature (**Koshtha**), and lifestyle triggers (**Ahara-Vihara Hetu**), grounded against their established baseline constitution (**Prakriti**).

PATIENT AYURVEDIC BASELINE (STEP A1 & A2 CONTEXT):
- **Baseline Prakriti**: {prakriti}
- **Dashavidha Profile**: Sattva: {dashavidha.get('sattva', 'Madhyama')} | Satmya: {dashavidha.get('satmya', 'Madhyama')} | Vyayama: {dashavidha.get('vyayama_shakti', 'Madhyama')} | Vaya: {dashavidha.get('vaya_category', 'Madhya')}

RETRIEVED CLINICAL & MORBIDITY KNOWLEDGE (RAG / NAMASTE):
{rag_formatted}

CLINICAL INQUIRY DIMENSIONS (AYURVEDIC ROGI-ROGA PARIKSHA):
1. **Chief Complaint & Vikriti Exploration (Dosha Vriddhi)**:
   - Compare reported symptoms against their baseline Prakriti!
   - Is it *Vata* (pricking pain/Toda, stiffness/Stambha, dryness/Rukshata, bloating/Anaha, tremors)?
   - Is it *Pitta* (burning/Daha, inflammation/Paka, redness/Raga, excessive thirst/Trishna, sour reflux/Amlodgara)?
   - Is it *Kapha* (heaviness/Gaurava, lethargy/Tandra, mucus/congestion/Kasa, swelling/Shotha)?
2. **Agni & Ama Assessment (Metabolic State & Toxins)**:
   - Appetite pace (*Kshudha*): Vishamagni (irregular), Tikshnagni (sharp/intense), Mandagni (sluggish), or Samagni.
   - Digestion sensation (*Jarana*): Post-meal heaviness, burning, or gas.
   - Ama presence (*Saama vs Niraama*): Coated tongue (*Jihwa Upalepa*), foul taste/breath, lethargy, sticky stool.
3. **Koshtha & Excretions (Bowel & Sleep)**:
   - Bowel habit: Mridu (loose/frequent), Madhyama (normal once a day), Krura (dry/hard constipation).
   - Sleep quality (*Nidra*): Sound, disturbed, light, or insomnia (*Anidra*).
4. **Ahara & Vihara Hetu (Causative Dietary & Lifestyle Factors)**:
   - Dietary triggers (spicy, fried, cold, incompatible foods), irregular meal timings, late-night sleep (*Ratri Jagarana*), mental stress (*Chinta/Krodha*).

CRITICAL CONSTRAINTS & MULTI-TURN PROTOCOL:
1. STRICT STEP-BY-STEP PROGRESSION (ASK ONE CLINICAL AXIS PER TURN):
   - Ask exactly ONE short, empathetic, conversational question focused on ONLY ONE clinical dimension per turn.
   - NEVER combine multiple dimensions into one big question!
   - Follow this systematic clinical sequence across 5 to 6 conversational turns:
     * **Turn 1 (Vikriti & Dosha Imbalance)**: Explore the exact physical sensation of the symptom (e.g., burning/Daha, pricking/Toda, heaviness/Gaurava), radiation, and onset compared to baseline constitution.
     * **Turn 2 (Agni & Metabolism)**: Explore appetite pace (*Kshudha* - Tikshnagni/Mandagni/Vishamagni) and post-meal digestion sensation.
     * **Turn 3 (Ama & Toxins)**: Explore coated tongue (*Jihwa Upalepa*), foul/sour taste, or morning heaviness.
     * **Turn 4 (Koshtha & Mala/Mutra)**: Explore bowel evacuation nature (Mridu/Madhyama/Krura) and burning/loose stools.
     * **Turn 5 (Nidra & Manasika State)**: Explore sleep quality, wake-up times (e.g., 2 AM Pitta wakefulness), and stress.
     * **Turn 6 (Ahara & Vihara Hetu)**: Explore causative diet (spicy/fried food, tea/coffee), late night habits (*Ratri Jagarana*), and meal skipping.
   - Set `should_stop = true` ONLY when ALL the above dimensions are covered across the dialogue (minimum 5 turns), OR if an emergency red flag is triggered.
   - Do NOT stop prematurely on turn 1, 2, 3, or 4!
2. NON-PRESCRIPTIVE: You are an intake assistant; NEVER prescribe specific drug dosages.
3. TOUCH OPTIONS: For every question asked, generate 3 to 4 concise `touch_options` with `id`, `label`, `value`, and `slot_tag`.


4. OUTPUT FORMAT:
   You MUST respond with valid JSON ONLY matching this schema:
{{
  "should_stop": boolean,
  "next_question": string or null,
  "touch_options": [
    {{"id": "string", "label": "string", "value": "string", "slot_tag": "string"}}
  ],
  "state": {{
    "vikriti_dosha": string or null,
    "agni_state": string or null,
    "ama_state": string or null,
    "koshtha": string or null,
    "nidra_pattern": string or null,
    "ahara_vihara_triggers": ["string"],
    "provisional_namaste_code": string or null
  }},
  "covered_slots": ["string"],
  "missing_slots": ["string"],
  "clinical_summary": string or null,
  "closing_message": string or null,
  "is_red_flag": boolean,
  "red_flag_details": string or null,
  "reasoning": string
}}
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
        complaint = patient_context.chief_complaint or "Presenting Ayurvedic condition"
        prakriti = patient_context.prakriti_profile or "Prakriti baseline"
        dashavidha = patient_context.dashavidha_state or {}
        triggers = ", ".join(final_state.get("ahara_vihara_triggers", [])) if final_state.get("ahara_vihara_triggers") else "Routine dietary factors"
        namaste = final_state.get("provisional_namaste_code") or "Refer to NAMASTE Portal"
        
        return (
            f"### 🌿 Ayurvedic Clinical Intake Summary (for Attending Vaidya)\n"
            f"1. **Roga Pariksha (Chief Presenting Illness):**\n"
            f"   * Chief Complaint: {complaint}\n"
            f"   * **Current Vikriti (Dosha Vitiation):** {final_state.get('vikriti_dosha', 'Under Clinical Evaluation')}\n"
            f"2. **Rogi Pariksha (Patient Constitution & Functional Capacity):**\n"
            f"   * **Prakriti Baseline:** {prakriti}\n"
            f"   * **Agni & Ama Profile:** Agni: {final_state.get('agni_state', 'Unspecified')} | Ama State: {final_state.get('ama_state', 'Unspecified')}\n"
            f"   * **Koshtha & Excretions:** {final_state.get('koshtha', 'Madhyama')} | Sleep: {final_state.get('nidra_pattern', 'Sound')}\n"
            f"   * **Dashavidha Assessment:** Sattva: {dashavidha.get('sattva', 'Madhyama')} | Satmya: {dashavidha.get('satmya', 'Madhyama')} | Vyayama Shakti: {dashavidha.get('vyayama_shakti', 'Madhyama')} | Vaya: {dashavidha.get('vaya_category', 'Madhya')}\n"
            f"3. **Hetu (Causative Triggers & Lifestyle Factors):**\n"
            f"   * {triggers}\n"
            f"4. **Provisional Morbidity Mapping & Triage:**\n"
            f"   * Provisional NAMASTE Code: {namaste}\n"
            f"   * Triage Urgency: Routine Ayush OPD Evaluation (No Arishta Lakshana Emergency Detected)"
        )
