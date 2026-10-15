"""Pydantic schemas for clubs, memberships, people, invites, and setup wizard."""

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
    code: Optional[str] = None
    department: Optional[str] = None
    academic_year: Optional[str] = None
    room_counter: int = 0
    event_counter: int = 0
    mom_counter: int = 0


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


class PersonCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    roll_no: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class PersonUpdate(BaseModel):
    full_name: Optional[str] = None
    roll_no: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class PersonOut(BaseModel):
    id: str
    club_id: str
    full_name: str
    name: Optional[str] = None
    roll_no: Optional[str] = None
    roll_number: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class SetupWizardRequest(BaseModel):
    chairman_name: str = Field(..., min_length=2)
    chairman_dept: str = "Computer Science & Engineering"
    student_head_name: str = Field(..., min_length=2)
    student_head_roll: str = "DEMO-001"
    student_head_branch: str = "Computer Science & Engineering"
    student_head_mobile: Optional[str] = None
    student_secretary_name: str = Field(..., min_length=2)
    student_secretary_roll: str = "DEMO-002"
    student_secretary_branch: str = "Computer Science & Engineering"
    faculty_co_chairman_name: Optional[str] = None
    approval_chain: list[str] = [
        "Demo Faculty In-charge",
        "Demo Head of Department",
        "Demo Dean (Students Welfare)",
    ]
    venues: list[str] = ["Seminar Hall", "Lab 1"]
    academic_year: str = "2026-27"


class ClubPermissionsOut(BaseModel):
    is_platform_admin: bool
    role: Optional[str] = None
    is_owner: bool = False
    can_edit_members: bool = False
    can_edit_settings: bool = False
    can_create_documents: bool = False
    can_finalize_documents: bool = False
    can_view_sensitive: bool = False
