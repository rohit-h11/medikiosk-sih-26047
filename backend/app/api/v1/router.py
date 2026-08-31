from fastapi import APIRouter
from app.api.v1.endpoints import auth, abdm, audio

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(abdm.router)
api_router.include_router(audio.router)

