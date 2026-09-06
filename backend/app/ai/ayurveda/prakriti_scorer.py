# backend/app/ai/ayurveda/prakriti_scorer.py
"""
CCRAS-SF-12 Deterministic Mathematical Scoring Engine
Implements the factorial classification and percentage calculations
specified in docs/PRAKRITI_SHORT_FORM_QUESTIONNAIRE.md
"""

from typing import Dict, Any, List, Union
from app.ai.ayurveda.models import PrakritiScores, PrakritiResult

def score_prakriti(answers: Union[Dict[str, str], List[str]]) -> PrakritiResult:
    """
    Calculates exact CCRAS-SF-12 dosha percentages and classification for N = 12.

    Parameters:
    - answers: Dictionary of item_id -> option ('A' | 'B' | 'C') or List of option strings.
      Option A = Vata Anchor [1, 0, 0]
      Option B = Pitta Anchor [0, 1, 0]
      Option C = Kapha Anchor [0, 0, 1]

    Returns:
    - PrakritiResult with exact percentages, classification, dominant doshas, and summary.
    """
    raw_list: List[str] = []
    if isinstance(answers, dict):
        raw_list = [str(v).strip().upper() for v in answers.values()]
    elif isinstance(answers, list):
        raw_list = [str(v).strip().upper() for v in answers]

    # Normalize option values if full strings were passed (e.g. 'A', 'OPT_A', 'VATA')
    s_v = 0
    s_p = 0
    s_k = 0

    for ans in raw_list:
        if ans in ["A", "OPT_A", "VATA", "V"]:
            s_v += 1
        elif ans in ["B", "OPT_B", "PITTA", "P"]:
            s_p += 1
        elif ans in ["C", "OPT_C", "KAPHA", "K"]:
            s_k += 1
        else:
            # Fallback based on substring
            if "VATA" in ans or ans.endswith("_A"):
                s_v += 1
            elif "PITTA" in ans or ans.endswith("_B"):
                s_p += 1
            elif "KAPHA" in ans or ans.endswith("_C"):
                s_k += 1
            else:
                s_v += 1 # Default neutral

    total_points = s_v + s_p + s_k
    if total_points == 0:
        total_points = 12
        s_v, s_p, s_k = 4, 4, 4

    # Calculate exact percentages
    p_v = round((s_v / total_points) * 100.0, 2)
    p_p = round((s_p / total_points) * 100.0, 2)
    p_k = round(100.0 - p_v - p_p, 2)

    dosha_map = [
        ("Vata", s_v, p_v),
        ("Pitta", s_p, p_p),
        ("Kapha", s_k, p_k)
    ]
    # Sort descending by raw points, then percentage
    sorted_doshas = sorted(dosha_map, key=lambda x: (x[1], x[2]), reverse=True)
    d1_name, d1_pts, d1_pct = sorted_doshas[0]
    d2_name, d2_pts, d2_pct = sorted_doshas[1]
    d3_name, d3_pts, d3_pct = sorted_doshas[2]

    # Decision Boundaries Calibration
    # 1. Samadoshaja (Equi-Doshic / Tridoshic)
    if (d1_pts == d2_pts == d3_pts == 4) or ((d1_pct - d2_pct <= 8.5) and (d2_pct - d3_pct <= 8.5)):
        classification = "Samadoshaja"
        prakriti_type = "Sama Prakriti (Tridoshaja)"
        dominant = "Tridosha"
        secondary = None
        summary = f"Balanced Tri-Doshic baseline ({p_v}% Vata, {p_p}% Pitta, {p_k}% Kapha). High constitutional equilibrium."

    # 2. Ekadoshaja (Monodoshic Dominance)
    elif d1_pts >= 6 and (d1_pts - d2_pts >= 2):
        classification = "Ekadoshaja"
        prakriti_type = f"{d1_name}ja Prakriti"
        dominant = d1_name
        secondary = d2_name
        summary = f"Dominant {d1_name} baseline ({d1_pct}%), showing primary {d1_name} physiological and somatic traits."

    # 3. Dvidoshaja (Dual-Doshic — Most Common)
    else:
        classification = "Dvidoshaja"
        prakriti_type = f"{d1_name}-{d2_name} Prakriti"
        dominant = d1_name
        secondary = d2_name
        summary = f"Dual-doshic {d1_name}-{d2_name} baseline with primary {d1_name} ({d1_pct}%) and secondary {d2_name} ({d2_pct}%)."

    return PrakritiResult(
        prakriti_type=prakriti_type,
        classification=classification,
        scores=PrakritiScores(
            vata=p_v,
            pitta=p_p,
            kapha=p_k,
            raw_points={"Vata": s_v, "Pitta": s_p, "Kapha": s_k}
        ),
        dominant_dosha=dominant,
        secondary_dosha=secondary,
        summary=summary
    )
