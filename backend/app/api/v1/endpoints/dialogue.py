from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.dialogue import (
    DialogueStartRequest,
    DialogueTurnInput,
    DialogueTurnResponse,
    DialogueSessionState,
    RedFlagAlert
)
from app.ai.dialogue import (
    DialogueController,
    get_session,
    scan_text_for_red_flags,
    load_ccras_battery,
    search_namaste_codes,
    get_namaste_item_by_code,
    NamasteDiagnosisItem
)

router = APIRouter(prefix="/dialogue", tags=["Dialogue Management & Clinical Intake"])

class RedFlagCheckRequest(BaseModel):
    text: str = Field(..., description="Patient utterance or symptom description to evaluate for emergencies")

class RedFlagCheckResponse(BaseModel):
    is_red_flag: bool
    alert: RedFlagAlert = None

@router.post("/start", response_model=DialogueTurnResponse, status_code=status.HTTP_201_CREATED)
async def start_dialogue_session(request: DialogueStartRequest):
    """
    Initialize a new clinical dialogue interview session.
    Supports both Allopathic SOCRATES intake and Ayurvedic CCRAS-PAS intake.
    """
    try:
        response = await DialogueController.start_session(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start dialogue session: {str(e)}"
        )

@router.post("/turn", response_model=DialogueTurnResponse)
async def submit_dialogue_turn(request: DialogueTurnInput):
    """
    Submit a patient utterance or touchscreen choice selection.
    Evaluates red-flags in real-time (<5ms), updates clinical slots, and generates next follow-up.
    """
    try:
        response = await DialogueController.process_turn(request)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dialogue turn: {str(e)}"
        )

@router.get("/session/{session_id}", response_model=DialogueSessionState)
async def get_dialogue_session(session_id: str):
    """
    Retrieve full session state, transcript history, SOCRATES slots, and CCRAS scores.
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
    Standalone sub-50ms rule-based check for acute emergency medical symptoms.
    """
    alert = scan_text_for_red_flags(request.text)
    return RedFlagCheckResponse(
        is_red_flag=bool(alert and alert.is_red_flag),
        alert=alert
    )

@router.get("/ccras-pas/battery")
async def get_ccras_pas_battery() -> Dict[str, Any]:
    """
    Retrieve the official CCRAS Prakriti Assessment Scale (PAS) standardized question battery.
    """
    return load_ccras_battery()

@router.get("/namaste-lookup", response_model=List[NamasteDiagnosisItem])
async def search_namaste(query: str = "", limit: int = 5):
    """
    Search standardized AYUSH diagnoses mapped to NAMASTE codes and WHO ICD-11 (TM2).
    Search by Sanskrit condition (e.g. 'Sandhivata'), English translation (e.g. 'Osteoarthritis'),
    or symptom keyword.
    """
    return search_namaste_codes(query=query, limit=limit)

@router.get("/namaste-lookup/{code}", response_model=NamasteDiagnosisItem)
async def get_namaste_by_code(code: str):
    """
    Retrieve full NAMASTE & ICD-11 TM2 coding entry and recommended Ayurvedic formulations by code.
    """
    item = get_namaste_item_by_code(code)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAMASTE / ICD-11 code '{code}' not found in standardized registry."
        )
    return item
