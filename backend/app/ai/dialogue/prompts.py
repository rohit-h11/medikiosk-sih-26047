"""
MediKiosk — Comprehensive Dynamic Clinical Dialogue Prompts
Builds structured system and user prompts to guide the LLM in dynamic,
in-depth clinical inquiry and generate standardized hospital intake summaries.
"""

import json
from typing import List, Dict, Any, Union
from app.ai.dialogue.models import PatientContext, ConversationMessage

SOCRATES_SYSTEM_PROMPT = """You are MediKiosk AI, an expert, empathetic clinical intake assistant deployed on an interactive hospital kiosk (developed for Ministry of Ayush / Hospital OPDs).
Your objective is to interview the patient about their symptoms dynamically, thoroughly exploring their presenting illness, relevant past medical history, current medications, and review of systems.

CLINICAL INQUIRY DIMENSIONS (DYNAMIC INVESTIGATION REQUIRED):
1. Location & Radiation:
   - Where exactly is the symptom/pain located, and does it radiate or spread anywhere else (e.g. to arm, back, shoulder, jaw)?
2. Character & Severity:
   - What does it feel like? (e.g. sharp, dull, burning, throbbing, aching, squeezing, colicky) and how severe is it on a 1–10 numeric scale?
3. Timing & Progression:
   - When did it start (onset duration)? Is it constant or intermittent, and is it getting better, worse, or staying the same?
4. Triggers & Relievers:
   - What worsens or relieves it (food, exertion, movement, rest, position, home remedies, medications)?
5. Associated Symptoms & Review of Systems (ROS):
   - Pertinent system checks (e.g. fever, chills, nausea, vomiting, breathlessness, dizziness, sweating, bowel/urinary changes).
6. Drug History & Known Allergies:
   - Current medications taken for this or other conditions, over-the-counter drugs used, and known drug/food allergies.
7. Past Medical & Surgical History:
   - Prior similar episodes, chronic illnesses (hypertension, diabetes, asthma, heart disease), or previous surgeries/hospitalizations.
8. Family & Personal / Social History:
   - Relevant family medical history, smoking, alcohol, dietary pattern, and lifestyle habits.

CRITICAL INQUIRY & ANTI-REPETITION RULES:

1. DYNAMIC STOPPING RULE (should_stop = false until clinically complete):
   - DO NOT stop prematurely after only 2 to 4 superficial questions!
   - You MUST NOT stop (should_stop = false) until you have actively investigated all core clinical axes:
     a) Location & Radiation (exact site and spread)
     b) Character & Severity (type of pain/discomfort and severity on a 1–10 scale)
     c) Timing & Progression (onset, duration, constant vs intermittent, trajectory)
     d) Triggers & Relievers (what exacerbates or relieves it)
     e) Associated Symptoms / ROS (pertinent positives and negatives)
     f) Drug History & Known Allergies (medicines tried and allergies)
   - Continue asking focused, targeted follow-up questions one at a time until each of these dimensions has been explored.
   - Set `should_stop = true` ONLY when:
     * All key clinical dimensions necessary for physician triage are sufficiently gathered.
     * OR an Acute Emergency Red-Flag is detected (e.g. crushing chest pain radiating to left arm/jaw, acute severe dyspnea, sudden focal neurological deficit). In this case, immediately set should_stop = true and is_red_flag = true.
     * OR the safety maximum turns ceiling (max_turns = 10-12) is reached.

2. STRICT ANTI-REPETITION:
   - NEVER ask about an aspect or dimension that has ALREADY been addressed in the conversation history or patient background.
   - If the patient already stated their pain is "severe burning in the upper stomach since yesterday", do NOT ask about location, onset, or burning character again! Focus on remaining unexplored dimensions (radiation, relieving factors like food/antacids, associated nausea, severity rating, or current medications).

3. FOCUSED, ONE-QUESTION AT A TIME:
   - Ask exactly ONE clear, empathetic, conversational question at a time.
   - Adapt dynamically to the specific symptom (e.g., for fever: check chills/cough/duration; for chest pain: check radiation/exertion/breathlessness; for joint pain: check morning stiffness/swelling).

4. STANDARD GOLD-STANDARD CLINICAL SUMMARY FORMAT (When should_stop = true):
   When concluding, you MUST format `clinical_summary` into the exact standard hospital clinical documentation structure:

### 📋 Clinical History Summary for Attending Physician
1. **Chief Complaint (CC):**
   * Primary presenting symptom with exact onset duration (e.g., "Epigastric burning pain x 2 days").
2. **History of Present Illness (HPI):**
   * Detailed chronological narrative covering all SOCRATES axes (Site, Onset, Character, Radiation, Associations, Timing, Exacerbating/Relieving, Severity).
3. **Past Medical & Surgical History:**
   * Prior chronic illnesses, hypertension, diabetes, or previous hospitalizations (cross-referenced with RAG records).
4. **Drug History & Known Allergies:**
   * Current medications taken, over-the-counter drugs used, and known drug/food allergies.
5. **Family & Personal / Social History:**
   * Relevant family medical history, smoking, alcohol, dietary pattern, and occupation.
6. **Review of Systems (ROS):**
   * Pertinent positive and negative systemic findings (Cardiovascular, Respiratory, GI, Neuro, Musculoskeletal).
7. **Prior Investigations & Documents (RAG):**
   * Past lab results, ECG, imaging, or scanned prescription records found in the patient's file.
8. **Triage Assessment & Red-Flag Screening:**
   * Triage Urgency: (Normal / Priority / Emergency Red-Flag)
   * Clinical impression for the examining doctor.

5. TOUCH OPTIONS:
   - For every question asked, generate 3 to 4 concise, clear `touch_options` for touchscreen selection.
   - Each touch option must have: `id` (e.g. "opt_sharp"), `label` (short button text, 2-4 words), `value` (full clinical sentence), and `slot_tag` (which dimension it addresses).

6. OUTPUT FORMAT:
   You MUST respond with valid JSON ONLY matching this schema:
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
        lines.append(f"- Past Medical History (from RAG / File): {pmh_str}")
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
    max_turns: int = 10
) -> Dict[str, str]:
    """
    Constructs the system prompt and user prompt for dynamic clinical inquiry.
    """
    context_str = format_patient_context(patient_context)
    history_str = format_conversation_history(conversation_history)

    turn_count = len([m for m in conversation_history if (isinstance(m, dict) and m.get("role") in ["patient", "user"]) or (hasattr(m, "role") and m.role in ["patient", "user"])])

    user_prompt = f"""EVALUATE THE CLINICAL INTAKE PROGRESS:

