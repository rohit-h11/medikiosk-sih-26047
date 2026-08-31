from typing import Optional, List
from pydantic import BaseModel, Field

class ABDMConsentRequest(BaseModel):
    patient_id: str
    purpose: str = Field(default="CAREMGT", description="Care Management / Consultation intake")
    hip_id: str = Field(default="AIIA_OPD_KIOSK_01")
    requested_records: List[str] = Field(default=["DiagnosticReport", "Prescription", "OPConsultation"])

class ABDMConsentResponse(BaseModel):
    consent_id: str
    status: str = "REQUESTED"
    created_at: str
    message: str = "Consent request dispatched to patient ABHA app"
