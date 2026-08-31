from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from app.config import settings

def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a JWT token (issued by Supabase Auth or internal backend).
    Returns the decoded payload if valid, None otherwise.
    """
    try:
        # First attempt decoding using SUPABASE_JWT_SECRET if provided, else fallback to internal JWT_SECRET_KEY
        secret = settings.SUPABASE_JWT_SECRET if settings.SUPABASE_JWT_SECRET != "your-supabase-jwt-secret" else settings.JWT_SECRET_KEY
        
        # Try decoding without strict issuer verification to support both local dev and Supabase Cloud
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False}
        )
        return payload
    except jwt.PyJWTError:
        # Fallback to internal secret key
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_aud": False}
            )
            return payload
        except jwt.PyJWTError:
            return None

def create_patient_session_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a secure JWT token for ABHA-authenticated patient sessions.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": "medikiosk-backend",
        "type": "patient_session"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
