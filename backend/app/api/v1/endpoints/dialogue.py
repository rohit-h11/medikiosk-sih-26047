"""
MediKiosk — Clinical Dialogue API Endpoints
Provides REST API endpoints for hospital kiosk touchscreens:
- /start: Initialize patient interview session and retrieve first SOCRATES question
- /turn: Submit patient response or touchscreen choice and receive next turn
- /session/{session_id}: View active session state and SOCRATES slot status
- /red-flag-check: Fast emergency screening
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.dialogue import (
    get_next_dialogue_turn,
    PatientContext,
    ConversationMessage,
    DialogueTurnResult,
    RedFlagAlert,
    scan_text_for_red_flags,
    create_session,
    get_session,
    save_session,
    DialogueSession
)

router = APIRouter(prefix="/dialogue", tags=["Dialogue Management & Clinical Intake"])

class StartSessionRequest(BaseModel):
    patient_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    chief_complaint: Optional[str] = None
    chief_complaint_hint: Optional[str] = None
    symptoms: List[str] = Field(default_factory=list)
    past_medical_history: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    vitals: Dict[str, Any] = Field(default_factory=dict)
    extracted_document_context: Optional[Dict[str, Any]] = None
    language: str = "en"
    max_turns: int = 10

class DialogueTurnRequest(BaseModel):
    session_id: str
    patient_response: str
    selected_option_id: Optional[str] = None

class SessionTurnResponse(BaseModel):
    session_id: str
    turn_number: int
    result: DialogueTurnResult

class RedFlagCheckRequest(BaseModel):
    text: str = Field(..., description="Patient utterance or symptom description to evaluate for emergencies")

class RedFlagCheckResponse(BaseModel):
    is_red_flag: bool
    alert: Optional[RedFlagAlert] = None

@router.post("/start", response_model=SessionTurnResponse, status_code=status.HTTP_201_CREATED)
async def start_dialogue_session(request: StartSessionRequest):
    """
    Initialize a new clinical dialogue interview session.
    Takes patient context (demographics, complaint, medical history) and calls the LLM
    to generate the initial question with touch-screen options according to SOCRATES.
    """
    try:
        complaint = request.chief_complaint or request.chief_complaint_hint
        ctx = PatientContext(
            patient_id=request.patient_id,
            name=request.name,
            age=request.age,
            gender=request.gender,
            chief_complaint=complaint,
            symptoms=request.symptoms,
            past_medical_history=request.past_medical_history,
            current_medications=request.current_medications,
            allergies=request.allergies,
            vitals=request.vitals,
            extracted_docs=request.extracted_document_context,
            language=request.language
        )

        session = create_session(patient_context=ctx, max_turns=request.max_turns)

        # Call the LLM with empty history to get the initial question
        turn_result = await get_next_dialogue_turn(
            patient_context=ctx,
            conversation_history=[],
            max_turns=request.max_turns
        )

        session.last_result = turn_result
        session.socrates_state = turn_result.socrates_state
        session.turn_count = 1
        if turn_result.should_stop:
            session.is_completed = True

        if turn_result.next_question:
            session.history.append(ConversationMessage(
                role="assistant",
                content=turn_result.next_question
            ))

        save_session(session)

        return SessionTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            result=turn_result
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start dialogue session: {str(e)}"
        )

@router.post("/turn", response_model=SessionTurnResponse)
async def submit_dialogue_turn(request: DialogueTurnRequest):
    """
    Submit a patient utterance or touchscreen choice selection.
    Appends the response to conversation history, invokes the LLM to assess SOCRATES progress,
    and returns the next relevant clinical question or decides to stop.
    """
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dialogue session '{request.session_id}' not found."
        )

    if session.is_completed:
        return SessionTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            result=session.last_result or DialogueTurnResult(
                should_stop=True,
                closing_message="This clinical intake session has already concluded.",
                socrates_state=session.socrates_state
            )
        )

    try:
        # Record patient utterance into conversation history
        session.history.append(ConversationMessage(
            role="patient",
            content=request.patient_response,
            slot_tag=request.selected_option_id
        ))

        # Call LLM with full conversation history & patient context
        turn_result = await get_next_dialogue_turn(
            patient_context=session.patient_context,
            conversation_history=session.history,
            max_turns=session.max_turns,
            current_socrates_state=session.socrates_state
        )

        session.turn_count += 1
        session.last_result = turn_result
        session.socrates_state = turn_result.socrates_state

        if turn_result.should_stop:
            session.is_completed = True
        elif turn_result.next_question:
            session.history.append(ConversationMessage(
                role="assistant",
                content=turn_result.next_question
            ))

        save_session(session)

        return SessionTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            result=turn_result
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dialogue turn: {str(e)}"
        )

@router.get("/session/{session_id}", response_model=DialogueSession)
async def get_dialogue_session_endpoint(session_id: str):
    """
    Retrieve full session details, conversation history, and accumulated SOCRATES state.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dialogue session '{session_id}' not found."
        )
    return session

@router.post("/red-flag-check", response_model=RedFlagCheckResponse)
async def check_red_flags(request: RedFlagCheckRequest):
    """
    Standalone sub-5ms rule-based check for acute emergency medical symptoms.
    """
    alert = scan_text_for_red_flags(request.text)
    return RedFlagCheckResponse(
        is_red_flag=bool(alert and alert.is_red_flag),
        alert=alert
    )
