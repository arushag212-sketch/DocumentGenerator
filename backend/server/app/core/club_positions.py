"""Club positions: who a person is in the club, as printed on documents.

ClubDocs has two separate kinds of role:

* **App access** (owner, admin, editor, viewer) on a membership decides what a user can do in
  ClubDocs: approve members and documents, create documents and templates, or only read.
* **Club positions** (this module) on a person decide who appears on documents: the faculty
  chairman and student head sign approval notes, a venue's technical assistant is named on
  permission letters, and so on. Faculty and staff hold positions without having an account.

A member can have both: a student head is usually an *admin* in the app and holds the
*student_head* position for signatures.
"""

from __future__ import annotations

POSITIONS: list[dict] = [
    {"key": "faculty_chairman", "label": "Faculty Chairman", "group": "faculty", "signs": True,
     "help": "Signs approval notes and bills as the club's faculty chairman."},
    {"key": "faculty_co_chairman", "label": "Faculty Co-Chairman", "group": "faculty", "signs": True,
     "help": "Second faculty signatory on approval notes."},
    {"key": "faculty_incharge", "label": "Faculty In-charge (venue)", "group": "faculty", "signs": False,
     "help": "Named on permission letters for a venue they look after."},
    {"key": "student_head", "label": "Student Head / Chairperson", "group": "student", "signs": True,
     "help": "Signs letters and receipts on behalf of the students."},
    {"key": "student_secretary", "label": "Student Secretary", "group": "student", "signs": True,
     "help": "Co-signs letters with the student head."},
    {"key": "treasurer", "label": "Treasurer", "group": "student", "signs": True,
     "help": "Signs bill summaries and certificates of expenditure."},
    {"key": "technical_assistant", "label": "Technical Assistant", "group": "staff", "signs": False,
     "help": "Named on permission letters for labs and halls."},
    {"key": "other", "label": "Other", "group": "other", "signs": False,
     "help": "Any other position; give it a designation."},
]

POSITION_KEYS = {p["key"] for p in POSITIONS}
POSITION_LABELS = {p["key"]: p["label"] for p in POSITIONS}
