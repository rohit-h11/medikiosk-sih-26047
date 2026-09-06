# backend/app/ai/ayurveda/models.py
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field

class PrakritiScores(BaseModel):
    vata: float = Field(..., description="Vata percentage (0.0 - 100.0)")
    pitta: float = Field(..., description="Pitta percentage (0.0 - 100.0)")
    kapha: float = Field(..., description="Kapha percentage (0.0 - 100.0)")
    raw_points: Dict[str, int] = Field(default_factory=dict, description="Raw point tallies (V, P, K)")

class PrakritiResult(BaseModel):
    prakriti_type: str = Field(..., description="e.g. 'Pitta-Vata Prakriti', 'Sama Prakriti (Tridoshaja)'")
    classification: str = Field(..., description="'Ekadoshaja' | 'Dvidoshaja' | 'Samadoshaja'")
    scores: PrakritiScores
    dominant_dosha: str
    secondary_dosha: Optional[str] = None
    summary: str

class DashavidhaState(BaseModel):
    # Step A1 Baseline
    prakriti_result: Optional[PrakritiResult] = None
    
    # Step A2 Static 3-Tier Scores
    sattva: Optional[Literal["Pravara", "Madhyama", "Avara"]] = Field(
        None, description="Mental strength & pain endurance: Pravara (High) | Madhyama (Moderate) | Avara (Low)"
    )
    satmya: Optional[Literal["Pravara", "Madhyama", "Avara"]] = Field(
        None, description="Dietary & environmental adaptability: Pravara | Madhyama | Avara"
    )
    vyayama_shakti: Optional[Literal["Pravara", "Madhyama", "Avara"]] = Field(
        None, description="Physical exertion capacity & stamina: Pravara | Madhyama | Avara"
    )
    
    # Auto-derived parameters
    vaya_category: Optional[Literal["Bala", "Madhya", "Vriddha"]] = Field(
        None, description="Age life stage: Bala (<16) | Madhya (16-60) | Vriddha (>60)"
    )
    ahara_shakti: Optional[str] = Field(
        None, description="Digestive & metabolic strength (Pravara/Madhyama/Avara)"
    )
    
    # Explicit Clinical Deferrals to Attending Vaidya
    sara: str = "Deferred to Attending Vaidya (Requires physical palpation & tissue examination)"
    samhanana: str = "Deferred to Attending Vaidya (Requires physician structural compactness exam)"
    pramana: str = "Deferred to Attending Vaidya (Requires clinical anthropometric measurement)"

class AyurvedaClinicalState(BaseModel):
    """Accumulated state during dynamic Vikriti dialogue (Step A3)."""
    vikriti_dosha: Optional[str] = Field(None, description="Active dosha vitiation (e.g., 'Pitta-Vata Vriddhi')")
    agni_state: Optional[str] = Field(None, description="'Samagni' | 'Tikshnagni' | 'Mandagni' | 'Vishamagni'")
    ama_state: Optional[str] = Field(None, description="'Saama' (toxins present) | 'Niraama' (clear)")
    koshtha: Optional[str] = Field(None, description="'Mridu' (loose) | 'Madhyama' (normal) | 'Krura' (constipated)")
    nidra_pattern: Optional[str] = Field(None, description="Sleep quality: 'Sound' | 'Disturbed' | 'Anidra' (Insomnia)")
    ahara_vihara_triggers: List[str] = Field(default_factory=list, description="Dietary and lifestyle causative factors (Hetu)")
    ashtavidha_findings: Dict[str, str] = Field(default_factory=dict, description="Jihwa (tongue), Sparsha (skin), etc.")
    provisional_namaste_code: Optional[str] = Field(None, description="Provisional NAMASTE Morbidity Code (e.g. 'EB-4')")
    provisional_icd11_tm2: Optional[str] = Field(None, description="Provisional WHO ICD-11 TM2 Code")
    covered_slots: List[str] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=lambda: [
        "vikriti_dosha", "agni_state", "ama_state", "koshtha", "nidra_pattern", "ahara_vihara_triggers"
    ])
