"""
MediKiosk — LLM Prompt Engine & Clinical Heuristic Generator
Implements the 3-part LLM call structure for both Allopathic SOCRATES and Ayurvedic Vikriti intake.
Grounded in classical Charaka Samhita criteria, baseline-deviation logic, and 2-type RAG chunks.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import httpx
from app.schemas.dialogue import (
    HistoryType,
    InterviewPhase,
    SocratesState,
    AyurvedicAssessment,
    TouchOption,
    StandardHistory
)
from app.ai.dialogue.ccras_pas import (
    get_representative_ccras_questions,
    convert_ccras_question_to_touch_options,
    classify_agni_koshtha_from_text,
    detect_ayurvedic_vikriti
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# -------------------------------------------------------------
# Slot Extraction from Natural Language Text
# -------------------------------------------------------------

def extract_socrates_slots(text: str, current_state: SocratesState) -> SocratesState:
    """Extract SOCRATES slots from patient natural language or selected options."""
    text_lower = text.lower()
    updated = current_state.model_copy()
    
    # 1. Site
    if not updated.site:
        site_matches = re.findall(r"\b(chest|head|abdomen|stomach|knee|back|lower back|shoulder|throat|neck|leg|arm|foot|ankle|eye|ear|hip|joints?)\b", text_lower)
        if site_matches:
            updated.site = site_matches[0].capitalize()
            if "site" in updated.missing_slots:
                updated.missing_slots.remove("site")
                
    # 2. Onset / Duration
    if not updated.onset:
        onset_matches = re.findall(r"\b(\d+\s*(?:days?|weeks?|months?|years?|hours?)|yesterday|today|since morning|few days|last week|sudden|gradual)\b", text_lower)
        if onset_matches:
            updated.onset = onset_matches[0]
            if "onset" in updated.missing_slots:
                updated.missing_slots.remove("onset")
                
    # 3. Character / Quality
    if not updated.character:
        char_matches = re.findall(r"\b(sharp|stabbing|dull|aching|burning|throbbing|pulsating|cramping|squeezing|tight|pricking|colicky)\b", text_lower)
        if char_matches:
            updated.character = char_matches[0].capitalize()
            if "character" in updated.missing_slots:
                updated.missing_slots.remove("character")

    # 4. Severity (1-10 scale)
    sev_match = re.search(r"\b(?:severity|scale|rate|pain|is)?\s*(\d{1,2})\s*(?:out of 10|/10|on 10)\b", text_lower)
    if not sev_match:
        sev_match = re.search(r"\b(?:rated|score|level)\s*(\d{1,2})\b", text_lower)
    if sev_match:
        try:
            val = int(sev_match.group(1))
            if 1 <= val <= 10:
                updated.severity_score = val
                if "severity" in updated.missing_slots:
                    updated.missing_slots.remove("severity")
        except ValueError:
            pass
    elif not updated.severity_score:
        if "mild" in text_lower:
            updated.severity_score = 3
            if "severity" in updated.missing_slots:
                updated.missing_slots.remove("severity")
        elif "moderate" in text_lower:
            updated.severity_score = 6
            if "severity" in updated.missing_slots:
                updated.missing_slots.remove("severity")
        elif "severe" in text_lower or "unbearable" in text_lower or "agonizing" in text_lower:
            updated.severity_score = 9
            if "severity" in updated.missing_slots:
                updated.missing_slots.remove("severity")

    # 5. Radiation
    if not updated.radiation:
        rad_match = re.search(r"\b(radiat(?:es|ing)|spread(?:s|ing)|goes down to|goes to)\s+([\w\s]+)", text_lower)
        if rad_match:
            updated.radiation = rad_match.group(2).strip().capitalize()
            if "radiation" in updated.missing_slots:
                updated.missing_slots.remove("radiation")
        elif any(k in text_lower for k in ["no spread", "stays in one place", "localized", "nowhere else"]):
            updated.radiation = "Localized (No radiation)"
            if "radiation" in updated.missing_slots:
                updated.missing_slots.remove("radiation")

    # 6. Associations
    assoc_keywords = ["nausea", "vomiting", "fever", "chills", "dizziness", "cough", "sweating", "fatigue", "breathlessness", "headache", "rash"]
    for kw in assoc_keywords:
        if kw in text_lower and kw not in updated.associations:
            updated.associations.append(kw.capitalize())
            if "associations" in updated.missing_slots:
                updated.missing_slots.remove("associations")

    # 7. Time Course / Timing
    if not updated.time_course:
        if any(k in text_lower for k in ["constant", "continuous", "all day", "always there"]):
            updated.time_course = "Constant / Continuous"
            if "time_course" in updated.missing_slots:
                updated.missing_slots.remove("time_course")
        elif any(k in text_lower for k in ["intermittent", "comes and goes", "waves", "periodic", "in morning", "at night"]):
            updated.time_course = "Intermittent / Comes and goes"
            if "time_course" in updated.missing_slots:
                updated.missing_slots.remove("time_course")

    # 8. Exacerbating / Relieving Factors
    if not updated.exacerbating_relieving:
        if any(k in text_lower for k in ["worse with movement", "worse after food", "better with rest", "better with medicine", "relieved by heat", "worse in morning"]):
            updated.exacerbating_relieving = text.strip()
            if "exacerbating_relieving" in updated.missing_slots:
                updated.missing_slots.remove("exacerbating_relieving")

    return updated

# -------------------------------------------------------------
# System Prompt Builders (3-Part Assembly as per PDF Task Sheet)
# -------------------------------------------------------------

def build_vikriti_system_prompt(
    prakriti_result: str,
    clinical_reference_chunks: List[str],
    patient_history_chunks: List[str]
) -> str:
    """
    Step A4: Build the Vikriti system prompt.
    Baseline-aware dosha evaluation + Ahara Shakti probing + 2-type RAG chunks.
    """
    clin_ref_str = "\n".join(clinical_reference_chunks) if clinical_reference_chunks else "No specific clinical reference chunks retrieved."
    pat_hist_str = "\n".join(patient_history_chunks) if patient_history_chunks else "New patient — no prior medical records found."

    prompt = f"""ROLE: You are assessing dosha imbalance (Vikriti) for an Ayurvedic consultation. The patient's baseline Prakriti is: {prakriti_result}.

