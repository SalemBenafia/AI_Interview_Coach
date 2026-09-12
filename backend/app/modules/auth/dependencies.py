"""
app/modules/auth/dependencies.py
==================================
FastAPI dependencies for route protection.

Two principal types only: "candidate" and "admin" (roles.txt). Admin role
sub-types (super_admin / platform_admin / ai_manager / flow_designer /
support) are enforced with `require_admin_role(*roles)`.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser, CandidateUser
from app.db.session import get_db
from app.modules.auth.jwt import (
    TokenClaims,
    decode_token,
    get_access_token_from_request,
)


class CurrentPrincipal:
    """Lightweight resolved-from-JWT principal — avoids an extra DB hit on every request."""

    def __init__(self, principal_id: str, principal_type: str, roles: list[str]):
        self.id = principal_id
        self.principal_type = principal_type
        self.roles = roles

    @property
    def is_admin(self) -> bool:
        return self.principal_type == "admin"

    @property
    def is_candidate(self) -> bool:
        return self.principal_type == "candidate"


def _extract_principal(request: Request) -> CurrentPrincipal:
    token = get_access_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "Authentication required."},
        )
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN_TYPE", "message": "Expected access token."},
        )
    return CurrentPrincipal(
        principal_id=payload[TokenClaims.PRINCIPAL_ID],
        principal_type=payload[TokenClaims.PRINCIPAL_TYPE],
        roles=payload.get(TokenClaims.ROLES, []),
    )


def get_current_principal(request: Request) -> CurrentPrincipal:
    """Any authenticated principal (candidate OR admin)."""
    return _extract_principal(request)


def get_current_candidate_id(request: Request) -> str:
    """Require an authenticated candidate; returns their id as a string."""
    principal = _extract_principal(request)
    if not principal.is_candidate:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CANDIDATE_ONLY", "message": "This endpoint is for candidates only."},
        )
    return principal.id


def get_current_admin(request: Request) -> CurrentPrincipal:
    """Require an authenticated admin (any role)."""
    principal = _extract_principal(request)
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_ONLY", "message": "This endpoint is for admins only."},
        )
    return principal


def require_admin_role(*allowed_roles: str):
    """
    Dependency factory for admin sub-role checks, e.g.:
        Depends(require_admin_role("super_admin", "ai_manager"))
    """

    def _checker(admin: CurrentPrincipal = Depends(get_current_admin)) -> CurrentPrincipal:
        if allowed_roles and not any(r in admin.roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "message": f"Requires one of: {', '.join(allowed_roles)}.",
                },
            )
        return admin

    return _checker


async def get_current_candidate(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
) -> CandidateUser:
    """Resolve the full CandidateUser row (use sparingly — most routes only need the id)."""
    result = await db.execute(
        select(CandidateUser).where(CandidateUser.id == candidate_id, CandidateUser.is_deleted == False)
    )
    candidate = result.scalar_one_or_none()
    if not candidate or not candidate.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Account not found or inactive."},
        )
    return candidate


async def get_current_admin_user(
    admin: CurrentPrincipal = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin.id, AdminUser.is_deleted == False)
    )
    row = result.scalar_one_or_none()
    if not row or not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Admin account not found or inactive."},
        )
    return row
