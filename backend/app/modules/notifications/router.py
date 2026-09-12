"""
app/modules/notifications/router.py
======================================
Candidate-facing in-app notification feed (roles.txt -> User -> Auth &
Profile -> "Manage notification preferences").
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import NotificationLog
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_candidate_id

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/")
async def list_notifications(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.candidate_id == uuid.UUID(candidate_id))
        .order_by(NotificationLog.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    return success([
        {
            "id": str(n.id),
            "channel": n.channel.value,
            "subject": n.subject,
            "body": n.body,
            "status": n.status.value,
            "isRead": n.is_read,
            "createdAt": n.created_at.isoformat(),
        }
        for n in items
    ])


@router.post("/{notification_id}/read/")
async def mark_read(
    notification_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.id == notification_id, NotificationLog.candidate_id == uuid.UUID(candidate_id)
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Notification not found."})
    notification.is_read = True
    await db.commit()
    return success({}, message="Marked as read.")


@router.post("/read-all/")
async def mark_all_read(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(NotificationLog)
        .where(NotificationLog.candidate_id == uuid.UUID(candidate_id), NotificationLog.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return success({}, message="All notifications marked as read.")
