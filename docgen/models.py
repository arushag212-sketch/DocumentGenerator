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
    item: str = "Budget Item"
    amount: Decimal = Decimal("0")

    @model_validator(mode="before")
    @classmethod
    def _preprocess_budget_item(cls, data: Any) -> Any:
        if isinstance(data, (int, float, Decimal)):
            return {"item": "Proposed Budget", "amount": Decimal(str(data))}
        if isinstance(data, str):
            import re
            s = data.strip()
            if not s:
                return {"item": "Budget Item", "amount": Decimal("0")}
            m = re.match(r'^(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:/-)?$', s, re.IGNORECASE)
            if m:
                return {"item": "Proposed Budget", "amount": Decimal(m.group(1).replace(",", ""))}
            m_item = re.match(r'^(.*?)(?::|-|\s+)\s*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:/-)?$', s, re.IGNORECASE)
            if m_item:
                return {"item": m_item.group(1).strip() or "Budget Item", "amount": Decimal(m_item.group(2).replace(",", ""))}
            return {"item": s, "amount": Decimal("0")}
        if isinstance(data, dict):
            import re
            item_desc = data.get("item") or data.get("description") or data.get("name") or data.get("title") or "Budget Item"
            raw_amt = data.get("amount") if data.get("amount") is not None else data.get("cost", data.get("price", 0))
            if isinstance(raw_amt, str):
                cleaned_amt = re.sub(r'[^\d.]', '', raw_amt) or '0'
                raw_amt = Decimal(cleaned_amt)
            return {"item": str(item_desc), "amount": raw_amt}
        return data


def coerce_to_list_of_strings(val: Any) -> list[str]:
    """Coerce various string or list inputs into a clean list of non-empty strings."""
    import re
    if val is None:
        return []
    if isinstance(val, list):
        res = []
        for x in val:
            if x is None:
                continue
            if isinstance(x, str):
                for part in re.split(r'[,;\n]+', x):
                    p = part.strip()
                    if p:
                        res.append(p)
            elif isinstance(x, dict) and "name" in x:
                if x["name"] and str(x["name"]).strip():
                    res.append(str(x["name"]).strip())
            else:
                s = str(x).strip()
                if s:
                    res.append(s)
        return res
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return coerce_to_list_of_strings(parsed)
            except Exception:
                pass
        return [p.strip() for p in re.split(r'[,;\n]+', s) if p.strip()]
    s = str(val).strip()
    return [s] if s else []


