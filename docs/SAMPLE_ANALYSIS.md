# Comprehensive Analysis of Sample PDF Documents

**Document Generator Template Specification & Field Mapping**  
*Date of Analysis: October 2026*  
*Target Engine: Python `python-docx` for automated DOCX document generation*

---

## 1. Executive Summary & Document Workflow

The analyzed document set represents the complete administrative lifecycle of student chapter events (specifically ACM NIT Surat Chapter) under Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat:

```
[1. ACM_Sample_Submitted.pdf] (Event Approval & Budget Sanction Note)
               │
               ▼
[2. Permission_public.pdf] (Room / Seminar Hall Permission Request)
               │
               ▼ (Event Execution)
               │
               ├────────────────────────────────────────┐
               ▼                                        ▼
[3. Bill Certificate_public.pdf] (Form BC-R)     [4. Prize Money Format 2026.pdf]
(Recurring Expenditure & Vendor Bill Passed)     (Receipt for Student Contest Winners)
               │                                        │
               └───────────────────┬────────────────────┘
                                   ▼
                   [5. BIll_summary_public.pdf]
                   (Consolidated Bill & Account Summary)
```

Each document adheres to strict administrative conventions, institutional headers, hierarchical signature blocks, and tabular financial summaries.

---

## 2. Document-by-Document In-Depth Analysis

---

### Document 1: `Permission_public.pdf` (Room / Venue Permission Letter)

#### 1. General Characteristics
- **Purpose**: Formal application to the Head of Department (HoD) requesting reservation and technical access to department infrastructure (Seminar Hall 402, 4th Floor, CSE Department).
- **Page Count in Sample**: 2 pages (Page 2 contains only the repeated letterhead header; the body fits entirely on Page 1. This is a common template spillover artifact).
- **Target Page Count**: Exactly 1 page.
- **Estimated Dimensions**: A4 (8.27 in × 11.69 in / 210 mm × 297 mm), Portrait.
- **Margins**: ~0.75 in (54 pt) Left/Right, ~0.6 in (43 pt) Top/Bottom.

#### 2. Visual Elements & Letterhead
- **Letterhead Type**: Dual-Logo Colored Header
  - **Left Logo**: Official SVNIT Colored Crest/Seal (incorporating sunburst, gear wheel, Sanskrit motto *श्रमम् विना न किमपि साध्यम्*, flame torch). Height: ~1.0 in (72 pt).
  - **Right Logo**: ACM Chapter Blue Diamond Logo (cyan/blue circular background with white lowercase "acm" text in rounded blue diamond/rhombus). Height: ~0.9 in (65 pt).
  - **Center Letterhead Text**:
    - Line 1: `ASSOCIATION for COMPUTING MACHINERY` (Font: Garamond / Times New Roman, Small Caps / Serif, Bold, Color: Hex `#1E5B94` / Steel Blue, ~16 pt).
    - Line 2: `SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT` (Font: Arial / Helvetica, Uppercase, Semi-bold, Color: Hex `#1E5B94` / Steel Blue, ~9.5 pt).
- **Divider**: Subtle spacing before metadata block (no hard line).

#### 3. Complete Verbatim Text (Page 1)
```text
ASSOCIATION for COMPUTING MACHINERY
SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT

REF NO.: ACM/26-27/ROOM/009                                    DATE:

SUBMITTED TO: HoD(CSE Dept.)

SUBJECT: Requesting Permission to Conduct ACM Executives Meet in
Seminar Hall 402, CSE Department.
SCHEDULE OF EVENT:

┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 ABOUT THE EVENT                                  │
├──────────────────────┬───────────────────────────────────────────────────────────┤
│ Brief Description    │ ACM NIT Surat is organizing an Executive Meet to discuss  │
│                      │ the chapter’s vision, provide guidance on organizing      │
│                      │ events and initiatives, and facilitate effective          │
│                      │ collaboration among executive members. The meet will also │
│                      │ focus on planning upcoming activities and coordinating    │
│                      │ group projects.                                           │
│                      │                                                           │
│                      │ We request permission to use Seminar Hall 402 (4th Floor) │
│                      │ on [DATE] from 06:00 PM to 07:30 PM for conducting       │
│                      │ the meet.                                                 │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ Objective            │ To provide guidance to the ACM executive team on          │
│                      │ organizing events, coordinating group projects, and       │
│                      │ fostering effective collaboration in alignment with the   │
│                      │ chapter’s vision and upcoming initiatives.                │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ Number of            │ 150+                                                      │
│ Participants         │                                                           │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ Mode                 │ Offline                                                   │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ Event Organizers     │ ACM Core 2026-27                                          │
└──────────────────────┴───────────────────────────────────────────────────────────┘

Name: Ansh Gupta                                   Name: Sunny Bodiwala
Designation: Chairperson , ACM                     Designation: Tech Assistant , Seminar Hall
Admission No.: I24AI005                            Branch: Computer Science & Engineering
Branch: Artificial Intelligence                    Mobile No.: [REDACTED]
Mobile No.: [REDACTED]

Name: Shri. Rakesh P . Gohil                       Name: Dr. Sankita J. Patel
Designation: Faculty in-charge , Seminar Hall      Designation: Chairman , ACM
Branch: Computer Science & Engineering             Branch: Computer Science & Engineering
```

