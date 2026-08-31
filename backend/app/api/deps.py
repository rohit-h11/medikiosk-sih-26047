from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_jwt_token
from app.schemas.auth import UserProfile

security_bearer = HTTPBearer(auto_error=True)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer)
) -> UserProfile:
    """
    FastAPI dependency that extracts Bearer token, verifies JWT signature,
    and resolves the authenticated user profile.
    """
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or invalid/expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract identity & claims (supporting standard JWT, Supabase JWT, and Patient Session JWTs)
    user_id = payload.get("sub") or payload.get("user_id") or payload.get("patient_id")
    email = payload.get("email") or f"patient_{user_id}@abha.internal"
    
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role") or payload.get("role") or "doctor"
    full_name = user_metadata.get("full_name") or payload.get("name") or "Healthcare Provider"
    specialization = user_metadata.get("specialization") or payload.get("specialization")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserProfile(
        id=str(user_id),
        email=email,
        full_name=full_name,
        role=role,
        specialization=specialization
    )

def require_roles(allowed_roles: List[str]):
    """
    Dependency factory to restrict route access based on user roles.
    Example usage: Depends(require_roles(["doctor", "admin"]))
    """
    async def role_checker(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' is not authorized to perform this operation. Allowed: {allowed_roles}"
            )
        return current_user
    return role_checker

async def get_current_active_doctor(
    current_user: UserProfile = Depends(require_roles(["doctor", "admin"]))
) -> UserProfile:
    """Dependency that guarantees the request comes from an authenticated Doctor or Admin."""
    return current_user
