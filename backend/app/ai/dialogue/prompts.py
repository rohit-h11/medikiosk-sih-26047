"""
MediKiosk — SOCRATES Clinical Dialogue Prompts
Builds structured system and user prompts to guide the LLM in adaptive,
non-repetitive SOCRATES clinical inquiry for hospital kiosk intake.
"""

import json
from typing import List, Dict, Any, Union
from app.ai.dialogue.models import PatientContext, ConversationMessage

SOCRATES_SYSTEM_PROMPT = """You are MediKiosk AI, an expert, empathetic clinical intake assistant deployed on an interactive hospital kiosk.
Your objective is to interview the patient about their symptoms using the clinical SOCRATES assessment framework.

SOCRATES FRAMEWORK AXES:
1. Site (S): Where exactly is the symptom or pain located?
2. Onset (O): When did it start? Was it sudden or gradual?
3. Character (C): What does it feel like? (e.g., sharp, dull, burning, aching, throbbing, colicky, tight)
4. Radiation (R): Does the pain spread anywhere else (e.g. to the back, shoulder, arm, jaw)?
5. Associations (A): Any other associated symptoms (e.g. nausea, vomiting, fever, breathlessness, dizziness, sweating)?
6. Time course (T): How has it changed over time? Is it constant, intermittent, or getting progressively worse?
7. Exacerbating / Relieving factors (E): Does anything make it better or worse (e.g. movement, rest, food, antacids, deep breathing)?
8. Severity (S): How bad is it? (1-10 numeric scale, or mild / moderate / severe)

CRITICAL INSTRUCTIONS & RULES:
1. STRICT ANTI-REPETITION:
   - Carefully review the provided Conversation History and Patient Context.
   - NEVER ask a question about an aspect or slot that has ALREADY been asked or answered.
   - If the patient already stated their pain is "severe throbbing in the forehead since yesterday", do NOT ask about site, onset, or character again! Focus on remaining missing slots (e.g., radiation, associated nausea/photophobia, or relieving factors).

2. CLINICAL RELEVANCE & ORDER:
   - Ask only ONE focused, natural, conversational question at a time.
   - Adapt the inquiry to the specific chief complaint (e.g., for headache, ask about photophobia or neck stiffness; for chest pain, ask about radiation or exertion).
   - If the complaint is not pain-related (e.g., cough, fever, rash), adapt the SOCRATES concept appropriately (e.g., Character: dry vs productive cough; Onset: when fever started; Severity: high grade vs low grade).

3. WHEN TO STOP (should_stop = true):
   - You must decide to STOP when sufficient clinical information has been gathered to triage the patient. Typically, 3 to 5 targeted questions covering the key axes are plenty.
   - Stop immediately if:
     a) Key essential dimensions are answered and enough information is known for the doctor.
     b) Nothing further is clinically required or meaningful to ask.
     c) Red Flag / Medical Emergency detected: (e.g. crushing chest pain radiating to left arm/jaw, acute unilateral weakness/facial droop, severe respiratory distress, acute severe hemorrhage). Immediately set should_stop = true and is_red_flag = true.
   - When stopping:
     - Set `should_stop`: true.
     - Set `next_question`: null.
     - Provide `touch_options`: [].
     - Provide a comprehensive `clinical_summary` summarizing the collected clinical picture for the physician.
     - Provide a warm, reassuring `closing_message` for the patient.

4. TOUCH OPTIONS:
   - For every question asked, generate 3 to 4 concise, clear `touch_options` that can be displayed as clickable buttons on the kiosk screen.
   - Make sure options cover common clinical variations, including a "None / Not applicable" or "Other" option where relevant.
   - Each touch option must have: `id` (e.g. "opt_sharp"), `label` (short text for button), `value` (full sentence representation), and `slot_tag` (which SOCRATES slot it answers).

5. OUTPUT FORMAT:
   You MUST respond with valid JSON ONLY. No preamble, no markdown ticks around the outside if possible, just the JSON object matching this schema:
{
  "should_stop": boolean,
  "next_question": string or null,
  "touch_options": [
    {"id": "string", "label": "string", "value": "string", "slot_tag": "string"}
  ],
  "socrates_state": {
    "site": string or null,
    "onset": string or null,
    "character": string or null,
    "radiation": string or null,
    "associations": ["string"],
    "time_course": string or null,
    "exacerbating_relieving": string or null,
    "severity": string or null
  },
  "covered_slots": ["string"],
  "missing_slots": ["string"],
  "clinical_summary": string or null,
  "closing_message": string or null,
  "is_red_flag": boolean,
  "red_flag_details": string or null,
  "reasoning": string
}
"""