#### 4. Field-by-Field Breakdown
| Field Name | Type | Sample Value | Notes & Formatting |
|---|---|---|---|
| `reference_number` | Text | `ACM/26-27/ROOM/009` | Bold label `REF NO.: `, followed by code |
| `date` | Date string | *(Blank in sample)* | Inline right-aligned label `DATE:` |
| `submitted_to` | Text | `HoD(CSE Dept.)` | Bold label `SUBMITTED TO: ` |
| `subject` | Text | `Requesting Permission to Conduct ACM Executives Meet in Seminar Hall 402, CSE Department.` | Bold label `SUBJECT: ` |
| `schedule_of_event` | Text | `[REDACTED / Bar]` | Bold label `SCHEDULE OF EVENT:` |
| `brief_description` | Paragraph | ACM executive meet description + venue request clause | Left cell bold: `Brief Description` |
| `venue` | Text | `Seminar Hall 402 (4th Floor)` | Embedded in description paragraph |
| `event_timing` | Text | `from 06:00 PM to 07:30 PM` | Embedded in description paragraph |
| `objective` | Text | To provide guidance to the ACM executive team... | Left cell bold: `Objective` |
| `number_of_participants` | Text | `150+` | Left cell bold: `Number of Participants` |
| `mode` | Option/Text | `Offline` | `Offline` / `Online` / `Hybrid` |
| `event_organizers` | Text | `ACM Core 2026-27` | Left cell bold: `Event Organizers` |
| `requester_name` | Text | `Ansh Gupta` | Student chairperson |
| `requester_designation` | Text | `Chairperson , ACM` | Note space before comma |
| `requester_admission_no` | Text | `I24AI005` | Roll / Admission Number |
| `requester_branch` | Text | `Artificial Intelligence` | Branch name |
| `requester_mobile` | Phone | *(Redacted)* | Mobile Number |
| `tech_assistant_name` | Text | `Sunny Bodiwala` | Technical Assistant for Venue |
| `tech_assistant_designation`| Text | `Tech Assistant , Seminar Hall` | Note space before comma |
| `tech_assistant_branch` | Text | `Computer Science & Engineering` | Department |
| `faculty_incharge_venue` | Text | `Shri. Rakesh P . Gohil` | Venue Faculty In-Charge |
| `faculty_incharge_desig` | Text | `Faculty in-charge , Seminar Hall` | Note space before comma |
| `faculty_advisor_name` | Text | `Dr. Sankita J. Patel` | Chapter Faculty Advisor |
| `faculty_advisor_desig` | Text | `Chairman , ACM` | Chapter Faculty Chairman |

#### 5. Layout & Typography
- **Fonts**: Primary font is Arial / Calibri (sans-serif) for body and tables. Letterhead title uses Garamond / Georgia (serif).
- **Table**: 2 columns (approx 28% left column, 72% right column). All borders visible (single line, ~0.75 pt, black). Cell padding: 4 pt top/bottom, 6 pt left/right.
- **Signature Layout**: A 2 × 2 grid. In DOCX, implemented as a 2-column borderless table with 2 rows.

#### 6. Official Typos & Peculiarities (Preserve)
- Spaces before commas in designations: `Chairperson , ACM`, `Tech Assistant , Seminar Hall`, `Faculty in-charge , Seminar Hall`, `Chairman , ACM`.
- Space before period in middle initial: `Shri. Rakesh P . Gohil`.
- Lack of spacing before opening parenthesis: `HoD(CSE Dept.)`.
- Redundant second page containing only the running header.

---

### Document 2: `Prize Money Format 2026.pdf` (Prize Money Receipt)

#### 1. General Characteristics
- **Purpose**: Formal receipt voucher signed by contest winners to acknowledge receipt of cash / bank prize transfer, capturing banking details and faculty chairman recommendation.
- **Page Count in Sample**: Exactly 1 page.
- **Estimated Dimensions**: A4 Portrait.
- **Margins**: Standard 0.75 in (54 pt) Left/Right, 0.75 in Top/Bottom.

#### 2. Visual Elements & Letterhead
- **Letterhead Type**: Monochromatic Institutional Header with Crest
  - **Left Logo**: Official SVNIT Seal (Grayscale / Black & White bitmap). Height: ~0.9 in (65 pt).
  - **Text Block (Center Aligned)**:
    - Line 1: `सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत` (Hindi, Mangal / Nirmala UI / Kruti Dev, ~14 pt, Bold).
    - Line 2: `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` (English, Times New Roman, Bold, ~10 pt). **CRITICAL TYPO**: `NATIOINAL`.
    - Line 3: `ACM` (Times New Roman / Calibri, Bold, ~13 pt).
- **Divider**: Single horizontal black line across the page width under the header.

#### 3. Complete Verbatim Text
```text
[SVNIT CREST]    सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत
        SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT
                                    ACM
────────────────────────────────────────────────────────────────────────────

                            Prize Money Receipt

Sr. No. ___________
Date: ___________

It is hereby acknowledged that an amount of ₹ _________________will be received by me for
securing _________________ Position in the competition/event named
____________________________________________________________________________________
organized by ACM
held on   /   / 2026                 at _________________________________

                              (Account Detail)

┌────────────────────────────┬──────────────────────────────────────────────┐
│ Affiliating Institute:     │ Sardar Vallabhbhai National Institute of     │
│                            │ Technology, Surat (SVNIT)                    │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Name as per Bank Account:  │                                              │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Bank Name:                 │                                              │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Branch:                    │                                              │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Account No.:               │                                              │
├────────────────────────────┼──────────────────────────────────────────────┤
│ IFSC Code:                 │                                              │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Pan Card No.:              │                                              │
└────────────────────────────┴──────────────────────────────────────────────┘

Student Details

  ● Name: __________________________________________________
  ● Roll No.: __________________________________________________
  ● Course & Semester: __________________________________________________
  ● Mobile No.: __________________________________________________

Signature: ______________________________

It is certified that the said amount is recommended for payment.

Chairman Signature  ______________________________
```

#### 4. Field-by-Field Breakdown
| Field Name | Type | Sample Value | Notes & Formatting |
|---|---|---|---|
| `sr_no` | Text | *(Blank underline)* | `Sr. No. ___________` |
| `date` | Date | *(Blank underline)* | `Date: ___________` |
| `prize_amount` | Currency | *(Blank underline)* | `amount of ₹ _________________will` |
| `position_secured` | Text | *(Blank underline)* | `securing _________________ Position` |
| `event_name` | Text | *(Blank underline)* | Multiline fill line |
| `event_date` | Date | ` / / 2026` | Hardcoded year `2026` with blank day/month |
| `event_venue` | Text | *(Blank underline)* | `at _________________________________` |
| `affiliating_institute` | Text | SVNIT fixed value | Fixed pre-filled cell in table |
| `account_holder_name` | Text | *(Blank cell)* | `Name as per Bank Account:` |
| `bank_name` | Text | *(Blank cell)* | `Bank Name:` |
| `branch` | Text | *(Blank cell)* | `Branch:` |
| `account_number` | Text | *(Blank cell)* | `Account No.:` |
| `ifsc_code` | Text | *(Blank cell)* | `IFSC Code:` |
| `pan_card_no` | Text | *(Blank cell)* | `Pan Card No.:` |
| `student_name` | Text | *(Blank line)* | Bullet item `● Name:` |
| `student_roll_no` | Text | *(Blank line)* | Bullet item `● Roll No.:` |
| `course_and_semester`| Text | *(Blank line)* | Bullet item `● Course & Semester:` |
| `student_mobile_no` | Phone | *(Blank line)* | Bullet item `● Mobile No.:` |
| `student_signature` | Signature | *(Blank line)* | `Signature: ______________________________` |
| `recommendation_text`| Text | Pre-printed certification | "It is certified that the said amount is recommended for payment." |
| `chairman_signature`| Signature | *(Blank line)* | `Chairman Signature ______________________________` |

