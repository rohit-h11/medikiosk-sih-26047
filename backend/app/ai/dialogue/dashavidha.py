"""
MediKiosk — Dashavidha Pariksha Static Questionnaires & Scoping Engine
Digitized from classical Charaka Samhita criteria (Vimana Sthana Ch. 8).
Note: No single AYUSH-validated standalone MCQ scale currently exists for Satmya,
Sattva, and Vyayama Shakti (unlike Prakriti which uses the CCRAS-PAS scale).
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Explicit Scoping Distinction for Clinical Understanding
EXCLUDED_PHYSICAL_EXAM_PARAMETERS = [
    {
        "parameter": "Sara",
        "english_name": "Tissue Quality / Excellence",
        "reason": "Requires direct physical palpation, dermatological inspection, and deep structural exam by physician. Cannot be reliably self-reported on a kiosk."
    },
    {
        "parameter": "Samhanana",
        "english_name": "Structural Compactness / Build",
        "reason": "Requires musculoskeletal inspection and physical assessment of bone-joint-muscle density by physician."
    },
    {
        "parameter": "Pramana",
        "english_name": "Anthropometry / Measurements",
        "reason": "Requires precise physical dimensional measurement (Anguli Pramana / height, weight, circumferences) by clinical staff."
    }
]

# -------------------------------------------------------------
# 1. Satmya Pariksha (Adaptability / Suitability)
# Classical Categories: Rasa Satmya, Desha Satmya, Ritu Satmya, Oka Satmya
# -------------------------------------------------------------

SATMYA_QUESTIONNAIRE: List[Dict[str, Any]] = [
    {
        "id": "satmya_01_tastes",
        "domain": "Rasa Satmya (Taste Adaptability)",
        "question": "How easily do you tolerate diverse food tastes (sweet, sour, salty, spicy, bitter, astringent)?",
        "options": [
            {"id": "opt_pravara", "label": "Easily tolerate all 6 tastes without any digestive or systemic disturbance (Sarva-Rasa Satmya)", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Tolerate most tastes, but sensitive to extreme spicy, sour, or heavy sweets (Madhyama)", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Narrow tolerance; very easily disturbed by spicy, sour, or unfamiliar foods (Avara)", "score": 1, "tier": "Avara"}
        ]
    },
    {
        "id": "satmya_02_climate",
        "domain": "Desha Satmya (Geographic/Climate Adaptability)",
        "question": "How do you adapt when traveling to a region with very different climate (hot/cold, dry/humid)?",
        "options": [
            {"id": "opt_pravara", "label": "Adapt smoothly with almost no health issues or discomfort", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Take 2-3 days to adjust with mild fatigue or mild digestive changes", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Get sick easily (colds, allergies, fever, or severe stomach upset) with climate shifts", "score": 1, "tier": "Avara"}
        ]
    },
    {
        "id": "satmya_03_seasonal",
        "domain": "Ritu Satmya (Seasonal Transition)",
        "question": "How do you experience seasonal changes (e.g. onset of winter, summer, or monsoons)?",
        "options": [
            {"id": "opt_pravara", "label": "Remain healthy and energetic across all seasons", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Occasional mild seasonal allergies or slight lethargy", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Frequently suffer acute flare-ups (colds, joint pain, skin rash, or digestive upsets) during transitions", "score": 1, "tier": "Avara"}
        ]
    }
]

# -------------------------------------------------------------
# 2. Sattva Pariksha (Mental / Psychic Strength)
# Classical Descriptors: Pain tolerance, grief/fear response, reassurance need
# -------------------------------------------------------------

SATTVA_QUESTIONNAIRE: List[Dict[str, Any]] = [
    {
        "id": "sattva_01_pain",
        "domain": "Pain & Distress Tolerance (Sattva Sara)",
        "question": "How do you cope with physical pain, injury, or bodily discomfort?",
        "options": [
            {"id": "opt_pravara", "label": "Endure pain calmly without panic or exaggeration; remain composed (Pravara Sattva)", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Manage pain reasonably well with support and encouragement from others (Madhyama Sattva)", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Easily overwhelmed by even mild pain; prone to extreme anxiety, fainting, or despair (Avara Sattva)", "score": 1, "tier": "Avara"}
        ]
    },
    {
        "id": "sattva_02_stress",
        "domain": "Emotional Shock & Crisis Response",
        "question": "How do you react when facing sudden grief, frightening situations, or severe life stress?",
        "options": [
            {"id": "opt_pravara", "label": "Maintain clear thinking, decisiveness, and steady emotional balance", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Experience temporary anxiety but regain balance after talking to family/doctor", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Paralyzed by fear or sorrow; inconsolable even with repeated reassurance", "score": 1, "tier": "Avara"}
        ]
    },
    {
        "id": "sattva_03_perseverance",
        "domain": "Mental Resilience & Enthusiasm",
        "question": "When pursuing a difficult health routine or treatment regimen, what is your mindset?",
        "options": [
            {"id": "opt_pravara", "label": "Highly disciplined, optimistic, patient, and adhere strictly to advice", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Consistent as long as I have periodic check-ins and encouragement", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Easily discouraged; frequently give up at the first hurdle or symptom flare", "score": 1, "tier": "Avara"}
        ]
    }
]

# -------------------------------------------------------------
# 3. Vyayama Shakti (Physical Exercise & Exertion Capacity)
# -------------------------------------------------------------

VYAYAMA_QUESTIONNAIRE: List[Dict[str, Any]] = [
    {
        "id": "vyayama_01_capacity",
        "domain": "Physical Exertion Threshold",
        "question": "What level of physical exertion can you comfortably sustain without severe breathlessness?",
        "options": [
            {"id": "opt_pravara", "label": "Heavy physical labor, running, or strenuous gym workouts with minimal fatigue (Pravara)", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Moderate activity like brisk walking (30-45 mins) or climbing 2-3 flights of stairs (Madhyama)", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Become breathless or exhausted with minimal effort like walking 100 meters or climbing 1 flight (Avara)", "score": 1, "tier": "Avara"}
        ]
    },
    {
        "id": "vyayama_02_recovery",
        "domain": "Post-Exertion Recovery",
        "question": "How quickly do your breathing and energy recover after physical exertion?",
        "options": [
            {"id": "opt_pravara", "label": "Within 5-10 minutes, feeling refreshed (Pravara)", "score": 3, "tier": "Pravara"},
            {"id": "opt_madhyama", "label": "Within 20-30 minutes of rest (Madhyama)", "score": 2, "tier": "Madhyama"},
            {"id": "opt_avara", "label": "Takes several hours or whole day to recover from simple exertion (Avara)", "score": 1, "tier": "Avara"}
        ]
    }
]

# -------------------------------------------------------------
# Scoring Functions
# -------------------------------------------------------------

def score_satmya_assessment(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Satmya score and classify into Pravara / Madhyama / Avara."""
    total_score = sum(a.get("score", 2) for a in answers)
    max_possible = len(SATMYA_QUESTIONNAIRE) * 3
    pct = (total_score / max_possible) * 100 if max_possible > 0 else 66.6

    if pct >= 80.0:
        tier = "Pravara Satmya (Superior Adaptability - Sarva-Rasa Satmya)"
    elif pct >= 50.0:
        tier = "Madhyama Satmya (Moderate Adaptability)"
    else:
        tier = "Avara Satmya (Poor Adaptability - Narrow Tolerance)"

    return {
        "score_percentage": round(pct, 1),
        "classification": tier,
        "citation": "Digitized from classical Charaka Samhita criteria (Vimana Sthana Ch. 8)"
    }

