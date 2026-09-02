"""
MediKiosk — Deterministic Emergency Red-Flag Triage Engine
Sub-50ms rule-based evaluation detecting acute life-threatening medical emergencies.
Integrates standard Allopathic red-flag criteria and classical Ayurvedic
Arishta Lakshana / Atyayika Vyadhi (emergency referral signals).
"""

import re
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from app.schemas.dialogue import RedFlagAlert, RedFlagSeverity

# Rule definitions: (category, severity, regex_patterns, emergency_message, destination)
RED_FLAG_RULES = [
    # 1. Cardiovascular / Acute Coronary Syndrome (Classical correlate: Acute Hridroga with collapse)
    (
        "Cardiovascular Emergency (ACS / Acute Hridroga with Collapse)",
        RedFlagSeverity.CRITICAL,
        [
            r"\b(crushing|heavy|squeezing|tight|pressure|severe)\b.*\b(chest pain|chest tightness|chest pressure)\b",
            r"\bchest pain\b.*\b(left arm|jaw|neck|back|shoulder|sweat|sweating|perspiration|diaphoresis|dizzy|faint|breathless|syncope)\b",
            r"\b(left arm|jaw)\b.*\b(chest pain|radiation|radiating)\b",
            r"\b(heart attack|angina|cardiac arrest|collapsed)\b",
            r"\b(hridroga|hridshula)\b.*\b(giddiness|collapse|fainting|sweating)\b"
        ],
        "CRITICAL: Symptoms indicate potential acute coronary compromise, myocardial ischemia, or acute Hridroga. Immediate casualty escalation required.",
        "Emergency Department / Red Triage Zone (Immediate ECG & Cardiac Monitor)"
    ),
    # 2. Cerebrovascular / Acute Stroke (FAST criteria / Pakshaghata)
    (
        "Cerebrovascular Emergency (Acute Stroke / FAST / Pakshaghata)",
        RedFlagSeverity.CRITICAL,
        [
            r"\b(facial droop|drooping face|uneven smile|crooked face|face numb)\b",
            r"\b(weakness|numbness|paralysis)\b.*\b(one side|left side|right side|arm and leg|cannot lift arm)\b",
            r"\b(slurred speech|cannot speak|lost speech|incoherent speech|difficulty speaking)\b",
            r"\b(worst headache of my life|thunderclap|sudden explosive headache)\b",
            r"\b(sudden vision loss|double vision|sudden blindness)\b",
            r"\b(pakshaghata|ardita)\b.*\b(sudden onset|slurred speech)\b"
        ],
        "CRITICAL: Acute neurological deficit detected (FAST criteria positive). Time-critical stroke evaluation protocol required.",
        "Emergency Stroke Unit / Resuscitation Bay"
    ),
    # 3. Severe Respiratory Compromise (Classical correlate: Pranahara Shwasa)
    (
        "Severe Respiratory Failure (Pranahara Shwasa / Acute Asphyxia)",
        RedFlagSeverity.CRITICAL,
        [
            r"\b(cannot breathe|gasping for air|suffocating|severe breathlessness|struggling to breathe)\b",
            r"\b(blue lips|blue fingers|cyanosis|turning blue)\b",
            r"\b(choking|foreign body in throat|throat closed|stridor)\b",
            r"\b(cannot speak full sentences|speaking only one word at a time)\b",
            r"\b(tamaka shwasa|pranahara shwasa)\b.*\b(cyanosis|severe gasping|collapsed)\b"
        ],
        "CRITICAL: Severe acute respiratory compromise or airway obstruction (Pranahara Shwasa). Immediate high-flow oxygen and airway evaluation required.",
        "Emergency Triage / Oxygenation & Resuscitation Area"
    ),
    # 4. Massive Hemorrhage & Acute Abdomen (Classical correlate: Raktapitta / Udara Shula)
    (
        "Massive Hemorrhage / Acute Surgical Abdomen (Raktapitta / Shula)",
        RedFlagSeverity.HIGH,
        [
            r"\b(vomiting blood|vomited blood|hematemesis|coffee ground vomit)\b",
            r"\b(black tarry stool|black stool|melena|bleeding heavily from rectum)\b",
            r"\b(coughing up blood|coughing blood|hemoptysis)\b",
            r"\b(board-like abdomen|rigid stomach|agonizing stomach pain|perforation)\b"
        ],
        "HIGH PRIORITY: Signs of acute gastrointestinal hemorrhage, active internal bleeding, or acute surgical abdomen.",
        "Surgical Emergency / Acute Casualty Care"
    ),
    # 5. Anaphylaxis / Acute Airway Angioedema
    (
        "Anaphylaxis / Severe Allergic Reaction",
        RedFlagSeverity.CRITICAL,
        [
            r"\b(swollen tongue|throat swelling|swollen lips and breathing problem)\b",
            r"\b(severe hives|allergic reaction)\b.*\b(cannot breathe|wheezing|dizzy|throat tight)\b"
        ],
        "CRITICAL: Acute systemic anaphylaxis with impending airway compromise. Immediate Intramuscular Epinephrine required.",
        "Emergency Resuscitation (Anaphylaxis Protocol)"
    ),
    # 6. Sepsis & Central Nervous System Infection (Classical correlate: Sannipata Jwara with Delirium)
    (
        "Severe Sepsis / Meningismus (Sannipata Jwara with Delirium)",
        RedFlagSeverity.HIGH,
        [
            r"\b(high fever|chills)\b.*\b(stiff neck|cannot bend neck|neck stiffness|severe confusion|delirium)\b",
            r"\b(unconscious|unresponsive|passing out|fainted and not waking)\b",
            r"\b(sannipata jwara|sannipata)\b.*\b(delirium|confusion|altered sensorium)\b"
        ],
        "HIGH PRIORITY: Severe systemic sepsis or acute central nervous system infection indicators (Sannipata Jwara with delirium).",
        "Acute Medical Triage (Sepsis / Neurological Isolation)"
    ),
    # 7. Severe Dehydration / Hypovolemic Collapse (Classical correlate: Severe Atisara with Collapse)
    (
        "Severe Dehydration & Hypovolemic Shock (Severe Atisara)",
        RedFlagSeverity.HIGH,
        [
            r"\b(profuse diarrhea|watery motions|severe loose motions)\b.*\b(collapsed|cannot stand|sunken eyes|fainting|no urine)\b",
            r"\b(atisara|visuchika)\b.*\b(dehydration|collapse|syncope)\b"
        ],
        "HIGH PRIORITY: Signs of severe hypovolemic dehydration or metabolic collapse (Severe Atisara / Visuchika). Immediate IV fluid resuscitation required.",
        "Emergency Casualty / IV Fluid Resuscitation Bay"
    )
]