#### 5. Layout & Typography
- **Fonts**: Times New Roman / Georgia (Serif) throughout body text and headers.
- **Title**: `Prize Money Receipt` is Bold, Centered, Underlined (~14 pt).
- **Table**: 2 columns (approx 35% left, 65% right). All cell borders black, single stroke (~0.75 pt).
- **Bullets**: Solid circle bullet `●` (Unicode `\u25cf`) with tab stop.

#### 6. Official Typos & Peculiarities (Preserve)
- **CRITICAL TYPO**: `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` - "NATIOINAL" is misspelled with extra 'I'.
- Hardcoded year: `held on / / 2026`.
- Missing whitespace in inline underline: `₹ _________________will` (no space between underline and "will").
- Capitalization: `Pan Card No.:` (Card capitalized).

---

### Document 3: `ACM_Sample_Submitted.pdf` (Event Approval & Sanction Note)

#### 1. General Characteristics
- **Purpose**: Formal administrative proposal for conducting an event, outlining objectives, judge details, and budget breakdown, submitted to the Dean (Students Welfare) for multi-tier institutional approval.
- **Page Count in Sample**: 3 pages (Page 1: Proposal & Budget; Page 2: Signatures & Office Note; Page 3: Blank page with header).
- **Target Page Count**: Exactly 2 pages.
- **Estimated Dimensions**: A4 Portrait.
- **Margins**: ~0.7 in Left/Right, ~0.6 in Top/Bottom.

#### 2. Visual Elements & Letterhead
- **Letterhead Type**: Trilingual Institutional Header with Crest & Vertical SVNIT Callout
  - **Left Logo**: SVNIT Crest (Grayscale). Height: ~0.95 in (68 pt).
  - **Center Text (3 Languages)**:
    - Line 1: `सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत` (Hindi, Bold, ~13 pt).
    - Line 2: `SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT` (English, Bold, ~10 pt - note: spelled correctly here!).
    - Line 3: `સરદાર વલ્લભભાઈ રાષ્ટ્રીય પ્રૌદ્યોગિકી સંસ્થા, સુરત` (Gujarati, Bold, ~10 pt).
  - **Right Edge**: Vertical text `SVNIT` placed vertically along the right border.
  - **Divider**: Double horizontal rule (or thick single rule) below the trilingual text.

#### 3. Complete Verbatim Text (Pages 1 & 2)

##### Page 1:
```text
No : ACM/2026-27/SIH/001                                   Date : 08/09/2026

Submitted to Dean (Students Welfare):

┌───────────────────────────────────────────────┬──────────────────────────────────┐
│ Subject : Requesting Permission to Conduct Internal Hackathon of SIH             │
├───────────────────────────────────────────────┼───┬──────────────────────────────┤
│ Chapter/Club/Society/Section Name             │ : │ ACM                          │
├───────────────────────────────────────────────┼───┼──────────────────────────────┤
│ Chapter/Club/Society/Section Code No          │ : │ 6/52                         │
├───────────────────────────────────────────────┼───┼──────────────────────────────┤
│ Schedule of Event (Date, Day)                 │ : │ September 12th 2026          │
├───────────────────────────────────────────────┼───┼──────────────────────────────┤
│ Event Venue                                   │ : │ CSE Department               │
└───────────────────────────────────────────────┴───┴──────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 About the Event                                  │
├───────────────────────────────┬───┬──────────────────────────────────────────────┤
│ Title of the Event            │ : │ Internal Hackathon of SIH                    │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Category of the Event         │ : │ Hackathon                                    │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Brief Description             │ : │ The Internal Hackathon for Smart India       │
│                               │   │ Hackathon (SIH) is an institute-level        │
│                               │   │ selection round organized to shortlist the   │
│                               │   │ best student teams who will represent the    │
│                               │   │ college/university at the National Level     │
│                               │   │ Smart India Hackathon.                       │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Objectives                    │ : │ The SIH Internal Hackathon aims to foster    │
│                               │   │ innovation and problem-solving among         │
│                               │   │ students by encouraging them to develop      │
│                               │   │ practical solutions for real-world           │
│                               │   │ challenges. It promotes teamwork,            │
│                               │   │ creativity, and technical expertise while    │
│                               │   │ selecting the most promising projects to     │
│                               │   │ represent the institute at the national      │
│                               │   │ Smart India Hackathon stage.                 │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Target Audience               │ : │ All year Student                             │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Expected Number of            │ : │ 1000+                                        │
│ Participants                  │   │                                              │
├───────────────────────────────┼───┼──────────────────────────────────────────────┤
│ Name of Judges                │ : │ Dr. Alok Kumar                               │
└───────────────────────────────┴───┴──────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│                                Financial Proposal                                │
├─────────────────┬─────────────────────────────┬──────────────────────────────────┤
│ Event Expenses  │ Items                       │ Approximate Amount (Rs)          │
├─────────────────┼─────────────────────────────┼──────────────────────────────────┤
│                 │ Banner (8*6)                │ 800                              │
│                 ├─────────────────────────────┼──────────────────────────────────┤
│                 │ Miscellaneous               │ 300                              │
├─────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ Total           │                             │ 1100                             │
└─────────────────┴─────────────────────────────┴──────────────────────────────────┘
```

