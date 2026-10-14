"""Document recommender: suggests documents based on event type and lifecycle stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from docgen.models import EventRecord
from docgen.schema import TemplateSchema


@dataclass
class Recommendation:
    template_id: str
    template_name: str
    reason: str
    stage: str
    priority: int = 0  # lower = higher priority


def recommend_documents(event: EventRecord,
                        schemas: dict[str, TemplateSchema],
                        stage: Optional[str] = None) -> list[Recommendation]:
    """Recommend documents based on event type and lifecycle stage.

    Args:
        event: The canonical event record
        schemas: All available template schemas
        stage: Optional filter ('pre_event', 'post_event', 'meeting').
               If None, recommends for all applicable stages.

    Returns:
        List of Recommendation objects, sorted by priority.
    """
    recommendations: list[Recommendation] = []
    record_type = event.record_type.value or "event"
    event_type = (event.event_type.value or event.category.value or "").lower()
    event_name = (event.event_name.value or "").lower()
    has_budget = len(event.budget_items) > 0
    has_winners = len(event.winners) > 0
    has_bills = len(event.bills) > 0

    for schema_id, schema in schemas.items():
        if stage and schema.stage != stage:
            continue

        reason = _get_recommendation_reason(
            schema, record_type, event_type, event_name,
            has_budget, has_winners, has_bills,
        )
        if reason:
            priority = _get_priority(schema.stage, schema_id)
            recommendations.append(Recommendation(
                template_id=schema_id,
                template_name=schema.name,
                reason=reason,
                stage=schema.stage,
                priority=priority,
            ))

    recommendations.sort(key=lambda r: r.priority)
    return recommendations


def _get_recommendation_reason(schema: TemplateSchema,
                                record_type: str,
                                event_type: str,
                                event_name: str,
                                has_budget: bool,
                                has_winners: bool,
                                has_bills: bool) -> Optional[str]:
    """Determine if and why a template should be recommended."""

    # Check triggers
    triggered = False
    for trigger in schema.triggers:
        trigger_lower = trigger.lower()
        if (trigger_lower in event_type or
            trigger_lower in event_name or
            trigger_lower in record_type):
            triggered = True
            break

    # Stage-based logic
    if schema.id == "permission_letter":
        if record_type in ("event", "meeting"):
            return ("Every event and meeting needs venue permission. "
                    "This letter requests the HoD to allow use of the venue.")
        return None

    elif schema.id == "approval_note":
        if has_budget:
            return ("Your event has budget items. An Approval Note is required "
                    "for the Dean (Students Welfare) to approve funding.")
        if triggered:
            return ("This event type typically requires Dean-level approval. "
                    "The Approval Note formalizes the event proposal with "
                    "financial details.")
        return None

    elif schema.id == "prize_money_receipt":
        if has_winners:
            return (f"You have {len(schema.triggers)} winner(s) to process. "
                    "Each winner needs an individual Prize Money Receipt "
                    "for official disbursement.")
        if "prize" in event_type or "competition" in event_type or "hackathon" in event_type:
            return ("This event type may have winners. Prize Money Receipts "
                    "will be needed once winners are decided.")
        return None

    elif schema.id == "bill_summary":
        if has_winners or has_bills:
            return ("Post-event reimbursement summary. Compiles all prize "
                    "money and vendor payments into one sheet for accounts.")
        return None

    elif schema.id == "bill_certificate":
        if has_bills:
            return (f"You have {len(schema.triggers)} vendor bill(s). Each needs "
                    "a Form BC-R certificate for official payment processing.")
        if has_budget:
            return ("Your event has a budget. Bill Certificates (Form BC-R) "
                    "will be needed once vendor invoices arrive.")
        return None

    elif schema.id == "mom":
        if record_type == "meeting":
            return ("Meeting minutes document the discussion, decisions, "
                    "and action items for the official record.")
        return None

    # Generic trigger match
    if triggered:
        return f"Matches event type/content triggers: {', '.join(schema.triggers[:3])}"

    return None


def _get_priority(stage: str, template_id: str) -> int:
    """Assign priority (lower = first)."""
    priority_map = {
        "permission_letter": 1,
        "approval_note": 2,
        "prize_money_receipt": 3,
        "bill_summary": 4,
        "bill_certificate": 5,
        "mom": 6,
    }
    return priority_map.get(template_id, 10)
