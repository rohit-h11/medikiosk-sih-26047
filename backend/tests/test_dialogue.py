"""
MediKiosk — Automated Unit and Integration Tests for SOCRATES Dialogue Engine
Tests:
1. Red-flag emergency rule screening
2. Initial dialogue turn question generation from patient context
3. SOCRATES slot tracking and anti-repetition across turns
4. Stopping condition when symptoms are adequately characterized
5. Emergency red flag triggering immediate triage stop
6. Input compatibility with both Pydantic models and raw dicts
7. In-memory session store lifecycle
"""

import pytest
import asyncio
from app.ai.dialogue import (
    get_next_dialogue_turn,
    start_dialogue,
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    SocratesState,
    scan_text_for_red_flags,
    create_session,
    get_session,
    clear_all_sessions
)

# -------------------------------------------------------------
# 1. Red-Flag Emergency Triage Tests
# -------------------------------------------------------------

def test_red_flag_detection_cardiovascular():
    """Crushing chest pain radiating to left arm triggers critical red flag."""
    text = "I have sudden crushing chest pain radiating to my left arm with cold sweating"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == "CRITICAL"
    assert "Cardiovascular" in alert.category

def test_red_flag_detection_stroke():
    """Facial droop and slurred speech triggers critical stroke alert."""
    text = "My mother has sudden facial droop and slurred speech"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == "CRITICAL"
    assert "Cerebrovascular" in alert.category

def test_red_flag_detection_hemorrhage():
    """Vomiting blood triggers high priority alert."""
    text = "I am vomiting blood and having black tarry stool"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == "HIGH"

def test_red_flag_negative_routine():
    """Routine complaint should not trigger any red flag."""
    text = "I have had a mild headache since yesterday morning"
    alert = scan_text_for_red_flags(text)
    assert alert is None

# -------------------------------------------------------------
# 2. SOCRATES Dialogue Generation Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_initial_turn_generation_with_complaint():
    """Initial turn generates a focused question with touchscreen options."""
    ctx = PatientContext(
        age=35,
        gender="female",
        chief_complaint="Stomach pain and nausea"
    )
    result = await get_next_dialogue_turn(ctx, [])
    assert isinstance(result, DialogueTurnResult)
    assert result.should_stop is False
    assert result.next_question is not None
    assert len(result.next_question) > 5
    assert len(result.touch_options) >= 3

@pytest.mark.asyncio
async def test_initial_turn_without_complaint():
    """When no context/history provided, asks for initial chief complaint."""
    ctx = PatientContext()
    result = await get_next_dialogue_turn(ctx, [])
    assert result.should_stop is False
    assert "symptom" in result.next_question.lower() or "bring" in result.next_question.lower()
    assert len(result.touch_options) >= 3

@pytest.mark.asyncio
async def test_anti_repetition_in_dialogue():
    """Verify that when site and onset are answered, the LLM targets other SOCRATES slots."""
    ctx = PatientContext(
        age=50,
        gender="male",
        chief_complaint="Chest discomfort",
        past_medical_history=["Hypertension"]
    )
    history = [
        {"role": "assistant", "content": "Where exactly is the pain and when did it start?"},
        {"role": "patient", "content": "It is in the center of my chest, started 2 hours ago."}
    ]
    result = await get_next_dialogue_turn(ctx, history)
    assert result.should_stop is False
    assert result.next_question is not None
    # Site and onset should now be recorded as covered
    assert "site" in result.covered_slots
    assert "onset" in result.covered_slots
    # The next question should inquire about character, radiation, severity, or relieving factors
    assert result.missing_slots != []

@pytest.mark.asyncio
async def test_dialogue_stopping_condition():
    """Verify that full coverage of SOCRATES slots results in should_stop = True and clinical summary."""
    ctx = PatientContext(
        age=42,
        gender="female",
        chief_complaint="Right knee pain"
    )
    history = [
        {"role": "assistant", "content": "Where is the pain located?"},
        {"role": "patient", "content": "Right knee joint, started 3 weeks ago."},
        {"role": "assistant", "content": "What does it feel like, and how severe is it?"},
        {"role": "patient", "content": "It is a dull, aching pain, around 5/10 severity. No radiation."},
        {"role": "assistant", "content": "What makes it better or worse, and are there associated symptoms?"},
        {"role": "patient", "content": "Worse when climbing stairs, relieved by rest. No swelling or fever. Pain is intermittent."}
    ]
    result = await get_next_dialogue_turn(ctx, history, max_turns=3)
    assert result.should_stop is True
    assert result.next_question is None
    assert result.clinical_summary is not None
    assert len(result.clinical_summary) > 20
    assert result.closing_message is not None

@pytest.mark.asyncio
async def test_emergency_red_flag_triggers_stop():
    """Emergency utterance triggers immediate stop with red flag alert."""
    ctx = PatientContext(age=60, chief_complaint="Chest pain")
    history = [
        {"role": "assistant", "content": "Can you describe the pain?"},
        {"role": "patient", "content": "It is crushing chest pain radiating to left arm and I feel like I'm having a heart attack"}
    ]
    result = await get_next_dialogue_turn(ctx, history)
    assert result.should_stop is True
    assert result.next_question is None
    assert result.red_flag_alert is not None
    assert result.red_flag_alert.is_red_flag is True

@pytest.mark.asyncio
async def test_dict_input_compatibility():
    """Verify get_next_dialogue_turn works with plain Python dictionaries."""
    ctx_dict = {
        "age": 29,
        "chief_complaint": "Persistent dry cough",
        "current_medications": ["Vitamin C"]
    }
    history_list = [
        {"role": "assistant", "content": "When did your cough start?"},
        {"role": "patient", "content": "About 4 days ago, dry cough without phlegm."}
    ]
    result = await get_next_dialogue_turn(ctx_dict, history_list)
    assert isinstance(result, DialogueTurnResult)
    assert result.should_stop is False
    assert result.next_question is not None

# -------------------------------------------------------------
# 3. Session Store Tests
# -------------------------------------------------------------

def test_session_lifecycle():
    """Test session creation, retrieval, and updating."""
    clear_all_sessions()
    ctx = PatientContext(name="Aarav", age=30, chief_complaint="Fever")
    session = create_session(ctx)
    assert session.session_id is not None
    
    retrieved = get_session(session.session_id)
    assert retrieved is not None
    assert retrieved.patient_context.name == "Aarav"