def coerce_to_budget_items(val: Any) -> list[BudgetItem]:
    """Coerce number, string, dictionary, or list into a valid list of BudgetItem models."""
    import re
    if val is None:
        return []
    if isinstance(val, BudgetItem):
        return [val]
    if isinstance(val, (int, float, Decimal)):
        return [BudgetItem(item="Proposed Budget", amount=Decimal(str(val)))]
    if isinstance(val, list):
        res = []
        for x in val:
            if isinstance(x, BudgetItem):
                res.append(x)
            elif isinstance(x, dict):
                res.append(BudgetItem.model_validate(x))
            elif isinstance(x, (int, float, Decimal, str)):
                b_items = coerce_to_budget_items(x)
                res.extend(b_items)
        return res
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return coerce_to_budget_items(parsed)
            except Exception:
                pass
        num_cleaned = re.sub(r'^(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:/-)?$', r'\1', s, flags=re.IGNORECASE).replace(",", "").strip()
        try:
            single_amt = Decimal(num_cleaned)
            return [BudgetItem(item="Proposed Budget", amount=single_amt)]
        except Exception:
            pass
        entries = [e.strip() for e in re.split(r'[\n,;]+', s) if e.strip()]
        res = []
        for entry in entries:
            res.append(BudgetItem._preprocess_budget_item(entry))
        return [BudgetItem.model_validate(r) if isinstance(r, dict) else r for r in res]
    if isinstance(val, dict):
        return [BudgetItem.model_validate(val)]
    return []


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
    ref_no: Optional[str] = None
    date: Optional[str | date] = None

    def model_post_init(self, __context: Any) -> None:
        if self.ref_no and not self.no:
            self.no = self.ref_no
        elif self.no and not self.ref_no:
            self.ref_no = self.no



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

    # Standing defaults / overrides
    purchase_order: Optional[str] = None
    advance: Optional[str] = None
    laboratory_office: Optional[str] = None

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _preprocess_event_record(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Normalize judges
        if "judges" in data:
            j_val = data["judges"]
            if isinstance(j_val, TrackedField):
                j_val.value = coerce_to_list_of_strings(j_val.value)
            elif isinstance(j_val, dict) and "value" in j_val:
                j_val["value"] = coerce_to_list_of_strings(j_val["value"])
            else:
                data["judges"] = tf(coerce_to_list_of_strings(j_val), FieldSource.user, True)

        # Normalize budget_items
        if "budget_items" in data:
            data["budget_items"] = coerce_to_budget_items(data["budget_items"])
        elif any(data.get(k) for k in ("estimated_budget", "budget", "budget_amount", "sanctioned_budget")):
            b_val = data.get("estimated_budget") or data.get("budget") or data.get("budget_amount") or data.get("sanctioned_budget")
            data["budget_items"] = coerce_to_budget_items(b_val)

        # Align participants and expected_participants
        if "participants" in data and ("expected_participants" not in data or not data.get("expected_participants")):
            data["expected_participants"] = data["participants"]
        elif "expected_participants" in data and ("participants" not in data or not data.get("participants")):
            data["participants"] = data["expected_participants"]

        # Normalize winners
        if "winners" in data:
            w_val = data["winners"]
            if isinstance(w_val, str):
                s = w_val.strip()
                if not s:
                    data["winners"] = []
                elif s.startswith("[") and s.endswith("]"):
                    try:
                        data["winners"] = json.loads(s)
                    except Exception:
                        data["winners"] = [{"name": part.strip()} for part in s.split(",") if part.strip()]
                else:
                    data["winners"] = [{"name": part.strip()} for part in re.split(r'[,;\n]+', s) if part.strip()]
            elif w_val is None:
                data["winners"] = []

        # Normalize bills
        if "bills" in data:
            b_val = data["bills"]
            if isinstance(b_val, str):
                s = b_val.strip()
                if not s:
                    data["bills"] = []
                elif s.startswith("[") and s.endswith("]"):
                    try:
                        data["bills"] = json.loads(s)
                    except Exception:
                        data["bills"] = []
                else:
                    data["bills"] = [{"invoice_no": part.strip()} for part in re.split(r'[,;\n]+', s) if part.strip()]
            elif b_val is None:
                data["bills"] = []

        # Normalize other_reimbursements
        if "other_reimbursements" in data:
            r_val = data["other_reimbursements"]
            if isinstance(r_val, str):
                s = r_val.strip()
                if not s:
                    data["other_reimbursements"] = []
                else:
                    data["other_reimbursements"] = [{"name": part.strip()} for part in re.split(r'[,;\n]+', s) if part.strip()]
            elif r_val is None:
                data["other_reimbursements"] = []

        # Normalize meeting
        if "meeting" in data and isinstance(data["meeting"], dict):
            m_dict = dict(data["meeting"])
            if "attendees" in m_dict:
                m_dict["attendees"] = coerce_to_list_of_strings(m_dict["attendees"])
            if "absentees" in m_dict:
                m_dict["absentees"] = coerce_to_list_of_strings(m_dict["absentees"])
            data["meeting"] = m_dict

        # Auto-wrap any plain value in TrackedField if field expects TrackedField
        for field_name, field_info in cls.model_fields.items():
            if field_name in data:
                val = data[field_name]
                if field_info.annotation and "TrackedField" in str(field_info.annotation):
                    if not isinstance(val, (TrackedField, dict)):
                        data[field_name] = tf(val, FieldSource.user, True)

        # Derive event_code from event_name if not provided
        ec_val = data.get("event_code")
        if not ec_val or (isinstance(ec_val, TrackedField) and not ec_val.is_present):
            ev_name = data.get("event_name")
            if isinstance(ev_name, TrackedField):
                ev_name = ev_name.value
            if ev_name:
                words = [w for w in str(ev_name).split() if w.lower() not in ("a", "an", "the", "for", "in", "on", "of", "&", "-")]
                code = "".join(w[0].upper() for w in words[:4]) or "EVT"
                data["event_code"] = tf(code, FieldSource.extracted_rule, True)

        # Derive category if not provided
        cat_val = data.get("category")
        if not cat_val or (isinstance(cat_val, TrackedField) and not cat_val.is_present):
            cat = data.get("event_type")
            if isinstance(cat, TrackedField):
                cat = cat.value
            data["category"] = tf(cat or "Technical Event", FieldSource.extracted_rule, True)

        return data

    def flat_dict(self) -> dict[str, Any]:
        """Return a flat dictionary suitable for template rendering.

        TrackedField values are unwrapped. Nested objects are kept as-is.
        """
        result: dict[str, Any] = {}
        for field_name in self.__class__.model_fields:
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

        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            for extra_key, extra_val in self.__pydantic_extra__.items():
                if isinstance(extra_val, TrackedField):
                    result[extra_key] = extra_val.value
                elif isinstance(extra_val, BaseModel):
                    result[extra_key] = extra_val.model_dump()
                elif isinstance(extra_val, list):
                    result[extra_key] = [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in extra_val
                    ]
                else:
                    result[extra_key] = extra_val

        # Guarantee both expected_participants and participants are in result
        if result.get("expected_participants") is not None and result.get("participants") is None:
            result["participants"] = result["expected_participants"]
        elif result.get("participants") is not None and result.get("expected_participants") is None:
            result["expected_participants"] = result["participants"]

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

    @classmethod
    def from_flat_dict(cls, data: dict[str, Any]) -> EventRecord:
        """Create an EventRecord from a flat dictionary, wrapping values as TrackedFields where expected."""
        clean_data = dict(data)

        # Normalize judges
        if "judges" in clean_data:
            clean_data["judges"] = coerce_to_list_of_strings(clean_data["judges"])

        # Normalize budget_items
        if "budget_items" in clean_data:
            clean_data["budget_items"] = coerce_to_budget_items(clean_data["budget_items"])
        elif any(clean_data.get(k) for k in ("estimated_budget", "budget", "budget_amount", "sanctioned_budget")):
            b_val = clean_data.get("estimated_budget") or clean_data.get("budget") or clean_data.get("budget_amount") or clean_data.get("sanctioned_budget")
            clean_data["budget_items"] = coerce_to_budget_items(b_val)

        # Normalize and cross-populate participants
        if "participants" in clean_data and ("expected_participants" not in clean_data or not clean_data.get("expected_participants")):
            clean_data["expected_participants"] = clean_data["participants"]
        elif "expected_participants" in clean_data and ("participants" not in clean_data or not clean_data.get("participants")):
            clean_data["participants"] = clean_data["expected_participants"]

        kwargs: dict[str, Any] = {}
        for field_name, field_info in cls.model_fields.items():
            if field_name in clean_data:
                val = clean_data[field_name]
                if field_info.annotation and "TrackedField" in str(field_info.annotation):
                    if isinstance(val, TrackedField):
                        kwargs[field_name] = val
                    else:
                        kwargs[field_name] = TrackedField(value=val, source=FieldSource.user, confirmed=True)
                else:
                    kwargs[field_name] = val
            elif field_name == "event_name" and ("title" in clean_data or "name" in clean_data):
                kwargs["event_name"] = TrackedField(value=clean_data.get("title") or clean_data.get("name"), source=FieldSource.user, confirmed=True)
            elif field_name == "expected_participants" and ("participants" in clean_data and clean_data.get("participants") is not None):
                kwargs["expected_participants"] = TrackedField(value=clean_data.get("participants"), source=FieldSource.user, confirmed=True)
            elif field_name == "participants" and ("expected_participants" in clean_data and clean_data.get("expected_participants") is not None):
                kwargs["participants"] = TrackedField(value=clean_data.get("expected_participants"), source=FieldSource.user, confirmed=True)

        if "budget_items" in clean_data:
            kwargs["budget_items"] = coerce_to_budget_items(clean_data["budget_items"])
        if "winners" in clean_data and isinstance(clean_data["winners"], list):
            kwargs["winners"] = [Winner(**w) if isinstance(w, dict) else w for w in clean_data["winners"]]
        if "bills" in clean_data and isinstance(clean_data["bills"], list):
            kwargs["bills"] = [BillRecord(**b) if isinstance(b, dict) else b for b in clean_data["bills"]]
        if "approval_note" in clean_data and isinstance(clean_data["approval_note"], dict):
            kwargs["approval_note"] = ApprovalNote(**clean_data["approval_note"])
        if "meeting" in clean_data and isinstance(clean_data["meeting"], dict):
            kwargs["meeting"] = MeetingBlock(**clean_data["meeting"])

        return cls(**kwargs)
