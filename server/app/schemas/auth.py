"""Pydantic schemas for authentication and user accounts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class ClubMembershipSummary(BaseModel):
    club_id: str
    club_name: str
    club_slug: str
    club_short: str
    role: str
    position: Optional[str] = None
    status: str


from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Any, Optional


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, description="Password must be at least 10 characters")
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    invite_code: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            val = data.get("name") or data.get("full_name")
            if val:
                data["name"] = str(val).strip()
                data["full_name"] = str(val).strip()
        return data


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_platform_admin: bool
    email_verified_at: Optional[datetime] = None
    created_at: datetime
    memberships: list[ClubMembershipSummary] = []


class TokenResponse(BaseModel):
    user: UserOut
    csrf_token: str
    token_type: str = "bearer"
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=10)


class SensitiveFieldOut(BaseModel):
    masked: str
    revealed: Optional[str] = None
