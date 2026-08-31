from typing import Optional
from pydantic import BaseModel, EmailStr, Field

# --- Supabase Auth (Staff / Doctor) Schemas ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: str
    role: str = Field(default="doctor", description="User role: doctor | receptionist | admin")
    specialization: Optional[str] = Field(default=None, description="Ayurvedic / Allopathic specialization")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "doctor"
    specialization: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

# --- ABDM / ABHA Auth (Patient Kiosk) Schemas ---

class ABHARequestOTP(BaseModel):
    abha_number: str = Field(..., description="14-digit ABHA Number or registered Mobile Number")

class ABHARequestOTPResponse(BaseModel):
    txn_id: str
    message: str = "OTP sent successfully to registered mobile number"

class ABHAVerifyOTP(BaseModel):
    txn_id: str
    otp: str = Field(..., min_length=4, max_length=6, description="OTP received on patient mobile")

class ABHASessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient_id: str
    abha_number: str
    abha_address: Optional[str] = None
    name: str
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    mobile: Optional[str] = None
