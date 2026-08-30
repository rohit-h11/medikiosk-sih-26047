import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Notice for local dev or unconfigured environment
    print("[WARNING] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in environment variables.")

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_supabase_client() -> Client:
    """Returns initialized Supabase Client."""
    if not supabase_client:
        raise ValueError("Supabase client is not initialized. Please set SUPABASE_URL and SUPABASE_KEY.")
    return supabase_client
