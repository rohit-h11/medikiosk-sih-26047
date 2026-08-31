import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "MediKiosk API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & CORS
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",  # React Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "medikiosk_super_secret_jwt_key_2026_change_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # Supabase Settings
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "your-anon-key")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "your-supabase-jwt-secret")
    
    # ABDM / ABHA Sandbox Credentials (Indian Health ID Integration)
    ABDM_SANDBOX_URL: str = os.getenv("ABDM_SANDBOX_URL", "https://dev.abdm.gov.in/gateway/v0.5")
    ABDM_CLIENT_ID: str = os.getenv("ABDM_CLIENT_ID", "")
    ABDM_CLIENT_SECRET: str = os.getenv("ABDM_CLIENT_SECRET", "")
    
    # Bhashini AI API Credentials (Indian Languages ASR/TTS/Translation)
    BHASHINI_USER_ID: str = os.getenv("BHASHINI_USER_ID", "")
    BHASHINI_API_KEY: str = os.getenv("BHASHINI_API_KEY", "")
    BHASHINI_PIPELINE_ID: str = os.getenv("BHASHINI_PIPELINE_ID", "64115e4f440356001275d691")
    BHASHINI_INFERENCE_API_KEY: str = os.getenv("BHASHINI_INFERENCE_API_KEY", "")
    
    # Groq API Key (Free Instant Whisper-Large-v3 ASR Fallback)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
