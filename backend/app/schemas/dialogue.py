from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class HistoryType(str, Enum):
    ALLOPATHIC = "allopathic"
    AYURVEDIC = "ayurvedic"
    MIXED = "mixed"  # Integrative Care (Primary framework + non-overlapping secondary block)

class InterviewPhase(str, Enum):
    CHIEF_COMPLAINT = "CHIEF_COMPLAINT"
    SOCRATES_EXPLORATION = "SOCRATES_EXPLORATION"
    CCRAS_PRAKRITI = "CCRAS_PRAKRITI"
    AYURVEDIC_PARIKSHA = "AYURVEDIC_PARIKSHA"
    BACKGROUND_HISTORY = "BACKGROUND_HISTORY"
    REVIEW_OF_SYSTEMS = "REVIEW_OF_SYSTEMS"
    COMPLETED = "COMPLETED"
    RED_FLAG_TRIAGE = "RED_FLAG_TRIAGE"

class RedFlagSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"

class RedFlagAlert(BaseModel):
    is_red_flag: bool = False
    severity: Optional[RedFlagSeverity] = None
    category: Optional[str] = None
    triggers: List[str] = Field(default_factory=list)
    emergency_message: Optional[str] = None
    triage_destination: Optional[str] = None
    detected_at: Optional[str] = None

class TouchOption(BaseModel):
    id: str
    label: str
    value: str
    slot_tag: Optional[str] = None
    dosha_bias: Optional[Dict[str, float]] = None

class SocratesState(BaseModel):
    site: Optional[str] = None
    onset: Optional[str] = None
    character: Optional[str] = None
    radiation: Optional[str] = None
    associations: List[str] = Field(default_factory=list)
    time_course: Optional[str] = None
    exacerbating_relieving: Optional[str] = None
    severity_score: Optional[int] = Field(default=None, ge=1, le=10)
    missing_slots: List[str] = Field(default_factory=lambda: [
        "site", "onset", "character", "radiation", "associations", "time_course", "exacerbating_relieving", "severity"
    ])

class CCRASPrakritiScores(BaseModel):
    vata_percentage: float = 0.0
    pitta_percentage: float = 0.0
    kapha_percentage: float = 0.0
    dominant_prakriti: str = "Undetermined"
    phenotype_type: str = "Undetermined"  # Ekadoshaja | Dvandvaja | Tridoshaja
    total_answers: int = 0
    domain_scores: Dict[str, Dict[str, float]] = Field(default_factory=dict)

class SatmyaAssessment(BaseModel):
    score_percentage: float = 0.0
    classification: str = "Madhyama Satmya"
    citation: str = "Charaka Samhita Vimana Sthana Ch. 8"

class SattvaAssessment(BaseModel):
    score_percentage: float = 0.0
    classification: str = "Madhyama Sattva"
    citation: str = "Charaka Samhita Vimana Sthana Ch. 8"

class VyayamaShaktiAssessment(BaseModel):
    score_percentage: float = 0.0
    classification: str = "Madhyama Vyayama Shakti"
    citation: str = "Charaka Samhita Vimana Sthana Ch. 8"

class AyurvedicAssessment(BaseModel):
    prakriti: Optional[CCRASPrakritiScores] = None
    vikriti: Optional[str] = None
    agni: Optional[str] = None         # Manda, Tikshna, Vishama, Sama (Ahara Shakti)
    koshtha: Optional[str] = None      # Krura, Mridu, Madhyama
    satmya: Optional[SatmyaAssessment] = None
    sattva: Optional[SattvaAssessment] = None
    vyayama_shakti: Optional[VyayamaShaktiAssessment] = None
    vaya_lifestage: Optional[str] = None
    ahara_vihara: Optional[str] = None # Diet & lifestyle triggers
    nidana: Optional[str] = None       # Etiological factors
    samprapti: Optional[str] = None    # Pathogenesis summary
    physical_exam_deferred: List[str] = Field(default_factory=lambda: [
        "Sara (Tissue Quality)", "Samhanana (Body Compactness)", "Pramana (Anthropometry)"
    ])

class StandardHistory(BaseModel):
    chief_complaint: Optional[str] = None
    hpi: Optional[str] = None
    socrates: Optional[SocratesState] = Field(default_factory=SocratesState)
    past_medical_history: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    known_allergies: List[str] = Field(default_factory=list)
    family_history: List[str] = Field(default_factory=list)
    review_of_systems: List[str] = Field(default_factory=list)

class UnifiedClinicalHistory(BaseModel):
    patient_id: str
    visit_id: str
    history_type: HistoryType
    primary_framework: Optional[HistoryType] = None
    standard_history: StandardHistory = Field(default_factory=StandardHistory)
    ayurvedic_assessment: Optional[AyurvedicAssessment] = Field(default_factory=AyurvedicAssessment)
    red_flags: List[RedFlagAlert] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)
    completed_at: Optional[str] = None

class DialogueTurn(BaseModel):
    turn_number: int
    speaker: str  # "ai" | "patient"
    utterance: str
    selected_option_id: Optional[str] = None
    phase: InterviewPhase
    timestamp: str = Field(default_factory=_utc_now_iso)

class DialogueStartRequest(BaseModel):
    patient_id: str
    history_type: HistoryType = HistoryType.ALLOPATHIC
    primary_framework: Optional[HistoryType] = None
    language: str = "en"
    age: Optional[int] = None
    chief_complaint_hint: Optional[str] = None
    extracted_document_context: Optional[Dict[str, Any]] = None
    clinical_reference_chunks: Optional[List[str]] = None
    patient_history_chunks: Optional[List[str]] = None

class DialogueTurnInput(BaseModel):
    session_id: str
    patient_response: str
    selected_option_id: Optional[str] = None
    clinical_reference_chunks: Optional[List[str]] = None
    patient_history_chunks: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class DialogueTurnResponse(BaseModel):
    session_id: str
    turn_number: int
    max_turns: int = 10
    phase: InterviewPhase
    question_text: str
    touch_options: List[TouchOption] = Field(default_factory=list)
    red_flag_alert: Optional[RedFlagAlert] = None
    is_completed: bool = False
    progress_percentage: float = 0.0
    clinical_history: UnifiedClinicalHistory
    audio_guidance_cue: Optional[str] = None

class DialogueSessionState(BaseModel):
    session_id: str
    patient_id: str
    history_type: HistoryType
    primary_framework: Optional[HistoryType] = None
    language: str = "en"
    age: Optional[int] = None
    phase: InterviewPhase = InterviewPhase.CHIEF_COMPLAINT
    turn_count: int = 0
    max_turns: int = 10
    turns: List[DialogueTurn] = Field(default_factory=list)
    clinical_history: UnifiedClinicalHistory
    extracted_document_context: Dict[str, Any] = Field(default_factory=dict)
    clinical_reference_chunks: List[str] = Field(default_factory=list)
    patient_history_chunks: List[str] = Field(default_factory=list)
    active_red_flag: Optional[RedFlagAlert] = None
    is_completed: bool = False
    ccras_battery_index: int = 0
    prakriti_raw_answers: List[Dict[str, Any]] = Field(default_factory=list)
    satmya_raw_answers: List[Dict[str, Any]] = Field(default_factory=list)
    sattva_raw_answers: List[Dict[str, Any]] = Field(default_factory=list)
    vyayama_raw_answers: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
