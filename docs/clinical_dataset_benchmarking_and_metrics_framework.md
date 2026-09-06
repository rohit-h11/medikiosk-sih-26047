# 📊 MediKiosk: Real-World Clinical Dataset Benchmarking & Metrics Framework

This document outlines the standard operating procedure (SOP), mathematical formulations, schema mappings, and step-by-step methodologies to evaluate **MediKiosk** against authentic clinical datasets aligned with its core real-world responsibilities: **Triage Safety, Multi-Turn SOCRATES Slot Extraction, Multi-Paradigm Routing (Allopathy & Ayurveda), and Doctor-Facing Differential Diagnosis Support**.

---

## 1. Why Real-World Intake Datasets vs Academic Exams?

| Characteristic | ❌ Academic Exams (e.g. MedQA / USMLE) | ✅ Real Intake Datasets (DDXPlus, MIMIC-IV, MTS-Dialog) |
| :--- | :--- | :--- |
| **Input Format** | Retrospective chart reviews with lab numbers, biopsies, and genetics (*"When phenol is added at 90°C..."*). | 1st-person conversational utterances (*"I have severe burning in my chest since morning"*). |
| **Target Task** | Answering 4-option board trivia (e.g. molecular drug mechanisms, agar cultures). | **1. Triage Urgency**, **2. Clinical Slot Filling**, **3. Provisional Differential List**. |
| **Ground Truth** | Biochemical phrases (*"Cross-linking of DNA"*, *"Caspase-9"*). | Definitive clinical diseases (*Acute MI, GERD, Viral Pharyngitis, Appendicitis*). |
| **Clinical Relevancy** | Tests academic medical knowledge. | Evaluates actual patient-facing intake and clinical safety. |

---

