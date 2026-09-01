"""
Pydantic schemas for MediKiosk document digitization, structured clinical extraction,
and Ayurvedic/Allopathic medical domain representations (Problem Statement 26047).
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

from .config import DocumentType, MedicineSystem, RoutingDecision



class AyurvedicForm(str, Enum):
    CHURNA = "churna"            # Herbal powder (e.g. Triphala Churna)
    KWATH = "kwath"              # Decoction / Kashayam (e.g. Maharasnadi Kwath)
    VATI = "vati"                # Tablet / Pill / Gutika (e.g. Chandraprabha Vati, Yograj Guggulu)
    GUTIKA = "gutika"            # Pill
    TAILA = "taila"              # Medicated oil (e.g. Mahanarayan Taila, Ksheerabala Taila)
    GHRITA = "ghrita"            # Medicated clarified butter/ghee (e.g. Brahmi Ghrita)
    ASAVA = "asava"              # Naturally fermented infusion (e.g. Drakshasava)
    ARISHTA = "arishta"          # Naturally fermented decoction (e.g. Ashwagandharishta)
    BHASMA = "bhasma"            # Calx / Calcined mineral (e.g. Swarna Bhasma, Shankha Bhasma)
    PISHTI = "pishti"            # Fine gemstone powder (e.g. Mukta Pishti)
    AVALEHA = "avaleha"          # Herbal jam / confection (e.g. Chyawanprash, Haridra Khanda)
    RASA = "rasa"                # Herbo-mineral preparation (e.g. Tribhuvankirti Rasa)
    LEPA = "lepa"                # Herbal paste for topical application
    TABLET = "tablet"            # Allopathic tablet
    CAPSULE = "capsule"          # Capsule
    SYRUP = "syrup"              # Liquid / Syrup
    INJECTION = "injection"      # Parenteral / IV
    DROPS = "drops"              # Eye / Ear / Nasal (Nasya) drops
    OINTMENT = "ointment"        # Topical cream/ointment
    OTHER = "other"


class AyurvedicKala(str, Enum):
    """Aushadha Sevana Kala — Time of Ayurvedic medicine administration."""
    ABHAKTA = "abhakta"          # Empty stomach / early morning
    PRAGBHAKTA = "pragbhakta"    # Just before meals
    ADHOBHAKTA = "adhobhakta"    # Immediately after meals
    MADHYABHAKTA = "madhyabhakta"# During meals / mid-meal
    SAMABHAKTA = "samabhakta"    # Mixed with food
    NISHI = "nishi"              # At bedtime / night
    MUHURMUHU = "muhurmuhu"      # Frequent intervals (for cough/breathlessness/thirst)
    SABHAKTA = "sabhakta"        # Prepared along with food
    OTHER = "other"


class AbnormalFlag(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"


class MedicationItem(BaseModel):
    name: str = Field(description="Name of the medicine/formulation")
    generic_name: Optional[str] = Field(default=None, description="Generic pharmacological / classical herb name")
    brand_name: Optional[str] = Field(default=None, description="Commercial brand name if identified")
    dosage: Optional[str] = Field(default=None, description="Dosage quantity (e.g. 500mg, 1 tsp, 2 vati, 15ml)")
    dosage_unit: Optional[str] = Field(default=None, description="Unit (mg, ml, g, ratti, masha, tola, karsha, vati, drops)")
    frequency: Optional[str] = Field(default=None, description="Frequency (e.g. Once daily, BD/Twice daily, TDS/TID, QID, SOS/PRN)")
    duration: Optional[str] = Field(default=None, description="Duration of treatment (e.g. 5 days, 1 month, 15 days)")
    route: Optional[str] = Field(default="oral", description="Route of administration (oral, topical, nasya, ophthalmic, etc.)")
    instructions: Optional[str] = Field(default=None, description="General intake instructions (e.g. after food, with lukewarm water)")
    
    # Ayurvedic specific extensions
    is_ayurvedic: bool = Field(default=False, description="Whether this formulation is Ayurvedic/AYUSH")
    ayurvedic_form: Optional[AyurvedicForm] = Field(default=None, description="Ayurvedic Kalpana form (Churna, Kwath, Vati, etc.)")
    anupana: Optional[str] = Field(default=None, description="Vehicle / Adjuvant (e.g. Koshna Jala/warm water, Dugdha/milk, Madhu/honey, Ghrita)")
    kala: Optional[AyurvedicKala] = Field(default=None, description="Ayurvedic timing of administration (Aushadha Sevana Kala)")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence score")


class DiagnosisItem(BaseModel):
    condition: str = Field(description="Diagnosed clinical condition or symptom")
    system_terminology: MedicineSystem = Field(default=MedicineSystem.ALLOPATHIC, description="Medical system terminology")
    ayurvedic_name: Optional[str] = Field(default=None, description="Classical Ayurvedic disease name (e.g. Amavata, Sandhivata, Prameha, Tamaka Shwasa)")
    biomedical_name: Optional[str] = Field(default=None, description="Standard biomedical allopathic name (e.g. Rheumatoid Arthritis, Osteoarthritis, Type 2 Diabetes)")
    coding_system: Optional[str] = Field(default=None, description="Coding standard: NAMASTE | ICD-11-TM2 | ICD-10 | SNOMED")
    code: Optional[str] = Field(default=None, description="Standardized disease code (e.g. NAMASTE code or ICD-11 TM2 code)")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class AyurvedicAssessment(BaseModel):
    """Ayurvedic Clinical History & Dashavidha Pariksha indicators."""
    prakriti: Optional[str] = Field(default=None, description="Constitution (Vata / Pitta / Kapha / Dwandwaja / Sama)")
    vikriti: Optional[str] = Field(default=None, description="Current doshic imbalance (e.g. Vata-Pitta Prakopa, Kapha Vriddhi)")
    agni: Optional[str] = Field(default=None, description="Digestive fire status (Manda / Tikshna / Vishama / Sama Agni)")
    koshtha: Optional[str] = Field(default=None, description="Bowel habit / nature (Krura / Mridu / Madhyama Koshtha)")
    dhatu_dushti: Optional[List[str]] = Field(default_factory=list, description="Tissues involved (Rasa, Rakta, Mamsa, Meda, Asthi, Majja, Shukra)")
    srotas_dushti: Optional[List[str]] = Field(default_factory=list, description="Channels involved (Pranavaha, Annavaha, Rasavaha, etc.)")
    nidana: Optional[str] = Field(default=None, description="Causative factors (dietary/lifestyle/seasonal)")
    notes: Optional[str] = Field(default=None, description="Additional Ayurvedic clinical observations")


class LabInvestigationItem(BaseModel):
    test_name: str = Field(description="Name of the laboratory or diagnostic test (e.g. HbA1c, Fasting Blood Sugar, Serum Creatinine)")
    category: Optional[str] = Field(default=None, description="Biochemistry, Hematology, Lipid Profile, LFT, KFT, Urine, Radiology, etc.")
    observed_value: Optional[str] = Field(default=None, description="Observed numeric or textual finding (e.g. 145, Positive, 7.8)")
    unit: Optional[str] = Field(default=None, description="Measurement unit (mg/dL, g/dL, %, U/L, mm/hr)")
    reference_range: Optional[str] = Field(default=None, description="Normal biological reference range (e.g. 70-100 mg/dL)")
    abnormal_flag: Optional[AbnormalFlag] = Field(default=AbnormalFlag.NORMAL, description="Abnormal status flag")
    clinical_interpretation: Optional[str] = Field(default=None, description="Brief clinical significance (e.g. Elevated fasting blood glucose)")



class ExtractedDocumentData(BaseModel):
    """Complete structured output from OCR / Vision LLM document digitization."""
    document_type: DocumentType = Field(default=DocumentType.HYBRID_MIXED, description="Classified document nature")
    medicine_system: MedicineSystem = Field(default=MedicineSystem.ALLOPATHIC, description="Dominant medical system in document")
    
    # Metadata
    patient_name: Optional[str] = Field(default=None, description="Patient full name if present")
    patient_age: Optional[str] = Field(default=None, description="Patient age / DOB")
    patient_gender: Optional[str] = Field(default=None, description="Patient gender")
    doctor_name: Optional[str] = Field(default=None, description="Doctor name / designation")
    doctor_registration_no: Optional[str] = Field(default=None, description="State Medical Council / NCISM / Board Reg Number")
    clinic_or_hospital: Optional[str] = Field(default=None, description="Hospital / OPD / Clinic name")
    document_date: Optional[str] = Field(default=None, description="Prescription / Report date (YYYY-MM-DD or as found)")
    
    # Clinical Entities
    chief_complaints: List[str] = Field(default_factory=list, description="Symptoms / chief complaints noted")
    vitals: Dict[str, Any] = Field(default_factory=dict, description="Vitals (BP, Pulse, Weight, Temp, SpO2)")
    medications: List[MedicationItem] = Field(default_factory=list, description="List of prescribed medicines")
    diagnoses: List[DiagnosisItem] = Field(default_factory=list, description="List of diagnoses / clinical impressions")
    ayurvedic_assessment: Optional[AyurvedicAssessment] = Field(default=None, description="Ayurvedic specific clinical parameters")
    lab_investigations: List[LabInvestigationItem] = Field(default_factory=list, description="Laboratory investigations and test results")
    red_flags: List[str] = Field(default_factory=list, description="Priority triage red flags or critical warnings detected")
    diet_and_lifestyle_advice: List[str] = Field(default_factory=list, description="Pathya-Apathya (Ayurvedic dietary advice) or general precautions")
    follow_up_date: Optional[str] = Field(default=None, description="Recommended review / follow-up date")
    
    # Raw & Extraction Quality
    raw_text: str = Field(default="", description="Complete raw extracted text")
    handwritten_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="Estimated fraction of content that is handwritten")
    extraction_confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Overall model extraction confidence")