##### Page 2:
```text
Signature of Student Head                          Signature of Student Secretary
Name: Ansh Gupta                                   Name: Arshad Khatib
Roll No. I24AI005                                  Roll No. U24AI112
Branch: AI                                         Branch: AI
Mobile No. +91 87806 37299                         Mobile No. +91 88060 45005


Signature of Faculty Co-Chairman                   Signature of Faculty Chairman
Name: Dr. Balu Parne                               Name: Dr. Sankita Patel
Designation: Co-Chairman                           Designation: Chairman
Dept: CSE                                          Dept: CSE
Moblie No. +91 94224 48729                         Moblie No. +91 98792 20919


┌──────────────────────────────────────────────────────────────────────────────────┐
│                                    Office Use                                    │
├───────────────────────────────────────────────────────────────┬──────────────────┤
│ Total amount Sanctioned in Current Academic Year              │ :                │
├───────────────────────────────────────────────────────────────┼──────────────────┤
│ Amount Utilized                                               │ :                │
├───────────────────────────────────────────────────────────────┼──────────────────┤
│ Current Proposed amount                                       │ :                │
├───────────────────────────────────────────────────────────────┼──────────────────┤
│ Balance amount                                                │ :                │
├───────────────────────────────────────────────────────────────┼──────────────────┤
│ Signature (Office Clerk)                                      │ :                │
└───────────────────────────────────────────────────────────────┴──────────────────┘

Recommended/Not Recommended     Recommended/Not Recommended     Approved/Not Approved


    Dr. Rakesh Maurya               Dr. Manish K Rathod             Dr. Sanjay R. Patel
   Chairman, F& SW                  Associate Dean(SW)             Dean (Students Welfare)
```

#### 4. Field-by-Field Breakdown
| Field Name | Type | Sample Value | Notes & Formatting |
|---|---|---|---|
| `proposal_no` | Text | `ACM/2026-27/SIH/001` | `No : ` label |
| `proposal_date` | Date | `08/09/2026` | `Date : ` label |
| `recipient` | Text | `Dean (Students Welfare)` | `Submitted to Dean (Students Welfare):` |
| `subject` | Text | `Requesting Permission to Conduct Internal Hackathon of SIH` | In table header cell |
| `chapter_name` | Text | `ACM` | `Chapter/Club/Society/Section Name` |
| `chapter_code` | Text | `6/52` | `Chapter/Club/Society/Section Code No` |
| `event_schedule` | Text | `September 12th 2026` | `Schedule of Event (Date, Day)` |
| `event_venue` | Text | `CSE Department` | `Event Venue` |
| `event_title` | Text | `Internal Hackathon of SIH` | `Title of the Event` |
| `event_category`| Text | `Hackathon` | `Category of the Event` |
| `brief_description` | Paragraph | SIH internal hackathon selection text | `Brief Description` |
| `objectives` | Paragraph | Innovation and problem-solving text | `Objectives` |
| `target_audience` | Text | `All year Student` | Note: singular "Student" |
| `expected_participants` | Text | `1000+` | `Expected Number of Participants` |
| `judges_name` | Text | `Dr. Alok Kumar` | `Name of Judges` |
| `budget_items` | Array of objects | `[{"item": "Banner (8*6)", "cost": 800}, {"item": "Miscellaneous", "cost": 300}]` | Rows in Financial Proposal |
| `budget_total` | Number | `1100` | Sum total in Financial Proposal |
| `student_head_name` | Text | `Ansh Gupta` | Student Head block |
| `student_head_roll` | Text | `I24AI005` | `Roll No.` without colon |
| `student_head_branch` | Text | `AI` | Branch code |
| `student_head_mobile` | Phone | `+91 87806 37299` | Mobile number |
| `student_sec_name` | Text | `Arshad Khatib` | Student Secretary block |
| `student_sec_roll` | Text | `U24AI112` | Roll number |
| `student_sec_branch` | Text | `AI` | Branch code |
| `student_sec_mobile` | Phone | `+91 88060 45005` | Mobile number |
| `faculty_cochair_name` | Text | `Dr. Balu Parne` | Faculty Co-Chairman |
| `faculty_cochair_desig`| Text | `Co-Chairman` | Designation |
| `faculty_cochair_dept` | Text | `CSE` | Department |
| `faculty_cochair_mobile`| Phone | `+91 94224 48729` | **TYPO LABEL**: `Moblie No.` |
| `faculty_chair_name` | Text | `Dr. Sankita Patel` | Faculty Chairman |
| `faculty_chair_desig` | Text | `Chairman` | Designation |
| `faculty_chair_dept` | Text | `CSE` | Department |
| `faculty_chair_mobile`| Phone | `+91 98792 20919` | **TYPO LABEL**: `Moblie No.` |
| `sanctioned_academic_year`| Currency | *(Blank in sample)* | `Total amount Sanctioned in Current Academic Year` |
| `amount_utilized` | Currency | *(Blank in sample)* | `Amount Utilized` |
| `current_proposed_amount`| Currency | *(Blank in sample)* | `Current Proposed amount` |
| `balance_amount` | Currency | *(Blank in sample)* | `Balance amount` |
| `recommender_1_name` | Text | `Dr. Rakesh Maurya` | Chairman, F& SW |
| `recommender_2_name` | Text | `Dr. Manish K Rathod` | Associate Dean(SW) |
| `approver_name` | Text | `Dr. Sanjay R. Patel` | Dean (Students Welfare) |

#### 5. Layout & Typography
- **Fonts**: Arial / Calibri (sans-serif) for body and tables.
- **Three distinct tables on Page 1**:
  - Event Metadata Table (3 columns: Field label ~45%, Colon separator ~5%, Value ~50%).
  - About Event Table (3 columns with same proportions).
  - Financial Proposal Table (3 columns: Event Expenses category, Items description, Amount).
- **Page 2 Signatures**:
  - Two rows of 2-column signature blocks.
  - Office Use Table (2 columns: Label ~75%, Colon/Value ~25%).
  - 3-column recommendation and approval footer block.

#### 6. Official Typos & Peculiarities (Preserve)
- **CRITICAL TYPO**: `Moblie No.` appears for BOTH faculty signature blocks on Page 2 ("Moblie" instead of "Mobile").
- In student blocks: `Roll No. I24AI005` has no colon after "Roll No.", while `Mobile No. +91...` has no colon either.
- Target audience wording: `All year Student` (singular).
- Page 3: Blank spillover page with only header and "SVNIT".

---

### Document 4: `BIll_summary_public.pdf` (Bill Summary)

#### 1. General Characteristics
- **Filename Quirk**: Capital 'I' in filename: `BIll_summary_public.pdf`.
- **Purpose**: Consolidated summary of all bills, expenses, prize money, and vendor reimbursements for an event, with individual recipient bank account disbursement details.
- **Page Count in Sample**: 3 pages (Page 1: Overall Bill Summary; Page 2: Other Bank Account Details; Page 3: Empty page containing only the page border box!).
- **Target Page Count**: Exactly 2 pages.
- **Estimated Dimensions**: A4 Portrait.
- **Border**: A distinct full-page thin black border line framing every page!

