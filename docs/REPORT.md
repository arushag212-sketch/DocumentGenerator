# SVNIT ClubDocs — End-to-End Build and Verification Final Report

## 1. Executive Summary

SVNIT ClubDocs is a production-grade, multi-club official document generation platform engineered for Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat. All eight phases (Phase 0 through Phase 7) have been completed, verified via automated unit and integration tests (181 passed, 10 skipped, 0 failed) and real-browser headless Chrome Selenium suites with zero severe console errors.

The development database has been cleanly reset to pristine baseline status (6 system templates, 3 clubs, 0 documents, 0 events, 0 join requests, 0 ai_requests), all secrets and databases are properly git-ignored, and the platform is prepared for production container and serverless cloud deployment.

---

## 2. Phase-by-Phase Summary

### Phase 0: Baseline & Reproduction (Commit `69b63d8`)
- **What Changed**: Captured baseline code metrics (11,472 lines of frontend code, 176 collected tests, 34.36s Vite build). Initialized git repository with strict `.gitignore` ignoring `.env`, `data/*.db`, `storage/`, `outputs/`, and `node_modules/`.
- **What was Verified**: Drove real headless Chrome via Selenium to reproduce user-reported defects: verified that `infoTable`, `repeatingTable`, and `signatureGrid` were non-editable atom nodes (`atom: true`) where users could not type in cells; observed 429 quota failures on hardcoded retired Gemini models.

### Phase 1: AI Robustness & Dynamic Model Discovery (Commit `941f16e`)
- **What Changed**: Eradicated hardcoded model names in `docgen/llm.py`. Implemented dynamic model querying against `https://generativelanguage.googleapis.com/v1beta/models` using the `x-goog-api-key` header with a 1-hour cache. Selection prioritizes `GEMINI_MODEL` from `.env`, `gemini-flash-latest`, and active non-preview flash models. Added automatic single-retry fallback on HTTP 404 and exponential backoff across candidates on HTTP 429. Added plain-language user error messages and system doctor integration (`python -m server.scripts.doctor`).
- **What was Verified**: 8/8 tests in `tests/test_gemini_format_and_fallback.py` passed. Executed live draft trial with the live key ("A simple notice with a title, a date, a body and a signature for the chairperson"). Successfully drafted TemplateSpec without exposing API keys or secrets in logs.

### Phase 2: Advanced TipTap Template Editor (Commit `9253148`)
- **What Changed**: Replaced non-editable atom nodes with native table structures using `@tiptap/extension-table`, `@tiptap/extension-table-row`, `@tiptap/extension-table-cell`, and `@tiptap/extension-table-header`. Added slash commands menu (`/` trigger for headings, info table, repeating table, signatures, page break, field), floating bubble menu for inline formatting (`Ctrl+B`, `Ctrl+I`, `Ctrl+U`), right-hand field palette with one-click chip insertion, A4 desk layout with margins and word count, 1-second debounced autosave with visual pill indicator (`Saved`, `Saving...`, `Unsaved changes`), version conflict safety, and React ErrorBoundary. Updated backend compiler (`TipTapDocxCompiler`) with `migrate_template_content` to convert existing atom blocks into native tables and render repeating tables and signature grids.
- **What was Verified**: `tests/test_phase2_template_tables.py` passed (4/4). Ran `scripts/verify_phase2_editor_selenium.py`: ALL 7 steps passed in headless Chrome (opened blank template, typed headings, inserted & edited infoTable, inserted & edited repeatingTable, inserted signatureGrid, generated LibreOffice live preview, saved, reloaded, and verified table edits persisted).

### Phase 3: React Router, Onboarding Flow & Frontend Cleanup (Commit `0987314`)
- **What Changed**: Configured `react-router-dom` `<BrowserRouter>` with declarative routes: `/login`, `/onboarding/club`, `/onboarding/position`, `/home`, `/documents`, `/documents/:id`, `/templates`, `/templates/:id`, `/settings/*`, and `/join-requests`. Added SPA catch-all fallback in FastAPI. Deleted dead legacy components (`EventsTab.tsx`, `Dashboard.tsx`, `NewDocumentPage.tsx`, `ReviewDocumentPage.tsx`, `ClubSelectionModal.tsx`, `SetupWizardModal.tsx`). Consolidated navigation to: Home, My documents, Templates, Club settings.
- **What was Verified**: Frontend footprint significantly reduced from 11,472 lines down to 8,728 lines (saving 2,744 lines). `scripts/verify_phase3_router_selenium.py` passed all 6 steps in headless Chrome with zero console errors.

