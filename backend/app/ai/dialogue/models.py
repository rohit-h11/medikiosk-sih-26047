# backend/app/ai/dialogue/models.py
"""
MediKiosk — Multi-Paradigm Clinical Dialogue Models
Pydantic schemas for Patient Context, multi-phase session tracking,
SOCRATES/Ayurveda slot extraction, and dialogue turn results.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class ConversationMessage(BaseModel):
    role: str = Field(..., description="'patient' | 'assistant' | 'system'")
    content: str = Field(..., description="Message text")
    timestamp: str = Field(default_factory=_utc_now_iso)
    slot_tag: Optional[str] = None

class TouchOption(BaseModel):
    id: str = Field(..., description="Unique key for option chip")
    label: str = Field(..., description="Display label for touchscreen chip")
    value: str = Field(..., description="Utterance value if selected")
    slot_tag: Optional[str] = Field(None, description="Associated clinical slot or option anchor")

class SocratesState(BaseModel):
    site: Optional[str] = Field(None, description="Site / anatomical location of the pain/symptom")
    onset: Optional[str] = Field(None, description="Onset timing: sudden or gradual, duration")
    character: Optional[str] = Field(None, description="Character/nature: sharp, dull, burning, aching, throbbing, etc.")
    radiation: Optional[str] = Field(None, description="Radiation: does the pain travel anywhere else?")
    associations: List[str] = Field(default_factory=list, description="Associated symptoms: fever, nausea, sweating, etc.")
    time_course: Optional[str] = Field(None, description="Time course: constant, intermittent, worsening, diurnal pattern")
    exacerbating_relieving: Optional[str] = Field(None, description="Exacerbating / relieving factors: food, rest, motion, etc.")
    severity: Optional[str] = Field(None, description="Severity: 1-10 scale or mild/moderate/severe")
    covered_slots: List[str] = Field(default_factory=list, description="Slots already determined")
    missing_slots: List[str] = Field(
        default_factory=lambda: [
            "site", "onset", "character", "radiation", "associations",
            "time_course", "exacerbating_relieving", "severity"
        ],
        description="Slots remaining to assess"
    )

class PatientContext(BaseModel):
    patient_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    hospital_type: str = Field(default="allopathy", description="'allopathy' | 'ayurveda'")
    prakriti_profile: Optional[str] = Field(None, description="Calculated baseline Prakriti, e.g. 'Pitta-Vata Prakriti'")
    dashavidha_state: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dashavidha 10-limb state")
    chief_complaint: Optional[str] = Field(None, description="Main presenting complaint")
    symptoms: List[str] = Field(default_factory=list, description="List of recognized symptoms")
    past_medical_history: List[str] = Field(default_factory=list, description="Chronic conditions, surgeries")
    current_medications: List[str] = Field(default_factory=list, description="Current drugs")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    vitals: Dict[str, Any] = Field(default_factory=dict, description="Vitals")
    extracted_docs: Optional[Dict[str, Any]] = Field(default=None, description="Context from OCR/uploaded documents")
    language: str = "en"

class RedFlagAlert(BaseModel):
    is_red_flag: bool = False
    severity: Optional[str] = Field(None, description="'CRITICAL' | 'HIGH' | 'MODERATE'")
    category: Optional[str] = None
    triggers: List[str] = Field(default_factory=list)
    emergency_message: Optional[str] = None

class DialogueTurnResult(BaseModel):
    should_stop: bool = Field(
        ...,
        description="True if interview should end (sufficient info collected or red flag triggered)"
    )
    next_question: Optional[str] = Field(
        None,
        description="The next clinical inquiry question to ask the patient. None if should_stop is True."
    )
    touch_options: List[TouchOption] = Field(
        default_factory=list,
        description="Quick-tap touch options for kiosk interface"
    )
    # Generic state supporting Allopathy and Ayurveda
    state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Accumulated paradigm clinical state"
    )
    socrates_state: SocratesState = Field(
        default_factory=SocratesState,
        description="Backwards-compatible SOCRATES extraction"
    )
    covered_slots: List[str] = Field(
        default_factory=list,
        description="Slots covered up to this turn"
    )
    missing_slots: List[str] = Field(
        default_factory=list,
        description="Slots remaining uncovered"
    )
    clinical_summary: Optional[str] = Field(
        None,
        description="Structured clinical summary of gathered data for doctor queue"
    )
    closing_message: Optional[str] = Field(
        None,
        description="Patient-facing closing message when should_stop is True"
    )
    red_flag_alert: Optional[RedFlagAlert] = Field(
        None,
        description="Emergency alert if red-flag symptoms detected"
    )
    reasoning: Optional[str] = Field(
        None,
        description="Clinical rationale for the question or stop decision"
    )
    primary_impression: Optional[str] = Field(
        None,
        description="Primary working clinical impression for attending physician EHR review"
    )
    provisional_differentials: List[str] = Field(
        default_factory=list,
        description="Top 3 probable clinical differential impressions for attending physician"
    )

