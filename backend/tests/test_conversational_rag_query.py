# backend/tests/test_conversational_rag_query.py
"""
Unit tests for Conversational RAG Query Synthesis (Anaphora & Ellipsis Resolution).
Verifies that multi-turn clinical context (doctor question + patient answer + chief complaint)
is correctly synthesized so vector search over 20-30+ patient documents captures
clinical entities that would otherwise be missed from isolated patient utterances.
"""

import pytest
from app.ai.rag.retriever import build_conversational_rag_query

def test_full_triad_query_synthesis():
    """Tests the full triad: Chief Complaint + Doctor Question + Patient Answer."""
    complaint = "Stomach and chest burning"
    question = "Does this burning sensation spread to your chest, neck, or down your left arm?"
    answer = "Sharp burn, especially when walking."

    query = build_conversational_rag_query(
        primary_complaint=complaint,
        last_doctor_question=question,
        patient_utterance=answer
    )

    assert "Complaint: Stomach and chest burning" in query
    assert "Doctor Question: Does this burning sensation spread to your chest, neck, or down your left arm?" in query
    assert "Patient Answer: Sharp burn, especially when walking." in query
    # Verify clinical anchors that solve the anaphora problem
    assert "left arm" in query
    assert "chest" in query
    assert "Sharp burn" in query
    assert "walking" in query

def test_first_turn_without_prior_question():
    """Tests Turn 1 when no doctor question exists in history yet."""
    complaint = "Type 2 Diabetes Mellitus"
    answer = "I have come for my routine sugar test and I have knee pain."

    query = build_conversational_rag_query(
        primary_complaint=complaint,
        last_doctor_question="",
        patient_utterance=answer
    )

    assert "Complaint: Type 2 Diabetes Mellitus" in query
    assert "Patient Answer: I have come for my routine sugar test and I have knee pain." in query
    assert "Doctor Question" not in query

def test_walk_in_without_prior_complaint():
    """Tests when patient arrives without a registered complaint string."""
    question = "What brings you to the hospital today?"
    answer = "High fever and shivering since yesterday."

    query = build_conversational_rag_query(
        primary_complaint=None,
        last_doctor_question=question,
        patient_utterance=answer
    )

    assert "Doctor Question: What brings you to the hospital today?" in query
    assert "Patient Answer: High fever and shivering since yesterday." in query
    assert "Complaint:" not in query

def test_ayurveda_vikriti_inquiry():
    """Tests Ayurvedic conversational RAG query synthesis for doshic/agni exploration."""
    complaint = "Amlapitta"
    question = "Do you experience sour belching or throat burning after spicy meals?"
    answer = "Yes, very sour liquid rises in morning."

    query = build_conversational_rag_query(
        primary_complaint=complaint,
        last_doctor_question=question,
        patient_utterance=answer
    )

    assert "Complaint: Amlapitta" in query
    assert "sour belching" in query
    assert "throat burning" in query
    assert "sour liquid rises" in query

def test_empty_inputs_graceful_fallback():
    """Tests that completely empty inputs return a safe fallback string."""
    query = build_conversational_rag_query(
        primary_complaint="",
        last_doctor_question="   ",
        patient_utterance=None
    )
    assert query == "symptoms"

def test_whitespace_stripping():
    """Tests that leading/trailing whitespaces are properly trimmed."""
    query = build_conversational_rag_query(
        primary_complaint="  Headache  ",
        last_doctor_question="  Is it on one side?  ",
        patient_utterance="  Yes, left temple.  "
    )
    assert query == "Complaint: Headache | Doctor Question: Is it on one side? | Patient Answer: Yes, left temple."
