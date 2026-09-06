# backend/tests/test_dialogue_protocols.py
import pytest
from app.ai.dialogue.protocols.registry import get_protocol
from app.ai.dialogue.protocols.allopathy import AllopathyProtocol
from app.ai.dialogue.protocols.ayurveda import AyurvedaProtocol
from app.ai.dialogue.models import PatientContext

def test_protocol_registry_resolution():
    proto_allo = get_protocol("allopathy")
    assert isinstance(proto_allo, AllopathyProtocol)
    assert proto_allo.system_name == "allopathy"
    assert "site" in proto_allo.target_slots

    proto_ayu = get_protocol("ayurveda")
    assert isinstance(proto_ayu, AyurvedaProtocol)
    assert proto_ayu.system_name == "ayurveda"
    assert "vikriti_dosha" in proto_ayu.target_slots

    # Default fallback
    proto_def = get_protocol("unknown_dept")
    assert isinstance(proto_def, AllopathyProtocol)

def test_ayurveda_prompt_includes_prakriti_baseline():
    proto_ayu = get_protocol("ayurveda")
    ctx = PatientContext(
        patient_id="PAT-TEST",
        hospital_type="ayurveda",
        prakriti_profile="Pitta-Vata Prakriti",
        chief_complaint="Acid reflux and burning in stomach"
    )
    prompt = proto_ayu.build_system_prompt(ctx, rag_context_snippets=["EB-4: Amlapitta"])
    
    assert "Pitta-Vata Prakriti" in prompt
    assert "EB-4: Amlapitta" in prompt
    assert "Vikriti" in prompt
