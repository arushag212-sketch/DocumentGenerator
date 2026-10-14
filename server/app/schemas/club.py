"""Pydantic schemas for clubs, memberships, and invites."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    short_name: str = Field(..., min_length=1, max_length=50)
    slug: str = Field(..., min_length=2, max_length=50, pattern="^[a-z0-9-]+$")
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: str = "2026-27"


class ClubUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    short_name: Optional[str] = Field(None, min_length=1, max_length=50)
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class ClubOut(BaseModel):
    id: str
    name: str
    short_name: str
    slug: str
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: str
    settings: dict[str, Any] = {}
    my_role: Optional[str] = None
    members_count: int = 0
    created_at: datetime


class ClubMemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    status: str
    joined_at: datetime


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field("editor", pattern="^(admin|editor|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(owner|admin|editor|viewer)$")


class InviteCreate(BaseModel):
    email_or_code: str
    role: str = Field("editor", pattern="^(admin|editor|viewer)$")
    expires_in_days: int = 7


class InviteOut(BaseModel):
    id: str
    club_id: str
    email_or_code: str
    role: str
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