#### 2. Visual Elements & Letterhead
- **Letterhead Type**: Pure Text Centered Header (NO LOGO IMAGES)
  - Line 1: `Association for Computing Machinery` (Centered, Georgia / Times New Roman serif, Regular/Semi-bold, ~13 pt).
  - Line 2: `Sardar Vallabhbhai National Institute of Technology, Surat - 395007` (Centered, serif, ~10 pt).
  - Date line below: `Date: ` (Right-aligned, ~10 pt).
- **Document Title**:
  - `BILL SUMMARY` (Centered, Bold, ~12 pt, Uppercase).
  - `Reimbursement for Cost incurred in SIH Internal Hackathon` (Centered, Regular, ~10 pt).

#### 3. Complete Verbatim Text (Pages 1 & 2)

##### Page 1:
```text
                       Association for Computing Machinery
         Sardar Vallabhbhai National Institute of Technology, Surat - 395007

                                                                        Date:

                                   BILL SUMMARY
            Reimbursement for Cost incurred in SIH Internal Hackathon

┌─────────┬──────────────┬────────────────────────┬─────────────────┬────────────────────┐
│ Sr. No. │ Name         │ Account Details        │ To Be Paid to   │ Prize Money (INR)  │
├─────────┴──────────────┴────────────────────────┴─────────────────┴────────────────────┤
│                                         Other                                          │
├─────────┬──────────────┬────────────────────────┬─────────────────┬────────────────────┤
│ 1.      │ [REDACTED]   │ [REDACTED]             │ [REDACTED]      │ [REDACTED]         │
├─────────┴──────────────┴────────────────────────┼─────────────────┼────────────────────┤
│ Grand Total                                     │                 │ [REDACTED]         │
└─────────────────────────────────────────────────┴─────────────────┴────────────────────┘

Student Head                       Student Secretary                 Faculty Chairman
Ansh Gupta                         Arshad Khatib                     Dr. Sankita Patel
ACM NIT-Surat                      ACM NIT-Surat                     ACM NIT-Surat
```

##### Page 2:
```text
                            Other Bank Account Details

┌─────────┬──────────────────┬──────────────────┬─────────────────┬──────────────────────┐
│ Sr. No. │ Name             │ Account No.      │ IFSC Code       │ Amount               │
├─────────┼──────────────────┼──────────────────┼─────────────────┼──────────────────────┤
│ 1.      │ [REDACTED]       │ [REDACTED]       │ [REDACTED]      │ [REDACTED]           │
├─────────┴──────────────────┴──────────────────┴─────────────────┼──────────────────────┤
│ Total:                                                          │ [REDACTED]           │
└─────────────────────────────────────────────────────────────────┴──────────────────────┘

Faculty Chairman
Dr. Sankita Patel
ACM NIT-Surat
```

#### 4. Field-by-Field Breakdown
| Field Name | Type | Sample Value | Notes & Formatting |
|---|---|---|---|
| `summary_date` | Date | *(Blank in sample)* | `Date:` right-aligned |
| `event_reimbursement_title`| Text | `Reimbursement for Cost incurred in SIH Internal Hackathon` | Subtitle below `BILL SUMMARY` |
| `bill_items` | Array of objects | `[{"sr_no": 1, "name": "...", "account_details": "...", "to_be_paid_to": "...", "prize_money": ...}]` | Main summary table |
| `grand_total` | Currency | *(Redacted)* | `Grand Total` row spanning across first 3 cols |
| `student_head_name` | Text | `Ansh Gupta` | Signatory 1 |
| `student_sec_name` | Text | `Arshad Khatib` | Signatory 2 |
| `faculty_chair_name` | Text | `Dr. Sankita Patel` | Signatory 3 |
| `bank_details_items` | Array of objects | `[{"sr_no": 1, "name": "...", "account_no": "...", "ifsc_code": "...", "amount": ...}]` | Page 2 breakdown table |
| `bank_details_total` | Currency | *(Redacted)* | `Total:` row spanning across first 4 cols |
| `page2_signatory_name`| Text | `Dr. Sankita Patel` | Page 2 single signatory (Faculty Chairman) |

#### 5. Layout & Typography
- **Fonts**: Times New Roman throughout.
- **Page Border**: Thin solid outer rectangle box enclosing the page margins on all pages.
- **Tables**: Full borders (single black line). Table 1 has header row, subheader row `Other` spanning full table, item rows, and `Grand Total` footer row.
- **Page 1 Signatures**: 3 columns evenly distributed horizontally across the bottom.
- **Page 2 Signatures**: Left-aligned single block.

#### 6. Official Typos & Peculiarities (Preserve)
- Filename has typo: `BIll_summary_public.pdf` (capital 'I').
- Page 3 is an empty blank page with only the border box.

---

### Document 5: `Bill Certificate_public.pdf` (Form BC-R)

#### 1. General Characteristics
- **Purpose**: Official SVNIT Dean Student Welfare Statutory Form BC-R: Bill Certificate for Recurring Expenditure. Essential audit document certifying vendor bills, indenter satisfaction, stock register entries, and accounts section voucher processing.
- **Page Count in Sample**: Exactly 2 pages.
- **Pagination**: Explicit footer pagination `Page 1 of 2` and `Page 2 of 2` (right-aligned).
- **Estimated Dimensions**: A4 Portrait.
- **Margins**: ~0.65 in Left/Right, ~0.55 in Top/Bottom.

#### 2. Visual Elements & Letterhead
- **Letterhead Type**: Formal Statutory Header with Seal and Form BC-R Identifier
  - **Top Left**: Official SVNIT Crest / Emblem. Height: ~0.95 in (68 pt).
  - **Top Right**: Boxed form indicator:
    ```
    FORM
    BC-R
    ```
    (Right-aligned, bold, ~11 pt).
  - **Center Header Lines**:
    - Line 1: `सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत` (Hindi, Bold, ~13 pt).
    - Line 2: `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` (English, Bold, ~10 pt). **CRITICAL TYPO**: `NATIOINAL`.
    - Line 3: `शिक्षा मंत्रालय, भारत सरकार के द्वारा NITSER अधिनियम के तहत स्थापित एक राष्ट्रीय महत्व का संस्थान` (Hindi, ~8 pt).
    - Line 4: `An Institute of National Importance, Established under NITSER Act by Ministry of Education, Govt. of India` (English, ~8 pt).
    - Line 5: `DEAN STUDENT WELFARE` (Bold, ~11 pt, centered).
- **Divider**: Full horizontal rule across page width below header.

#### 3. Complete Verbatim Text (Pages 1 & 2)

