# backend/app/ai/ayurveda/dashavidha_scorer.py
"""
Dashavidha Pariksha (10-Fold Assessment) Scoring Engine
Implements classical Charaka Samhita 3-tier criteria for Sattva, Satmya,
and Vyayama Shakti, with auto-derived Vaya and explicit physician deferrals.
"""

from typing import Dict, Any, Optional, List, Union
from app.ai.ayurveda.models import DashavidhaState, PrakritiResult

def calculate_vaya_category(age: Optional[int]) -> str:
    """Calculates classical Ayurvedic life stage from age."""
    if age is None:
        return "Madhya"
    if age < 16:
        return "Bala"
    elif age <= 60:
        return "Madhya"
    else:
        return "Vriddha"

def normalize_tier_answer(ans: Optional[str]) -> str:
    """Normalizes option key or text into Pravara / Madhyama / Avara."""
    if not ans:
        return "Madhyama"
    ans_upper = str(ans).strip().upper()
    if ans_upper in ["A", "OPT_A", "PRAVARA", "HIGH", "1"]:
        return "Pravara"
    elif ans_upper in ["B", "OPT_B", "MADHYAMA", "MODERATE", "MEDIUM", "2"]:
        return "Madhyama"
    elif ans_upper in ["C", "OPT_C", "AVARA", "LOW", "POOR", "3"]:
        return "Avara"
    
    if "PRAVARA" in ans_upper: return "Pravara"
    if "AVARA" in ans_upper: return "Avara"
    return "Madhyama"

def score_dashavidha(
    answers: Union[Dict[str, str], List[str]],
    age: Optional[int] = None,
    prakriti_result: Optional[PrakritiResult] = None
) -> DashavidhaState:
    """
    Evaluates the 10-limb Dashavidha profile:
    1. Prakriti (Step A1 result)
    2. Sattva (Mental resilience: Pravara / Madhyama / Avara)
    3. Satmya (Adaptability: Pravara / Madhyama / Avara)
    4. Vyayama Shakti (Stamina: Pravara / Madhyama / Avara)
    5. Vaya (Auto-derived from age)
    6. Ahara Shakti (Auto-derived baseline)
    7-9. Sara, Samhanana, Pramana (Clinically deferred to attending Vaidya)
    """
    ans_dict: Dict[str, str] = {}
    if isinstance(answers, list):
        keys = ["sattva", "satmya", "vyayama_shakti"]
        for idx, val in enumerate(answers):
            if idx < len(keys):
                ans_dict[keys[idx]] = val
    elif isinstance(answers, dict):
        ans_dict = answers

    sattva_tier = normalize_tier_answer(ans_dict.get("sattva") or ans_dict.get("dash_sattva"))
    satmya_tier = normalize_tier_answer(ans_dict.get("satmya") or ans_dict.get("dash_satmya"))
    vyayama_tier = normalize_tier_answer(ans_dict.get("vyayama_shakti") or ans_dict.get("dash_vyayama"))
    vaya_cat = calculate_vaya_category(age)

    return DashavidhaState(
        prakriti_result=prakriti_result,
        sattva=sattva_tier, # type: ignore
        satmya=satmya_tier, # type: ignore
        vyayama_shakti=vyayama_tier, # type: ignore
        vaya_category=vaya_cat, # type: ignore
        ahara_shakti="Madhyama",
        sara="Deferred to Attending Vaidya (Requires physical palpation & inspection)",
        samhanana="Deferred to Attending Vaidya (Requires physician structural exam)",
        pramana="Deferred to Attending Vaidya (Requires anthropometric measurement)"
    )
