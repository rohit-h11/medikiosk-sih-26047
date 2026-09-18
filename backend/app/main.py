from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    setup_exception_handlers
)
from app.api.v1.router import api_router

import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm embedding model in background thread to avoid 17s cold start on first turn
    async def _preload():
        try:
            from app.ai.rag.retriever import get_embedding_model
            await asyncio.to_thread(get_embedding_model)
        except Exception:
            pass
    asyncio.create_task(_preload())
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="MediKiosk — AI Clinical History Software Platform API Backend (Ministry of Ayush / AIIA)",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 1. Register Essential Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Setup Exception Handling
setup_exception_handlers(app)

# 3. Mount API V1 Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "ok"
    }