##### Page 1:
```text
[CREST]          सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत
        SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT         FORM
     शिक्षा मंत्रालय, भारत सरकार के द्वारा NITSER अधिनियम के तहत स्थापित एक राष्ट्रीय महत्व का संस्थान     BC-R
  An Institute of National Importance, Established under NITSER Act by Ministry of Education, Govt. of India
                                 DEAN STUDENT WELFARE
──────────────────────────────────────────────────────────────────────────────────

                                BILL CERTIFICATE
                             (RECURRING EXPENDITURE)

┌───────────────────────────────────────────────┬──────────────────────────────────┐
│ Chapter Name: ACM                             │ Code No . 6/52                   │
├───────────────────────────────────────────────┼──────────────────────────────────┤
│ Approval Note No.: ACM/26-27/SIH/001          │ Date: 08/09/2026                 │
├───────────────────────────────────────────────┴──────────────────────────────────┤
│ Original Approval Note/Comparative Statement attached herewith/sent with bill    │
│ No. __________________ dtd.: ____________ for Rs. ____________ of M/s. ________ │
├───────────────────────────────────────────────┬──────────────────────────────────┤
│ Purchase Order No. and date                   │ : NiL                            │
├───────────────────────────────────────────────┼──────────────────────────────────┤
│ Head of Account (Code No.)                    │ : 6/52                           │
├───────────────────────────────────────────────┼──────────────────────────────────┤
│ Advance drawn in Rs. (if any)                 │ : NiL                            │
└───────────────────────────────────────────────┴──────────────────────────────────┘

“I, am ________________, personally satisfied that the goods (described below)
purchased are of the requisite quality and specification and have been purchased
from a reliable supplier / contractor at a reasonable price.”

┌─────┬────────────────────────────────────┬──────────┬──────────────┬─────────────┐
│ Sr. │ Name of the Equipment/ item(s)     │ Quantity │ Unit Cost    │ Total Cost  │
│ No. │                                    │          │ (Rs.)        │ of Item(s)  │
│     │                                    │          │              │ (Rs.)       │
├─────┼────────────────────────────────────┼──────────┼──────────────┼─────────────┤
│ 1.  │ [REDACTED]                         │ 1        │ [REDACTED]   │ [REDACTED]  │
├─────┼────────────────────────────────────┼──────────┼──────────────┼─────────────┤
│ 2.  │ [REDACTED]                         │ 7        │ [REDACTED]   │ [REDACTED]  │
├─────┴────────────────────────────────────┴──────────┴──────────────┼─────────────┤
│ Total Amount (Rs.)                                                 │ [REDACTED]  │
├────────────────────────────────────────────────────────────────────┼─────────────┤
│ + Taxes or other charges                                           │ [REDACTED]  │
├────────────────────────────────────────────────────────────────────┼─────────────┤
│ Total Estimated Amount Including Taxes (Rs.)                       │ [REDACTED]  │
└────────────────────────────────────────────────────────────────────┴─────────────┘

                                SUPPLIER DETAILS
┌──────────────────────────────────────┬───────────────────────────────────────────┐
│ Name of the Supplier                 │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ GST No.                              │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Any other Taxes                      │ -                                         │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Invoice No. and date                 │ 1059 and 08/09/2026                       │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Amount (Rs.)                         │ [REDACTED]                                │
└──────────────────────────────────────┴───────────────────────────────────────────┘

                                PAYMENT DETAILS
┌──────────────────────────────────────┬───────────────────────────────────────────┐
│ Name of the Party                    │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Account Number                       │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Account Holder Name                  │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Name of the Bank                     │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Name of the Branch                   │ [REDACTED]                                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ IFSC Code                            │ [REDACTED]                                │
└──────────────────────────────────────┴───────────────────────────────────────────┘
                                                                        Page 1 of 2
```

##### Page 2:
```text
                              STOCK ENTRY DETAILS
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Name of the Laboratory / Office: Student Council                                 │
├──────────────────────┬──────────────────────┬────────────────────────────────────┤
│ Recurring Register   │ Consumable Register  │        Miscellaneous Register      │
│                      │                      ├────────────────────────────────────┤
│                      │                      │ Name/Type                          │
├──────────────────────┼──────────────────────┼────────────────────────────────────┤
│ Serial Number        │                      │                                    │
├──────────────────────┼──────────────────────┼────────────────────────────────────┤
│ Page Number          │                      │                                    │
├──────────────────────┴──────────────────────┼────────────────────────────────────┤
│ Date                                        │ Name and Signature of a            │
│                                             │ Clerk/Staff                        │
└─────────────────────────────────────────────┴────────────────────────────────────┘

                                INDENTER DETAILS
┌──────────────────────────────────────┬─────────────┬─────────────────────────────┐
│ Name of the Faculty                  │             │ Designation                 │
│ Chairman/Co-Chairman                 │             │ Assistant Professor         │
├──────────────────────────────────────┤             ├─────────────────────────────┤
│ Dr. Sankita J. Patel                 │             │                             │
├──────────────────────────────────────┤             ├─────────────────────────────┤
│ Department : CSE                     │             │ Signature with Date         │
└──────────────────────────────────────┴─────────────┴─────────────────────────────┘

                     Recommendation (Head of the Department)
┌──────────────────────────────────────┬───────────────────────────────────────────┐
│ Recommended Amount                   │ [REDACTED]                                │
├──────────────────────────────────────┴───────────────────────────────────────────┤
│ Approved and Recommended for Bill Payment                                        │
├──────────────────────────────────────┬───────────────────────────────────────────┤
│ Date:                                │ Dean Student Welfare                      │
└──────────────────────────────────────┴───────────────────────────────────────────┘

                           (FOR USE IN ACCOUNT SECTION)
┌─────────────────────────────────────────────────────────────┬────────────────────┐
│                                                             │ Date:              │
├──────────────────────────────────────┬──────────────────────┴────────────────────┤
│ Head of Account                      │ :                                         │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Budget Code No.                      │ :                                         │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Mode of Payment                      │ : Cash/ Cheque/ Online/                   │
│                                      │   Adjusted Against Advance                │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Details of Mode of Payment           │ :                                         │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Voucher No. and Date                 │ :                                         │
├──────────────────────────────────────┴───────────────────────────────────────────┤
│ Passed for payment/adjustment of Amount in (Rs.) _________________               │
│ (in figs.) ________________                                                      │
│ (in words)_________________________________________________________________      │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Signature                                                                        │
├──────────────────────┬──────────────────────────────┬────────────────────────────┤
│ Office Supt.         │ Dy. Registrar (A/cs.)        │ Registrar/Director         │
└──────────────────────┴──────────────────────────────┴────────────────────────────┘
                                                                        Page 2 of 2
```

