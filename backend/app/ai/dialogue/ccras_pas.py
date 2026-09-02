import json
import os
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.dialogue import (
    CCRASPrakritiScores,
    AyurvedicAssessment,
    TouchOption
)

# Load CCRAS Battery
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BATTERY_PATH = os.path.join(_CURRENT_DIR, "ccras_pas_battery.json")

def load_ccras_battery() -> Dict[str, Any]:
    """Load the full CCRAS Prakriti Assessment Scale question battery from JSON."""
    with open(_BATTERY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

_BATTERY_DATA = load_ccras_battery()

def get_all_battery_questions() -> List[Dict[str, Any]]:
    """Flatten and return all questions across the 4 CCRAS domains."""
    all_questions = []
    for domain in _BATTERY_DATA.get("domains", []):
        d_id = domain.get("domain_id")
        d_name = domain.get("domain_name")
        for q in domain.get("questions", []):
            item = dict(q)
            item["domain_id"] = d_id
            item["domain_name"] = d_name
            all_questions.append(item)
    return all_questions

def get_representative_ccras_questions(max_count: int = 4) -> List[Dict[str, Any]]:
    """
    Select high-yield representative questions (1 from each domain)
    to fit within rapid 6-8 turn OPD interview limits.
    """
    selected = []
    for domain in _BATTERY_DATA.get("domains", []):
        d_id = domain.get("domain_id")
        d_name = domain.get("domain_name")
        questions = domain.get("questions", [])
        if questions:
            # Pick representative question from domain
            target_index = 0
            if d_id == "physiological":
                # Pick Appetite/Agni as highest yield
                target_index = 0
            elif d_id == "physical":
                # Pick Body Frame / Build
                target_index = 0
            elif d_id == "psychological":
                # Pick Temperament
                target_index = 1
            elif d_id == "behavioral":
                # Pick Movement pace
                target_index = 0
            
            q = dict(questions[min(target_index, len(questions) - 1)])
            q["domain_id"] = d_id
            q["domain_name"] = d_name
            selected.append(q)
            if len(selected) >= max_count:
                break
    return selected

def compute_prakriti_scores(answers: List[Dict[str, Any]]) -> CCRASPrakritiScores:
    """
    Calculate Vata, Pitta, and Kapha constitution percentages based on patient selections.
    Each answer dict: { "domain_id": str, "dosha": "vata"|"pitta"|"kapha", "weight": float }
    """
    scores = {"vata": 0.0, "pitta": 0.0, "kapha": 0.0}
    domain_scores: Dict[str, Dict[str, float]] = {
        "physical": {"vata": 0.0, "pitta": 0.0, "kapha": 0.0},
        "physiological": {"vata": 0.0, "pitta": 0.0, "kapha": 0.0},
        "psychological": {"vata": 0.0, "pitta": 0.0, "kapha": 0.0},
        "behavioral": {"vata": 0.0, "pitta": 0.0, "kapha": 0.0}
    }
    
    total_answers = len(answers)
    if total_answers == 0:
        return CCRASPrakritiScores(
            vata_percentage=33.3,
            pitta_percentage=33.3,
            kapha_percentage=33.4,
            dominant_prakriti="Tridoshaja (Balanced)",
            phenotype_type="Tridoshaja",
            total_answers=0,
            domain_scores=domain_scores
        )
    
    for ans in answers:
        dosha = ans.get("dosha", "").lower()
        weight = float(ans.get("weight", 1.0))
        domain = ans.get("domain_id", "general")
        
        if dosha in scores:
            scores[dosha] += weight
            if domain in domain_scores and dosha in domain_scores[domain]:
                domain_scores[domain][dosha] += weight

    total_weight = sum(scores.values()) or 1.0
    v_pct = round((scores["vata"] / total_weight) * 100, 1)
    p_pct = round((scores["pitta"] / total_weight) * 100, 1)
    k_pct = round(100.0 - (v_pct + p_pct), 1)

    # Phenotype & Dominance Classification
    ranked = sorted([("Vata", v_pct), ("Pitta", p_pct), ("Kapha", k_pct)], key=lambda x: x[1], reverse=True)
    top_name, top_val = ranked[0]
    second_name, second_val = ranked[1]
    third_name, third_val = ranked[2]

    # If all three doshas are nearly balanced (within 8% of each other) -> Tridoshaja
    if (top_val - third_val) <= 8.0:
        dominant = "Tridoshaja (Balanced)"
        phenotype = "Tridoshaja"
    # If single dosha has a clear dominant lead (>= 15% lead over second) -> Ekadoshaja
    elif (top_val - second_val) >= 15.0:
        dominant = f"{top_name} Dominant"
        phenotype = "Ekadoshaja"
    # Otherwise dual constitution -> Dvandvaja
    else:
        dominant = f"{top_name}-{second_name}"
        phenotype = "Dvandvaja"

    return CCRASPrakritiScores(
        vata_percentage=v_pct,
        pitta_percentage=p_pct,
        kapha_percentage=k_pct,
        dominant_prakriti=dominant,
        phenotype_type=phenotype,
        total_answers=total_answers,
        domain_scores=domain_scores
    )

def convert_ccras_question_to_touch_options(q_dict: Dict[str, Any]) -> List[TouchOption]:
    """Convert question options into UI TouchOption models."""
    options = []
    for opt in q_dict.get("options", []):
        dosha = opt.get("dosha", "vata")
        options.append(
            TouchOption(
                id=opt.get("id"),
                label=opt.get("label"),
                value=opt.get("label"),
                slot_tag=f"prakriti_{dosha}",
                dosha_bias={dosha: opt.get("weight", 1.0)}
            )
        )
    return options

def classify_agni_koshtha_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract Agni (digestive fire) and Koshtha (bowel tendency) from natural clinical text.
    """
    text_lower = text.lower()
    agni = None
    koshtha = None
    
    # Agni rules
    if any(k in text_lower for k in ["irregular hunger", "sometimes hungry", "gas after eating", "variable", "vishama"]):
        agni = "Vishama Agni (Vata-imbalanced / Variable digestion)"
    elif any(k in text_lower for k in ["burning", "acid", "sharp hunger", "intense hunger", "cannot tolerate fast", "tikshna", "sour burp"]):
        agni = "Tikshna Agni (Pitta-dominant / Hyperactive digestion)"
    elif any(k in text_lower for k in ["heavy stomach", "slow digestion", "rarely hungry", "sluggish", "manda", "mucus"]):
        agni = "Manda Agni (Kapha-dominant / Hypoactive digestion)"
    elif any(k in text_lower for k in ["balanced", "normal hunger", "digests on time", "sama"]):
        agni = "Sama Agni (Balanced / Optimal digestion)"

    # Koshtha rules
    if any(k in text_lower for k in ["constipat", "hard stool", "dry stool", "krura", "straining", "every 2-3 days"]):
        koshtha = "Krura Koshtha (Vata / Hard & Constipated)"
    elif any(k in text_lower for k in ["loose", "soft stool", "frequent", "mridu", "diarrhea", "sensitive to milk"]):
        koshtha = "Mridu Koshtha (Pitta / Soft & Rapid)"
    elif any(k in text_lower for k in ["regular", "normal stool", "once daily", "madhyama"]):
        koshtha = "Madhyama Koshtha (Kapha/Sama / Formed & Regular)"

    return agni, koshtha

def detect_ayurvedic_vikriti(chief_complaint: str, symptoms: List[str]) -> str:
    """
    Determine primary active dosha imbalance (Vikriti) based on complaints and symptoms.
    """
    combined = (chief_complaint + " " + " ".join(symptoms)).lower()
    
    vata_count = 0
    pitta_count = 0
    kapha_count = 0
    
    vata_keywords = ["joint pain", "dryness", "constipation", "insomnia", "anxiety", "cracking", "numbness", "tingling", "tremor", "sciatica", "bodyache", "spasm"]
    pitta_keywords = ["burning", "acidity", "fever", "inflammation", "rash", "redness", "ulcer", "heat", "sweating", "loose motions", "irritability"]
    kapha_keywords = ["heaviness", "congestion", "cough", "mucus", "weight gain", "lethargy", "swelling", "edema", "excess sleep", "loss of taste"]

    for kw in vata_keywords:
        if kw in combined:
            vata_count += 1
    for kw in pitta_keywords:
        if kw in combined:
            pitta_count += 1
    for kw in kapha_keywords:
        if kw in combined:
            kapha_count += 1

    counts = [("Vataja Vikriti (Air/Ether imbalance)", vata_count),
              ("Pittaja Vikriti (Fire/Water imbalance)", pitta_count),
              ("Kaphaja Vikriti (Water/Earth imbalance)", kapha_count)]
    counts.sort(key=lambda x: x[1], reverse=True)
    
    if counts[0][1] > 0 and counts[0][1] == counts[1][1]:
        return "Sannipataja / Dvidoshaja Vikriti (Dual dosha imbalance)"
    elif counts[0][1] > 0:
        return counts[0][0]
    return "Vata-Pittaja Vikriti (Mild systemic metabolic imbalance)"
