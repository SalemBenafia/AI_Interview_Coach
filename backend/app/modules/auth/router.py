"""
app/modules/auth/router.py
===========================
Authentication endpoints for both actors described in roles.txt:
Candidate (User) and Admin.

Tokens issued as HttpOnly cookies — never in response JSON.

NOTE ON UX: there is exactly ONE login form and ONE endpoint
(POST /auth/login/) — the candidate/admin never chooses which kind of
account they're signing into. The backend resolves the principal purely
from the submitted credentials: it looks the email up among candidates
first, then admins, and authenticates against whichever table matches.
The response's principal_type tells the frontend where to route the
signed-in user.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.core.settings import settings
from app.db.models import AdminUser, CandidateUser, RefreshToken, SupportedLanguage
from app.db.session import get_db
from app.modules.auth.jwt import (
    TokenClaims,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_refresh_token_from_request,
    hash_password,
    set_auth_cookies,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    preferred_language: SupportedLanguage = SupportedLanguage.EN


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PrincipalResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    principal_type: str
    roles: list[str] = []


def _persist_refresh_token(db: AsyncSession, principal_id: str, principal_type: str, jti: str) -> None:
    db.add(RefreshToken(
        principal_id=principal_id,
        principal_type=principal_type,
        jti=jti,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))


# ─── Candidate Registration ────────────────────────────────────────────────────

@router.post("/register/", status_code=status.HTTP_201_CREATED)
async def register_candidate(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a candidate account and immediately sign them in."""
    existing = await db.execute(
        select(CandidateUser).where(CandidateUser.email == payload.email, CandidateUser.is_deleted == False)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "An account with this email already exists."},
        )

    candidate = CandidateUser(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        preferred_language=payload.preferred_language,
    )
    db.add(candidate)
    await db.flush()  # populate candidate.id before issuing tokens

    access = create_access_token(principal_id=str(candidate.id), principal_type="candidate", roles=["candidate"])
    refresh, jti = create_refresh_token(principal_id=str(candidate.id), principal_type="candidate")
    _persist_refresh_token(db, str(candidate.id), "candidate", jti)
    candidate.last_login_at = datetime.now(tz=timezone.utc)
    await db.commit()

    set_auth_cookies(response, access, refresh)

    return success({
        "user": PrincipalResponse(
            id=str(candidate.id), email=candidate.email,
            first_name=candidate.first_name, last_name=candidate.last_name,
            principal_type="candidate", roles=["candidate"],
        ).model_dump()
    }, message="Account created.")


# ─── Unified Login ──────────────────────────────────────────────────────────
#
# One form, one endpoint. Which table the email belongs to determines the
# principal type — the client never declares it. Candidates are checked
# first (the overwhelmingly common case); a candidate and an admin could in
# principle share an email since the two tables have independent uniqueness
# constraints, in which case the candidate account wins deterministically.

