"""Canonical Event Record — single source of truth for all documents.

Every field is wrapped in a TrackedField that records its value, source,
and confirmation status.  The EventRecord is JSON-serializable and stored
in SQLite via SQLAlchemy.
"""

from __future__ import annotations

import enum
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Generic, List, Literal, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field, model_serializer, model_validator

# ---------------------------------------------------------------------------
# TrackedField: wraps every piece of data with provenance
# ---------------------------------------------------------------------------

T = TypeVar("T")


class FieldSource(str, enum.Enum):
    user = "user"
    config = "config"
    extracted_rule = "extracted_rule"
    extracted_llm = "extracted_llm"
    computed = "computed"
    default = "default"


class TrackedField(BaseModel, Generic[T]):
    """A field value with provenance metadata."""

    value: Optional[T] = None
    source: FieldSource = FieldSource.default
    confirmed: bool = False

    def set(self, value: T, source: FieldSource, confirmed: bool = False) -> None:
        self.value = value
        self.source = source
        self.confirmed = confirmed

    @property
    def is_present(self) -> bool:
        return self.value is not None

    def __repr__(self) -> str:
        return f"TrackedField(value={self.value!r}, source={self.source.value}, confirmed={self.confirmed})"


# Convenience factory
def tf(value: T | None = None, source: FieldSource = FieldSource.default,
       confirmed: bool = False) -> TrackedField[T]:
    return TrackedField(value=value, source=source, confirmed=confirmed)


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class BankDetails(BaseModel):
    name_as_per_bank: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    account_no: Optional[str] = None
    ifsc: Optional[str] = None
    pan: Optional[str] = None


class Winner(BaseModel):
    position: Optional[str] = None  # e.g., "1st", "2nd"
    name: Optional[str] = None
    roll_no: Optional[str] = None
    course_semester: Optional[str] = None
    mobile: Optional[str] = None
    amount: Optional[Decimal] = None
    bank: Optional[BankDetails] = None


class BudgetItem(BaseModel):
    item: str
    amount: Decimal


class BillItem(BaseModel):
    name: str
    qty: int = 1
    unit_cost: Decimal = Decimal("0")


class SupplierDetails(BaseModel):
    name: Optional[str] = None
    gst_no: Optional[str] = None


class PaymentDetails(BaseModel):
    party: Optional[str] = None
    account_no: Optional[str] = None
    holder: Optional[str] = None
    bank: Optional[str] = None
    branch: Optional[str] = None
    ifsc: Optional[str] = None


class BillRecord(BaseModel):
    supplier: Optional[SupplierDetails] = None
    invoice_no: Optional[str] = None
    invoice_date: Optional[str | date] = None
    items: List[BillItem] = Field(default_factory=list)
    tax_type: Optional[str] = None
    tax_rate_or_amount: Optional[Decimal] = None
    payment: Optional[PaymentDetails] = None


class OtherReimbursement(BaseModel):
    name: Optional[str] = None
    account_no: Optional[str] = None
    ifsc: Optional[str] = None
    amount: Optional[Decimal] = None


class ApprovalNote(BaseModel):
    no: Optional[str] = None
    date: Optional[str | date] = None


class AgendaItem(BaseModel):
    topic: str
    discussion: Optional[str] = None
    decision: Optional[str] = None


class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    deadline: Optional[str | date] = None


class MeetingBlock(BaseModel):
    title: Optional[str] = None
    ref_no: Optional[str] = None
    date: Optional[str | date] = None
    start_time: Optional[str | time] = None
    end_time: Optional[str | time] = None
    venue: Optional[str] = None
    mode: Optional[str] = None
    chaired_by: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)
    absentees: List[str] = Field(default_factory=list)
    agenda_items: List[AgendaItem] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    next_meeting_date: Optional[str | date] = None
    prepared_by: Optional[str] = None
    approved_by: Optional[str] = None


class PersonRef(BaseModel):
    """A person with role-dependent designation labels."""
    name: str
    admission_no: Optional[str] = None
    branch: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    roles: dict[str, str] = Field(default_factory=dict)  # role_key -> designation label


