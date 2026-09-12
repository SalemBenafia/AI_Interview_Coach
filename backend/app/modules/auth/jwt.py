"""
app/modules/auth/jwt.py
========================
JWT token creation, validation, and HTTP-only cookie management.
Tokens NEVER returned to client as JSON — only set as HttpOnly cookies
(roles.txt Non-Functional Requirements → Security: "JWT authentication,
HTTP-only cookies").

Both candidates and admins authenticate through this same module — the
`principal_type` claim ("candidate" | "admin") is what the dependency layer
uses to enforce access. Per product decision, both log in from a single
unified login form on the frontend (a role switch chooses which endpoint
to call), but the backend still issues distinct, clearly-typed tokens.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from fastapi.responses import Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import settings


# ─── Password Hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── Token Claims ─────────────────────────────────────────────────────────────
class TokenClaims:
    """Standard JWT claim names used across the platform."""
    PRINCIPAL_TYPE = "principal_type"   # "admin" | "candidate"
    PRINCIPAL_ID = "principal_id"
    ROLES = "roles"
    JTI = "jti"   # JWT ID for refresh token rotation


# ─── Token Creation ───────────────────────────────────────────────────────────

def create_access_token(
    principal_id: str,
    principal_type: str,
    roles: Optional[list[str]] = None,
) -> str:
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": principal_id,
        TokenClaims.PRINCIPAL_TYPE: principal_type,
        TokenClaims.PRINCIPAL_ID: principal_id,
        TokenClaims.ROLES: roles or [],
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(principal_id: str, principal_type: str) -> Tuple[str, str]:
    """Returns (token_string, jti)."""
    jti = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: Dict[str, Any] = {
        "sub": principal_id,
        TokenClaims.PRINCIPAL_TYPE: principal_type,
        TokenClaims.PRINCIPAL_ID: principal_id,
        TokenClaims.JTI: jti,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": str(e)},
        )


# ─── Cookie Management ────────────────────────────────────────────────────────

def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly auth cookies on the response."""
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies on logout."""
    response.delete_cookie(key=settings.ACCESS_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=settings.REFRESH_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)


# ─── Token Extraction ─────────────────────────────────────────────────────────

def get_access_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(settings.ACCESS_COOKIE_NAME)


def get_refresh_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(settings.REFRESH_COOKIE_NAME)