#### 4. Field-by-Field Breakdown
| Field Name | Type | Sample Value | Notes & Formatting |
|---|---|---|---|
| `chapter_name` | Text | `ACM` | `Chapter Name:` |
| `chapter_code` | Text | `6/52` | `Code No . 6/52` (note space before dot) |
| `approval_note_no` | Text | `ACM/26-27/SIH/001` | Links to Approval Note |
| `approval_date` | Date | `08/09/2026` | Date of Approval Note |
| `bill_no_ref` | Text | *(Blank underline)* | Reference bill number |
| `bill_date_ref` | Date | *(Blank underline)* | Reference bill date |
| `bill_amount_ref` | Currency | *(Blank underline)* | Reference bill amount |
| `vendor_m_s` | Text | *(Blank underline)* | Vendor M/s. |
| `purchase_order_ref`| Text | `NiL` | Note capitalization `NiL` |
| `head_of_account` | Text | `6/52` | `Head of Account (Code No.)` |
| `advance_drawn` | Text | `NiL` | Note capitalization `NiL` |
| `indenter_cert_name`| Text | *(Blank underline)* | In certification clause `“I, am ________________”` |
| `items_table` | Array of objects | `[{"sr": 1, "name": "...", "qty": 1, "unit_cost": ..., "total_cost": ...}, ...]` | Purchased items table |
| `items_total_amount`| Currency | *(Redacted)* | `Total Amount (Rs.)` |
| `items_taxes` | Currency | *(Redacted)* | `+ Taxes or other charges` |
| `items_grand_total` | Currency | *(Redacted)* | `Total Estimated Amount Including Taxes (Rs.)` |
| `supplier_name` | Text | *(Redacted)* | `Name of the Supplier` |
| `supplier_gst` | Text | *(Redacted)* | `GST No.` |
| `supplier_other_taxes`| Text | `-` | `Any other Taxes` |
| `supplier_invoice_ref`| Text | `1059 and 08/09/2026` | `Invoice No. and date` |
| `supplier_amount` | Currency | *(Redacted)* | `Amount (Rs.)` |
| `payee_name` | Text | *(Redacted)* | `Name of the Party` |
| `payee_account_no` | Text | *(Redacted)* | `Account Number` |
| `payee_holder_name` | Text | *(Redacted)* | `Account Holder Name` |
| `payee_bank_name` | Text | *(Redacted)* | `Name of the Bank` |
| `payee_branch` | Text | *(Redacted)* | `Name of the Branch` |
| `payee_ifsc` | Text | *(Redacted)* | `IFSC Code` |
| `stock_office_name` | Text | `Student Council` | `Name of the Laboratory / Office:` |
| `stock_register_type`| Option | `Recurring / Consumable / Miscellaneous` | Register selection columns |
| `stock_sr_no` | Text | *(Blank)* | `Serial Number` in stock register |
| `stock_page_no` | Text | *(Blank)* | `Page Number` in stock register |
| `indenter_faculty_name`| Text | `Dr. Sankita J. Patel` | Faculty Chairman |
| `indenter_designation`| Text | `Assistant Professor` | Designation |
| `indenter_dept` | Text | `CSE` | `Department : CSE` |
| `hod_rec_amount` | Currency | *(Redacted)* | `Recommended Amount` |
| `acct_head` | Text | *(Blank)* | `Head of Account :` |
| `acct_budget_code` | Text | *(Blank)* | `Budget Code No. :` |
| `acct_payment_mode` | Option | `Cash/ Cheque/ Online/ Adjusted Against Advance` | Pre-printed choices |
| `acct_voucher_ref` | Text | *(Blank)* | `Voucher No. and Date :` |
| `acct_passed_fig` | Currency | *(Blank)* | `(in figs.)` |
| `acct_passed_words` | Text | *(Blank)* | `(in words)` |

#### 5. Layout & Typography
- **Fonts**: Arial / Calibri (sans-serif) for body and tables. Headings in Times New Roman / Arial Bold.
- **Tables**: Heavy use of boxed tables (6 separate tables across 2 pages).
- **Pagination**: Centered or right-aligned footer: `Page 1 of 2`, `Page 2 of 2`.

#### 6. Official Typos & Peculiarities (Preserve)
- **CRITICAL TYPO**: `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` - "NATIOINAL" is misspelled with extra 'I' in the official institute English name.
- Punctuation typo in indenter clause: `“I, am ________________, personally satisfied...` (erroneous comma after 'I').
- Punctuation spacing: `Code No . 6/52` (space before dot).
- Mixed capitalization: `NiL` (capital N, lower i, capital L).
- Form header: `FORM BC-R` aligned to top right.

---

## 3. Cross-Document Shared Fields & Unified Data Schema

### 1. Unified Shared Data Model
The 5 documents share a unified data core representing the Student Chapter, the Event, and the Key People:

| Entity Field | JSON Property | Sources | Example Value |
|---|---|---|---|
| **Institute Name (English)** | `institute_name_en` | All 5 | `Sardar Vallabhbhai National Institute of Technology, Surat` |
| **Institute Name (Hindi)** | `institute_name_hi` | Docs 2, 3, 5 | `सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत` |
| **Institute Name (Gujarati)** | `institute_name_gu` | Doc 3 | `સરદાર વલ્લભભાઈ રાષ્ટ્રીય પ્રૌદ્યોગિકી સંસ્થા, સુરત` |
| **Institute Short Name** | `institute_code` | Docs 1, 2, 3, 4, 5 | `SVNIT` |
| **Chapter Name** | `chapter_name` | All 5 | `ACM` / `Association for Computing Machinery` |
| **Chapter Code** | `chapter_code` | Docs 3, 5 | `6/52` |
| **Academic Year** | `academic_year` | Docs 1, 2, 3, 5 | `2026-27` / `26-27` |
| **Event Reference Code** | `event_ref_code` | Docs 1, 3, 5 | `SIH` (or `ROOM`, etc.) |
| **Event Reference Number** | `event_ref_no` | Docs 1, 3, 5 | `ACM/2026-27/SIH/001` |
| **Event Title** | `event_title` | Docs 1, 3, 4 | `Internal Hackathon of SIH` |
| **Event Date** | `event_date` | Docs 1, 3, 5 | `September 12th 2026` / `08/09/2026` |
| **Event Venue** | `event_venue` | Docs 1, 3 | `Seminar Hall 402, CSE Department` |
| **Faculty Chairman Name** | `faculty_chairman_name` | Docs 1, 2, 3, 4, 5 | `Dr. Sankita J. Patel` / `Dr. Sankita Patel` |
| **Faculty Chairman Dept** | `faculty_chairman_dept` | Docs 1, 3, 5 | `Computer Science & Engineering` / `CSE` |
| **Student Head Name** | `student_head_name` | Docs 1, 3, 4 | `Ansh Gupta` |
| **Student Head Roll No** | `student_head_roll` | Docs 1, 3 | `I24AI005` |
| **Student Secretary Name** | `student_sec_name` | Docs 3, 4 | `Arshad Khatib` |
| **Student Secretary Roll** | `student_sec_roll` | Doc 3 | `U24AI112` |
| **Dean Student Welfare** | `dean_sw_name` | Docs 3, 5 | `Dr. Sanjay R. Patel` |