TASK: Ask ONE question at a time to identify symptoms indicating deviation from the patient's baseline constitution.
Also probe digestive capacity and appetite patterns (Ahara Shakti) as part of this conversation.
Use the retrieved reference knowledge to map symptoms to dosha aggravation:
- Vata Vriddhi: Toda (pricking pain), Stambha (stiffness), Kampa (tremor), Rukshata (dryness), Anaha (gas), Vibandha (constipation), Nidranasha (insomnia).
- Pitta Vriddhi: Daha (burning), Paka (ulceration), Raga (redness), Sweda (excess sweat), Tikshnagni (sharp hunger), Amlodgara (acid burps).
- Kapha Vriddhi: Gaurava (heaviness), Tandra (lethargy), Kasa/Shwasa (mucus cough), Agnimandya (sluggish digestion), Shotha (swelling).

BASELINE vs. VIKRITI DISTINCTION:
Consider that a symptom may be NORMAL for this patient's Prakriti and not an active imbalance (e.g. mild heat sensitivity in a Pitta-dominant patient may be baseline; light sleep in a Vata patient may be baseline). Flag as Vikriti ONLY if it is a new deviation, has escalated in severity/frequency, or clusters with other dosha signs.

RELEVANT RAG CHUNKS:
[Clinical Reference Knowledge]:
{clin_ref_str}

[Patient Historical Record Chunks]:
{pat_hist_str}

CONSTRAINTS:
- Do NOT diagnose a Western/allopathic disease.
- Do NOT suggest or prescribe medications/treatments.
- Do NOT repeat questions already answered.
- If patient history chunks show a relevant prior condition, factor that into your questioning and note it in your summary.
- Stop and summarize once you have sufficient clinical confidence, or after 6-8 questions.

