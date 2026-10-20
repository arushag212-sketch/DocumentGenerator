# ClubDocs — Implementation Plan (Track 1: Smart Document Generator)

Goal: a system SVNIT clubs can adopt and keep using after the event. Every club document
is produced from **club-owned data + editable templates**, with AI used to *understand
input and draft templates*, never to invent official facts.

The original sample documents were reference material only. Templates now live as data
(DB records, editable in the Studio) rather than as code.

---

## 1. Requirement matrix

| Requirement | Before this phase | Work in this phase |
|---|---|---|
| Forms and natural-language input | Home prompt, document-type cards, missing-info forms | Unchanged; fed by the data-driven recommender below |
| Extract info, identify/recommend document type | Rules + Gemini fallback; **recommendations hardcoded per template slug** | **Data-driven recommender**: each template declares `recommend` rules (intents, keywords, stage, required signals) in its schema; one generic scorer. New templates take part without code changes |
| Multiple document types, customizable templates | 6 system templates + AI/wizard/blank/DOCX import | **Template library as data** (`templates/library/*.json`): Event Proposal, Certificate of Participation, Certificate of Achievement, Sponsorship Request, Volunteer Appreciation, Circular/Notice, Event Report. Compiled by the same pipeline as user templates; forkable and editable per club |
| DOCX and PDF preserving structure | docxtpl + LibreOffice | Unchanged; verified in the evaluation |
| Club branding: logos, colours, fonts, headers, footers | Per-club banner/letterhead (previous phase); design settings | Club **brand kit** in settings (primary colour, fonts, footer text) applied to new templates and the composed banner; **footer** with club name and page numbers |
| Detect missing info, never fabricate | Grouped missing-field questions; grounding checks | Unchanged; covered by evaluation cases |
| Review and edit generated documents | View/download only | **Edit and regenerate**: change any field value and regenerate as a new version (same reference number) |
| Consistency throughout the document | Single context per render, field aliases | Unchanged; checked by the evaluation (same value everywhere) |
| LLM fallback for unstructured input | Gemini with grounding | Unchanged |
| Add/modify templates without code changes | Studio, AI draft, wizard, import | Library templates as data; recommender metadata editable in the template's settings |

### Good to have

| Feature | Before | Work |
|---|---|---|
| Automatic document-type detection | Hardcoded rules | Data-driven recommender (above) |
| Conditional/dynamic sections | None | Block-level **"show only if field has a value"** condition (compiled to `{%p if %}`), editable in the Studio |
| Batch generation | Event packages, per-winner/bill | **Batch from CSV / Google Sheets (published CSV link)**: one document per row (e.g. certificates for 120 participants) |
| Version history | Yes | Shown on the document page with a diff of changed fields |
| Approval/review workflow | Status column only | **Draft → Submitted → Approved / Changes requested**, role-gated, with reviewer comments and audit log |
| Reusable clauses | Preset clauses palette | Unchanged |
| Update documents when source info changes | No | Editing an event offers **"Regenerate affected documents"** (new versions, numbers kept) |
| Template preview/editor | Yes | Canvas now matches output (previous phase) |
| Role-based access control | Owner/Admin/Editor/Viewer + join approval | Approval actions gated to finalizers |
| Google Drive/Sheets | None | Sheets via published CSV link (no OAuth needed). Drive upload needs a Google Cloud OAuth client from the club; documented, not enabled |
| Email distribution | Only auth emails | **Send document by email** (PDF/DOCX attachments) via SMTP; console backend in development |
| Digital signatures | None | **Approval e-signature + verification**: approval stamps the PDF with approver, time and a verification code; `/verify/<code>` checks the SHA-256 fingerprint |
| Usage analytics | None | **Club dashboard**: documents per type/month, time saved estimate, top templates, AI usage |
| Multilingual | Hindi/Gujarati translation | Unchanged |

---

## 2. What we must not do (how the design avoids it)

- **Not a ChatGPT wrapper**: AI output is structured (fields, blocks, actions) and validated; documents are rendered from templates, never pasted text.
- **No single hardcoded template / combination table**: templates and recommendation rules are data.
- **No random formatting**: fixed compiler typography per layout and per-club design settings.
- **No fabrication**: grounded extraction, missing-field questions, AI drafts marked for review, no invented signatories/numbers/dates.
- **No manual copy-paste**: DOCX/PDF downloads, ZIP packages, email.

---

## 3. Demo data (realistic, not hardcoded)

Clubs from SVNIT's official [Chapters | Clubs | Society](https://www.svnit.ac.in/web/Student_Chapter) page, logos downloaded from there with permission:

| Club | Kind | Typical documents |
|---|---|---|
| ACM SVNIT | Computing chapter | Workshops, hackathons, certificates |
| GDSC SVNIT | Developer club | Study jams, sponsorship letters |
| DRISHTI | Technical hobby club | Exhibitions, equipment gate passes |
| CHRD | Cultural umbrella | Cultural nights, volunteer letters |
| SAE SVNIT | Automotive | Competitions, sponsorship, travel permission |

Each club gets an owner, an admin, an editor and a viewer account (credentials in `docs/DEMO_ACCOUNTS.md`, development seed only), its logo, brand colours, venues, people/roles and a few club templates created **through the template pipeline** from natural-language descriptions (stored as data in `demo/club_templates.json`), not written in code.

---

## 4. Evaluation

A scripted run (`scripts/evaluate.py`) feeds varied natural-language requests to each club through the real API and scores the results against the official criteria:

| Criterion | Measured by |
|---|---|
| Practical club utility | Right documents recommended for the request |
| Automation | Fields filled automatically vs asked |
| Document quality | PDF renders, single-page where expected, no `{{ }}`, `None`, `null` |
| Accuracy | Every stated fact appears; no unstated fact appears |
| Template flexibility | Template-from-prompt success and editability |
| Technical implementation / reliability | Errors, retries, timing |
| Extensibility | New template recommended with no code change |
| Usability | Steps from sentence to PDF |

Results go to `docs/EVALUATION.md`.

---

## 5. UI redesign

Remove the "generated" look: emoji icons, gradient banners, sparkle icons on every button, ALL-CAPS section titles, competing accent colours, decorative badges, inconsistent radii and shadows.
Replace with one design system: neutral surfaces, one brand accent (SVNIT navy), consistent type scale, a left sidebar app shell, clear primary actions, empty states that explain what to do, and a dashboard home.

---

## 6. Phases

1. Data-driven recommender + template library (Event Proposal, certificates, letters).
2. Review/edit/regenerate, approval workflow with e-signature verification, email distribution.
3. Conditional sections, CSV/Sheets batch, regenerate-on-change, analytics dashboard, club brand kit and footer.
4. Demo clubs, users, logos and club templates (seed).
5. Evaluation run and report.
6. UI redesign across all pages.
7. Full test run, browser verification.
