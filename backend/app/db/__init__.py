# backend/app/db/__init__.py
import os
import logging
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("medikiosk.db")

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

supabase_client: Optional[Client] = None
_supabase_enabled: bool = False

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        _supabase_enabled = True
        logger.info(f"Connected to Supabase at {SUPABASE_URL}")
    except Exception as e:
        logger.warning(f"Could not initialize Supabase client: {e}")
        _supabase_enabled = False

def get_supabase_client() -> Client:
    """Returns initialized Supabase Client."""
    if not supabase_client or not _supabase_enabled:
        raise ValueError("Supabase client is not initialized or disabled.")
    return supabase_client
