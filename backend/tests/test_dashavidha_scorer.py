# backend/tests/test_dashavidha_scorer.py
import pytest
from app.ai.ayurveda.dashavidha_scorer import score_dashavidha, calculate_vaya_category

def test_vaya_calculation():
    assert calculate_vaya_category(12) == "Bala"
    assert calculate_vaya_category(35) == "Madhya"
    assert calculate_vaya_category(68) == "Vriddha"

def test_dashavidha_scoring():
    answers = {
        "sattva": "Pravara",
        "satmya": "Madhyama",
        "vyayama_shakti": "Avara"
    }
    state = score_dashavidha(answers, age=28)
    
    assert state.sattva == "Pravara"
    assert state.satmya == "Madhyama"
    assert state.vyayama_shakti == "Avara"
    assert state.vaya_category == "Madhya"
    assert "Deferred to Attending Vaidya" in state.sara
