from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status

from core.config import get_supabase_client

logger = logging.getLogger(__name__)


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be a Bearer token",
        )
    return token


def _decode_jwt_unverified(token: str) -> Dict[str, Any]:
    # TODO: verify JWT signature against Supabase JWKS for production.
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT format",
        )
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT payload",
        ) from exc
    return payload


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be a Bearer token",
        )

    payload = _decode_jwt_unverified(raw_token)
    auth_user_id = payload.get("sub")
    exp = payload.get("exp")
    if not auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT subject (sub) claim missing",
        )
    if exp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT exp claim missing",
        )
    if int(exp) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT has expired",
        )

    supabase = get_supabase_client()
    response = (
        supabase.table("app_users")
        .select("id, auth_user_id, firm_id, role, email")
        .eq("auth_user_id", auth_user_id)
        .single()
        .execute()
    )
    if response.data is None:
        logger.info("No app_users record found for auth_user_id")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No app user record; create app_users row.",
        )
    return {
        "app_user_id": response.data.get("id"),
        "auth_user_id": response.data.get("auth_user_id"),
        "firm_id": response.data.get("firm_id"),
        "role": response.data.get("role"),
        "email": response.data.get("email"),
    }