OUTPUT FORMAT: Reply ONLY in valid JSON with one of two formats:
EITHER:
{{
  "next_question": "string",
  "touch_options": [{{"id": "opt1", "label": "string", "value": "string", "slot_tag": "string"}}]
}}
OR:
{{
  "vikriti_summary": "string",
  "dosha_scores": {{"vata": float, "pitta": float, "kapha": float}},
  "confidence": float (0-1)
}}"""
    return prompt

def build_socrates_system_prompt(
    clinical_reference_chunks: List[str],
    patient_history_chunks: List[str]
) -> str:
    """
    Step B2: Build the SOCRATES system prompt.
    8-axis symptom exploration + prior-history urgency escalation + 2-type RAG chunks.
    """
    clin_ref_str = "\n".join(clinical_reference_chunks) if clinical_reference_chunks else "No specific clinical reference chunks retrieved."
    pat_hist_str = "\n".join(patient_history_chunks) if patient_history_chunks else "New patient — no prior medical records found."

    prompt = f"""ROLE: You are taking a structured symptom history using the SOCRATES framework for an OPD consultation.

TASK: Ask ONE question at a time, covering:
- Site (Where exactly is the symptom located)
- Onset (Sudden or gradual, when it started)
- Character (Sharp, dull, burning, throbbing, etc.)
- Radiation (Does it spread anywhere)
- Associated symptoms (Fever, nausea, cough, breathlessness, etc.)
- Time course (Constant, intermittent, diurnal variation)
- Exacerbating / Relieving factors (Movement, rest, food, medication)
- Severity (1-10 verbal numeric rating)
Ask in whatever logical order fits the conversation naturally. Do NOT ask about an axis already covered.

RELEVANT RAG CHUNKS:
[Clinical Reference Knowledge]:
{clin_ref_str}

[Patient Historical Record Chunks]:
{pat_hist_str}

CONSTRAINTS:
- Do NOT diagnose.
- Do NOT suggest medications.
- If the patient describes a red-flag symptom (see reference chunks), OR if patient history chunks show a relevant prior condition alongside current symptoms (e.g. past heart attack alongside current chest pain), treat this as elevated urgency: stop the questionnaire and flag for immediate escalation instead of continuing.

