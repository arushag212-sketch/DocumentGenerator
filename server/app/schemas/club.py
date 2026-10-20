"""Pydantic schemas for clubs, memberships, people, invites, and setup wizard."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    short_name: str = Field(..., min_length=1, max_length=50)
    slug: Optional[str] = Field(None, min_length=2, max_length=50, pattern="^[a-z0-9-]+$")
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: str = "2026-27"
    position: Optional[str] = Field(None, max_length=100)
    is_signatory: bool = False


class ClubUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    short_name: Optional[str] = Field(None, min_length=1, max_length=50)
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: Optional[str] = None
    department: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class ClubSearchOut(BaseModel):
    id: str
    name: str
    short_name: str
    slug: str
    chapter_code: Optional[str] = None
    academic_year_default: Optional[str] = None
    members_count: int = 0
    membership_role: Optional[str] = None
    membership_status: Optional[str] = None
    membership_position: Optional[str] = None
    join_request_status: Optional[str] = None
    admin_name: Optional[str] = None


class JoinRequestCreate(BaseModel):
    position: str = Field(..., min_length=2, max_length=100)
    # Applicants may only ask for editor (create documents/templates) or viewer (read-only);
    # admin/owner access is granted by an existing admin, never self-requested.
    requested_role: str = Field("editor", pattern="^(editor|viewer)$")
    message: Optional[str] = Field(None, max_length=500)


class ApproveJoinRequest(BaseModel):
    # Omit to grant the access level the applicant requested.
    role: Optional[str] = Field(None, pattern="^(owner|admin|editor|viewer)$")
    is_signatory: bool = False
    signatory_role: Optional[str] = None
    conflict_resolution: Optional[str] = Field(None, pattern="^(replace|keep_both)$")


class JoinRequestOut(BaseModel):
    id: str
    club_id: str
    club_name: str
    user_id: str
    user_name: str
    user_email: str
    position: str
    requested_role: str = "editor"
    message: Optional[str] = None
    status: str
    admin_name: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ClubOut(BaseModel):
    id: str
    name: str
    short_name: str
    slug: str
    chapter_code: Optional[str] = None
    head_of_account: Optional[str] = None
    academic_year_default: Optional[str] = "2026-27"
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
    position: Optional[str] = None
    status: str
    joined_at: datetime


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field("editor", pattern="^(admin|editor|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(owner|admin|editor|viewer)$")


class InviteCreate(BaseModel):
    role: str = Field("editor", pattern="^(owner|admin|editor|viewer)$")
    max_uses: int = Field(1, ge=1, le=100)
    expiry_days: int = Field(7, ge=1, le=30)


class InviteOut(BaseModel):
    id: str
    club_id: str
    code: str
    role: str
    created_by: Optional[str] = None
    max_uses: int
    use_count: int
    revoked: bool
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    invite_link: str
    created_at: datetime


class InvitePreview(BaseModel):
    code: str
    club_id: str
    club_name: str
    club_slug: str
    role: str
    expires_at: Optional[datetime] = None
    max_uses: int
    use_count: int
    is_valid: bool
    status: str  # active, expired, revoked, used_up


class AcceptInviteRequest(BaseModel):
    club_id: Optional[str] = None


class RoleHeldCreate(BaseModel):
    person_id: str
    role_key: str
    designation_label: str
    academic_year: str


class RoleHeldUpdate(BaseModel):
    role_key: Optional[str] = None
    designation_label: Optional[str] = None
    academic_year: Optional[str] = None


class RoleHeldOut(BaseModel):
    id: str
    person_id: str
    role_key: str
    designation_label: str
    academic_year: str
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
    roles: list[RoleHeldOut] = []
    created_at: datetime


class VenueCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    short_name: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    addressee_default: Optional[str] = None
    addressee: Optional[str] = None
    tech_assistant_person_id: Optional[str] = None
    tech_assistant: Optional[str] = None
    faculty_incharge_person_id: Optional[str] = None
    faculty_in_charge: Optional[str] = None


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    addressee_default: Optional[str] = None
    addressee: Optional[str] = None
    tech_assistant_person_id: Optional[str] = None
    tech_assistant: Optional[str] = None
    faculty_incharge_person_id: Optional[str] = None
    faculty_in_charge: Optional[str] = None


class VenueOut(BaseModel):
    id: str
    club_id: Optional[str] = None
    name: str
    short_name: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    addressee_default: Optional[str] = None
    addressee: Optional[str] = None
    tech_assistant_person_id: Optional[str] = None
    tech_assistant_name: Optional[str] = None
    tech_assistant: Optional[str] = None
    faculty_incharge_person_id: Optional[str] = None
    faculty_incharge_name: Optional[str] = None
    faculty_in_charge: Optional[str] = None
    created_at: datetime


class NumberingSeriesCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    format: str = Field(..., min_length=3, max_length=255)
    academic_year: str
    last_seq: int = 0


class NumberingSeriesUpdate(BaseModel):
    format: str = Field(..., min_length=3, max_length=255)


class NumberingSeriesOut(BaseModel):
    id: str
    club_id: str
    key: str
    series_key: Optional[str] = None
    format: str
    academic_year: str
    last_seq: int
    current_counter: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime


class LetterheadCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    left_logo_asset_id: Optional[str] = None
    right_logo_asset_id: Optional[str] = None
    title_text: Optional[str] = None
    subtitle_text: Optional[str] = None
    colors: dict[str, Any] = {}
    fonts: dict[str, Any] = {}
    layout: dict[str, Any] = {}


class LetterheadUpdate(BaseModel):
    name: Optional[str] = None
    left_logo_asset_id: Optional[str] = None
    right_logo_asset_id: Optional[str] = None
    title_text: Optional[str] = None
    subtitle_text: Optional[str] = None
    colors: Optional[dict[str, Any]] = None
    fonts: Optional[dict[str, Any]] = None
    layout: Optional[dict[str, Any]] = None


class LetterheadOut(BaseModel):
    id: str
    club_id: Optional[str] = None
    name: str
    left_logo_asset_id: Optional[str] = None
    right_logo_asset_id: Optional[str] = None
    institute_logo_asset_id: Optional[str] = None
    title_text: Optional[str] = None
    subtitle_text: Optional[str] = None
    colors: dict[str, Any] = {}
    fonts: dict[str, Any] = {}
    layout: dict[str, Any] = {}
    created_at: datetime


class AssetOut(BaseModel):
    id: str
    club_id: Optional[str] = None
    kind: str
    filename: str
    mime: str
    size: int
    is_system: bool
    url: str
    created_at: datetime


class SetupWizardRequest(BaseModel):
    chairman_name: str = Field(..., min_length=2)
    chairman_dept: str = ""
    student_head_name: str = Field(..., min_length=2)
    student_head_roll: str = "DEMO-001"
    student_head_branch: str = ""
    student_head_mobile: Optional[str] = None
    student_secretary_name: str = Field(..., min_length=2)
    student_secretary_roll: str = "DEMO-002"
    student_secretary_branch: str = ""
    faculty_co_chairman_name: Optional[str] = None
    approval_chain: list[str] = [
        "Demo Faculty In-charge",
        "Demo Head of Department",
        "Demo Dean (Students Welfare)",
    ]
    venues: list[str] = ["Seminar Hall", "Lab 1"]
    academic_year: str


class ClubPermissionsOut(BaseModel):
    is_platform_admin: bool
    role: Optional[str] = None
    is_owner: bool = False
    can_edit_members: bool = False
    can_edit_settings: bool = False
    can_create_documents: bool = False
    can_finalize_documents: bool = False
    can_view_sensitive: bool = False
    position: Optional[str] = None


class UpdatePositionRequest(BaseModel):
    position: str

