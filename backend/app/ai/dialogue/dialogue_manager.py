# backend/app/ai/dialogue/dialogue_manager.py
"""
MediKiosk — Multi-Paradigm Clinical Dialogue Manager
Orchestrates clinical interview turns across Allopathy (SOCRATES) and
Ayurveda (Vikriti / Agni / Ama) using clean, plug-and-play protocol strategies.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union

from app.ai.dialogue.models import (
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState,
    TouchOption,
    RedFlagAlert
)
from app.ai.dialogue.protocols.registry import get_protocol
from app.ai.dialogue.llm_client import (
    call_groq_llm,
    call_gemini_llm,
    call_openai_llm,
    generate_heuristic_turn,
    scan_text_for_red_flags
)

logger = logging.getLogger("medikiosk.dialogue.manager")

def _normalize_context(patient_context: Union[PatientContext, Dict[str, Any]]) -> PatientContext:
    if isinstance(patient_context, PatientContext):
        return patient_context
    return PatientContext(**patient_context)

def _normalize_history(
    conversation_history: List[Union[ConversationMessage, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    normalized = []
    for turn in conversation_history:
        if isinstance(turn, ConversationMessage):
            normalized.append(turn.model_dump())
        elif isinstance(turn, dict):
            normalized.append(turn)
        else:
            normalized.append({
                "role": getattr(turn, "role", "speaker"),
                "content": getattr(turn, "content", str(turn))
            })
    return normalized

def detect_inquired_axes(history: List[Dict[str, Any]]) -> List[str]:
    """Scans prior assistant turns to determine which clinical axes have already been questioned."""
    inquired = set()
    for turn in history:
        if turn.get("role") in ["assistant", "model"]:
            content = (turn.get("content") or turn.get("text") or "").lower()
            slot_tag = (turn.get("slot_tag") or "").lower()
            if slot_tag in ["site", "onset", "character", "radiation", "associations", "time_course", "exacerbating_relieving", "severity"]:
                inquired.add(slot_tag)
            if any(w in content for w in ["feel like", "how would you describe", "nature of", "sharp", "dull", "burning", "throbbing", "tight", "squeezing", "burst", "कैसा महसूस", "झगड़न", "जकड़न"]):
                inquired.add("character")
            if any(w in content for w in ["1 to 10", "scale", "rate", "how severe", "severity", "1 से 10", "पैमाने"]):
                inquired.add("severity")
            if any(w in content for w in ["where", "location", "which part", "कहाँ", "किस हिस्से"]):
                inquired.add("site")
            if any(w in content for w in ["when did", "how long", "how many days", "start", "कब शुरू"]):
                inquired.add("onset")
            if any(w in content for w in ["spread", "radiat", "travel", "move to", "फैलता", "कहाँ तक"]):
                inquired.add("radiation")
            if any(w in content for w in ["worse", "better", "reliev", "trigger", "aggravat", "eating", "food"]):
                inquired.add("exacerbating_relieving")
            if any(w in content for w in ["nausea", "fever", "vomit", "sweat", "breathless", "dizz"]):
                inquired.add("associations")
    return list(inquired)

def _format_conversation_history_text(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "No previous dialogue turns (First turn)."
    lines = []
    for idx, turn in enumerate(history, start=1):
        role = turn.get("role", "speaker").capitalize()
        content = turn.get("content", turn.get("text", "")).strip()
        lines.append(f"Turn {idx} [{role}]: {content}")
    return "\n".join(lines)


async def get_next_dialogue_turn(
    patient_context: Union[PatientContext, Dict[str, Any]],
    conversation_history: List[Union[ConversationMessage, Dict[str, Any]]],
    max_turns: int = 14,
    current_state: Optional[Dict[str, Any]] = None,
    rag_context_snippets: Optional[List[str]] = None
) -> DialogueTurnResult:
    """
    Unified Multi-Paradigm Dialogue Engine:
    1. Resolves ClinicalProtocol strategy (Allopathy vs. Ayurveda).
    2. Builds paradigm-specific system prompt with RAG grounding.
    3. Invokes fast LLM reasoning (Groq -> OpenAI -> Heuristic).
    4. Normalizes state & generates standardized physician/vaidya clinical summaries.
    """
    ctx = _normalize_context(patient_context)
    history = _normalize_history(conversation_history)
    protocol = get_protocol(ctx.hospital_type)
    rag_snippets = rag_context_snippets or []

    # If opening turn with empty history and no complaint, return specialized opening question
    if not history and not ctx.chief_complaint and not ctx.symptoms:
        if ctx.hospital_type == "ayurveda":
            return DialogueTurnResult(
                should_stop=False,
                next_question="Hello, welcome to the Ayush OPD. What main health issue or discomfort brings you to the hospital today?",
                touch_options=[
                    TouchOption(id="opt_acidity", label="Acidity / Burning", value="I have severe acidity and burning in stomach", slot_tag="vikriti_dosha"),
                    TouchOption(id="opt_joint", label="Joint Pain / Stiffness", value="I have joint pain and morning stiffness", slot_tag="vikriti_dosha"),
                    TouchOption(id="opt_indigestion", label="Gas / Indigestion", value="I have gas, bloating and sluggish digestion", slot_tag="agni_state"),
                    TouchOption(id="opt_cough", label="Cough / Breathing issue", value="I have persistent cough and chest congestion", slot_tag="vikriti_dosha"),
                    TouchOption(id="opt_other_ayu", label="Other Health Issue", value="I have a different health problem", slot_tag="vikriti_dosha")
                ],
                state={},
                covered_slots=[],
                missing_slots=protocol.target_slots,
                reasoning="Initial Ayush interview turn: collecting primary chief complaint."
            )
        else:
            return DialogueTurnResult(
                should_stop=False,
                next_question="Hello, welcome to MediKiosk. Please tell me what main symptoms or health concern brings you in today?",
                touch_options=[
                    TouchOption(id="opt_fever", label="Fever & Cough", value="I have fever and cough", slot_tag="onset"),
                    TouchOption(id="opt_stomach", label="Stomach Pain", value="I have stomach discomfort and pain", slot_tag="site"),
                    TouchOption(id="opt_headache", label="Headache", value="I have a severe headache", slot_tag="site"),
                    TouchOption(id="opt_chest", label="Chest Discomfort", value="I have chest pain or tightness", slot_tag="site"),
                    TouchOption(id="opt_other", label="Other Health Issue", value="I have a different health concern", slot_tag="site")
                ],
                state={},
                covered_slots=[],
                missing_slots=protocol.target_slots,
                reasoning="Initial Allopathic interview turn: collecting primary chief complaint."
            )

    # Build system prompt using resolved ClinicalProtocol strategy
    system_prompt = protocol.build_system_prompt(ctx, rag_snippets)
    
    # Build confirmed clinical facts from current state
    active_state = current_state or {}
    confirmed_slots = {
        k: v for k, v in active_state.items()
        if v and str(v).lower() not in ["null", "none", "[]", "{}"]
    }
    missing_slots = [s for s in protocol.target_slots if s not in confirmed_slots]
    if confirmed_slots:
        confirmed_facts_text = "\n".join([f"- {k.replace('_', ' ').title()}: {v}" for k, v in confirmed_slots.items()])
    else:
        confirmed_facts_text = "None confirmed yet (initial presentation)."

    missing_slots_text = ", ".join([s.replace('_', ' ').title() for s in missing_slots]) if missing_slots else "All core clinical dimensions collected."

    # Extract patient's latest utterance for prominent emphasis
    latest_patient_utterance = ctx.chief_complaint or "Initial presentation"
    if history:
        for m in reversed(history):
            if m.get("role") in ["patient", "user"]:
                latest_patient_utterance = m.get("content", m.get("text", ""))
                break

    # Paradigm-specific context and instructions
    if ctx.hospital_type.lower() in ["ayurveda", "ayush"]:
        paradigm_context = f"""- Baseline Prakriti: {ctx.prakriti_profile or 'Pending Assessment'}
