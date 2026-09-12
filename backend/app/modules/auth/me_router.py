"""
app/modules/auth/me_router.py
================================
"Who am I" endpoints, consumed by the frontend on every page load to
hydrate the auth store. Separate from the candidate profile-editing
endpoints in app/modules/users/router.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import AdminUser, CandidateUser
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("/")
async def get_me(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    if principal.is_admin:
        result = await db.execute(select(AdminUser).where(AdminUser.id == principal.id))
        admin = result.scalar_one_or_none()
        if not admin:
            return success(None)
        return success({
            "id": str(admin.id),
            "email": admin.email,
            "firstName": admin.first_name,
            "lastName": admin.last_name,
            "principalType": "admin",
            "roles": [admin.role.value],
            "mfaEnabled": admin.mfa_enabled,
            "lastLoginAt": admin.last_login_at.isoformat() if admin.last_login_at else None,
            "createdAt": admin.created_at.isoformat(),
        })

    result = await db.execute(select(CandidateUser).where(CandidateUser.id == principal.id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return success(None)
    return success({
        "id": str(candidate.id),
        "email": candidate.email,
        "firstName": candidate.first_name,
        "lastName": candidate.last_name,
        "principalType": "candidate",
        "roles": ["candidate"],
        "avatarUrl": candidate.avatar_url,
        "resumeUrl": candidate.resume_url,
        "headline": candidate.headline,
        "preferredLanguage": candidate.preferred_language.value,
        "notificationPrefs": candidate.notification_prefs,
        "lastLoginAt": candidate.last_login_at.isoformat() if candidate.last_login_at else None,
        "createdAt": candidate.created_at.isoformat(),
    })