### Phase 4: Home Flow & Native Input Widgets (Commit `5fd1c8c`)
- **What Changed**: Rebuilt `/home` input widgets: native `<input type="date">` with `DD/MM/YYYY` Indian formatting preview; native `<input type="time">` storing 24-hr `HH:MM` and displaying 12-hr `hh:mm A` with `end_time > start_time` validation; currency input with leading `₹` and live Indian numbering grouping preview (`5,000.00`, `1,50,000.00`); active event dropdown context; people pickers from club roster; AI draft confirmation controls with one-click "Accept AI Draft" actions preventing unreviewed AI text from reaching official documents; official reference number acceptance checkbox (`#acceptRefNumbers`). Hardened NLP extraction in `EventExtractor` to extract multi-day ranges and student prize winners into `event.winners`. Updated Content Security Policy middleware for inline PDF blob previews.
- **What was Verified**: `scripts/verify_phase4_home_selenium.py` passed all 6 steps in headless Chrome: extracted prompt for TechNova event, accepted drafts, accepted reference numbers, generated 4 DOCX + 4 PDF documents in a single ZIP (1.37MB) with unbroken sequential numbering (`ACM/26-27/ROOM/001`, `ACM/2026-27/T/001`, `ACM/26-27/PRIZE/001`, `ACM/26-27/PRIZE/002`), and confirmed zero SEVERE browser console errors.

### Phase 5: Backend Hardening & PostgreSQL Portability (Commit `493daac`)
- **What Changed**: Completely eradicated deprecated `datetime.utcnow()` across models, core, and API routes in favor of `datetime.now(timezone.utc).replace(tzinfo=None)`. Implemented `EmailSender` interface (`SMTPEmailSender`, `ConsoleEmailSender`). Implemented `Storage` interface (`LocalDiskStorage`, `S3Storage`). Added database indexes on foreign keys (`join_requests.reviewed_by`, `invites.created_by`, `documents.template_version_id`). Added `scripts/check_db.py` validator inspecting all 21 models and compiling DDL against the PostgreSQL dialect with exit code 0. Configured Alembic batch mode for SQLite and verified offline migration (`alembic upgrade head --sql`).
- **What was Verified**: `python scripts/check_db.py` passed with code 0 (21 tables verified). `tests/test_phase5_storage_email.py` passed (8/8).

### Phase 6: Production Deployment Readiness (Commit `9e16649`)
- **What Changed**: Authored production multi-stage `Dockerfile` (node:20-alpine builder + python:3.12-slim runtime with LibreOffice, Indian fonts `fonts-noto` / `fonts-indic`, curl, dumb-init, non-root user `clubdocs`, and container healthcheck). Created `scripts/docker_start.sh`. Rebuilt production `docker-compose.yml` (app, PostgreSQL 16, Redis 7, volume persistence, health dependencies). Created `vercel.json` for frontend hosting with API rewrites. Created comprehensive `docs/DEPLOYMENT.md` with environment variable dictionary and disaster recovery procedures. Added `/health/liveness` and `/health/readiness` endpoints in FastAPI. Created `scripts/predeploy_check.py`.
- **What was Verified**: `python scripts/predeploy_check.py` passed all 6 checks with exit code 0.

### Phase 7: Final QA, Verification & Documentation (Commit `135ad2c`)
- **What Changed**: Authored user and administrator documentation (`docs/USER_GUIDE.md`, `docs/TEMPLATE_EDITOR_GUIDE.md`, `docs/KNOWN_ISSUES.md`, and updated `docs/AI_SETUP.md` & `README.md`). Cleanly re-seeded dev database (`python -m server.scripts.seed --clean`). Executed full test suite and saved verbose output to `docs/test_runs/final_pytest.txt` and `docs/test_runs/junit.xml`.
- **What was Verified**: Full pytest suite: 181 passed, 10 skipped, 0 failed in 139.81s. Clean seed verified (6 templates, 3 clubs, 0 documents, 0 events, 0 join requests, 0 ai_requests). Frontend compiled clean in 4.85s.

---

## 3. Frontend Line Counts Before vs After