def format_patient_context(context: Union[PatientContext, Dict[str, Any]]) -> str:
    """Formats patient context into readable clinical bullets for the LLM."""
    if isinstance(context, PatientContext):
        data = context.model_dump()
    else:
        data = dict(context)

    lines = []
    if data.get("name"):
        lines.append(f"- Name: {data['name']}")
    if data.get("age"):
        lines.append(f"- Age: {data['age']} years")
    if data.get("gender"):
        lines.append(f"- Gender: {data['gender']}")
    if data.get("chief_complaint"):
        lines.append(f"- Chief Complaint: {data['chief_complaint']}")
    if data.get("symptoms"):
        symptoms_str = ", ".join(data["symptoms"]) if isinstance(data["symptoms"], list) else str(data["symptoms"])
        lines.append(f"- Initial Reported Symptoms: {symptoms_str}")
    if data.get("past_medical_history"):
        pmh_str = ", ".join(data["past_medical_history"]) if isinstance(data["past_medical_history"], list) else str(data["past_medical_history"])
        lines.append(f"- Past Medical History: {pmh_str}")
    if data.get("current_medications"):
        meds_str = ", ".join(data["current_medications"]) if isinstance(data["current_medications"], list) else str(data["current_medications"])
        lines.append(f"- Current Medications: {meds_str}")
    if data.get("allergies"):
        alg_str = ", ".join(data["allergies"]) if isinstance(data["allergies"], list) else str(data["allergies"])
        lines.append(f"- Known Allergies: {alg_str}")
    if data.get("vitals"):
        lines.append(f"- Current Vitals: {json.dumps(data['vitals'])}")
    if data.get("extracted_docs"):
        lines.append(f"- Extracted Medical Record Context: {json.dumps(data['extracted_docs'])}")

    if not lines:
        return "No prior patient background provided."
    return "\n".join(lines)

def format_conversation_history(history: List[Union[ConversationMessage, Dict[str, Any]]]) -> str:
    """Formats conversation turns chronologically to ensure no repetitive questions."""
    if not history:
        return "No conversation history yet. This is the beginning of the interview."

    formatted = []
    turn_idx = 1
    for msg in history:
        if isinstance(msg, ConversationMessage):
            role = msg.role.capitalize()
            text = msg.content
        elif isinstance(msg, dict):
            role = msg.get("role", "speaker").capitalize()
            text = msg.get("content") or msg.get("utterance", "")
        else:
            role = getattr(msg, "role", "speaker").capitalize()
            text = getattr(msg, "content", str(msg))

        formatted.append(f"Turn {turn_idx} [{role}]: {text}")
        turn_idx += 1

    return "\n".join(formatted)

def build_dialogue_prompt(
    patient_context: Union[PatientContext, Dict[str, Any]],
    conversation_history: List[Union[ConversationMessage, Dict[str, Any]]],
    max_turns: int = 6
) -> Dict[str, str]:
    """
    Constructs the system prompt and user prompt for the next dialogue turn evaluation.
    """
    context_str = format_patient_context(patient_context)
    history_str = format_conversation_history(conversation_history)

    turn_count = len([m for m in conversation_history if (isinstance(m, dict) and m.get("role") in ["patient", "user"]) or (hasattr(m, "role") and m.role in ["patient", "user"])])

    user_prompt = f"""EVALUATE THE CURRENT CLINICAL INTAKE STATE:

[PATIENT BACKGROUND & KNOWN CONTEXT]:
{context_str}

[CHRONOLOGICAL CONVERSATION HISTORY]:
{history_str}

[INTERVIEW STATS]:
- Patient responses so far: {turn_count} / max target {max_turns} turns.

TASK:
1. Extract and update all known SOCRATES slots from the Patient Background and Conversation History.
2. Check if a medical red flag exists.
3. Check if all relevant clinical details are collected or if turn target is reached:
   - If yes: stop questioning (`should_stop: true`).
   - If no: choose the SINGLE most relevant missing SOCRATES axis and generate the next natural question with 3-4 touch options.
   - REMEMBER: DO NOT REPEAT ANY QUESTION ON TOPICS ALREADY ADDRESSED!

Generate the JSON response:"""

    return {
        "system": SOCRATES_SYSTEM_PROMPT,
        "user": user_prompt
    }