- Dashavidha Profile: Sattva: {ctx.dashavidha_state.get('sattva', 'Madhyama') if ctx.dashavidha_state else 'Madhyama'} | Satmya: {ctx.dashavidha_state.get('satmya', 'Madhyama') if ctx.dashavidha_state else 'Madhyama'}"""
        clinical_selection_instructions = f"""3. HYPOTHESIS-DRIVEN AYURVEDIC CLINICAL SELECTION:
   - Step 1 (Active Vikriti vs. Baseline Prakriti): Compare presenting symptoms against baseline constitution ({ctx.prakriti_profile or 'baseline'}). Inquire about the exact physical sensation of the symptom (burning/Daha, pricking/Toda, heaviness/Gaurava).
   - Step 2 (Agni & Ama Assessment): Inquire about metabolic fire (appetite pace: sharp vs sluggish vs irregular) or signs of undigested toxins (Ama: coated tongue in morning, heaviness, foul breath).
   - Step 3 (Koshtha, Medications & Ahara-Vihara Hetu): Inquire about bowel movements (loose/frequent vs dry/constipated), active medications from chart, and causative dietary/lifestyle factors (spicy/oily food, late-night sleep / Ratri Jagarana).
   - Step 4 (Clinical Closure Gate): When essential Ayurvedic slots are gathered, ask ONE final wrap-up question:
     "I have noted your symptoms. Before I finalize your summary for the attending Vaidya, is there any other symptom or concern you want to mention?"
   - If the patient confirms closure (e.g. "no", "that's all") or turns reach {max_turns}, set should_stop = true and generate the clinical summary."""
    else:
        paradigm_context = f"- Triage Mode: Allopathic Clinical Intake (SOCRATES)"
        clinical_selection_instructions = f"""3. HYPOTHESIS-DRIVEN CLINICAL SELECTION:
   - If red flags have not been screened yet (Turn 1 in a patient with chest discomfort and chronic risks like diabetes or hypertension), ask ONE question ruling out cardiac ischemia red flags (diaphoresis, dyspnea, jaw/left arm radiation).
   - In subsequent turns, target remaining missing slots in TARGET REMAINING CLINICAL SLOTS, proactively correlating with their past hospital records and medications (e.g. Pantoprazole compliance, food triggers).
   - When core slots are gathered and red flags are negative, ask ONE final wrap-up question:
     "I have noted your symptoms. Before I finalize your summary for the attending doctor, is there any other symptom or concern you want to mention?"
   - If the patient confirms closure (e.g., "no", "that's all") or turns reach {max_turns}, set should_stop = true and generate the clinical summary."""

    # Construct user prompt with clear separation of facts, transcript, and latest utterance
    history_text = _format_conversation_history_text(history)
    user_prompt = f"""PATIENT CONTEXT:
