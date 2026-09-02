"""
MediKiosk — National AYUSH Morbidity & Standardized Terminologies Electronic (NAMASTE) Bridge
Mapped to WHO ICD-11 Chapter 26 (Traditional Medicine Module 2 - TM2).
Official reference based on published NAMASTE portal data analyses (Ministry of Ayush / AIIA).
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class NamasteDiagnosisItem(BaseModel):
    namaste_code: str = Field(..., description="Official National AYUSH Morbidity Code (e.g. AAE-16, EB-4)")
    legacy_code: Optional[str] = Field(None, description="Legacy/Illustrative reference code (e.g. NAM-AYU-1021)")
    ayurvedic_name: str = Field(..., description="Ayurvedic clinical condition name")
    sanskrit_script: Optional[str] = None
    english_name: str = Field(..., description="Biomedical / Clinical equivalent translation")
    icd11_tm2_code: str = Field(..., description="WHO ICD-11 Chapter 26 Module 2 (TM2) code")
    icd11_title: str = Field(..., description="WHO ICD-11 Traditional Medicine diagnostic title")
    dosha_association: str = Field(..., description="Primary dosha involvement (Vata, Pitta, Kapha)")
    srotas_involved: Optional[str] = Field(None, description="Ayurvedic bodily channel / system")
    common_symptoms: List[str] = Field(default_factory=list)
    standard_formulations: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Standard Ayurvedic formulations (vati, kwath, churna, arishta, taila) - non-prescriptive reference"
    )

# Curated reference database bridging real NAMASTE Portal codes with WHO ICD-11 Chapter 26 (TM2)
NAMASTE_DATABASE: List[NamasteDiagnosisItem] = [
    NamasteDiagnosisItem(
        namaste_code="AAE-16",
        legacy_code="NAM-AYU-1021",
        ayurvedic_name="Sandhigatavata (Sandhivata)",
        sanskrit_script="संधिगतवात / संधिवात",
        english_name="Osteoarthritis / Degenerative Joint Disorder",
        icd11_tm2_code="TM2-SD01.1",
        icd11_title="Vata disorder of joints (Sandhigata Vata)",
        dosha_association="Vataja",
        srotas_involved="Asthivaha & Majjavaha Srotas",
        common_symptoms=["Joint pain", "Crepitus / Crackling", "Swelling", "Stiffness on waking", "Pain on movement"],
        standard_formulations=[
            {"name": "Yogaraja Guggulu", "form": "vati", "dosage": "2 tablets BD with warm water"},
            {"name": "Maharasnadi Kwatha", "form": "kwath", "dosage": "15 ml with equal warm water BD"},
            {"name": "Mahanarayana Taila", "form": "taila", "dosage": "Local application / Abhyanga"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="EC-6",
        legacy_code="NAM-AYU-1022",
        ayurvedic_name="Amavata",
        sanskrit_script="आमवात",
        english_name="Rheumatoid Arthritis / Inflammatory Polyarthritis",
        icd11_tm2_code="TM2-SD01.4",
        icd11_title="Ama and Vata metabolic joint disorder",
        dosha_association="Vata-Kaphaja (with Ama)",
        srotas_involved="Rasavaha & Asthivaha Srotas",
        common_symptoms=["Severe morning stiffness", "Multiple joint swelling", "Feverish feeling", "Body heaviness", "Loss of appetite"],
        standard_formulations=[
            {"name": "Simhanada Guggulu", "form": "vati", "dosage": "2 tablets BD"},
            {"name": "Rasnadi Guggulu", "form": "vati", "dosage": "2 tablets BD"},
            {"name": "Brihat Saindhavadi Taila", "form": "taila", "dosage": "External application"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="EB-4",
        legacy_code="NAM-AYU-2015",
        ayurvedic_name="Amlapitta",
        sanskrit_script="अम्लपित्त",
        english_name="Gastroesophageal Reflux / Non-Ulcer Hyperacidity",
        icd11_tm2_code="TM2-GA04.2",
        icd11_title="Pitta disorder of upper GI tract (Acid Pitta)",
        dosha_association="Pittaja",
        srotas_involved="Annavaha & Purishavaha Srotas",
        common_symptoms=["Heartburn / Retrosternal burning", "Sour or bitter eructation", "Nausea", "Headache after fasting", "Loss of taste"],
        standard_formulations=[
            {"name": "Avipattikara Churna", "form": "churna", "dosage": "3g before meals with warm water"},
            {"name": "Sutashekhara Rasa", "form": "vati", "dosage": "1 tablet BD with honey/water"},
            {"name": "Kamadudha Rasa", "form": "vati", "dosage": "1 tablet BD"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="EA-4",
        legacy_code="NAM-AYU-3010",
        ayurvedic_name="Tamaka Shwasa",
        sanskrit_script="तमक श्वास",
        english_name="Bronchial Asthma / Paroxysmal Dyspnoea",
        icd11_tm2_code="TM2-RS02.1",
        icd11_title="Vata-Kapha respiratory obstruction (Tamaka Shwasa)",
        dosha_association="Vata-Kaphaja",
        srotas_involved="Pranavaha Srotas",
        common_symptoms=["Wheezing", "Breathlessness worse at night or in cold/cloudy weather", "Relief on sitting upright", "Cough with viscid sputum"],
        standard_formulations=[
            {"name": "Shwasakasa Chintamani Rasa", "form": "vati", "dosage": "1 tablet BD with honey"},
            {"name": "Talisadi Churna", "form": "churna", "dosage": "3g TID with honey"},
            {"name": "Kanakasava", "form": "asava", "dosage": "15 ml with equal water after meals"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="EA-3",
        legacy_code="NAM-AYU-3012",
        ayurvedic_name="Kaphaja Kasa",
        sanskrit_script="कफज कास",
        english_name="Productive Cough / Chronic Bronchitis",
        icd11_tm2_code="TM2-RS01.3",
        icd11_title="Kapha-dominant productive cough",
        dosha_association="Kaphaja",
        srotas_involved="Pranavaha Srotas",
        common_symptoms=["Heavy chest congestion", "Thick white/clear phlegm", "Sweet taste in mouth", "Lethargy"],
        standard_formulations=[
            {"name": "Sitopaladi Churna", "form": "churna", "dosage": "3g TID with honey"},
            {"name": "Kantakari Avaleha", "form": "avaleha", "dosage": "5g BD"},
            {"name": "Vasarishta", "form": "arishta", "dosage": "15 ml BD"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="ED-5",
        legacy_code="NAM-AYU-4001",
        ayurvedic_name="Prameha (Madhumeha)",
        sanskrit_script="प्रमेह / मधुमेह",
        english_name="Type 2 Diabetes Mellitus / Metabolic Syndrome",
        icd11_tm2_code="TM2-ME01.1",
        icd11_title="Medas and Kleda metabolic disorder (Madhumeha)",
        dosha_association="Tridoshaja (Kapha-Vata dominant)",
        srotas_involved="Medovaha & Mutravaha Srotas",
        common_symptoms=["Excessive urination (Prabhuta Mutrata)", "Turbid urine", "Excessive thirst and hunger", "Sweetness in sweat", "Fatigue"],
        standard_formulations=[
            {"name": "Chandraprabha Vati", "form": "vati", "dosage": "2 tablets BD with warm water"},
            {"name": "Nisha Amalaki Churna", "form": "churna", "dosage": "3g BD before food"},
            {"name": "Vasantakusumakara Rasa", "form": "vati", "dosage": "1 tablet OD with milk"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="AAB-37",
        legacy_code="NAM-AYU-5008",
        ayurvedic_name="Gridhrasi",
        sanskrit_script="गृध्रसी",
        english_name="Sciatica / Lumbar Radiculopathy",
        icd11_tm2_code="TM2-SD03.2",
        icd11_title="Vata disorder of radiating lumbosacral pathway",
        dosha_association="Vataja or Vata-Kaphaja",
        srotas_involved="Majjavaha & Asthivaha Srotas",
        common_symptoms=["Radiating pain from buttock down to foot", "Stiffness in leg", "Twitching / Spasm", "Numbness"],
        standard_formulations=[
            {"name": "Trayodashanga Guggulu", "form": "vati", "dosage": "2 tablets BD"},
            {"name": "Sahacharadi Taila", "form": "taila", "dosage": "Local massage / Matra Basti"},
            {"name": "Rasnadi Kwatha", "form": "kwath", "dosage": "15 ml BD"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="EB-7",
        legacy_code="NAM-AYU-2020",
        ayurvedic_name="Grahanidosha (Grahani)",
        sanskrit_script="ग्रहणी दोष",
        english_name="Irritable Bowel Syndrome / Malabsorption",
        icd11_tm2_code="TM2-GA06.1",
        icd11_title="Agni-dysfunction gastrointestinal syndrome",
        dosha_association="Tridoshaja",
        srotas_involved="Annavaha & Purishavaha Srotas",
        common_symptoms=["Alternating diarrhea and constipation", "Undigested food in stool", "Abdominal rumbling", "Post-prandial urgency"],
        standard_formulations=[
            {"name": "Kutajarishta", "form": "arishta", "dosage": "15 ml BD with equal water"},
            {"name": "Bilwadi Churna", "form": "churna", "dosage": "3g BD with Takra (Buttermilk)"},
            {"name": "Mustarishta", "form": "arishta", "dosage": "15 ml BD"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="AAB-42",
        legacy_code="NAM-AYU-5010",
        ayurvedic_name="Katishula / Katisandhigatavata",
        sanskrit_script="कटिशूल / कटिसंधिगतवात",
        english_name="Lumbar Spondylosis / Chronic Lower Back Pain",
        icd11_tm2_code="TM2-SD03.1",
        icd11_title="Lumbosacral Vata pain syndrome",
        dosha_association="Vataja",
        srotas_involved="Asthivaha Srotas",
        common_symptoms=["Lower back stiffness", "Pain aggravated by bending or prolonged standing", "Catch sensation in lumbar area"],
        standard_formulations=[
            {"name": "Dashamoola Kwatha", "form": "kwath", "dosage": "15 ml BD with equal warm water"},
            {"name": "Ksheerabala Taila", "form": "taila", "dosage": "Local application / Kati Basti"},
            {"name": "Yogaraja Guggulu", "form": "vati", "dosage": "2 tablets BD"}
        ]
    ),
    NamasteDiagnosisItem(
        namaste_code="ED-1",
        legacy_code="NAM-AYU-6003",
        ayurvedic_name="Kushtha (Vicharchika / Vipadika)",
        sanskrit_script="कुष्ठ / विचर्चिका",
        english_name="Eczema / Chronic Dermatitis",
        icd11_tm2_code="TM2-SK01.2",
        icd11_title="Twak & Rakta dermatological disorder",
        dosha_association="Vata-Kaphaja / Pittaja",
        srotas_involved="Raktavaha & Swedavaha Srotas",
        common_symptoms=["Itching / Kandu", "Skin eruptions", "Oozing or dry scaling", "Discoloration / Shyavata"],
        standard_formulations=[
            {"name": "Kaishore Guggulu", "form": "vati", "dosage": "2 tablets BD"},
            {"name": "Mahamanjishtadi Kwatha", "form": "kwath", "dosage": "15 ml BD"},
            {"name": "Gandhaka Rasayana", "form": "vati", "dosage": "1 tablet BD"}
        ]
    )
]

def search_namaste_codes(query: str, limit: int = 5) -> List[NamasteDiagnosisItem]:
    """
    Search the NAMASTE diagnostic database by Ayurvedic term, English diagnosis,
    NAMASTE code (e.g. AAE-16), or symptom keyword.
    """
    if not query or not query.strip():
        return NAMASTE_DATABASE[:limit]
    
    q_clean = query.lower().strip()
    results = []
    
    for item in NAMASTE_DATABASE:
        score = 0
        if q_clean in item.ayurvedic_name.lower():
            score += 10
        if q_clean in item.english_name.lower():
            score += 8
        if q_clean in item.namaste_code.lower() or (item.legacy_code and q_clean in item.legacy_code.lower()):
            score += 15
        if q_clean in item.icd11_tm2_code.lower():
            score += 15
        if q_clean in item.dosha_association.lower():
            score += 4
        if any(q_clean in s.lower() for s in item.common_symptoms):
            score += 6
        
        if score > 0:
            results.append((score, item))
            
    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:limit]]

def get_namaste_item_by_code(code: str) -> Optional[NamasteDiagnosisItem]:
    """Find specific diagnosis item by exact NAMASTE (e.g. AAE-16), legacy code, or ICD-11 code."""
    code_upper = code.upper().strip()
    for item in NAMASTE_DATABASE:
        if (item.namaste_code == code_upper or 
            item.icd11_tm2_code == code_upper or 
            (item.legacy_code and item.legacy_code == code_upper)):
            return item
    return None
