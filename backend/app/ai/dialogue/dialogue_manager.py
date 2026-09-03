"""
MediKiosk — SOCRATES Clinical Dialogue Manager
Primary deliverable: `get_next_dialogue_turn` takes patient context and conversation
history, passes them to the LLM with SOCRATES instructions, avoids repetition,
and returns the next relevant clinical question or decides to stop.
"""

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
from app.ai.dialogue.prompts import build_dialogue_prompt
from app.ai.dialogue.llm_client import (
    call_groq_llm,
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

def _normalize_socrates_state(state_dict: Optional[Dict[str, Any]]) -> SocratesState:
    if not state_dict:
        return SocratesState()
    
    all_slots = [
        "site", "onset", "character", "radiation", "associations",
        "time_course", "exacerbating_relieving", "severity"
    ]
    covered = []
    for s in all_slots:
        val = state_dict.get(s)
        if val:
            if isinstance(val, list) and len(val) > 0:
                covered.append(s)
            elif isinstance(val, str) and val.strip():
                covered.append(s)

    missing = [s for s in all_slots if s not in covered]

    return SocratesState(
        site=state_dict.get("site"),
        onset=state_dict.get("onset"),
        character=state_dict.get("character"),
        radiation=state_dict.get("radiation"),
        associations=state_dict.get("associations") or [],
        time_course=state_dict.get("time_course"),
        exacerbating_relieving=state_dict.get("exacerbating_relieving"),
        severity=state_dict.get("severity"),
        covered_slots=covered,
        missing_slots=missing
    )

async def get_next_dialogue_turn(
    patient_context: Union[PatientContext, Dict[str, Any]],
    conversation_history: List[Union[ConversationMessage, Dict[str, Any]]],
    max_turns: int = 10,
    current_socrates_state: Optional[Union[SocratesState, Dict[str, Any]]] = None
) -> DialogueTurnResult:
    """
    Main deliverable function for MediKiosk clinical dialogue.

    Parameters:
    - patient_context: Patient demographics, chief complaint, initial symptoms, medical history, vitals, docs.
    - conversation_history: Chronological list of previous dialogue turns between AI and Patient.
    - max_turns: Target maximum questions before summarizing.
    - current_socrates_state: Optional prior state of filled SOCRATES slots.

    Returns:
    - DialogueTurnResult:
      - should_stop: True if all necessary information is collected or emergency detected; False to continue.
      - next_question: The next tailored clinical question (None if should_stop is True).
      - touch_options: 3-4 clickable options for touchscreen input.
      - socrates_state: Updated SOCRATES state.
      - clinical_summary: Summary of collected findings.
      - closing_message: Patient-facing closing text when complete.
      - red_flag_alert: Alert details if an acute emergency is detected.
    """
    ctx = _normalize_context(patient_context)
    history = _normalize_history(conversation_history)

    # Fast sub-millisecond red flag triage on latest patient utterances
    if history:
        latest_patient_utterances = " ".join([
            m.get("content", "") for m in history[-2:] if m.get("role") in ["patient", "user"]
        ])
        red_flag = scan_text_for_red_flags(latest_patient_utterances)
        if red_flag:
            state = current_socrates_state if isinstance(current_socrates_state, SocratesState) else SocratesState()
            return DialogueTurnResult(
                should_stop=True,
                next_question=None,
                touch_options=[],
                socrates_state=state,
                covered_slots=state.covered_slots,
                missing_slots=state.missing_slots,
                clinical_summary=f"EMERGENCY RED FLAG DETECTED: {red_flag.emergency_message}",
                closing_message="A critical medical symptom has been detected. Please proceed immediately to the Emergency Room / Triage Desk.",
                red_flag_alert=red_flag,
                reasoning="Immediate red flag detected via safety screening."
            )

    # If no conversation history yet and no chief complaint provided, ask initial symptom question
    if not history and not ctx.chief_complaint and not ctx.symptoms:
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
            socrates_state=SocratesState(),
            covered_slots=[],
            missing_slots=[
                "site", "onset", "character", "radiation", "associations",
                "time_course", "exacerbating_relieving", "severity"
            ],
            reasoning="Initial interview turn: collecting primary chief complaint."
        )

    # Build prompts containing patient context + conversation history
    prompts = build_dialogue_prompt(ctx, history, max_turns=max_turns)

    # Call LLM (Groq -> OpenAI -> Fallback)
    llm_output = await call_groq_llm(prompts["system"], prompts["user"])
    if not llm_output:
        llm_output = await call_openai_llm(prompts["system"], prompts["user"])

    # Fall back to heuristic engine if no LLM response
    if not llm_output:
        logger.info("External LLM unavailable. Utilizing intelligent clinical heuristic fallback.")
        base_state = current_socrates_state if isinstance(current_socrates_state, SocratesState) else SocratesState()
        return generate_heuristic_turn(ctx, history, base_state, max_turns=max_turns)

    # Process and validate LLM output
    try:
        should_stop = bool(llm_output.get("should_stop", False))
        next_q = llm_output.get("next_question") if not should_stop else None
        
        # Format touch options
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

        # Format SOCRATES state
        raw_socrates = llm_output.get("socrates_state", {})
        socrates_state = _normalize_socrates_state(raw_socrates)

        # Red flag check from LLM
        is_red_flag = bool(llm_output.get("is_red_flag", False))
        red_flag_alert = None
        if is_red_flag:
            should_stop = True
            next_q = None
            touch_options = []
            red_flag_alert = RedFlagAlert(
                is_red_flag=True,
                severity="CRITICAL",
                category="LLM Detected Red Flag",
                emergency_message=llm_output.get("red_flag_details", "Urgent medical attention required.")
            )

        clinical_summary = llm_output.get("clinical_summary")
        closing_msg = llm_output.get("closing_message")
        if should_stop and not closing_msg:
            closing_msg = "Thank you for answering these questions. Your clinical details have been recorded for your doctor."

        return DialogueTurnResult(
            should_stop=should_stop,
            next_question=next_q,
            touch_options=touch_options,
            socrates_state=socrates_state,
            covered_slots=socrates_state.covered_slots,
            missing_slots=socrates_state.missing_slots,
            clinical_summary=clinical_summary,
            closing_message=closing_msg,
            red_flag_alert=red_flag_alert,
            reasoning=llm_output.get("reasoning")
        )

    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}. Falling back to heuristic engine.")
        base_state = current_socrates_state if isinstance(current_socrates_state, SocratesState) else SocratesState()
        return generate_heuristic_turn(ctx, history, base_state, max_turns=max_turns)

async def start_dialogue(patient_context: Union[PatientContext, Dict[str, Any]]) -> DialogueTurnResult:
    """Convenience helper to initialize dialogue with empty history."""
    return await get_next_dialogue_turn(patient_context=patient_context, conversation_history=[])