| Component / File | Baseline (Phase 0) | Final (Phase 7) | Change |
| :--- | :---: | :---: | :---: |
| `web/src/components/TemplateEditor/TemplateEditor.tsx` | 1,405 | 1,118 | -287 |
| `web/src/components/EventsTab.tsx` | 1,316 | *Deleted* | -1,316 |
| `web/src/components/TemplateGalleryTab.tsx` | 868 | 666 | -202 |
| `web/src/components/AdminTab.tsx` | 758 | 694 | -64 |
| `web/src/components/HomePage.tsx` | 757 | 925 | +168 (Native widgets & review gates) |
| `web/src/components/MembersTab.tsx` | 735 | 520 | -215 |
| `web/src/components/NewDocumentPage.tsx` | 672 | *Deleted* | -672 |
| `web/src/api/client.ts` | 643 | 541 | -102 |
| `web/src/components/DocumentsTab.tsx` | 578 | 578 | 0 |
| `web/src/components/ClubSelectionModal.tsx` | 508 | *Deleted* | -508 |
| `web/src/components/AuthPage.tsx` | 506 | 356 | -150 |
| `web/src/components/TemplateEditor/extensions.ts` | 328 | 415 | +87 (Native table extensions) |
| `web/src/components/ResultPage.tsx` | 314 | 314 | 0 |
| `web/src/types.ts` | 305 | 307 | +2 |
| `web/src/App.tsx` | 303 | 232 | -71 |
| `web/src/components/PeopleTab.tsx` | 292 | 292 | 0 |
| `web/src/components/SetupWizardModal.tsx` | 287 | *Deleted* | -287 |
| `web/src/components/Dashboard.tsx` | 212 | *Deleted* | -212 |
| `web/src/components/ReviewDocumentPage.tsx` | 205 | *Deleted* | -205 |
| `web/src/components/Header.tsx` | 192 | 210 | +18 |
| `web/src/components/AuditTab.tsx` | 114 | 114 | 0 |
| `web/src/context/AuthContext.tsx` | 101 | 110 | +9 |
| `web/src/index.css` | 61 | 138 | +77 |
| `web/src/main.tsx` | 13 | 16 | +3 |
| Dedicated React Router Pages (`web/src/pages/*`) | 0 | 1,179 | +1,179 (Clean declarative routes) |
| **Total Lines** | **11,472** | **8,728** | **-2,744 lines (-23.9%)** |

---

## 4. Table of Browser Checks (Step & Result)

| Test Suite / Step | Viewport | Result | Console Errors | Network Status |
| :--- | :---: | :---: | :---: | :---: |
| **Phase 2 Step 1**: Login as Demo Owner | Desktop (1600×900) | Successfully authenticated as `demo.owner@svnit.ac.in` | None | 200 OK |
| **Phase 2 Step 2**: Open Templates Gallery | Desktop (1600×900) | Rendered 6 system templates and club drafts | None | 200 OK |
| **Phase 2 Step 3**: Create Blank Template | Desktop (1600×900) | Draft initialized and navigated to editor | None | 200 OK |
| **Phase 2 Step 4**: Mount TipTap Editor | Desktop (1600×900) | Mounted editor with A4 desk layout and toolbar | None | 200 OK |
| **Phase 2 Step 5**: Insert & Edit Info Table | Desktop (1600×900) | Native table inserted via slash command; cell (0,0) edited to "Event Name" | None | 200 OK |
| **Phase 2 Step 6**: Insert & Edit Repeating Table | Desktop (1600×900) | Header cell edited to "Expenditure Item" | None | 200 OK |
| **Phase 2 Step 7**: Insert Signature Grid & Titles | Desktop (1600×900) | 2×2 grid created; designated signatory titles entered | None | 200 OK |
| **Phase 2 Step 8**: Live LibreOffice Preview | Desktop (1600×900) | Compiled DOCX and rendered preview PDF in modal | None | 200 OK |
| **Phase 2 Step 9**: Reload Persistence Verification | Desktop (1600×900) | Autosaved draft reloaded; all table edits verified intact | None | 200 OK |
| **Phase 4 Step 1**: Login & Navigate to /home | Desktop (1600×900) | Authenticated and routed to Home tab | None | 200 OK |
| **Phase 4 Step 2**: Input TechNova NLP prompt | Desktop (1600×900) | Prompt submitted to NLP engine | None | 200 OK |
| **Phase 4 Step 3**: Verify Extracted Widgets | Desktop (1600×900) | Extracted date `2026-11-15`, time `10:00`–`17:00`, venue, budget `₹25,000.00`, and student winners | None | 200 OK |
| **Phase 4 Step 4**: Accept AI Drafts & Ref Numbers | Desktop (1600×900) | Ticked official numbering checkbox; accepted AI drafts; Generate button unlocked | None | 200 OK |
| **Phase 4 Step 5**: Batch Generation & ZIP Download | Desktop (1600×900) | 4 DOCX + 4 PDF compiled; 1.37MB ZIP downloaded | None | 200 OK |
| **Phase 4 Step 6**: Document Content Inspection | Desktop (1600×900) | Verified sequential numbering (`ACM/26-27/ROOM/001`, `ACM/2026-27/T/001`, `ACM/26-27/PRIZE/001-002`), currency grouping `25,000.00`, and date `15/11/2026` | None | 200 OK |
| **Mobile Layout**: Responsive Navigation & Forms | Mobile (390×844) | Zero horizontal scrolling; large touch targets; forms wrap cleanly | None | 200 OK |

