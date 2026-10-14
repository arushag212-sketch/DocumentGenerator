# Smart Document Generator for ACM SVNIT Surat

A reusable, template-driven document automation system for the ACM Student Chapter at SVNIT Surat. Converts event requirements (from natural-language prompts, forms, or meeting notes) into standardized, editable club documents (`.docx` and `.pdf`) using real DOCX templates and official institutional branding.

---

## 🚀 Quick Start

### 1. Installation
Ensure Python 3.11+ is installed, then install dependencies:
```bash
pip install -e .
```
*(Or install requirements directly via `pip install docxtpl python-docx dateparser pydantic PyYAML SQLAlchemy fastapi uvicorn streamlit PyMuPDF Pillow num2words`)*

### 2. Configuration
Copy the example configuration to your local config file:
```bash
cp config/club_config.example.yaml config/club_config.yaml
```
*Note: `club_config.yaml` is gitignored to protect sensitive student contact and banking information.*

### 3. Generate Templates
Generate all baseline DOCX templates programmatically:
```bash
python scripts/build_templates.py
```

### 4. Validate All Templates
Validate all schemas and confirm tag integrity:
```bash
python -m docgen.cli validate-templates
```

### 5. Run the End-to-End Demo
Execute the natural language prompt scenario:
```bash
python scripts/demo.py
```

### 6. Launch the Interactive Web UI
Start the Streamlit dashboard:
```bash
streamlit run docgen/ui.py
```

---

## 📂 Project Architecture

```
DocumentGenerator/
├── assets/                 # SVNIT seals, ACM logos, badges
├── config/
│   ├── club_config.yaml         # Real local configuration (gitignored)
│   └── club_config.example.yaml # Committed example configuration
├── docgen/                 # Importable core package
│   ├── api.py              # FastAPI backend endpoints
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration schema and loader
│   ├── db.py               # SQLite storage & document versioning
│   ├── functions.py        # Safe computed math & Indian currency formatting
│   ├── llm.py              # Pluggable LLM interface (Gemini + fallback)
│   ├── missing_fields.py   # Missing and unconfirmed field detector
│   ├── models.py           # Pydantic Canonical Event Record & TrackedFields
│   ├── recommender.py      # Lifecycle stage document recommender
│   ├── renderer.py         # docxtpl rendering and headless PDF conversion
│   ├── schema.py           # YAML template schema loader
│   ├── ui.py               # Streamlit web interface
│   ├── validator.py        # Template tag validator
│   └── extractors/         # Deterministic regex & NLP extractors
├── docs/                   # Full documentation & sample analysis
│   ├── OPEN_QUESTIONS.md
│   ├── SAMPLE_ANALYSIS.md
│   ├── TEMPLATE_AUTHORING.md
│   └── TEMPLATE_NOTES.md
├── outputs/                # Rendered DOCX and PDF documents
├── sample docs/            # Ground truth official PDF reference files
├── scripts/                # Utility scripts (build_templates, extract_images, demo)
└── templates/              # Real DOCX templates & schema definitions
    ├── permission_letter/
    ├── prize_money_receipt/
    ├── approval_note/
    ├── bill_summary/
    ├── bill_certificate/
    └── mom/
```

---

## 📑 Supported Documents

1. **Permission Letter** (`permission_letter`): Venue and seminar hall permission request to HoD (CSE Dept.) with ACM letterhead.
2. **Prize Money Receipt** (`prize_money_receipt`): Individual winner disbursement receipt voucher with SVNIT letterhead.
3. **Event Approval Note** (`approval_note`): Event proposal and financial sanction note submitted to Dean (Students Welfare).
4. **Bill Summary** (`bill_summary`): Consolidated post-event reimbursement summary sheet for accounts.
5. **Bill Certificate (Form BC-R)** (`bill_certificate`): Official recurring expenditure passing certificate for vendor bills.
6. **Minutes of Meeting** (`mom`): Structured minutes for executive and general meetings with action items.

---

## 🧪 Running Tests
Run the test suite:
```bash
python tests/test_core.py
```