- Name: {ctx.name or 'Patient'} | Age: {ctx.age or 'Unspecified'} | Gender: {ctx.gender or 'Unspecified'}
- Chief Complaint: {ctx.chief_complaint or 'Under investigation'}
- Hospital Paradigm: {ctx.hospital_type.upper()}
{paradigm_context}
- Maximum Safe Turns: {max_turns}

CONFIRMED CLINICAL FACTS (LOCKED IN CHART - NEVER RE-ASK ANY OF THESE):
{confirmed_facts_text}

TARGET REMAINING CLINICAL SLOTS TO ASSESS:
{missing_slots_text}

CONVERSATION TRANSCRIPT:
{history_text}

PATIENT'S LATEST STATEMENT:
"{latest_patient_utterance}"

INSTRUCTIONS FOR THIS TURN:
1. SPONTANEOUS EXTRACTION & CHART LOCKING (CRITICAL):
   - Extract ALL newly mentioned clinical facts from "{latest_patient_utterance}" directly into `state` (e.g. symptoms, appetite, bowel pattern, triggers).
   - If a clinical fact is ALREADY present in CONFIRMED CLINICAL FACTS, you are STRICTLY FORBIDDEN from asking about it again!

2. EXACTLY ONE QUESTION (STRICT SINGLE-BARREL RULE):
   - Your `next_question` MUST contain EXACTLY ONE question mark (?).
   - NEVER ask compound or multi-part questions (e.g. do NOT combine appetite, bowel, and sleep into one sentence).
   - Keep the question concise, empathetic, and under 25 words so the patient can easily answer by voice or touch pill.