### 2. Numbering Conventions
- **Event Proposal Number**: `ACM/<Year>/<EventCode>/<Serial3Digits>` (e.g. `ACM/2026-27/SIH/001`)
- **Venue Permission Number**: `ACM/<Year2Digit>/<VenueCode>/<Serial3Digits>` (e.g. `ACM/26-27/ROOM/009`)
- **Bill Certificate Approval Ref**: Mirrors Event Proposal Number exactly (`ACM/2026-27/SIH/001`)

---

## 4. Master Catalog of Official Typos & Administrative Quirks

In official institutional document generation, preserving exact existing historical letterhead text and formatting quirks is essential so generated templates match signed precedents verbatim:

| Document | Location | Exact Quirk / Typo Text | Normal English Correction | Rule for Template Generation |
|---|---|---|---|---|
| **Prize Money Format 2026** | Letterhead Line 2 | `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` | `...NATIONAL...` | **PRESERVE VERBATIM** in letterhead |
| **Bill Certificate (Form BC-R)** | Letterhead Line 2 | `SARDAR VALLABHBHAI NATIOINAL INSTITUTE OF TECHNOLOGY, SURAT` | `...NATIONAL...` | **PRESERVE VERBATIM** in letterhead |
| **ACM Sample Submitted** | Faculty Signature Blocks (Page 2) | `Moblie No.` (appears under both Co-Chairman and Chairman) | `Mobile No.` | **PRESERVE VERBATIM** in signature blocks |
| **Bill Certificate (Form BC-R)** | Indenter clause (Page 1) | `“I, am ________________, personally satisfied...` | `"I am ..."` (no comma after I) | **PRESERVE VERBATIM** in certification |
| **Bill Certificate (Form BC-R)** | Header Table Row 1 | `Code No . 6/52` (space before dot) | `Code No. 6/52` | **PRESERVE VERBATIM** |
| **Bill Certificate (Form BC-R)** | Purchase Order & Advance | `NiL` (mixed capitalization) | `NIL` or `Nil` | **PRESERVE VERBATIM** |
| **Permission Letter** | Signature blocks | `Chairperson , ACM`, `Tech Assistant , Seminar Hall`, `Faculty in-charge , Seminar Hall` | Comma without preceding space | **PRESERVE VERBATIM** |
| **Permission Letter** | Signatory initial | `Shri. Rakesh P . Gohil` | `Rakesh P. Gohil` | **PRESERVE VERBATIM** |
| **BIll Summary** | Document filename | `BIll_summary_public.pdf` (Capital 'I') | `Bill_summary_public.pdf` | Note in template documentation |

---

## 5. Visual Assets & Image Extraction Specifications

The documents require three distinct graphic asset files to be maintained in `assets/`:

| Asset Filename | Visual Content | Source Documents | Recommended Format & DPI |
|---|---|---|---|
| `svnit_crest_color.png` | Official SVNIT Circular Crest (Full Color with sun, gear, torch) | `Permission_public.pdf` | PNG, 300 DPI, Transparent Background, ~600×600 px |
| `acm_logo_blue.png` | ACM Chapter Logo (Blue/cyan rounded diamond badge with white 'acm') | `Permission_public.pdf` | PNG, 300 DPI, Transparent Background, ~500×500 px |
| `svnit_crest_mono.png` | Official SVNIT Crest (Grayscale / Monochrome high contrast) | `Prize Money Format 2026.pdf`, `ACM_Sample_Submitted.pdf`, `Bill Certificate_public.pdf` | PNG, 300 DPI, Transparent/White Background, ~600×600 px |

---

## 6. Implementation Guidelines for Python `python-docx` Templates

To achieve 100% pixel-faithful rendering in DOCX:

### 1. Letterhead Layout Strategies
- **Dual-Logo Header (`Permission_public.pdf`)**:
  - Implement as a 3-column borderless table (`width=100%`):
    - Col 1 (~1.2 in): Left-aligned SVNIT color crest.
    - Col 2 (~5.5 in): Centered 2-line title in Garamond / Arial blue text.
    - Col 3 (~1.2 in): Right-aligned ACM diamond logo.
- **Single Monochromatic Header (`Bill Certificate`, `Prize Money`, `Approval Note`)**:
  - Implement as a 2-column borderless table:
    - Col 1 (~1.1 in): Left-aligned monochrome SVNIT crest.
    - Col 2 (~6.5 in): Centered Hindi / English institute title.
    - For Form BC-R: Add right column or right-aligned floating frame for `FORM BC-R`.

### 2. Table Borders & Padding
- In `python-docx`, explicit XML manipulation (`w:tcBorders`, `w:tblCellMar`) should be applied:
  - Outer & inner borders: `w:val="single"`, `w:sz="4"`, `w:space="0"`, `w:color="000000"`.
  - Cell margins: top `80`, bottom `80`, left `120`, right `120` dxa (twips).

### 3. Preventing Trailing Blank Pages
- Three of the five samples suffered from trailing blank pages with headers due to MS Word paragraph spacing pushing a final page break.
- In `python-docx`:
  - Set `paragraph_format.space_after = Pt(2)` to `Pt(4)`.
  - Set table rows `cantSplit` attribute to prevent row fragmentation.
  - Omit trailing blank paragraphs after final tables or signature blocks.
