# PROJECT PHASE 2: "ClubDocs" — Multi-Club Document Platform (Website)

You already built the `docgen` engine (template folders, schema.yaml, Event Record, renderer, validator, recommender, missing-field detector, extractors, SQLite). That engine is GOOD. **Do not rewrite it. Wrap it.** This phase turns it into a website where many clubs of SVNIT can sign up, pick or create templates, and generate documents.

Read this whole file, then start at Step 0. Stop at every GATE and show me real results (rendered files, screenshots, test output). Never claim something works without running it.

---

## STEP 0 — Fix leftover defects from Review Round 2 (before any web work)
1. Permission Letter currently prints `REF NO.: ACM/2026-27/SIH/001` (the Approval Note number). It must use its own ROOM series, e.g. `ACM/26-27/ROOM/###`, as a SUGGESTION with `confirmed=False`. The fixture must not reuse one ref for two document types. Add a rendered-PDF test: the Permission Letter ref contains `ROOM`, the Approval Note ref does not.
2. `certifier_name` ("I, am ____") must never be pre-filled from a default person. If the user has not supplied it, render a blank underline and flag it in the missing-info list.
3. Number formatting must be uniform in every document: Indian grouping with two decimals for money (`5,000.00`, `144.00`, `1,100.00`), dates `DD/MM/YYYY`. Today `5000`, `144`, `800` appear without formatting while totals have it.
4. Keep the Approval Note readable: body font must not go below 9pt. If it cannot fit one page, tighten spacing before shrinking fonts.
5. Replace tests that only assert fixture values with tests that assert RENDERED PDF text.
Report with evidence, then continue.

---

## 1. Product requirements

**Who:** student clubs/chapters/societies of SVNIT Surat (ACM, and others). Each club has its own members, logo, signatories, templates and documents.