# ---------------------------------------------------------------------------
# Canonical Event Record
# ---------------------------------------------------------------------------

class RecordType(str, enum.Enum):
    event = "event"
    meeting = "meeting"


class EventRecord(BaseModel):
    """The single source of truth for an event or meeting."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Core identity
    record_type: TrackedField[str] = Field(default_factory=lambda: tf("event", FieldSource.default))
    event_name: TrackedField[str] = Field(default_factory=lambda: tf())
    event_code: TrackedField[str] = Field(default_factory=lambda: tf())
    ref_no: TrackedField[str] = Field(default_factory=lambda: tf())
    room_ref_no: TrackedField[str] = Field(default_factory=lambda: tf())
    document_date: TrackedField[str] = Field(default_factory=lambda: tf())
    submitted_to: TrackedField[str] = Field(default_factory=lambda: tf())
    category: TrackedField[str] = Field(default_factory=lambda: tf())
    event_type: TrackedField[str] = Field(default_factory=lambda: tf())
    description: TrackedField[str] = Field(default_factory=lambda: tf())
    objectives: TrackedField[str] = Field(default_factory=lambda: tf())
    target_audience: TrackedField[str] = Field(default_factory=lambda: tf())

    # Schedule & logistics
    dates: TrackedField[str] = Field(default_factory=lambda: tf())  # stored as ISO string or range
    date_start: TrackedField[str] = Field(default_factory=lambda: tf())
    date_end: TrackedField[str] = Field(default_factory=lambda: tf())
    time_start: TrackedField[str] = Field(default_factory=lambda: tf())
    time_end: TrackedField[str] = Field(default_factory=lambda: tf())
    venue: TrackedField[str] = Field(default_factory=lambda: tf())
    mode: TrackedField[str] = Field(default_factory=lambda: tf("Offline", FieldSource.default))
    expected_participants: TrackedField[int] = Field(default_factory=lambda: tf())

    # People
    organizers: TrackedField[str] = Field(default_factory=lambda: tf())
    judges: TrackedField[list] = Field(default_factory=lambda: tf([]))

    # Financial
    budget_items: List[BudgetItem] = Field(default_factory=list)
    winners: List[Winner] = Field(default_factory=list)
    bills: List[BillRecord] = Field(default_factory=list)
    other_reimbursements: List[OtherReimbursement] = Field(default_factory=list)

    # Cross-document references
    approval_note: Optional[ApprovalNote] = None

    # Meeting
    meeting: Optional[MeetingBlock] = None

    # Config-derived
    academic_year: TrackedField[str] = Field(default_factory=lambda: tf())

    def flat_dict(self) -> dict[str, Any]:
        """Return a flat dictionary suitable for template rendering.

        TrackedField values are unwrapped. Nested objects are kept as-is.
        """
        result: dict[str, Any] = {}
        for field_name, field_info in self.model_fields.items():
            val = getattr(self, field_name)
            if isinstance(val, TrackedField):
                result[field_name] = val.value
            elif isinstance(val, BaseModel):
                result[field_name] = val.model_dump()
            elif isinstance(val, list):
                result[field_name] = [
                    item.model_dump() if isinstance(item, BaseModel) else item
                    for item in val
                ]
            else:
                result[field_name] = val
        return result

    def get_missing_fields(self, required_keys: list[str]) -> list[str]:
        """Return keys that are required but have no value."""
        missing = []
        for key in required_keys:
            val = getattr(self, key, None)
            if val is None:
                missing.append(key)
            elif isinstance(val, TrackedField) and not val.is_present:
                missing.append(key)
        return missing

    def get_unconfirmed_fields(self) -> dict[str, TrackedField]:
        """Return all TrackedFields that are present but not confirmed."""
        result = {}
        for field_name in self.model_fields:
            val = getattr(self, field_name)
            if isinstance(val, TrackedField) and val.is_present and not val.confirmed:
                result[field_name] = val
        return result
