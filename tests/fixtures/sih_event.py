"""Canonical test fixture: SIH Internal Hackathon event.

Rebuilt for Review Round 2 to mirror the non-redacted sample data:
- Title: "Internal Hackathon of SIH"
- Category: "Hackathon"
- Date: "12/09/2026"
- Venue: "CSE Department"
- Target Audience: "All year Student"
- Participants: "1000+"
- Judge: Dr. Alok Kumar
- Budget: Banner (8*6) 800 + Miscellaneous 300 = 1100
- Note date: "08/09/2026"
- Redacted values clearly fake: "TEST VENDOR PVT LTD", "0000000000"
- Fields marked confirmed=True ONLY where the sample shows them.
"""

from decimal import Decimal
from docgen.models import (
    ActionItem,
    AgendaItem,
    ApprovalNote,
    BankDetails,
    BillItem,
    BillRecord,
    BudgetItem,
    EventRecord,
    FieldSource,
    MeetingBlock,
    OtherReimbursement,
    PaymentDetails,
    SupplierDetails,
    TrackedField,
    Winner,
    tf,
)


def get_sih_fixture() -> EventRecord:
    """Return the canonical SIH event fixture mirroring sample PDFs."""
    event = EventRecord()

    # Core identity - from sample ACM_Sample_Submitted.pdf
    event.event_name = tf("Internal Hackathon of SIH", FieldSource.user, confirmed=True)
    event.event_code = tf("SIH", FieldSource.user, confirmed=True)
    event.category = tf("Hackathon", FieldSource.user, confirmed=True)
    event.event_type = tf("Hackathon", FieldSource.user, confirmed=True)
    
    # Description & Objective: Separate AI drafts or user inputs
    event.description = tf(
        "Internal Hackathon of Smart India Hackathon (SIH) for shortlisting institute teams for national submission.",
        FieldSource.user, confirmed=True
    )
    event.objectives = tf(
        "To evaluate problem statements, innovate technical solutions, and select top teams.",
        FieldSource.user, confirmed=True
    )
    event.target_audience = tf("All year Student", FieldSource.user, confirmed=True)
    event.expected_participants = tf("1000+", FieldSource.user, confirmed=True)

    # Schedule & Venue
    event.dates = tf("12/09/2026", FieldSource.user, confirmed=True)
    event.date_start = tf("12/09/2026", FieldSource.user, confirmed=True)
    event.date_end = tf("12/09/2026", FieldSource.user, confirmed=True)
    event.venue = tf("CSE Department", FieldSource.user, confirmed=True)
    event.mode = tf("Offline", FieldSource.user, confirmed=True)
    event.time_start = tf("09:00 AM", FieldSource.user, confirmed=True)
    event.time_end = tf("06:00 PM", FieldSource.user, confirmed=True)

    # Reference & Dates
    # Approval Note reference number
    event.ref_no = tf("ACM/2026-27/SIH/001", FieldSource.user, confirmed=True)
    # Permission Letter ROOM series reference number (suggested, unconfirmed)
    event.room_ref_no = tf("ACM/26-27/ROOM/001", FieldSource.computed, confirmed=False)
    event.document_date = tf("08/09/2026", FieldSource.user, confirmed=True)
    event.submitted_to = tf("HoD(CSE Dept.)", FieldSource.config, confirmed=True)

    # Judges
    event.judges = tf(["Demo Guest Judge"], FieldSource.user, confirmed=True)

    # Financial Proposal: Banner (8*6) 800 + Miscellaneous 300 = 1100 (exactly matching sample)
    event.budget_items = [
        BudgetItem(item="Banner (8*6)", amount=Decimal("800")),
        BudgetItem(item="Miscellaneous", amount=Decimal("300")),
    ]

    # Approval note reference with 08/09/2026 note date
    event.approval_note = ApprovalNote(
        no="ACM/2026-27/SIH/001",
        date="08/09/2026",
    )

    # Winners for Prize Money Receipts (Redacted values are clearly fake)
    event.winners = [
        Winner(
            position="1st",
            name="TEST WINNER ONE",
            roll_no="U24AI000",
            course_semester="B.Tech Artificial Intelligence 3rd Semester",
            mobile="0000000000",
            amount=Decimal("5000"),
            bank=BankDetails(
                name_as_per_bank="TEST WINNER ONE",
                bank_name="TEST STATE BANK",
                branch="TEST CAMPUS BRANCH",
                account_no="000000000000",
                ifsc="TEST0000001",
                pan="ABCDE0000F",
            ),
        ),
        Winner(
            position="2nd",
            name="TEST WINNER TWO",
            roll_no="U24CS000",
            course_semester="B.Tech Computer Science & Engineering 3rd Semester",
            mobile="0000000000",
            amount=Decimal("3000"),
            bank=BankDetails(
                name_as_per_bank="TEST WINNER TWO",
                bank_name="TEST NATIONAL BANK",
                branch="TEST CITY BRANCH",
                account_no="000000000000",
                ifsc="TEST0000002",
                pan="FGHIJ0000K",
            ),
        ),
    ]

    # Bills for Bill Certificate (Form BC-R)
    # Redacted values clearly fake e.g. "TEST VENDOR PVT LTD", "0000000000"
    event.bills = [
        BillRecord(
            supplier=SupplierDetails(name="TEST VENDOR PVT LTD", gst_no="24AAAAA0000A1Z0"),
            invoice_no="INV/TEST/001",
            invoice_date="12/09/2026",
            items=[
                BillItem(name="Banner (8*6)", qty=1, unit_cost=Decimal("800")),
            ],
            tax_type="GST 18%",
            tax_rate_or_amount=Decimal("144"),
            payment=PaymentDetails(
                party="TEST VENDOR PVT LTD",
                account_no="00000000000000",
                holder="TEST VENDOR PVT LTD",
                bank="TEST COMMERCIAL BANK",
                branch="TEST BRANCH",
                ifsc="TEST0000123",
            ),
        )
    ]

    # Other reimbursements for Bill Summary
    event.other_reimbursements = [
        OtherReimbursement(
            name="TEST REIMBURSE PERSON",
            account_no="000000000000",
            ifsc="TEST0000123",
            amount=Decimal("300"),
        )
    ]

    # Meeting block for MoM
    event.meeting = MeetingBlock(
        title="SIH 2026 Core Coordination Meeting",
        ref_no="ACM/2026-27/MOM/001",
        date="10/09/2026",
        start_time="04:00 PM",
        end_time="05:30 PM",
        venue="Seminar Hall 402, CSE Department",
        mode="Offline",
        chaired_by="Demo Faculty Chairman",
        attendees=["Demo Faculty Chairman", "Demo Faculty Co-Chairman", "Demo Student Head", "Demo Student Secretary"],
        absentees=["None"],
        agenda_items=[
            AgendaItem(
                topic="Hackathon Logistics & Lab Allocations",
                discussion="Reviewed internet connectivity and Seminar Hall seating arrangements.",
                decision="Approved Lab 1 and Seminar Hall 402.",
            ),
            AgendaItem(
                topic="Jury Coordination",
                discussion="Confirmed Demo Guest Judge as guest evaluator.",
                decision="Travel honorarium and memento arranged.",
            ),
        ],
        action_items=[
            ActionItem(task="Print banners and signage", owner="Demo Tech Assistant", deadline="11/09/2026"),
            ActionItem(task="Prepare winner certificates and receipts", owner="Demo Student Secretary", deadline="12/09/2026"),
        ],
        prepared_by="Demo Student Head",
        approved_by="Demo Faculty Chairman",
    )

    return event
