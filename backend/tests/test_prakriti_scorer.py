# backend/tests/test_prakriti_scorer.py
import pytest
from app.ai.ayurveda.prakriti_scorer import score_prakriti

def test_prakriti_samadoshaja_equidistributed():
    # 4 Vata, 4 Pitta, 4 Kapha = 33.33% each
    answers = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    result = score_prakriti(answers)
    
    assert result.classification == "Samadoshaja"
    assert "Sama Prakriti" in result.prakriti_type
    assert result.scores.vata == 33.33
    assert result.scores.pitta == 33.33
    assert result.scores.kapha == 33.34

def test_prakriti_ekadoshaja_vata_dominant():
    # 8 Vata (66.67%), 2 Pitta (16.67%), 2 Kapha (16.67%)
    answers = ["A"] * 8 + ["B"] * 2 + ["C"] * 2
    result = score_prakriti(answers)
    
    assert result.classification == "Ekadoshaja"
    assert result.dominant_dosha == "Vata"
    assert result.prakriti_type == "Vataja Prakriti"
    assert result.scores.vata == 66.67

def test_prakriti_ekadoshaja_pitta_dominant():
    # 7 Pitta (58.33%), 3 Vata (25.0%), 2 Kapha (16.67%)
    answers = ["B"] * 7 + ["A"] * 3 + ["C"] * 2
    result = score_prakriti(answers)
    
    assert result.classification == "Ekadoshaja"
    assert result.dominant_dosha == "Pitta"
    assert result.prakriti_type == "Pittaja Prakriti"

def test_prakriti_dvidoshaja_pitta_vata():
    # 6 Pitta (50%), 5 Vata (41.67%), 1 Kapha (8.33%) -> difference is 1 point (<2), so Dvidoshaja
    answers = ["B"] * 6 + ["A"] * 5 + ["C"] * 1
    result = score_prakriti(answers)
    
    assert result.classification == "Dvidoshaja"
    assert "Pitta-Vata" in result.prakriti_type
    assert result.dominant_dosha == "Pitta"
    assert result.secondary_dosha == "Vata"

def test_prakriti_dict_input():
    answers_dict = {f"prakriti_{i:02d}": "B" for i in range(1, 13)}
    result = score_prakriti(answers_dict)
    
    assert result.classification == "Ekadoshaja"
    assert result.prakriti_type == "Pittaja Prakriti"
    assert result.scores.pitta == 100.0
