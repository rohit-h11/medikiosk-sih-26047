from datetime import datetime, timezone
from typing import Dict, Any, List
from app.schemas.dialogue import (
    DialogueSessionState,
    UnifiedClinicalHistory,
    HistoryType
)
from app.ai.dialogue.namaste_bridge import search_namaste_codes

def convert_dialogue_to_fhir_r4(session: DialogueSessionState) -> Dict[str, Any]:
    """
    Convert a completed DialogueSessionState and UnifiedClinicalHistory into a
    FHIR R4 compliant Document Bundle containing Patient, Encounter, Condition,
    Observation, and QuestionnaireResponse resources.
    """
    history: UnifiedClinicalHistory = session.clinical_history
    std = history.standard_history
    ayur = history.ayurvedic_assessment

    now_iso = datetime.now(timezone.utc).isoformat()
    bundle_id = f"bundle-{session.session_id}"

    entries: List[Dict[str, Any]] = []

    # 1. Patient Resource
    patient_entry = {
        "fullUrl": f"urn:uuid:patient-{session.patient_id}",
        "resource": {
            "resourceType": "Patient",
            "id": session.patient_id,
            "identifier": [
                {
                    "system": "https://healthid.abdm.gov.in",
                    "value": session.patient_id
                }
            ],
            "active": True
        }
    }
    entries.append(patient_entry)

    # 2. Encounter Resource
    encounter_id = f"enc-{session.session_id}"
    encounter_entry = {
        "fullUrl": f"urn:uuid:{encounter_id}",
        "resource": {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "finished" if session.is_completed else "in-progress",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "Ambulatory / OPD Triage"
            },
            "subject": {
                "reference": f"Patient/{session.patient_id}"
            },
            "period": {
                "start": session.created_at,
                "end": session.updated_at
            }
        }
    }
    entries.append(encounter_entry)

    # 3. Condition Resource (Chief Complaint / Assessment)
    condition_id = f"cond-{session.session_id}"
    coding_list = []
    
    # Check if Ayurvedic NAMASTE mapping applies
    if session.history_type == HistoryType.AYURVEDIC and std.chief_complaint:
        namaste_results = search_namaste_codes(std.chief_complaint, limit=1)
        if namaste_results:
            top_nam = namaste_results[0]
            coding_list.append({
                "system": "https://namstp.ayush.gov.in/#/sat",
                "code": top_nam.namaste_code,
                "display": top_nam.ayurvedic_name
            })
            coding_list.append({
                "system": "http://id.who.int/icd/release/11/mms",
                "code": top_nam.icd11_tm2_code,
                "display": top_nam.icd11_title
            })

    condition_entry = {
        "fullUrl": f"urn:uuid:{condition_id}",
        "resource": {
            "resourceType": "Condition",
            "id": condition_id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "provisional"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis",
                            "display": "Encounter Diagnosis"
                        }
                    ]
                }
            ],
            "code": {
                "text": std.chief_complaint or "Unspecified Symptom",
                "coding": coding_list
            },
            "subject": {
                "reference": f"Patient/{session.patient_id}"
            },
            "encounter": {
                "reference": f"Encounter/{encounter_id}"
            },
            "note": [
                {"text": f"HPI: {std.hpi}"},
                {"text": f"SOCRATES: Site={std.socrates.site}, Severity={std.socrates.severity_score}/10, Character={std.socrates.character}"}
            ]
        }
    }
    entries.append(condition_entry)

    # 4. Observation: Pain Severity / Clinical Severity Score
    if std.socrates and std.socrates.severity_score:
        obs_sev_id = f"obs-sev-{session.session_id}"
        obs_sev = {
            "fullUrl": f"urn:uuid:{obs_sev_id}",
            "resource": {
                "resourceType": "Observation",
                "id": obs_sev_id,
                "status": "final",
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "72514-3",
                            "display": "Pain severity - 0-10 verbal numeric rating"
                        }
                    ],
                    "text": "Pain Severity Score"
                },
                "subject": {"reference": f"Patient/{session.patient_id}"},
                "valueInteger": std.socrates.severity_score
            }
        }
        entries.append(obs_sev)

    # 5. Observation: Ayurvedic Prakriti Breakdown (If Ayurvedic mode)
    if ayur and ayur.prakriti and ayur.prakriti.total_answers > 0:
        obs_prak_id = f"obs-prak-{session.session_id}"
        obs_prak = {
            "fullUrl": f"urn:uuid:{obs_prak_id}",
            "resource": {
                "resourceType": "Observation",
                "id": obs_prak_id,
                "status": "final",
                "code": {
                    "coding": [
                        {
                            "system": "https://ccras.res.in/ccras_pas",
                            "code": "CCRAS-PAS-01",
                            "display": "CCRAS Prakriti Assessment Phenotype"
                        }
                    ],
                    "text": "CCRAS Prakriti Assessment"
                },
                "subject": {"reference": f"Patient/{session.patient_id}"},
                "valueString": ayur.prakriti.dominant_prakriti,
                "component": [
                    {
                        "code": {"text": "Vata Percentage"},
                        "valueQuantity": {"value": ayur.prakriti.vata_percentage, "unit": "%"}
                    },
                    {
                        "code": {"text": "Pitta Percentage"},
                        "valueQuantity": {"value": ayur.prakriti.pitta_percentage, "unit": "%"}
                    },
                    {
                        "code": {"text": "Kapha Percentage"},
                        "valueQuantity": {"value": ayur.prakriti.kapha_percentage, "unit": "%"}
                    }
                ]
            }
        }
        entries.append(obs_prak)

    # 6. QuestionnaireResponse Resource (Turn-by-turn transcript)
    qr_id = f"qr-{session.session_id}"
    qr_items = []
    for turn in session.turns:
        qr_items.append({
            "linkId": f"turn-{turn.turn_number}",
            "text": f"[{turn.speaker.upper()}] {turn.utterance}",
            "answer": [
                {
                    "valueString": turn.utterance
                }
            ]
        })

    qr_entry = {
        "fullUrl": f"urn:uuid:{qr_id}",
        "resource": {
            "resourceType": "QuestionnaireResponse",
            "id": qr_id,
            "status": "completed" if session.is_completed else "in-progress",
            "subject": {"reference": f"Patient/{session.patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "authored": now_iso,
            "item": qr_items
        }
    }
    entries.append(qr_entry)

    # Complete FHIR R4 Bundle
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "document",
        "timestamp": now_iso,
        "entry": entries
    }

    return bundle
