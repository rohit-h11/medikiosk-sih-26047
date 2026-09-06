"""
MediKiosk — LLM Client for Clinical Dialogue
Invokes Groq, OpenAI, or Gemini with structured JSON output,
with an intelligent offline clinical heuristic fallback.
"""

import os
import json
import re
import logging
from typing import Dict, Any, Optional, List
import httpx
from dotenv import load_dotenv
load_dotenv()

from app.ai.dialogue.models import (
    DialogueTurnResult,
    SocratesState,
    TouchOption,
    RedFlagAlert,
    PatientContext
)

try:
    from app.config import settings
    _DEFAULT_GROQ = settings.GROQ_API_KEY
    _DEFAULT_OPENAI = getattr(settings, "OPENAI_API_KEY", "")
    _DEFAULT_GEMINI = getattr(settings, "GEMINI_API_KEY", "")
except Exception:
    _DEFAULT_GROQ = ""
    _DEFAULT_OPENAI = ""
    _DEFAULT_GEMINI = ""

logger = logging.getLogger("medikiosk.dialogue.llm")

def get_groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY") or _DEFAULT_GROQ

def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or _DEFAULT_OPENAI

def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY") or _DEFAULT_GEMINI

# Preferred Groq models in order of priority (20b has higher TPM quota and faster inference)
GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"]

def _clean_json_text(raw_text: str) -> str:
    """Strip markdown code fence if LLM wraps output in ```json ... ```"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

def parse_llm_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON string safely, handling edge cases."""
    if not raw_text:
        return None
    cleaned = _clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except Exception:
        # Regex search for outermost curly brackets
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