def scan_text_for_red_flags(text: str) -> Optional[RedFlagAlert]:
    """
    Deterministically scan a patient text utterance against clinical red-flag rules.
    Runs in < 5 milliseconds.
    """
    if not text or not text.strip():
        return None
    
    clean_text = text.lower().strip()
    
    for category, severity, patterns, emergency_message, destination in RED_FLAG_RULES:
        for pat in patterns:
            match = re.search(pat, clean_text, re.IGNORECASE)
            if match:
                matched_snippet = match.group(0)
                return RedFlagAlert(
                    is_red_flag=True,
                    severity=severity,
                    category=category,
                    triggers=[matched_snippet],
                    emergency_message=emergency_message,
                    triage_destination=destination,
                    detected_at=datetime.now(timezone.utc).isoformat()
                )
    return None

def evaluate_patient_safety(
    current_utterance: str,
    cumulative_transcript: List[str],
    patient_history_chunks: Optional[List[str]] = None
) -> Optional[RedFlagAlert]:
    """
    Scan latest patient statement, recent conversational context, and prior history chunks
    (e.g., chest pain in a patient with a prior MI record raises urgency).
    """
    # 1. Immediate scan of current utterance
    latest_alert = scan_text_for_red_flags(current_utterance)
    if latest_alert:
        return latest_alert
    
    # 2. Compound scan across last 2 turns combined
    if cumulative_transcript:
        recent_combined = " ".join(cumulative_transcript[-2:]) + " " + current_utterance
        compound_alert = scan_text_for_red_flags(recent_combined)
        if compound_alert:
            return compound_alert

    # 3. Urgency Escalation: Current symptom + Relevant Prior History Chunk
    if patient_history_chunks and current_utterance:
        history_text = " ".join(patient_history_chunks).lower()
        curr_lower = current_utterance.lower()
        
        # Prior heart attack/MI/CABG + current chest discomfort -> Emergency
        if any(k in curr_lower for k in ["chest pain", "chest discomfort", "chest pressure", "heavy chest"]):
            if any(h in history_text for h in ["myocardial infarction", "heart attack", "coronary", "cabg", "stent", "angioplasty", "ischemic"]):
                return RedFlagAlert(
                    is_red_flag=True,
                    severity=RedFlagSeverity.CRITICAL,
                    category="Cardiovascular Emergency (Chest Pain with Documented Prior MI)",
                    triggers=["Current chest symptom + Prior documented Cardiac/MI history"],
                    emergency_message="ELEVATED URGENCY: Patient with documented prior cardiac history presenting with acute chest symptoms. Immediate escalation protocol required.",
                    triage_destination="Emergency Department / Red Triage Zone (Stat ECG)",
                    detected_at=datetime.now(timezone.utc).isoformat()
                )

        # Prior stroke/TIA + current weakness/headache -> Emergency
        if any(k in curr_lower for k in ["weakness", "headache", "dizziness", "numbness", "vision"]):
            if any(h in history_text for h in ["stroke", "cva", "infarct", "tia", "aneurysm", "hemorrhage"]):
                return RedFlagAlert(
                    is_red_flag=True,
                    severity=RedFlagSeverity.CRITICAL,
                    category="Cerebrovascular Emergency (Neurological Symptom with Documented Prior Stroke)",
                    triggers=["Current neuro symptom + Prior documented Stroke/CVA history"],
                    emergency_message="ELEVATED URGENCY: Patient with prior cerebrovascular history presenting with new neurological complaints. Immediate neurological evaluation required.",
                    triage_destination="Emergency Stroke Unit / Resuscitation Bay",
                    detected_at=datetime.now(timezone.utc).isoformat()
                )
            
    return None