def score_sattva_assessment(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Sattva score and classify psychic strength."""
    total_score = sum(a.get("score", 2) for a in answers)
    max_possible = len(SATTVA_QUESTIONNAIRE) * 3
    pct = (total_score / max_possible) * 100 if max_possible > 0 else 66.6

    if pct >= 80.0:
        tier = "Pravara Sattva (Strong-Minded / High Pain & Distress Tolerance)"
    elif pct >= 50.0:
        tier = "Madhyama Sattva (Moderate Mental Resilience / Needs Reassurance)"
    else:
        tier = "Avara Sattva (Low Mental Endurance / Easily Overwhelmed)"

    return {
        "score_percentage": round(pct, 1),
        "classification": tier,
        "citation": "Digitized from classical Charaka Samhita criteria (Vimana Sthana Ch. 8)"
    }

def score_vyayama_assessment(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Vyayama Shakti score and classify physical capacity."""
    total_score = sum(a.get("score", 2) for a in answers)
    max_possible = len(VYAYAMA_QUESTIONNAIRE) * 3
    pct = (total_score / max_possible) * 100 if max_possible > 0 else 66.6

    if pct >= 80.0:
        tier = "Pravara Vyayama Shakti (High Physical Capacity & Endurance)"
    elif pct >= 50.0:
        tier = "Madhyama Vyayama Shakti (Moderate Physical Capacity)"
    else:
        tier = "Avara Vyayama Shakti (Low Stamina / Rapid Exertional Fatigue)"

    return {
        "score_percentage": round(pct, 1),
        "classification": tier,
        "citation": "Digitized from classical Charaka Samhita criteria (Vimana Sthana Ch. 8)"
    }

def classify_vaya_lifestage(age: Optional[int]) -> str:
    """Classify age into classical Ayurvedic life stages."""
    if age is None or age < 0:
        return "Vaya: Not specified"
    if age <= 16:
        return f"{age} yrs (Bala Vaya / Childhood - Kapha dominant phase)"
    elif age <= 60:
        return f"{age} yrs (Madhyama Vaya / Adult - Pitta dominant phase)"
    else:
        return f"{age} yrs (Vriddha Vaya / Elderly - Vata dominant phase)"
