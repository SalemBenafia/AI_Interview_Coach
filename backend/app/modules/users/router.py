"""
app/modules/users/router.py
=============================
Candidate profile management (roles.txt → User Role → Authentication & Profile).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import CandidateUser, SupportedLanguage
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_candidate_id
from app.modules.auth.jwt import hash_password, verify_password

router = APIRouter(prefix="/users/me", tags=["Candidate — Profile"])


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[SupportedLanguage] = None
    notification_prefs: Optional[dict] = None


class ResumeUpdate(BaseModel):
    resume_url: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("/")
async def get_profile(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Profile not found."})
    return success(_serialize(user))


@router.patch("/")
async def update_profile(
    payload: ProfileUpdate,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Profile not found."})

    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    await db.commit()
    return success(_serialize(user), message="Profile updated.")


@router.patch("/resume/")
async def update_resume(
    payload: ResumeUpdate,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    """Set the resume URL after the file has been uploaded to object storage."""
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Profile not found."})
    user.resume_url = payload.resume_url
    await db.commit()
    return success({"resumeUrl": user.resume_url}, message="Resume updated.")


@router.post("/change-password/")
async def change_password(
    payload: ChangePasswordRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PASSWORD", "message": "Current password is incorrect."},
        )
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return success({}, message="Password changed.")


def _serialize(user: CandidateUser) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "headline": user.headline,
        "avatarUrl": user.avatar_url,
        "resumeUrl": user.resume_url,
        "preferredLanguage": user.preferred_language.value,
        "notificationPrefs": user.notification_prefs,
        "createdAt": user.created_at.isoformat(),
    }