**Core user stories**
1. A visitor creates an account (email + password), verifies/logs in, and either creates a club (becomes its owner) or joins one by invite link/code.
2. A user belongs to one or more clubs and switches between them from a club switcher. Everything (templates, logos, people, events, documents) is scoped to the active club. One club can never see another club's private data.
3. **Make a document from an existing template:** pick a template from the gallery (system templates: Permission Letter, Prize Money Receipt, Event Approval Note, Bill Summary, Bill Certificate, MoM; plus the club's own), fill a form OR describe it in plain text, get missing-info questions, preview, edit, download DOCX/PDF.
4. **Create a new template by text ("describe it"):** user types e.g. "A sponsorship request letter to a company with event name, date, expected footfall, sponsorship tiers table, and signature of chairman". The AI proposes a template (structure + fields) which opens in the visual editor for review. AI output is a *proposal*, never auto-published.
5. **Create/edit a template manually in an interactive editor** (section 5).
6. **Upload an existing DOCX** and convert it to a template by highlighting text and marking it "make this a field" (stretch, but design for it).
7. **Draft documents for different clubs:** a user in several clubs picks the club first; the logo, letterhead, signatories and numbering follow that club.
8. **Logos:** user can pick the club's logo from a menu (library), upload a new image, or say it in text ("use the ACM logo, left side"). 
9. **A permanent SVNIT logo** is always visible in the website header/shell on every page and cannot be removed or hidden. On documents, an `institute_logo` slot (SVNIT) is a LOCKED element of the letterhead: club users can choose the club logo and layout but cannot delete the SVNIT slot from system letterheads. (If a template is a plain internal document, an admin may mark it `institute_logo: optional`.)
10. Review/edit generated documents, re-render, see version history, restore a version, download.
11. Batch: generate one document per winner/bill, download as ZIP.

**Never-fabricate rule (still absolute):** reference numbers, approval numbers, amounts, bill/invoice numbers, GST/PAN/bank details, names of judges/signatories, roll numbers, mobile numbers must come from the user or the club's saved people/config. If missing, the UI asks. LLM-drafted text is always labelled "AI-drafted — review" and blocks finalization until the user accepts or edits it. Arithmetic and amount-in-words are done in code only.

---

## 2. Architecture

```
repo/
  docgen/          existing engine (keep; refactor only where noted)
  server/          FastAPI app: auth, API, DB models, services, jobs
    app/ (main.py, api/, models/, schemas/, services/, core/)
    alembic/       migrations
  web/             React + TypeScript + Vite + Tailwind (+ TanStack Query, React Router)
  storage/         dev file storage (templates, logos, outputs) — S3-compatible adapter later
  docker-compose.yml   postgres, server, web, worker (with LibreOffice)
  docs/
```

**Key refactor in `docgen`:** the engine currently reads `config/club_config.yaml` and `templates/` from disk. Make it accept **injected** objects: `ClubContext` (built from DB rows: club info, logos, people, venues, numbering, defaults) and a **TemplateSource** (loads `template.docx` + `schema.yaml` from storage by template_version id). The existing YAML/folder loaders stay as one implementation (used by CLI and tests). The web server uses the DB implementation. No club-specific values hardcoded anywhere in Python.

**Stack decisions (follow unless you find a blocker, then ask):**
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2.
- DB: **PostgreSQL** (docker) for real use; SQLite allowed for quick local dev through the same SQLAlchemy models. Do NOT keep the club's data only in the old `data/docgen.db` — write a one-time migration script from it.
- Auth: email + password hashed with argon2; sessions via httpOnly, SameSite cookies (access + refresh) or server-side sessions; CSRF protection; login rate limiting; password reset flow (email sending behind an interface; log the link in dev). Optional Google sign-in as a stretch.
- Background jobs: DOCX→PDF with LibreOffice is slow; run it in a worker (RQ/Arq/Celery or a simple DB-backed job table + worker process). The API returns a job id; the UI polls. A hung `soffice` must time out and surface a clear error.
- Frontend: React + TypeScript + Vite + Tailwind. Component library of your choice (shadcn/ui or similar). Responsive (works on a phone).
- Rich template editor: **TipTap (ProseMirror)** with custom nodes (see section 5). Compile its JSON to DOCX on the server with python-docx + docxtpl tags. Do NOT embed Word itself.
- LLM: keep the pluggable `LLMClient` (Gemini default). Keys are server-side env vars only, never sent to the browser. The system must still work with no key (forms + rules + manual editor).
- Check the environment first (Windows dev machine): Python, Node version, Docker availability, `soffice` path, and fonts. Tell me what to install. Provide both a Docker path and a no-Docker path (SQLite + local worker) to run it.

---

## 3. Database design (proper, normalized, migrated with Alembic)

All tables have `id` (UUID), `created_at`, `updated_at`. Club-scoped tables have `club_id` with an index and every query goes through a scoped repository that REQUIRES club_id, so cross-club leaks are impossible by construction.

- `users` (email unique, password_hash, name, is_platform_admin, email_verified_at, last_login_at, disabled_at)
- `clubs` (name, short_name, slug unique, chapter_code e.g. 6/52, head_of_account, academic_year_default, default_letterhead_id, settings JSONB)
- `memberships` (user_id, club_id, role: owner|admin|editor|viewer, status) unique(user_id, club_id)
- `invites` (club_id, email or code, role, expires_at, accepted_at)
- `assets` (club_id nullable for system assets, kind: logo|letterhead|signature|other, filename, mime, sha256, size, storage_key, uploaded_by, is_system) — the SVNIT logo is a system asset, locked
- `letterheads` (club_id nullable for system, name, left_logo_asset_id, right_logo_asset_id, institute_logo_asset_id (locked), title_text, subtitle_text, colors JSONB, fonts JSONB, footer_text, layout JSONB) — system letterheads: SVNIT bilingual, ACM
- `people` (club_id, full_name, roll_no, branch, department, mobile (sensitive), email, notes) — signatories/contacts stored once
- `roles_held` (club_id, person_id, role_key e.g. student_head|student_secretary|faculty_chairman|faculty_cochairman|chairperson|tech_assistant|faculty_incharge, designation_label, valid_from, valid_to, academic_year) — same person can have different labels per template
- `venues` (club_id nullable for shared campus venues, name, addressee_default, tech_assistant_person_id, faculty_incharge_person_id)
- `templates` (club_id nullable for system templates, slug, name, description, category, stage, is_system, forked_from_template_id, status: draft|published|archived, current_version_id)
- `template_versions` (template_id, version_no, schema_yaml TEXT/JSONB, editor_json JSONB (TipTap doc, nullable for uploaded DOCX), docx_storage_key, letterhead_id, validation_report JSONB, created_by, change_note) — immutable once published
- `clauses` (club_id nullable, key, title, body_jinja, description) — reusable snippets
- `numbering_series` (club_id, key e.g. ROOM|MOM|<event_code>, format, academic_year, last_seq) with row-level locking when allocating (no duplicate numbers under concurrency). Allocation only happens when the user confirms, never at suggestion time.
- `events` (club_id, title, event_code, record JSONB (canonical Event Record with per-field {value, source, confirmed}), status, created_by)
- `documents` (club_id, event_id nullable, template_id, template_version_id, title, ref_no, status: draft|needs_info|ready|finalized, current_version_id, created_by)
- `document_versions` (document_id, version_no, record_snapshot JSONB, overrides JSONB, docx_key, pdf_key, diff_summary, created_by, source: generated|manually_edited_upload)
- `jobs` (club_id, kind: render|pdf|batch|ai, status, payload JSONB, result JSONB, error, started_at, finished_at)
- `ai_requests` (club_id, user_id, purpose, model, prompt_hash, tokens_in/out, created_at) — usage tracking; do NOT store raw sensitive data
- `audit_log` (club_id, user_id, action, entity_type, entity_id, meta JSONB, ip, created_at)

Rules: sensitive fields (mobile, bank account, PAN, IFSC of persons) are encrypted at rest (field-level encryption with a server key) and masked in API responses by default (last 4 digits) with an explicit "reveal" permission. Deleting a club/user must be soft-delete first. Provide seed scripts: system letterheads, SVNIT logo asset, the six system templates (imported from the existing `templates/` folders), a demo club "ACM" with the people already in `club_config.yaml` (mobile/bank blank). Write an ER diagram (Mermaid) to `docs/DB_SCHEMA.md`.

---

## 4. Roles & permissions
- **owner**: everything for the club incl. deleting the club, transferring ownership.
- **admin**: manage members, letterheads, logos, people, numbering, templates (publish).
- **editor**: create/edit drafts of templates and documents, generate and download; cannot publish templates to the whole club or manage members.
- **viewer**: read-only, download finalized documents.
- **platform admin** (a few SVNIT staff/me): manage system templates, system letterheads, all clubs.
Enforce on the server in one permission layer (not just hidden buttons) and test it (viewer cannot POST, club A user cannot read club B by guessing a UUID).

---

## 5. Template creation (the heart of the product)

Three ways, all producing the SAME stored format (a `template_version` with `schema_yaml` + `template.docx`), so the existing renderer/validator are reused unchanged.

### 5.1 From the gallery (pre-existing)
Gallery shows system templates + the club's templates with thumbnail preview, description, and a "Use" and "Customize (fork)" button. Forking copies the system template into the club so the club can edit freely without affecting others. System templates are read-only.

### 5.2 By text ("Describe your template")
1. User types a description (any language they like; English first, Hindi/Gujarati as stretch).
2. LLM returns a strict-JSON **TemplateSpec**: `{name, category, stage, blocks[], fields[], suggested_numbering, signatories[]}` using only the block types below. Validate it with Pydantic; if invalid, retry once, then show an error.
3. The spec opens in the visual editor. Fields the AI invented are marked "AI-suggested". Official wording (e.g. certifications, approvals) is NOT invented: the AI leaves a labelled placeholder block "Add official wording here" unless the user supplied the text.
4. The user edits and clicks **Publish**. Publishing runs the validator and a dry render with dummy data and shows a preview. Nothing is usable until it passes.

### 5.3 Manually in an interactive editor
A TipTap-based visual editor with a left palette, centre A4 canvas, right properties panel. Requirements:
- **Blocks:** heading, paragraph (bold/italic/underline/align/lists), **field chip** (inline variable like `{{ event_name }}` shown as a coloured pill, not raw braces), **info table** (label : value rows like the sample forms), **repeating table** (rows loop over a list e.g. winners/budget items, with column definitions and computed total row), **signature grid** (N columns × M rows, each cell: label + linked person/role + blank signature space), **conditional section** (show if a field has a value / equals X), **clause insert** (from the clause library), **page break**, **image** (logo slot, not arbitrary remote images), **horizontal rule**, **ref/date line**.
- **Header/footer:** choose a letterhead from the menu (logo slots + title text + colours + fonts). Page number "Page X of Y" option. The SVNIT slot is locked on letterheads that include it.
- **Fields panel:** list of all fields in the template with type (text, longtext, int, money, date, date_range, time_range, enum, person_ref, table), required, ask-prompt, default source, "can be left blank for hand-filling" (`defer_ok`), sensitive flag. Adding a field chip in the canvas auto-creates the field entry. Renaming a field updates all chips.
- **Computed values:** pick from the function registry (sum, line total, tax, amount in words INR, format INR, ordinal, date range). No free-form code execution. Conditions use the safe expression evaluator.
- **Live preview:** button renders with sample data to PDF and shows page images; side-by-side editor ↔ preview toggle. Undo/redo, autosave drafts, keyboard shortcuts.
- **Compile step (server):** `TipTap JSON → template.docx` with docxtpl tags in single runs (reuse the lessons from `scripts/build_templates.py`), plus `schema.yaml`. Fonts/colours/spacing come from a style sheet in the letterhead/theme, never ad hoc. The DOCX must open cleanly in Word and keep tables from splitting across pages (`cantSplit`, keep-with-next).
- **Round trip:** the editor JSON is stored; the compiled DOCX is the render source. If a template was uploaded as raw DOCX (5.4), editing is limited to the field panel and metadata.

### 5.4 Upload a DOCX (stretch, design for it)
Upload `.docx`, show its text, user selects text → "Make field", the server rewrites it into a `{{ tag }}` inside one run and builds the schema. Reject macros (.docm), scan size/type.

### 5.5 Template lifecycle
draft → published (immutable version) → new edit creates a new version; documents remember the exact `template_version_id` they used; the user can "re-render with latest version" explicitly. Archive instead of delete when documents reference a template.

---

## 6. Creating documents (user flow)

1. **Choose club** (switcher) → **New document**.
2. Two entry points on one screen: **(a) "Describe what you need"** a text box ("Two-day web workshop on 14–15 Oct in Seminar Hall for ~120 students, need permission and approval note") and **(b) pick a template/gallery**.
3. For (a): rules/dateparser extraction first, LLM fallback with strict JSON; show an **extracted data panel** with source badges (you typed / from club settings / AI-guessed — unconfirmed). Show recommended documents with a one-line reason each (checkboxes, overridable). The recommender must use the club's templates' `triggers/stage`, not hardcoded document names.
4. **Missing-info panel**: grouped questions by field, which documents need each, inline answer boxes. "Leave blank to fill by hand" appears only for `defer_ok` fields and is an explicit click.
5. **Generate**: jobs run; show progress; open the **Review screen**.
6. **Review screen:** PDF page preview on the right; on the left an editable form grouped by section. Edit → "Re-render" → new version. Per-document **text overrides** (a stored map for one-off wording changes) so edits survive re-render, with a warning when an override conflicts with changed data. "Download DOCX / PDF", "Upload my hand-edited DOCX as a new version" (flagged `manually_edited`; warn that data re-render overwrites it). Version history with timestamps, author, diff summary, restore.
7. **Event workspace:** an event groups its documents. Changing the venue/date/amount on the event offers "Update N documents" with a diff preview; all documents stay consistent. Bill Certificate pulls approval note no./date from the Approval Note; Bill Summary totals equal the sum of prize receipts + other payees.
8. Finalize: status → finalized, reference number allocated from the series (user confirms the suggested number; collisions rejected), document locked until a new version is made.
9. Batch ZIP for winners/bills.

---

## 7. Logos & branding UX
- **Brand settings page per club:** upload logo(s) (PNG/JPG/SVG, max 2 MB, validated by content not just extension, SVG sanitized, EXIF stripped, auto-resized copies), crop tool, name them, choose primary/secondary colours and fonts from a safe list (fonts must exist in the renderer; list the font fallback chain, e.g. Liberation Serif for Times New Roman).
- **Letterhead builder:** pick left logo, right logo, title/subtitle text, alignment, live preview. SVNIT institute logo slot is locked on.
- **In the template editor and document review:** a "Logo" menu lists system + club logos; plus "Upload new". By text: "use the ACM logo on the left" is resolved by the AI helper to a logo asset id by name match (ask if ambiguous).
- **Website shell:** a fixed top bar with the SVNIT logo (system asset, always rendered, not editable by any club role) + app name + club switcher + user menu. 
- Logos in documents are embedded at the right resolution so PDF output is sharp; PDF and DOCX must show identical branding on every regeneration.

---

## 8. API (REST, versioned `/api/v1`, OpenAPI docs on)
Auth: register, login, logout, refresh, verify email, forgot/reset password, me.
Clubs: create, list mine, get, update, switch (client-side), members CRUD, invites CRUD.
Assets: upload, list, get (signed URL), delete.
Letterheads, people, roles_held, venues, clauses, numbering: CRUD (admin).
Templates: list (system + club), get, fork, create-from-text (AI), create/update draft, publish, validate, preview (render with sample data → job), archive, versions.
Events & documents: create from text (extract), create from form, get missing-fields, recommend, generate (job), batch (job), versions, restore, update fields, overrides, upload-edited-docx, download docx/pdf, finalize, "update documents from event".
Jobs: get status. Admin: audit log, usage.
Consistent error format `{code, message, field_errors[]}`. Pagination and search on lists. Idempotency key on generate/finalize.

---

## 9. Frontend pages
Landing/login/register/forgot password → **Club picker / create club** → **Dashboard** (recent documents, drafts needing info, quick "New document") → **Documents** (list, filter by club/type/status/event) → **New document** (describe + gallery) → **Review/Editor** → **Events** → **Templates** (gallery, my templates, editor, versions) → **Brand & Letterheads** → **People & Signatories** → **Venues & Numbering** → **Members & Invites** → **Settings** → **Admin** (platform admin only). Empty states, loading skeletons, toasts, form validation, dark mode optional. Accessible (labels, keyboard nav, contrast). Mobile layout for review and download.

---

## 10. Security & privacy checklist (must be implemented and tested)
- Club scoping everywhere; test cross-club access attempts.
- Argon2, rate limiting, secure cookies, CSRF, CORS locked to the web origin, security headers, request size limits.
- File upload validation (magic bytes), image re-encoding, SVG sanitization, no execution of uploaded DOCX content, no `.docm`.
- Template engine safety: Jinja sandbox (`SandboxedEnvironment`), `autoescape=True`, no arbitrary Python from templates or conditions.
- Prompt-injection safety: text pasted into the "describe" box and uploaded notes are DATA; the LLM output is validated against a schema and can never trigger actions (publish, delete, send).
- Secrets only in env; `.env.example` committed; real `.env` and real club config in `.gitignore`.
- PII (mobile, bank, PAN) encrypted + masked + excluded from logs and AI prompts (send only what the extraction needs; never send bank/PAN to the LLM).
- Audit log for login, member changes, template publish, document finalize, downloads of sensitive documents.
- Backups doc: how to dump/restore Postgres and storage.

---

## 11. Testing & acceptance
- Keep all existing tests green. Add: auth flows; permission matrix; cross-club isolation; numbering concurrency (parallel allocation yields unique numbers); template compile (editor JSON → DOCX → validator passes → render → PDF text assertions); text-to-template with a stubbed LLM; upload validation; version restore; event update propagates to all documents; batch ZIP contents; sensitive-field masking; job timeout handling.
- Playwright E2E: register → create club → upload logo → create template manually → publish → generate document → fix missing field → review → edit → re-render → download PDF → verify text in the PDF.
- Visual checks: render every system template through the web flow and save PNGs to `tests/visual/web/` next to the sample PDFs. No blank trailing pages, no overflow, SVNIT logo present where required, "&" intact, no "None", no unresolved `{{`.
- Acceptance: a new club can sign up, brand itself, create one custom template by text and one manually, and produce DOCX+PDF for it without touching code or files.

---

## 12. Phases (STOP at each gate with evidence)
- **Step 0:** leftover fixes (above). GATE.
- **Phase W1 — Foundations:** repo layout, Docker + no-Docker run paths, Postgres models + Alembic, seeds (SVNIT logo, system letterheads, system templates, demo ACM club), config-from-DB refactor of `docgen` (engine accepts injected ClubContext/TemplateSource; old CLI still works). GATE: engine renders all 6 system documents from DB data, tests green.
- **Phase W2 — Auth, clubs, roles:** register/login/reset, club create/join, memberships, permission layer, club switcher, audit log, permanent SVNIT logo in the shell. GATE: permission/isolation tests pass; screenshots.
- **Phase W3 — Documents from templates:** assets/letterheads/people/venues/numbering CRUD, new-document flow (describe + gallery), extraction, missing-info panel, jobs, review/edit/re-render, versions, downloads. GATE: example sentence works end to end in the browser for ACM.
- **Phase W4 — Template builder:** gallery/fork, TipTap editor with all blocks, field panel, compile to DOCX+schema, validator, live preview, publish/version. GATE: a template built manually in the editor produces a correct PDF.
- **Phase W5 — Text-to-template and logo-by-text:** TemplateSpec LLM path, logo resolution, AI usage tracking. GATE: demo "sponsorship request letter" created from text and published after review.
- **Phase W6 — Events, batch, polish:** event workspace and propagate-changes, batch ZIP, search/filter, empty states, mobile layout, E2E suite, README, `docs/DB_SCHEMA.md`, `docs/TEMPLATE_AUTHORING.md` update, admin page. 
- **Stretch (only after all above):** DOCX upload-to-template, approval workflow (submit → faculty review → approve), email distribution, Google Drive export, digital signature images, multilingual (Hindi/Gujarati), usage analytics dashboard, SSO.

## 13. Deliverables
Working repo; `README.md` (install, run with and without Docker, create the first admin, add a club, add a template); `.env.example`; migrations; seed scripts; docs; tests; demo script/video steps; a short "what was fixed in Step 0" report. If anything affects official wording or layout and the samples don't settle it, ask me instead of guessing.