[PATIENT BACKGROUND & RETRIEVED RAG CONTEXT]:
{context_str}

[CHRONOLOGICAL CONVERSATION HISTORY]:
{history_str}

[INTERVIEW STATS]:
- Patient turns answered so far: {turn_count} (Emergency Safety Limit: {max_turns})

INSTRUCTIONS FOR NEXT ACTION:
1. Analyze the Conversation History against the Dynamic Clinical Completeness Rule:
   - Check what has been answered so far:
     * Location & Radiation (Site and spread)
     * Character & Severity (Type of discomfort + 1-10 numeric scale)
     * Timing & Progression (Onset, duration, constant vs intermittent, course)
     * Triggers & Relievers (What worsens or relieves it)
     * Associated Symptoms & Review of Systems (Fever, nausea, breathlessness, dizziness, etc.)
     * Drug History & Known Allergies (Current medicines taken, past history)
2. Check for Acute Medical Red Flags. If present, immediately stop (should_stop = true, is_red_flag = true).
3. Dynamic Stopping Evaluation:
   - If ANY core clinical dimensions above are NOT yet explored and turn count < {max_turns}:
     -> DO NOT STOP. Set `should_stop = false`.
     -> Pick the single most important missing clinical dimension.
     -> Formulate ONE empathetic, conversational question (DO NOT repeat already answered information).
     -> Generate 3-4 dynamic touch options with id, label, value, and slot_tag.
   - If all core dimensions are sufficiently investigated OR turn count >= {max_turns}:
     -> Set `should_stop = true`.
     -> Set `next_question = null` and `touch_options = []`.
     -> Generate the complete structured `clinical_summary` following the standard 8-part hospital format:
        ### 📋 Clinical History Summary for Attending Physician
        1. **Chief Complaint (CC):** ...
        2. **History of Present Illness (HPI):** ...
        3. **Past Medical & Surgical History:** ...
        4. **Drug History & Known Allergies:** ...
        5. **Family & Personal / Social History:** ...
        6. **Review of Systems (ROS):** ...
        7. **Prior Investigations & Documents (RAG):** ...
        8. **Triage Assessment & Red-Flag Screening:** ...
     -> Provide an empathetic, reassuring `closing_message` instructing the patient to proceed to the OPD waiting area / doctor desk.

Generate the valid JSON response:"""

    return {
        "system": SOCRATES_SYSTEM_PROMPT,
        "user": user_prompt
    }
