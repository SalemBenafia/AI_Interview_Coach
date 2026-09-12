"""
app/common/schemas.py
======================
Standard response envelopes and shared Pydantic schemas.
Every API endpoint returns a consistent shape for easy frontend consumption.
"""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ─── Response Envelopes ───────────────────────────────────────────────────────

class SuccessResponse(BaseModel, Generic[T]):
    """Successful API response envelope."""
    success: bool = True
    data: T
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """Structured error detail."""
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response envelope."""
    success: bool = False
    error: ErrorDetail
    details: Optional[List[ErrorDetail]] = None


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response envelope."""
    success: bool = True
    data: List[T]
    meta: PaginationMeta


# ─── Common Query Params ──────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    """Reusable pagination query parameters."""
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class SortParams(BaseModel):
    """Reusable sort query parameters."""
    sort: str = Field(default="-created_at", description="Field to sort by. Prefix with '-' for descending.")

    @property
    def field(self) -> str:
        return self.sort.lstrip("-")

    @property
    def ascending(self) -> bool:
        return not self.sort.startswith("-")


# ─── Helper Factories ─────────────────────────────────────────────────────────

def success(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def paginated(data: List[Any], page: int, limit: int, total: int) -> Dict[str, Any]:
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return {
        "success": True,
        "data": data,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def error(code: str, message: str, status_code: int = 400) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message},
    }