async def call_groq_llm(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Call Groq API using HTTP/REST or SDK for fast JSON inference."""
    api_key = get_groq_api_key()
    if not api_key or api_key.startswith("your-"):
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for model_name in GROQ_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 512
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = parse_llm_json_response(content)
                    if parsed:
                        return parsed
                else:
                    logger.warning(f"Groq {model_name} failed with status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Groq API error with {model_name}: {e}")

    return None

async def call_gemini_llm(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Call Gemini API for fast JSON inference."""
    api_key = get_gemini_api_key()
    if not api_key or api_key.startswith("your-"):
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        return parse_llm_json_response(text)
            else:
                logger.warning(f"Gemini API returned {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"Gemini API error: {e}")

    return None

async def call_openai_llm(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Call OpenAI API if key is present."""
    api_key = get_openai_api_key()
    if not api_key or api_key.startswith("your-"):
        return None

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 2048
                }
            )
            if res.status_code == 200:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return parse_llm_json_response(content)
    except Exception as e:
        logger.warning(f"OpenAI API error: {e}")

    return None

# ----------------------------------------------------------------------
# Rule-Based Heuristic Clinical Engine (100% Offline / Fallback Support)
# ----------------------------------------------------------------------

RED_FLAG_PATTERNS = [
    # Cardiovascular Emergencies (STEMI, Acute Coronary, Aortic Dissection, Malignant Arrhythmia)
    (
        r"\b(crushing|substernal|radiat(?:es|ing)\s+to\s+(?:left\s+arm|jaw|back|shoulder)|chest\s+(?:pressure|tightness|pain).*(?:sweat|diaphoresis|dizziness|faint|vomit|pallor|cold)|heart\s+attack|retrosternal|elephant\s+sitting|syncope.*loss\s+of\s+consciousness|systolic\s+bp\s+80|cad.*chest\s+tightness|pink\s+frothy\s+sputum)\b",
        "CRITICAL",
        "Cardiovascular Emergency",
        "Acute coronary syndrome, STEMI, or cardiogenic shock suspected. Immediate ECG & resuscitation."
    ),
    # Cerebrovascular & Neurological (Stroke FAST, Subarachnoid Hemorrhage, Status Epilepticus)
    (
        r"\b(facial\s+droop|slurred\s+speech|one\s+sided\s+weakness|paralysis|stroke|thunderclap\s+headache|worst\s+headache\s+of\s+my\s+life|tonic\s+clonic\s+seizure|asymmetric\s+pupil|unresponsive|ataxia.*inability\s+to\s+move|sudden\s+loss\s+of\s+vision.*facial\s+numbness)\b",
        "CRITICAL",
        "Cerebrovascular / Neurological Emergency",
        "Acute stroke (FAST criteria), acute intracranial hemorrhage, or active seizure. Immediate neuro triage."
    ),
    # Respiratory & Airway (Stridor, Foreign Body, Silent Chest, Severe Hypoxemia)
    (
        r"\b(cannot\s+breathe|gasping|severe\s+shortness\s+of\s+breath|stridor|cyanosis|lips\s+turning\s+blue|silent\s+chest|respiratory\s+distress|choking\s+on\s+foreign\s+body|respiratory\s+arrest|intercostal\s+retractions|tracheal\s+tug)\b",
        "CRITICAL",
        "Respiratory Emergency",
        "Critical airway compromise or impending respiratory failure. Immediate oxygen & airway support."
    ),
    # Hemorrhage, Shock, Anaphylaxis & Ayurvedic Arishta Lakshana (Severe Dehydration / Dhatukshaya)
    (
        r"\b(vomiting.*(?:blood|clots)|coughing.*blood|hemoptysis|hematemesis|black\s+tarry|profuse\s+watery\s+diarrhea.*(?:cold|faint|sunken)|delirium.*rigid\s+neck|arishta\s+lakshana|clammy\s+extremities.*thready\s+pulse|anaphylaxis|septic\s+shock|postpartum.*heavy.*hemorrhage|penetrating\s+abdominal\s+trauma)\b",
        "HIGH",
        "Severe Hemorrhage / Shock / Arishta Lakshana",
        "Severe active internal hemorrhage, anaphylaxis, severe shock, or Ayurvedic Arishta Lakshana. Immediate ICU / Emergency triage."
    )
]

def scan_text_for_red_flags(text: str) -> Optional[RedFlagAlert]:
    """Fast regex-based triage for high-risk red-flag clinical presentations."""
    text_lower = text.lower()
    for pattern, severity, category, message in RED_FLAG_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return RedFlagAlert(
                is_red_flag=True,
                severity=severity,
                category=category,
                triggers=[match.group(0)],
                emergency_message=message
            )
    return None

def heuristic_socrates_extraction(text: str, current_state: SocratesState) -> SocratesState:
    """Rule-based extractor for SOCRATES slots from patient utterances."""
    text_lower = text.lower()
    updated = current_state.model_copy()

    # Site
    if not updated.site:
        site_match = re.search(r"\b(chest|head|stomach|abdomen|knee|back|lower back|shoulder|throat|neck|leg|arm|foot|eye|ear|belly)\b", text_lower)
        if site_match:
            updated.site = site_match.group(1).capitalize()

    # Onset
    if not updated.onset:
        onset_match = re.search(r"\b(\d+\s*(?:days?|weeks?|months?|hours?)|yesterday|today|since morning|sudden|gradual)\b", text_lower)
        if onset_match:
            updated.onset = onset_match.group(1)

    # Character
    if not updated.character:
        char_match = re.search(r"\b(sharp|dull|burning|aching|throbbing|pulsating|cramping|tight|squeezing|colicky)\b", text_lower)
        if char_match:
            updated.character = char_match.group(1).capitalize()

    # Radiation
    if not updated.radiation:
        rad_match = re.search(r"\b(radiat(?:es|ing)|spread(?:s|ing)|goes to|moves to)\s+([\w\s]+)", text_lower)
        if rad_match:
            updated.radiation = rad_match.group(2).strip().capitalize()
        elif any(k in text_lower for k in ["no spread", "nowhere else", "stays in one place", "localized"]):
            updated.radiation = "Localized (No radiation)"

    # Severity
    if not updated.severity:
        sev_match = re.search(r"\b(?:severity|rate|scale)?\s*(\d{1,2})\s*(?:out of 10|/10|on 10)\b", text_lower)
        if sev_match:
            updated.severity = f"{sev_match.group(1)}/10"
        elif "severe" in text_lower or "unbearable" in text_lower:
            updated.severity = "Severe (8/10)"
        elif "moderate" in text_lower:
            updated.severity = "Moderate (5/10)"
        elif "mild" in text_lower:
            updated.severity = "Mild (3/10)"

    # Associations
    assoc_keywords = ["nausea", "vomiting", "fever", "sweating", "dizziness", "cough", "breathlessness", "headache"]
    for kw in assoc_keywords:
        if kw in text_lower and kw not in updated.associations:
            updated.associations.append(kw)

    # Recompute covered and missing slots
    all_slots = ["site", "onset", "character", "radiation", "associations", "time_course", "exacerbating_relieving", "severity"]
    covered = []
    if updated.site: covered.append("site")
    if updated.onset: covered.append("onset")
    if updated.character: covered.append("character")
    if updated.radiation: covered.append("radiation")
    if updated.associations: covered.append("associations")
    if updated.time_course: covered.append("time_course")
    if updated.exacerbating_relieving: covered.append("exacerbating_relieving")
    if updated.severity: covered.append("severity")

    updated.covered_slots = covered
    updated.missing_slots = [s for s in all_slots if s not in covered]
    return updated

def generate_heuristic_turn(
    patient_context: PatientContext,
    conversation_history: List[Dict[str, Any]],
    current_state: SocratesState,
    max_turns: int = 10
) -> DialogueTurnResult:
    """
    Zero-latency heuristic fallback when offline or LLM is unreachable.
    """
    # Combine all utterances to update state
    full_text = " ".join([m.get("content", "") for m in conversation_history if m.get("role") in ["patient", "user"]])
    if patient_context.chief_complaint:
        full_text += " " + patient_context.chief_complaint
    if patient_context.symptoms:
        full_text += " " + " ".join(patient_context.symptoms)

    updated_socrates = heuristic_socrates_extraction(full_text, current_state)
    prim_imp = f"Clinical Presentation: {patient_context.chief_complaint or 'General Intake'}"
    prov_diffs = []

    # Safety check: red flag scan
    red_flag = scan_text_for_red_flags(full_text)
    if red_flag:
        return DialogueTurnResult(
            should_stop=True,
            next_question=None,
            touch_options=[],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=updated_socrates.missing_slots,
            red_flag_alert=red_flag,
            closing_message="🚨 EMERGENCY ALERT: Critical clinical red flag detected. Please seek immediate emergency medical care.",
            clinical_summary=f"### 🚨 EMERGENCY CLINICAL ESCALATION\n- Category: {red_flag.category}\n- Severity: {red_flag.severity}\n- Clinical Guidance: {red_flag.emergency_message}",
            reasoning=f"Emergency red flag triggered under offline heuristic fallback: {red_flag.category}"
        )

    # Stop conditions: 6 or more slots covered, or reached max turns
    turn_count = len([m for m in conversation_history if m.get("role") in ["patient", "user"]])
    if (len(updated_socrates.covered_slots) >= 6 and turn_count >= 2) or turn_count >= max_turns:
        complaint = patient_context.chief_complaint or "Reported symptoms"
        meds_str = ", ".join(patient_context.current_medications) if patient_context.current_medications else "None reported"
        alg_str = ", ".join(patient_context.allergies) if patient_context.allergies else "No known drug allergies (NKDA)"
        pmh_str = ", ".join(patient_context.past_medical_history) if patient_context.past_medical_history else "No chronic illnesses noted"
        assoc_str = ", ".join(updated_socrates.associations) if updated_socrates.associations else "None reported"

        summary = (
            f"### 📋 Clinical History Summary for Attending Physician\n"
            f"1. **Chief Complaint (CC):**\n"
            f"   * {complaint} (Onset: {updated_socrates.onset or 'Reported duration'})\n"
            f"2. **History of Present Illness (HPI):**\n"
            f"   * Location: {updated_socrates.site or 'General / Unspecified'}\n"
            f"   * Character: {updated_socrates.character or 'Unspecified'}\n"
            f"   * Radiation: {updated_socrates.radiation or 'No radiation reported'}\n"
            f"   * Severity: {updated_socrates.severity or 'Unspecified'}\n"
            f"   * Timing & Course: {updated_socrates.time_course or 'Reported progression'}\n"
            f"   * Triggers & Relievers: {updated_socrates.exacerbating_relieving or 'None identified'}\n"
            f"   * Associated Symptoms: {assoc_str}\n"
            f"3. **Past Medical & Surgical History:**\n"
            f"   * {pmh_str}\n"
            f"4. **Drug History & Known Allergies:**\n"
            f"   * Current Medications: {meds_str}\n"
            f"   * Known Allergies: {alg_str}\n"
            f"5. **Family & Personal / Social History:**\n"
            f"   * Standard intake / non-contributory\n"
            f"6. **Review of Systems (ROS):**\n"
            f"   * Pertinent positive/negative findings as documented above\n"
            f"7. **Prior Investigations & Documents (RAG):**\n"
            f"   * Cross-referenced with patient records\n"
            f"8. **Triage Assessment & Red-Flag Screening:**\n"
            f"   * Triage Urgency: Routine / OPD Evaluation\n"
            f"   * Clinical Impression: Patient presenting with {complaint.lower()} for physician assessment."
        )
        return DialogueTurnResult(
            should_stop=True,
            next_question=None,
            touch_options=[],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=updated_socrates.missing_slots,
            clinical_summary=summary,
            closing_message="Thank you. We have collected the necessary details about your symptoms for your doctor.",
            reasoning="Sufficient clinical slots gathered under offline heuristic mode.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )

    # Choose next missing slot in priority order
    missing = updated_socrates.missing_slots
    if "site" in missing:
        return DialogueTurnResult(
            should_stop=False,
            next_question="Where exactly are you feeling the discomfort or pain?",
            touch_options=[
                TouchOption(id="opt_chest", label="Chest", value="I feel it in my chest", slot_tag="site"),
                TouchOption(id="opt_stomach", label="Stomach / Abdomen", value="I feel it in my stomach", slot_tag="site"),
                TouchOption(id="opt_head", label="Head", value="I feel it in my head", slot_tag="site"),
                TouchOption(id="opt_other_site", label="Other Location", value="It is located in another area", slot_tag="site")
            ],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=missing,
            reasoning="Site slot missing; inquiring anatomical location.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )
    elif "onset" in missing:
        return DialogueTurnResult(
            should_stop=False,
            next_question="When did this symptom start, and did it come on suddenly or gradually?",
            touch_options=[
                TouchOption(id="opt_today", label="Earlier today (Sudden)", value="It started suddenly earlier today", slot_tag="onset"),
                TouchOption(id="opt_few_days", label="A few days ago (Gradual)", value="It started gradually a few days ago", slot_tag="onset"),
                TouchOption(id="opt_weeks", label="Over a week ago", value="I have had this for more than a week", slot_tag="onset"),
                TouchOption(id="opt_chronic", label="Months / Long term", value="This has been ongoing for months", slot_tag="onset")
            ],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=missing,
            reasoning="Onset slot missing; inquiring start and progression.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )
    elif "character" in missing:
        return DialogueTurnResult(
            should_stop=False,
            next_question="How would you describe the feeling or pain?",
            touch_options=[
                TouchOption(id="opt_sharp", label="Sharp / Stabbing", value="It is a sharp, stabbing feeling", slot_tag="character"),
                TouchOption(id="opt_dull", label="Dull / Aching", value="It is a dull, constant ache", slot_tag="character"),
                TouchOption(id="opt_burning", label="Burning", value="It feels like a burning sensation", slot_tag="character"),
                TouchOption(id="opt_throbbing", label="Throbbing / Pulsing", value="It is a throbbing, pulsating sensation", slot_tag="character")
            ],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=missing,
            reasoning="Character slot missing; inquiring symptom sensation.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )
    elif "severity" in missing:
        return DialogueTurnResult(
            should_stop=False,
            next_question="On a scale from 1 to 10, how severe is your discomfort right now?",
            touch_options=[
                TouchOption(id="opt_mild", label="1-3 (Mild)", value="It is mild, around 2 or 3 out of 10", slot_tag="severity"),
                TouchOption(id="opt_moderate", label="4-6 (Moderate)", value="It is moderate, around 5 out of 10", slot_tag="severity"),
                TouchOption(id="opt_severe", label="7-9 (Severe)", value="It is severe, around 8 out of 10", slot_tag="severity"),
                TouchOption(id="opt_worst", label="10 (Unbearable)", value="It is unbearable, 10 out of 10", slot_tag="severity")
            ],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=missing,
            reasoning="Severity slot missing; inquiring intensity score.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )
    else:
        # Ask about exacerbating/relieving factors or associated symptoms
        return DialogueTurnResult(
            should_stop=False,
            next_question="Does anything specific make the symptom better or worse (like movement, food, or rest)?",
            touch_options=[
                TouchOption(id="opt_worse_movement", label="Worse with movement", value="It gets worse when I move or exercise", slot_tag="exacerbating_relieving"),
                TouchOption(id="opt_better_rest", label="Better with rest", value="Resting makes it feel better", slot_tag="exacerbating_relieving"),
                TouchOption(id="opt_worse_food", label="Worse with food / meals", value="Eating makes it worse", slot_tag="exacerbating_relieving"),
                TouchOption(id="opt_no_factor", label="No clear trigger", value="Nothing specific seems to change it", slot_tag="exacerbating_relieving")
            ],
            socrates_state=updated_socrates,
            covered_slots=updated_socrates.covered_slots,
            missing_slots=missing,
            reasoning="Inquiring about aggravating and relieving factors to complete SOCRATES profile.",
            primary_impression=prim_imp,
            provisional_differentials=prov_diffs
        )
