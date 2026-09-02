from fastapi import APIRouter
from app.api.v1.endpoints import auth, abdm, ocr
from app.api.v1.endpoints import auth, abdm, audio, dialogue

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(abdm.router)
api_router.include_router(ocr.router)

api_router.include_router(audio.router)
api_router.include_router(dialogue.router)
