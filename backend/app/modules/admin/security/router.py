"""
app/modules/admin/security/router.py
=======================================
Admin -> Security (roles.txt -> Admin Role -> Authentication, and
Non-Functional -> Security -> "Role-based access control (RBAC), Audit
logs"). Only super_admin / platform_admin can manage other admin accounts.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import paginated, success
from app.db.models import AdminRole, AdminUser, AuditLog
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role
from app.modules.auth.jwt import hash_password

router = APIRouter(prefix="/admin/security", tags=["Admin — Security"])

_SECURITY_ROLES = ("super_admin", "platform_admin")


class AdminCreate(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    role: AdminRole = AdminRole.SUPPORT


class AdminUpdate(BaseModel):
    role: Optional[AdminRole] = None
    is_active: Optional[bool] = None


@router.get("/admins/")
async def list_admins(
    admin: CurrentPrincipal = Depends(require_admin_role(*_SECURITY_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdminUser).where(AdminUser.is_deleted == False).order_by(AdminUser.created_at.desc()))
    admins = result.scalars().all()
    return success([
        {
            "id": str(a.id), "email": a.email, "username": a.username,
            "firstName": a.first_name, "lastName": a.last_name, "role": a.role.value,
            "isActive": a.is_active, "mfaEnabled": a.mfa_enabled,
            "lastLoginAt": a.last_login_at.isoformat() if a.last_login_at else None,
        }
        for a in admins
    ])


@router.post("/admins/", status_code=201)
async def create_admin(
    payload: AdminCreate,
    requester: CurrentPrincipal = Depends(require_admin_role(*_SECURITY_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(AdminUser).where(AdminUser.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "EMAIL_TAKEN", "message": "An admin with this email already exists."})

    new_admin = AdminUser(
        email=payload.email, username=payload.username,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name, last_name=payload.last_name, role=payload.role,
    )
    db.add(new_admin)
    await db.flush()
    db.add(AuditLog(
        admin_id=uuid.UUID(requester.id), action="admin.create",
        resource_type="admin_user", resource_id=str(new_admin.id), details={"role": payload.role.value},
    ))
    await db.commit()
    return success({"adminId": str(new_admin.id)}, message="Admin account created.")


@router.patch("/admins/{admin_id}/")
async def update_admin(
    admin_id: uuid.UUID,
    payload: AdminUpdate,
    requester: CurrentPrincipal = Depends(require_admin_role(*_SECURITY_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Admin not found."})
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(target, k, v)
    db.add(AuditLog(
        admin_id=uuid.UUID(requester.id), action="admin.update",
        resource_type="admin_user", resource_id=str(admin_id), details=payload.model_dump(exclude_none=True),
    ))
    await db.commit()
    return success({}, message="Admin updated.")


@router.get("/audit-logs/")
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None),
    admin: CurrentPrincipal = Depends(require_admin_role(*_SECURITY_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit)
    logs = (await db.execute(query)).scalars().all()
    return paginated([
        {
            "id": str(l.id), "adminId": str(l.admin_id) if l.admin_id else None,
            "action": l.action, "resourceType": l.resource_type, "resourceId": l.resource_id,
            "details": l.details, "ipAddress": l.ip_address, "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ], page=page, limit=limit, total=total)