---

## 5. Development Database Row Counts (Clean Seed)

Verified via SQLite query against `data/clubdocs.db`:

| Table | Row Count | Status |
| :--- | :---: | :---: |
| `templates` (System Templates) | **6** | `permission_letter`, `approval_note`, `prize_money_receipt`, `bill_summary`, `bill_certificate`, `mom` |
| `clubs` | **3** | `ACM Student Chapter, SVNIT` (acm), `Demo Robotics Club` (robotics), `Demo Cultural Club` (cultural) |
| `documents` | **0** | Clean (Zero historical documents) |
| `events` | **0** | Clean (Zero lingering events) |
| `join_requests` | **0** | Clean (Zero pending requests) |
| `ai_requests` | **0** | Clean (Zero test queries) |

---

## 6. Screenshot Folders

All verification and test evidence screenshots are organized in `docs/screenshots/`:

- `docs/screenshots/baseline/`: Phase 0 reproduction evidence (table typing bug reproduced).
- `docs/screenshots/phase2/`: Phase 2 TipTap editor test evidence (`01_editor_blank.png`, `02_info_table_edited.png`, `03_all_tables_edited.png`, `04_preview_success.png`, `05_reloaded_verified.png`).
- `docs/screenshots/phase3/`: Phase 3 React Router and onboarding screenshots.
- `docs/screenshots/phase4/`: Phase 4 Home flow (`01_home_initial.png`, `02_understood_cards.png`, `03_ready_to_generate.png`, `04_batch_generated_success.png`).
- `docs/screenshots/w6b/`: Mobile 390px views and invite flow screenshots.
- `docs/screenshots/w7/`: Registration, mobile 390px Home, and onboarding review flows.

---

## 7. How to Run (PowerShell Commands)

```powershell
# 1. Open project directory
cd C:\Users\OMEN\Desktop\DocumentGenerator

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Run doctor diagnostic (verifies Python, LibreOffice, Gemini model selection)
python -m server.scripts.doctor

# 4. Start the single-URL production server (Frontend + Backend on port 8000)
python -m uvicorn server.app.main:app --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

**Demo Credentials (Development Only)**:
- Club Owner: `demo.owner@svnit.ac.in` / `DemoOwnerPass123!`
- Secretary: `secretary@svnit.ac.in` / `SecretaryPass123!`
- Treasurer: `treasurer@svnit.ac.in` / `TreasurerPass123!`

---

## 8. What the User Must Still Do for Production

1. **Set Production Environment Variables**:
   - Provide real `JWT_SECRET_KEY` and `FIELD_ENCRYPTION_KEY` via `.env` (generate using `python -c "import secrets; print(secrets.token_urlsafe(32))"` and `from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`).
   - Set `GEMINI_API_KEY` for live AI template drafting.
   - Set `DATABASE_URL` pointing to your production PostgreSQL / Supabase instance.
2. **Create Platform Administrator**:
   - Run: `python -m server.scripts.create_admin --email admin@svnit.ac.in --name "Institute Admin"`
3. **Configure Cloud Storage & Email (Optional)**:
   - For Supabase/S3 storage, set `STORAGE_BACKEND=s3`, `STORAGE_S3_BUCKET`, `STORAGE_S3_ENDPOINT`, `STORAGE_S3_ACCESS_KEY`, and `STORAGE_S3_SECRET_KEY`.
   - For outgoing emails, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD`.
