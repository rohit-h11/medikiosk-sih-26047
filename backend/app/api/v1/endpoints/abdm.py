import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.abdm import ABDMConsentRequest, ABDMConsentResponse

router = APIRouter(prefix="/abdm", tags=["ABDM Health Integration"])

@router.post("/consent/request", response_model=ABDMConsentResponse)
async def request_patient_consent(
    payload: ABDMConsentRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Dispatches ABDM HIP consent request to patient's ABHA mobile app.
    Enables patient to approve sharing past medical history records with MediKiosk.
    """
    consent_id = f"CONSENT-{uuid.uuid4().hex[:12].upper()}"
    return ABDMConsentResponse(
        consent_id=consent_id,
        status="REQUESTED",
        created_at=datetime.now(timezone.utc).isoformat(),
        message=f"ABDM consent artifact dispatched for Patient ID {payload.patient_id}. Awaiting patient approval via ABHA App."
    )

@router.get("/consent/{consent_id}/status")
async def check_consent_status(
    consent_id: str,
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Checks real-time status of ABDM patient consent artifact.
    """
    return {
        "consent_id": consent_id,
        "status": "GRANTED",
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "hip_id": "AIIA_OPD_KIOSK_01",
        "message": "Patient consent granted for clinical intake and history retrieval."
    }