OUTPUT FORMAT: Reply ONLY in valid JSON with one of two formats:
EITHER:
{{
  "next_question": "string",
  "touch_options": [{{"id": "opt1", "label": "string", "value": "string", "slot_tag": "string"}}]
}}
OR:
{{
  "socrates_summary": {{
    "site": "string",
    "onset": "string",
    "character": "string",
    "radiation": "string",
    "associated": ["string"],
    "timecourse": "string",
    "factors": "string",
    "severity": "string"
  }},
  "confidence": float (0-1),
  "red_flags": ["string"]
}}"""
    return prompt

# -------------------------------------------------------------
# Clinical Heuristic Fallback Generator (Zero-Latency Offline)
# -------------------------------------------------------------

def generate_heuristic_next_turn(
    history_type: HistoryType,
    phase: InterviewPhase,
    turn_count: int,
    max_turns: int,
    transcript: List[Dict[str, str]],
    socrates: SocratesState,
    ayurvedic: Optional[AyurvedicAssessment],
    extracted_docs: Dict[str, Any],
    ccras_battery_index: int = 0,
    patient_history_chunks: Optional[List[str]] = None
) -> Tuple[str, List[TouchOption], InterviewPhase, Optional[str]]:
    """
    Deterministic clinical fallback engine that generates logically sound medical follow-up questions
    and touch-friendly options for the Kiosk without needing an external API key.
    """
    if turn_count >= max_turns - 1:
        return (
            "Thank you. I have captured your complete clinical history. Your structured summary has been prepared for the doctor.",
            [TouchOption(id="opt_confirm", label="Confirm & Send to Doctor Queue", value="Confirmed and completed", slot_tag="confirm")],
            InterviewPhase.COMPLETED,
            "Intake complete. Directing to doctor waiting area."
        )

    # ------------------ ALLOPATHIC / MIXED PRIMARY ------------------
    if history_type in (HistoryType.ALLOPATHIC, HistoryType.MIXED) and phase in (InterviewPhase.CHIEF_COMPLAINT, InterviewPhase.SOCRATES_EXPLORATION, InterviewPhase.BACKGROUND_HISTORY):
        if phase == InterviewPhase.CHIEF_COMPLAINT or turn_count == 0:
            return (
                "Hello! I am your MediKiosk clinical intake assistant. What main symptom or health concern brings you to the clinic today?",
                [
                    TouchOption(id="cc_pain", label="Joint / Body Pain", value="I have severe joint and body pain", slot_tag="site"),
                    TouchOption(id="cc_fever", label="Fever & Weakness", value="I have high fever and weakness", slot_tag="associations"),
                    TouchOption(id="cc_cough", label="Cough & Cold", value="I have persistent cough and chest congestion", slot_tag="character"),
                    TouchOption(id="cc_stomach", label="Stomach / Digestive issue", value="I have abdominal pain and indigestion", slot_tag="site")
                ],
                InterviewPhase.SOCRATES_EXPLORATION,
                "Please speak clearly into the microphone or tap your primary concern."
            )

        elif phase == InterviewPhase.SOCRATES_EXPLORATION:
            if not socrates.character or not socrates.severity_score:
                site_str = socrates.site or "your symptom"
                return (
                    f"Could you describe what the {site_str} feels like (e.g. sharp, dull aching, burning, throbbing), and how severe it is from 1 to 10?",
                    [
                        TouchOption(id="char_sharp", label="Sharp / Stabbing (7/10)", value="It is a sharp, stabbing sensation rated 7 out of 10", slot_tag="character"),
                        TouchOption(id="char_dull", label="Dull / Constant Aching (5/10)", value="It is a dull, constant ache rated 5 out of 10", slot_tag="character"),
                        TouchOption(id="char_burn", label="Burning / Acidity (6/10)", value="It feels like a burning sensation rated 6 out of 10", slot_tag="character"),
                        TouchOption(id="char_throb", label="Throbbing / Pulsating (8/10)", value="It is throbbing and pulsating rated 8 out of 10", slot_tag="character")
                    ],
                    InterviewPhase.SOCRATES_EXPLORATION,
                    "Select the option that matches your feeling or rate your pain level."
                )

            elif not socrates.time_course or not socrates.radiation:
                return (
                    "Does this discomfort stay in one spot or spread elsewhere, and is it constant throughout the day or does it come and go?",
                    [
                        TouchOption(id="rad_local", label="Localized / Stays in one spot", value="It stays in one localized spot and comes and goes intermittently", slot_tag="radiation"),
                        TouchOption(id="rad_spread", label="Spreads / Radiates outward", value="It radiates and spreads to surrounding areas, especially when active", slot_tag="radiation"),
                        TouchOption(id="time_const", label="Constant / Continuous all day", value="It is constant throughout the day without much relief", slot_tag="time_course"),
                        TouchOption(id="time_inter", label="Comes in waves / Intermittent", value="It comes in waves and gets worse at specific times", slot_tag="time_course")
                    ],
                    InterviewPhase.SOCRATES_EXPLORATION,
                    "Tell us if the symptom spreads or when it happens."
                )

            elif not socrates.exacerbating_relieving:
                return (
                    "What makes your symptoms better or worse (for example: physical movement, rest, meals, or medications)?",
                    [
                        TouchOption(id="factor_move", label="Worse with movement / Better with rest", value="It gets significantly worse with movement and improves with rest", slot_tag="exacerbating_relieving"),
                        TouchOption(id="factor_food", label="Worse after eating / Better with empty stomach", value="It worsens after meals and feels better on an empty stomach", slot_tag="exacerbating_relieving"),
                        TouchOption(id="factor_meds", label="Temporarily relieved by pain medicine", value="It gets slightly better after taking over-the-counter medication", slot_tag="exacerbating_relieving"),
                        TouchOption(id="factor_none", label="No obvious trigger / Constant", value="Nothing specific seems to make it better or worse", slot_tag="exacerbating_relieving")
                    ],
                    InterviewPhase.BACKGROUND_HISTORY,
                    "Let us know what relieves or aggravates your condition."
                )

        # Background history / medications / OCR document review
        doc_meds = extracted_docs.get("medications", [])
        if doc_meds:
            med_names = ", ".join([m.get("name", "") for m in doc_meds[:2] if isinstance(m, dict)])
            if med_names:
                return (
                    f"From your uploaded documents, we noted previous medications ({med_names}). Are you still taking these, and do you have any drug allergies?",
                    [
                        TouchOption(id="med_yes", label="Yes, currently taking / No allergies", value=f"Yes, I am currently taking {med_names} and have no known drug allergies", slot_tag="current_medications"),
                        TouchOption(id="med_no", label="Stopped taking / No allergies", value="I have stopped taking those medications and have no known allergies", slot_tag="current_medications"),
                        TouchOption(id="med_allergy", label="I have a drug allergy", value="I have known drug allergies that the doctor should know about", slot_tag="known_allergies")
                    ],
                    InterviewPhase.BACKGROUND_HISTORY if history_type != HistoryType.MIXED else InterviewPhase.AYURVEDIC_PARIKSHA,
                    "Verify your current medications and mention any known drug allergies."
                )

        return (
            "Do you have any other associated symptoms like fever, nausea, dizziness, or any past medical conditions (like Diabetes or Hypertension)?",
            [
                TouchOption(id="bg_none", label="No other medical conditions", value="No other chronic medical conditions or associated symptoms", slot_tag="past_history"),
                TouchOption(id="bg_htn_dm", label="Hypertension / Diabetes history", value="I have a history of high blood pressure / diabetes", slot_tag="past_history"),
                TouchOption(id="bg_fever", label="Mild fever & fatigue", value="I also have mild fever, fatigue, and loss of appetite", slot_tag="associations")
            ],
            InterviewPhase.COMPLETED if history_type != HistoryType.MIXED else InterviewPhase.AYURVEDIC_PARIKSHA,
            "Mention any chronic health conditions."
        )

    # ------------------ AYURVEDIC / MIXED SECONDARY ------------------
    else:
        if phase == InterviewPhase.CHIEF_COMPLAINT or turn_count == 0:
            return (
                "Namaste! Welcome to the AYUSH Clinical Intake Kiosk. What primary health concern or discomfort (Vikriti) brings you to the clinic today?",
                [
                    TouchOption(id="ay_joint", label="Joint Pain & Stiffness (Sandhivata)", value="I have severe joint pain, stiffness and crackling in knees", slot_tag="vikriti"),
                    TouchOption(id="ay_acid", label="Hyperacidity & Burning (Amlapitta)", value="I have burning sensation in chest, sour burps and indigestion", slot_tag="vikriti"),
                    TouchOption(id="ay_resp", label="Cough & Congestion (Kasa/Shwasa)", value="I have heavy chest congestion, chronic cough and mucus", slot_tag="vikriti"),
                    TouchOption(id="ay_skin", label="Skin Itching & Eruptions (Kushtha)", value="I have skin redness, itching and dry patches", slot_tag="vikriti")
                ],
                InterviewPhase.CCRAS_PRAKRITI,
                "Please speak your concern or choose from the common Ayurvedic presentations."
            )

        elif phase == InterviewPhase.CCRAS_PRAKRITI:
            rep_questions = get_representative_ccras_questions(max_count=4)
            q_idx = min(ccras_battery_index, len(rep_questions) - 1)
            active_q = rep_questions[q_idx]
            touch_opts = convert_ccras_question_to_touch_options(active_q)
            
            domain_name = active_q.get("domain_name", "Prakriti Assessment")
            next_phase = InterviewPhase.CCRAS_PRAKRITI if q_idx < len(rep_questions) - 1 else InterviewPhase.AYURVEDIC_PARIKSHA

            return (
                f"[{domain_name}] {active_q.get('text')}",
                touch_opts,
                next_phase,
                f"Assessing constitution ({domain_name}). Tap the option that best fits your natural baseline."
            )

        elif phase == InterviewPhase.AYURVEDIC_PARIKSHA:
            return (
                "How are your regular digestive fire (Agni), appetite patterns, dietary habits (Ahara), and daily stress (Vihara)?",
                [
                    TouchOption(id="av_irregular", label="Irregular hunger & high stress (Vishama Agni)", value="I have irregular hunger, bloating, high work stress and late night sleep", slot_tag="ahara_vihara"),
                    TouchOption(id="av_spicy", label="Sharp burning hunger & acidic burps (Tikshna Agni)", value="I have intense hunger, heartburn, frequently consume spicy and oily foods", slot_tag="ahara_vihara"),
                    TouchOption(id="av_heavy", label="Low hunger & heavy sluggish stomach (Manda Agni)", value="I have sluggish digestion, heavy feeling after small meals and low physical activity", slot_tag="ahara_vihara"),
                    TouchOption(id="av_balanced", label="Normal appetite & balanced home routine (Sama Agni)", value="I eat balanced home-cooked meals with regular sleep timings", slot_tag="ahara_vihara")
                ],
                InterviewPhase.COMPLETED,
                "Assessing digestive capacity (Ahara Shakti) and lifestyle factors (Vihara)."
            )

        return (
            "Thank you. Your CCRAS Prakriti assessment and Ayurvedic clinical case intake are complete. Your case summary is ready for the Vaidya/Doctor.",
            [TouchOption(id="opt_confirm_ay", label="Confirm & Submit to Doctor Queue", value="Ayurvedic intake confirmed", slot_tag="confirm")],
            InterviewPhase.COMPLETED,
            "Intake finished. Directing to Ayurvedic consultation queue."
        )

# -------------------------------------------------------------
# LLM Async Runner with 3-Part Assembly & Provider Dispatch
# -------------------------------------------------------------

async def generate_dialogue_turn_llm(
    history_type: HistoryType,
    phase: InterviewPhase,
    turn_count: int,
    max_turns: int,
    transcript: List[Dict[str, str]],
    socrates: SocratesState,
    ayurvedic: Optional[AyurvedicAssessment],
    extracted_docs: Dict[str, Any],
    clinical_reference_chunks: Optional[List[str]] = None,
    patient_history_chunks: Optional[List[str]] = None,
    ccras_battery_index: int = 0
) -> Tuple[str, List[TouchOption], InterviewPhase, Optional[str]]:
    """
    Main LLM dialogue generation routine assembling the 3-part structure:
    [1] Server Instructions (System Prompt)
    [2] What Patient Said (Transcript)
    [3] Relevant RAG Chunks (Clinical Reference + Patient History)
    """
    clin_chunks = clinical_reference_chunks or []
    pat_chunks = patient_history_chunks or []

    # 1. If no external LLM API key, use verified Clinical Heuristic Engine
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        return generate_heuristic_next_turn(
            history_type=history_type,
            phase=phase,
            turn_count=turn_count,
            max_turns=max_turns,
            transcript=transcript,
            socrates=socrates,
            ayurvedic=ayurvedic,
            extracted_docs=extracted_docs,
            ccras_battery_index=ccras_battery_index,
            patient_history_chunks=pat_chunks
        )

    # 2. Build System Prompt based on domain
    if history_type == HistoryType.AYURVEDIC:
        prakriti_str = ayurvedic.prakriti.dominant_prakriti if (ayurvedic and ayurvedic.prakriti) else "Undetermined"
        system_prompt = build_vikriti_system_prompt(prakriti_str, clin_chunks, pat_chunks)
    else:
        system_prompt = build_socrates_system_prompt(clin_chunks, pat_chunks)

    # 3. Call LLM (OpenAI / Gemini)
    try:
        user_prompt = f"Transcript history so far: {json.dumps(transcript[-4:])}. Generate the next adaptive clinical turn."

        if OPENAI_API_KEY:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    content = json.loads(data["choices"][0]["message"]["content"])
                    q_text = content.get("next_question") or content.get("question_text", "")
                    raw_opts = content.get("touch_options", [])
                    next_ph = InterviewPhase(content.get("next_phase", phase.value))
                    cue = content.get("audio_guidance_cue", "Please respond to the question.")
                    opts = [TouchOption(**opt) for opt in raw_opts] if raw_opts else []
                    return q_text, opts, next_ph, cue

    except Exception:
        # Fall back to heuristic engine on any network or parsing failure
        pass

    return generate_heuristic_next_turn(
        history_type=history_type,
        phase=phase,
        turn_count=turn_count,
        max_turns=max_turns,
        transcript=transcript,
        socrates=socrates,
        ayurvedic=ayurvedic,
        extracted_docs=extracted_docs,
        ccras_battery_index=ccras_battery_index,
        patient_history_chunks=pat_chunks
    )