{clinical_selection_instructions}

4. RED FLAGS & SAFETY:
   - Set `is_red_flag = true` and `should_stop = true` ONLY for active life-threatening emergencies experienced by the patient (acute severe respiratory distress, acute severe hemorrhage, sudden collapse).
   - Otherwise, set `is_red_flag = false` and `red_flag_details = null`.

5. TOUCH OPTIONS:
   - Provide 3 to 4 distinct, concrete `touch_options` that directly answer your ONE question. Each option must have `id`, `label`, `value`, and `slot_tag`.
   - IMPORTANT: Option labels MUST be descriptive phrases in English.

6. Update "state" with all newly extracted findings.
Respond strictly in JSON format."""


    # Call LLM (Groq -> Gemini -> OpenAI -> Fallback Heuristic)
    llm_output = await call_groq_llm(system_prompt, user_prompt)
    if not llm_output:
        llm_output = await call_gemini_llm(system_prompt, user_prompt)
    if not llm_output:
        llm_output = await call_openai_llm(system_prompt, user_prompt)

    # Fallback if external LLM is offline
    if not llm_output:
        logger.info(f"External LLM unavailable. Utilizing intelligent clinical heuristic fallback for {ctx.hospital_type}.")
        if ctx.hospital_type.lower() in ["ayurveda", "ayush"]:
            norm = protocol.normalize_state(active_state)
            return DialogueTurnResult(
                should_stop=(len(history) >= max_turns * 2),
                next_question="Could you please describe how your digestion, appetite, and sleep are affected?",
                touch_options=[
                    TouchOption(id="opt1", label="Digestion is poor/heavy", value="Poor digestion"),
                    TouchOption(id="opt2", label="Sharp appetite & acid reflux", value="Acid reflux"),
                    TouchOption(id="opt3", label="Irregular appetite & constipation", value="Irregular digestion"),
                    TouchOption(id="opt4", label="Sleep is disturbed", value="Disturbed sleep")
                ],
                state=norm["state"],
                covered_slots=norm["covered_slots"],
                missing_slots=norm["missing_slots"],
                clinical_summary=protocol.format_doctor_summary(norm["state"], ctx) if len(history) >= max_turns * 2 else None,
                closing_message="Thank you. Your Ayurvedic consultation details have been recorded." if len(history) >= max_turns * 2 else None
            )
        base_socrates = SocratesState(
            site=active_state.get("site"),
            onset=active_state.get("onset"),
            character=active_state.get("character"),
            radiation=active_state.get("radiation"),
            associations=active_state.get("associations", []) if isinstance(active_state.get("associations"), list) else ([active_state.get("associations")] if active_state.get("associations") else []),
            time_course=active_state.get("time_course"),
            exacerbating_relieving=active_state.get("exacerbating_relieving"),
            severity=active_state.get("severity")
        )
        return generate_heuristic_turn(ctx, history, base_socrates, max_turns=max_turns)

    # Parse and normalize LLM response
    try:
        should_stop = bool(llm_output.get("should_stop", False))
        next_q = llm_output.get("next_question") if not should_stop else None
        
        # Touch options
        raw_options = llm_output.get("touch_options", [])
        touch_options = []
        if not should_stop and raw_options:
            for opt in raw_options:
                if isinstance(opt, dict) and "id" in opt and "label" in opt:
                    touch_options.append(TouchOption(
                        id=str(opt.get("id")),
                        label=str(opt.get("label")),
                        value=str(opt.get("value", opt.get("label"))),
                        slot_tag=opt.get("slot_tag")
                    ))

        # State normalization via protocol with cumulative merge
        raw_state = llm_output.get("state", llm_output.get("socrates_state", {}))
        merged_state = dict(active_state)
        if isinstance(raw_state, dict):
            for k, v in raw_state.items():
                if v and str(v).lower() not in ["null", "none", "[]", "{}"]:
                    merged_state[k] = v

        normalized = protocol.normalize_state(merged_state)


        # Red flag check
        is_red_flag = bool(llm_output.get("is_red_flag", False))
        red_flag_alert = None
        if is_red_flag:
            should_stop = True
            next_q = None
            touch_options = []
            red_flag_alert = RedFlagAlert(
                is_red_flag=True,
                severity="CRITICAL",
                category="Clinical Red Flag Alert",
                emergency_message=llm_output.get("red_flag_details", "Urgent emergency medical evaluation required.")
            )

        # Force stopping if patient turns reach safety ceiling
        patient_turns_count = len([m for m in history if m.get("role") in ["patient", "user"]])
        if patient_turns_count >= max_turns:
            should_stop = True
            next_q = None
            touch_options = []

        # Generate summary if stopping
        clinical_summary = llm_output.get("clinical_summary")
        if should_stop and not clinical_summary:
            clinical_summary = protocol.format_doctor_summary(normalized["state"], ctx)

        closing_msg = llm_output.get("closing_message")
        if should_stop and not closing_msg:
            closing_msg = "Thank you. Your clinical intake details have been recorded for the attending doctor."

        return DialogueTurnResult(
            should_stop=should_stop,
            next_question=next_q,
            touch_options=touch_options,
            state=normalized["state"],
            covered_slots=normalized["covered_slots"],
            missing_slots=normalized["missing_slots"],
            primary_impression=llm_output.get("primary_impression"),
            provisional_differentials=llm_output.get("provisional_differentials", []),
            clinical_summary=clinical_summary,
            closing_message=closing_msg,
            red_flag_alert=red_flag_alert,
            reasoning=llm_output.get("reasoning")
        )

    except Exception as e:
        logger.error(f"Error parsing protocol LLM response: {e}. Falling back to heuristic.")
        if ctx.hospital_type.lower() == "ayurveda":
            # Ayurveda fallback
            norm = protocol.normalize_state({})
            return DialogueTurnResult(
                should_stop=(len(history) >= max_turns * 2),
                next_question="Could you please describe how your digestion, appetite, and sleep are affected?",
                touch_options=[
                    TouchOption(id="opt1", label="Digestion is poor/heavy", value="Poor digestion"),
                    TouchOption(id="opt2", label="Sharp appetite & acid reflux", value="Acid reflux"),
                    TouchOption(id="opt3", label="Irregular appetite & constipation", value="Irregular digestion"),
                    TouchOption(id="opt4", label="Sleep is disturbed", value="Disturbed sleep")
                ],
                state=norm["state"],
                covered_slots=norm["covered_slots"],
                missing_slots=norm["missing_slots"],
                clinical_summary=protocol.format_doctor_summary(norm["state"], ctx) if len(history) >= max_turns * 2 else None,
                closing_message="Thank you. Your Ayurvedic consultation details have been recorded." if len(history) >= max_turns * 2 else None
            )
        base_socrates = SocratesState()
        return generate_heuristic_turn(ctx, history, base_socrates, max_turns=max_turns)

async def start_dialogue(patient_context: Union[PatientContext, Dict[str, Any]]) -> DialogueTurnResult:
    """Convenience helper to initialize dialogue with empty history."""
    return await get_next_dialogue_turn(patient_context=patient_context, conversation_history=[])