## 2. The Three Gold-Standard Benchmark Datasets

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  MEDIKIOSK EVALUATION ECOSYSTEM                                      │
├───────────────────────────────┬──────────────────────────────────┬───────────────────────────────────┤
│ 1. DDXPlus (NeurIPS / Synthea)│ 2. MIMIC-IV Emergency (ESI)      │ 3. MTS-Dialog (Clinical Transcripts│
├───────────────────────────────┼──────────────────────────────────┼───────────────────────────────────┤
│ • Primary Impression Top-1    │ • Level 1-2 Emergency Sensitivity│ • SOCRATES Slot Extraction (8/8)  │
│ • Differential Top-3 / Top-5  │ • Undertriage Rate (Safety Crit) │ • Doctor Summary Faithfulness     │
│ • Disease Classification Acc. │ • Overtriage Rate (OPD Pacing)   │ • Multi-Turn Turn Efficiency      │
└───────────────────────────────┴──────────────────────────────────┴───────────────────────────────────┘
```

---

## 3. Dataset 1: DDXPlus (Patient Intake & Differential Diagnosis)

### Overview
- **Source**: [NeurIPS 2022 DDXPlus Dataset](https://huggingface.co/datasets/maluuba/ddxplus) (Maluuba / Microsoft / Synthea).
- **Cohort Size**: 100,000+ synthetic yet clinically grounded patient presentations across 49 distinct pathologies.
- **Ground Truth Format**: Precise pathological disease diagnosis + list of differential considerations + patient demographic context.

### Mapping DDXPlus to MediKiosk Schema
```json
{
  "ddxplus_case_id": "ddx_001928",
  "patient_context": {
    "age": 54,
    "gender": "M",
    "initial_complaint": "Acute crushing retrosternal chest tightness with radiating pain to left jaw and profuse cold sweating."
  },
  "ground_truth": {
    "primary_diagnosis": "Myocardial infarction",
    "differential_list": [
      "Myocardial infarction",
      "Unstable angina",
      "Gastroesophageal reflux disease (GERD)",
      "Pericarditis"
    ]
  }
}
```

### Metrics to Calculate

#### A. Top-1 Primary Impression Accuracy
$$\text{Top-1 Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{MediKiosk\_Primary\_Impression}_i = \text{Ground\_Truth\_Diagnosis}_i)}{N} \times 100\%$$

#### B. Top-3 & Top-5 Differential Diagnosis (DDx) Inclusion
$$\text{Top-K Inclusion} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{Ground\_Truth\_Diagnosis}_i \in \text{MediKiosk\_Top\_K\_Differentials}_i)}{N} \times 100\%$$

#### C. Target Production Baselines
- **Top-1 Primary Match**: $\ge 68.0\%$
- **Top-3 Differential Inclusion**: $\ge 88.5\%$
- **Top-5 Differential Inclusion**: $\ge 94.0\%$

---

## 4. Dataset 2: MIMIC-IV-ED (5-Tier Emergency Triage / ESI)

### Overview
- **Source**: [PhysioNet MIMIC-IV Emergency Department](https://physionet.org/content/mimic-iv-ed/2.2/)
- **Target Task**: Classifying patients into the standardized 5-level Emergency Severity Index (ESI):
  - **ESI 1**: Immediate Resuscitation / Life-threatening (Cardiac arrest, severe anaphylaxis).
  - **ESI 2**: Emergent / High Risk (STEMI, acute stroke, altered mental state, severe asthma).
  - **ESI 3**: Urgent / Moderate Risk (2+ diagnostic resources needed; stable vitals).
  - **ESI 4**: Less Urgent (1 resource needed; e.g. simple laceration, mild sprain).
  - **ESI 5**: Non-Urgent / Routine OPD (0 resources; medication refill, chronic rash).

### Mapping ESI to MediKiosk Triage
```
ESI 1 & ESI 2 ──► EMERGENCY_ESCALATION (Immediate Red-Flag Alert & Resuscitation Interruption)
ESI 3, 4, 5   ──► ROUTINE_INTAKE (SOCRATES Clinical Exploration & OPD Consultation)
```

### Metrics to Calculate

#### A. Critical Triage Sensitivity (Recall on Emergencies)
$$\text{Sensitivity (ESI 1 & 2)} = \frac{\text{True Emergency Escalations}}{\text{True Emergency Escalations} + \text{False Routine Passes}} \times 100\%$$
> **Clinical Requirement**: Must be **$\ge 99.0\%$**. Zero tolerance for undertriaging life-threatening emergencies.

#### B. Undertriage Rate (Critical Safety Failure)
$$\text{Undertriage Rate} = \frac{\text{Emergencies misclassified as Routine}}{\text{Total True Emergency Cases}} \times 100\%$$
> **Clinical Safety Ceiling**: Must be **$< 1.0\%$**.

#### C. Overtriage Rate (Routine Misclassified as Emergency)
$$\text{Overtriage Rate} = \frac{\text{Routine OPD cases misclassified as Emergency}}{\text{Total True Routine Cases}} \times 100\%$$
> **Efficiency Target**: Must be **$< 5.0\%$** to prevent overwhelming hospital emergency crash teams.

---

## 5. Dataset 3: MTS-Dialog (Conversational Dialogue & Slot Extraction)

### Overview
- **Source**: [MTS-Dialog / ACI-BENCH Clinical Transcripts](https://huggingface.co/datasets/roberta/mts-dialog)
- **Target Task**: Evaluating multi-turn conversational dialogue, slot filling, and doctor summary generation from multi-sentence patient utterances.

### Metrics to Calculate

#### A. Multi-Turn SOCRATES Slot Extraction F1-Score
For each of the 8 SOCRATES axes:
$$\text{Slot F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

| SOCRATES Slot | Target Axes | Benchmark Criterion | Target F1 |
| :--- | :--- | :--- | :---: |
| **S** - Site | Anatomical location | Correct organ / region identified | $\ge 0.95$ |
| **O** - Onset | Temporal start / speed | Duration & progression extracted | $\ge 0.92$ |
| **C** - Character | Qualitative sensation | Burning, sharp, dull, throbbing | $\ge 0.90$ |
| **R** - Radiation | Directional spread | Arm, jaw, back, or localized | $\ge 0.88$ |
| **A** - Associations | Review of Systems (ROS) | Sweating, nausea, fever, dyspnea | $\ge 0.91$ |
| **T** - Timing | Diurnal / cyclical pattern | Morning, post-prandial, constant | $\ge 0.87$ |
| **E** - Exacerbating/Relieving | Triggers / relievers | Rest, food, exertion, medications | $\ge 0.86$ |
| **S** - Severity | Pain intensity rating | Numerical scale (1-10) or qualitative | $\ge 0.94$ |

#### B. Doctor Summary Clinical Faithfulness
- **ROUGE-L Score**: Overlap between generated physician intake note and clinical gold standard ($\ge 0.72$).
- **Medical Entity Hallucination Rate**: Evaluates whether any medication, allergy, or symptom was fabricated ($\le 0.1\%$).

---

## 6. Standardized Evaluation Harness Architecture

When evaluating MediKiosk against DDXPlus, MIMIC-IV, or MTS-Dialog, use the following standardized test structure:

```
benchmark_harness/
├── datasets/
│   ├── ddxplus_test_sample.json         # 500 validated cases
│   ├── mimic_iv_esi_triage_sample.json  # 500 validated ESI cases
│   └── mts_dialog_sample.json           # 200 multi-turn transcripts
├── evaluate_ddx_differential.py         # Computes Top-1, Top-3, Top-5 DDx
├── evaluate_esi_triage_safety.py        # Computes Sensitivity, Undertriage %
├── evaluate_socrates_slots.py           # Computes 8-axis Slot F1 & ROUGE-L
└── export_clinical_report.py            # Generates FDA/NABH-grade audit reports
```

### Clean Execution Pipeline Code Structure
```python
import asyncio
from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn
from app.ai.dialogue.models import PatientContext

async def benchmark_case(case_data: dict) -> dict:
    patient_ctx = PatientContext(
        name=case_data["patient_id"],
        chief_complaint=case_data["patient_utterance"],
        hospital_type=case_data.get("hospital_type", "allopathy")
    )
    
    # Run MediKiosk Turn
    result = await get_next_dialogue_turn(
        patient_context=patient_ctx,
        conversation_history=[{"role": "patient", "content": case_data["patient_utterance"]}],
        max_turns=5
    )
    
    # 1. Triage Safety
    is_escalated = (result.red_flag_alert is not None and result.red_flag_alert.is_red_flag)
    
    # 2. Doctor Decision Support (Differentials)
    primary = result.primary_impression
    differentials = result.provisional_differentials
    
    # 3. SOCRATES Slot Coverage
    slots_filled = result.covered_slots
    
    return {
        "case_id": case_data["case_id"],
        "is_escalated": is_escalated,
        "primary_impression": primary,
        "differentials": differentials,
        "slots_filled": slots_filled
    }
```

---

## 7. Summary Benchmark Reference Scorecard

| Evaluation Dimension | Benchmark Dataset | Target Metric | Clinical Significance |
| :--- | :--- | :---: | :--- |
| **Emergency Triage Sensitivity** | MIMIC-IV-ED | **$\ge 99.0\%$** | Never misses critical emergencies (STEMI, stroke, shock). |
| **Undertriage Rate** | MIMIC-IV-ED | **$< 1.0\%$** | Zero dangerous downgrades to routine OPD. |
| **Top-1 Primary Match** | DDXPlus | **$\ge 68.0\%$** | First diagnostic impression aligns with gold standard. |
| **Top-3 Differential Inclusion** | DDXPlus | **$\ge 88.5\%$** | Attending physician receives comprehensive differential list. |
| **SOCRATES Slot Accuracy** | MTS-Dialog | **$\ge 91.0\%$ F1** | Comprehensive 8-axis clinical intake without missing details. |
| **Hallucination Rate** | MTS-Dialog | **$\le 0.1\%$** | Zero fabricated clinical history or medications. |