@router.post("/login/")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate either a candidate or an admin from the same form,
    resolving which one purely from the submitted credentials. Sets
    HttpOnly cookies."""
    result = await db.execute(
        select(CandidateUser).where(
            CandidateUser.email == payload.email,
            CandidateUser.is_deleted == False,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate and verify_password(payload.password, candidate.hashed_password):
        if not candidate.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_SUSPENDED", "message": "This account has been suspended."},
            )

        access = create_access_token(principal_id=str(candidate.id), principal_type="candidate", roles=["candidate"])
        refresh, jti = create_refresh_token(principal_id=str(candidate.id), principal_type="candidate")
        _persist_refresh_token(db, str(candidate.id), "candidate", jti)
        candidate.last_login_at = datetime.now(tz=timezone.utc)
        await db.commit()

        set_auth_cookies(response, access, refresh)
        return success({
            "user": PrincipalResponse(
                id=str(candidate.id), email=candidate.email,
                first_name=candidate.first_name, last_name=candidate.last_name,
                principal_type="candidate", roles=["candidate"],
            ).model_dump()
        }, message="Login successful.")

    result = await db.execute(
        select(AdminUser).where(
            AdminUser.email == payload.email,
            AdminUser.is_deleted == False,
        )
    )
    admin = result.scalar_one_or_none()
    if admin and verify_password(payload.password, admin.hashed_password):
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_SUSPENDED", "message": "This admin account has been disabled."},
            )

        access = create_access_token(principal_id=str(admin.id), principal_type="admin", roles=[admin.role.value])
        refresh, jti = create_refresh_token(principal_id=str(admin.id), principal_type="admin")
        _persist_refresh_token(db, str(admin.id), "admin", jti)
        admin.last_login_at = datetime.now(tz=timezone.utc)
        await db.commit()

        set_auth_cookies(response, access, refresh)
        return success({
            "user": PrincipalResponse(
                id=str(admin.id), email=admin.email,
                first_name=admin.first_name, last_name=admin.last_name,
                principal_type="admin", roles=[admin.role.value],
            ).model_dump()
        }, message="Login successful.")

    # Deliberately identical error/status for "no such account" and "wrong
    # password" on either table -- never reveal which table (or whether an
    # account exists at all) a submitted email belongs to.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."},
    )


# ─── Token Refresh ────────────────────────────────────────────────────────────

@router.post("/token/refresh/")
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Silent token refresh. Reads refresh cookie, issues new token pair (rotation)."""
    refresh_token = get_refresh_token_from_request(request)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NO_REFRESH_TOKEN", "message": "Refresh token missing."},
        )

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN_TYPE", "message": "Expected refresh token."},
        )

    jti = payload.get(TokenClaims.JTI)
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti, RefreshToken.is_revoked == False))
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_REVOKED", "message": "Refresh token has been revoked."},
        )

    token_record.is_revoked = True  # rotate: revoke old, issue new

    principal_id = payload.get(TokenClaims.PRINCIPAL_ID)
    principal_type = payload.get(TokenClaims.PRINCIPAL_TYPE)

    roles: list[str] = []
    if principal_type == "admin":
        r = await db.execute(select(AdminUser).where(AdminUser.id == principal_id))
        admin = r.scalar_one_or_none()
        if admin:
            roles = [admin.role.value]
    else:
        roles = ["candidate"]

    new_access = create_access_token(principal_id=principal_id, principal_type=principal_type, roles=roles)
    new_refresh, new_jti = create_refresh_token(principal_id=principal_id, principal_type=principal_type)
    _persist_refresh_token(db, principal_id, principal_type, new_jti)
    await db.commit()

    set_auth_cookies(response, new_access, new_refresh)
    return success({}, message="Token refreshed.")


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout/")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and clear auth cookies."""
    refresh_token = get_refresh_token_from_request(request)
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get(TokenClaims.JTI)
            if jti:
                result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
                token_record = result.scalar_one_or_none()
                if token_record:
                    token_record.is_revoked = True
                    await db.commit()
        except Exception:
            pass  # Always clear cookies even if the token is malformed/expired.

    clear_auth_cookies(response)
    return success({}, message="Logged out successfully.")


# ─── Password Reset (roles.txt → Candidate → Authentication & Profile) ───────

@router.post("/forgot-password/")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Always returns success regardless of whether the email exists, to avoid
    leaking account existence. In dev mode the reset token is logged instead
    of emailed (MailHog catches real emails — see notifications module).
    """
    result = await db.execute(
        select(CandidateUser).where(CandidateUser.email == payload.email, CandidateUser.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if user:
        reset_token = secrets.token_urlsafe(32)
        # Store as a short-lived "refresh"-style record so we can verify it
        # later without a dedicated table. principal_type marks its purpose.
        db.add(RefreshToken(
            principal_id=str(user.id),
            principal_type="password_reset",
            jti=reset_token,
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=1),
        ))
        await db.commit()

        from app.modules.notifications.tasks import send_password_reset_email
        send_password_reset_email.delay(user.email, reset_token)

    return success({}, message="If that email exists, a reset link has been sent.")


@router.post("/reset-password/")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.jti == payload.token,
            RefreshToken.principal_type == "password_reset",
            RefreshToken.is_revoked == False,
        )
    )
    record = result.scalar_one_or_none()
    if not record or record.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RESET_TOKEN", "message": "This reset link is invalid or has expired."},
        )

    user_result = await db.execute(select(CandidateUser).where(CandidateUser.id == record.principal_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Account not found."})

    user.hashed_password = hash_password(payload.new_password)
    record.is_revoked = True
    await db.commit()

    return success({}, message="Password updated. You can now log in.")
