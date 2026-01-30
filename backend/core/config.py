from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import HTTPException, status
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def validate_env() -> list[str]:
    missing: list[str] = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    return missing


def get_supabase_client() -> Client:
    missing = validate_env()
    if missing:
        missing_vars = ", ".join(missing)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing required environment variables: {missing_vars}",
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
