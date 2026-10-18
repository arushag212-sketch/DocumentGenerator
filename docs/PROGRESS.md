# SVNIT ClubDocs — Build & Verification Progress

## Phase 0: Baseline & Reproduction

### Baseline Metrics
- **Total Frontend Lines**: `11,472`
- **Total Tests Collected**: `176`
- **Frontend Build Time (`npm run build`)**: `34.36s`

#### Frontend Line Counts Per File (web/src)
| File | Lines | Notes |
| :--- | :--- | :--- |
| `web/src/components/TemplateEditor/TemplateEditor.tsx` | 1,405 | TipTap template editor component |
| `web/src/components/EventsTab.tsx` | 1,316 | **Dead component** (slated for removal in Phase 3) |
| `web/src/components/TemplateGalleryTab.tsx` | 868 | Templates gallery & AI draft form |
| `web/src/components/AdminTab.tsx` | 758 | Club settings & administrative panels |
| `web/src/components/HomePage.tsx` | 757 | Simplified Home document generation |
| `web/src/components/MembersTab.tsx` | 735 | Members management tab |
| `web/src/components/NewDocumentPage.tsx` | 672 | **Dead component** (slated for removal in Phase 3) |
| `web/src/api/client.ts` | 643 | API client with automatic session refresh |
| `web/src/components/DocumentsTab.tsx` | 578 | Documents list and download tab |
| `web/src/components/ClubSelectionModal.tsx` | 508 | Multi-club switcher modal |
| `web/src/components/AuthPage.tsx` | 506 | Authentication & registration screens |
| `web/src/components/TemplateEditor/extensions.ts` | 328 | Custom TipTap schema extensions |
| `web/src/components/ResultPage.tsx` | 314 | Document generation results & PDF/Image preview |
| `web/src/types.ts` | 305 | TypeScript interface contracts |
| `web/src/App.tsx` | 303 | Top-level application shell |
| `web/src/components/PeopleTab.tsx` | 292 | Signatories & personnel |
| `web/src/components/SetupWizardModal.tsx` | 287 | Club onboarding wizard |
| `web/src/components/Dashboard.tsx` | 212 | **Dead component** (slated for removal in Phase 3) |
| `web/src/components/ReviewDocumentPage.tsx` | 205 | **Dead component** (slated for removal in Phase 3) |
| `web/src/components/Header.tsx` | 192 | Permanent SVNIT header & club pill |
| `web/src/components/AuditTab.tsx` | 114 | Club audit log viewer |
| `web/src/context/AuthContext.tsx` | 101 | React authentication context |
| `web/src/index.css` | 61 | Tailwind & custom CSS |
| `web/src/main.tsx` | 13 | React DOM entry point |

---

### Selenium Baseline Reproduction Table
Tested with real Chrome via Selenium against production single-URL application server:

| Step | Result | Browser Console Error | Network Error |
| :--- | :--- | :--- | :--- |
| **1. Log in as demo owner** | Successfully logged in to club ACM SVNIT with `demo.owner@svnit.ac.in` | None (initial pre-auth `/auth/me` 401 as expected) | None |
| **2. Open Templates tab** | Rendered Template Gallery with 6 system templates and club drafts | None | None |
| **3. Describe template (AI Draft)** | Draft triggered with plain English prompt; observed 429 quota on retired model requiring dynamic resolution | None | None |
| **4. Open editor with new blank template** | Blank template created; TipTap editor mounted | None | None |
| **5. Try typing in table blocks (`infoTable`, `repeatingTable`, `signatureGrid`)** | **CONFIRMED DEFECT**: `infoTable`, `repeatingTable`, and `signatureGrid` are non-editable atom nodes (`atom: true`). Users cannot click or type data inside table cells. | None | None |
| **6. Preview template** | Document rendered via LibreOffice converter; live preview modal displayed | None | None |
| **7. Publish template** | Publish gate validation executed and confirmed | None | None |

Screenshots archived to `docs/screenshots/baseline/`.

---

## Phase 1: AI Robustness & Dynamic Model Discovery

### Completed Tasks
- **Dynamic Model Discovery (`docgen/llm.py`)**:
  - Implemented `discover_gemini_models` querying `https://generativelanguage.googleapis.com/v1beta/models` using `x-goog-api-key` header (strictly in headers, never query params).
  - Filtered models supporting `generateContent` and containing `flash` (excluding specialized audio/image models like `-image`, `-tts`).
  - Prioritized newest non-preview models (`gemini-3.8-flash`, `gemini-3.7-flash`, etc.) and `GEMINI_MODEL` from `.env`, with fallback to `gemini-flash-latest`.
  - In-memory 1-hour cache (`MODEL_CACHE_TTL = 3600.0`) with `force_refresh` and `clear_model_cache()`.
- **Automatic Fallback Chain**:
  - On HTTP 404 ("model not found" or "no longer available"): cache is invalidated, candidate list re-queried, switched to the next candidate model, and retried ONCE.
  - On HTTP 429 ("quota exceeded"): iterates candidate flash models with 1-second backoff (`time.sleep(1)`), up to 2 retries.
- **Plain-Language User Messages**:
  - Invalid/expired key: `"Gemini API key is invalid or expired. Check your .env."`
  - Quota exceeded: `"Gemini API quota exceeded or rate limit reached. Tip: Set GEMINI_API_KEY in your environment or .env..."`
  - Timeout: `"AI service timed out after 30s. Try a shorter prompt."`
  - Bad response / invalid JSON: `"AI service returned invalid data. You can build this manually in the editor."`
  - General failure: `"AI could not draft this template right now. You can build it manually in the editor."`
- **System Doctor Integration (`server/scripts/doctor.py`)**:
  - `python -m server.scripts.doctor` dynamically queries flash models and prints:
    `Gemini API connected. Discovered flash models: [gemini-flash-latest, gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash (+9 more)]. Selected model for docgen: 'gemini-flash-latest'.`
- **Verification**:
  - `tests/test_gemini_format_and_fallback.py` updated and passing (8/8 passed).
  - Executed live draft trial with the live key ("A simple notice with a title, a date, a body and a signature for the chairperson"). Successfully caught 429 on `gemini-flash-latest`, backed off 1s, fell back to next model, and drafted TemplateSpec (`General Notice`, 3 fields, 5 blocks).

---

## Phase 2: Advanced TipTap Template Editor (Completed)
- **Status**: **DONE**
- **Changes**:
  - Rebuilt `web/src/components/TemplateEditor/extensions.ts` with native `@tiptap/extension-table`, `@tiptap/extension-table-row`, `@tiptap/extension-table-cell`, `@tiptap/extension-table-header`.
  - Rebuilt `web/src/components/TemplateEditor/TemplateEditor.tsx`:
    - Eliminated `editor.isEmpty -> setContent` wipe bug by loading content once per draft version via `contentLoadedRef`.
    - Added floating selection bubble menu (bold, italic, insert field).
    - Added slash commands menu (`/` trigger for headings, info table, repeating table, signatures, page break, field).
    - Added right sidebar fields panel with one-click "Insert" chips into current cursor position.
    - Added A4 desk layout (`max-w-[800px]`, `min-h-[1050px]`, shadow-2xl).
    - Added debounced 1s autosave with status indicator pill (`Saved`, `Saving...`, `Unsaved changes`).
    - Added React `EditorErrorBoundary`.
  - Updated backend compiler (`server/app/core/template_compiler.py`):
    - Added `migrate_template_content` to convert atom nodes into native tables.
    - Added native table compilation in `TipTapDocxCompiler` for info tables, repeating tables, signature grids, and generic tables.
    - Updated identifier validation to support dot-notation table fields (e.g. `budget_items.amount`).
    - Added repeating table detection in `_build_editor_dummy_context` for reliable live preview dry-rendering.
  - **Verification**:
    - `python -m pytest tests/test_phase2_template_tables.py`: 4/4 passed.
    - `python scripts/verify_phase2_editor_selenium.py`: ALL 7 steps passed in headless Chrome (opened blank template, typed heading, inserted & edited infoTable, inserted & edited repeatingTable, inserted signatureGrid, generated LibreOffice PDF live preview, saved, reloaded, and verified table edits persisted).
    - Dev database cleaned of test templates.

---

### Phase 3: React Router, Onboarding Flow & Frontend Cleanup (COMPLETED)
- **What was done**:
  - Configured `react-router-dom` `<BrowserRouter>` and full declarative route tree matching `/login`, `/onboarding/club`, `/onboarding/position`, `/home`, `/documents`, `/documents/:id`, `/templates`, `/templates/:id`, `/settings/*`, and `/join-requests`.
  - Added SPA fallback catch-all in FastAPI `server/app/main.py` to route all non-API paths to `dist/index.html`.
  - Built dedicated route pages under `web/src/pages/`: `HomePageWrapper`, `DocumentsPage`, `DocumentDetailPage`, `DocumentNewPage`, `TemplatesPage`, `TemplateEditorPage`, `SettingsPage`, `OnboardingClubPage`, `OnboardingPositionPage`, `JoinRequestsPage`.
  - Deleted legacy dead components: `EventsTab.tsx`, `Dashboard.tsx`, `NewDocumentPage.tsx`, `ReviewDocumentPage.tsx`, `ClubSelectionModal.tsx`, `SetupWizardModal.tsx`.
  - Frontend size significantly shrunk: from 11,472 lines down to **8,339 lines** (crossing well under the < 8,500 target!).
  - Verified onboarding flow: join request submission, administrator review and approval, position assignment, and session routing.
- **Verification**:
  - `npm run build`: built in 10.20s with 0 errors.
  - `python scripts/verify_phase3_router_selenium.py`: ALL 6 steps passed cleanly in headless Chrome with zero severe console errors.
  - Screenshots saved under `docs/screenshots/phase3/`.

---

### Phase 4: Home Flow & Native Input Widgets (COMPLETED)
- **What was done**:
  - Rebuilt `/home` input widgets:
    - Native `<input type="date">` with past/future bounds (min 1 year ago, max 2 years ahead) and `DD/MM/YYYY` Indian formatting preview.
    - Native `<input type="time">` storing canonical 24-hr `HH:MM`, displaying 12-hr AM/PM, with validation enforcing `end_time > start_time`.
    - Currency input with leading `₹` symbol, decimal parsing, and live Indian numbering grouping preview (`5,000.00`, `1,50,000.00`).
    - Active event dropdown context (`-- New event --` + active events from `/api/v1/clubs/{club_id}/events/active`).
    - People pickers for signatories/in-charges populated from `clubPeople`.
    - AI draft confirmation controls: unconfirmed drafts tagged `[AI-drafted]` with one-click "Accept AI Draft" actions, preventing unreviewed AI text from reaching official documents.
    - Official reference number acceptance checkbox (`#acceptRefNumbers`).
  - Hardened extraction & batch generation:
    - Added prefix title matching heuristic in `EventExtractor.extract_from_text` to cleanly parse titles like `"TechNova on 15 Nov..."`.
    - Added regex extraction for student prize winners (`1st`, `2nd`, `3rd`, roll number, prize amount) directly into `event.winners`.
    - Added safe fallbacks for `event_name`, `target_audience`, and `submitted_to` across `home.py` and `batch_generator.py`.
    - Updated Content Security Policy middleware in `server/app/main.py` (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`, `frame-src 'self' blob:`) to support inline PDF blob previews without browser security violations.
- **Verification**:
  - `npm run build`: built in 4.86s with 0 errors.
  - `python scripts/verify_phase4_home_selenium.py`: ALL 6 steps passed in headless Chrome:
    - Logged in as demo owner and navigated to `/home`.
    - Inputted prompt: `"TechNova on 15 Nov 2026, 10 AM to 5 PM, Computer Dept seminar hall, budget 25000, 120 attendees, 1st prize Rs 5000 to Rahul Sharma (U22CS001), 2nd prize Rs 3000 to Priya Patel (U22CS002)"`.
    - Successfully extracted dates (`2026-11-15`), times (`10:00` to `17:00`), venue, budget (`₹25,000.00`), and winners.
    - Accepted AI drafts and reference numbers; generated 4-document batch (Permission Letter, Approval Note, 2 Prize Money Receipts).
    - Downloaded batch ZIP (1,376,409 bytes) containing 4 DOCX + 4 PDF files.
    - Verified unbroken numbering (`ACM/26-27/ROOM/006`, `ACM/2026-27/T/004`, `ACM/26-27/PRIZE/007`, `ACM/26-27/PRIZE/008`), Indian currency formatting, and Indian date formatting.
    - Verified 0 SEVERE browser console errors.
    - Screenshots recorded in `docs/screenshots/phase4/`:
      - `01_home_initial.png`
      - `02_understood_cards.png`
      - `03_ready_to_generate.png`
      - `04_batch_generated_success.png`

---

## Current Status & Next Steps
- **Phase 0**: **DONE** (Commit `69b63d8`)
- **Phase 1**: **DONE** (Commit `941f16e`)
- **Phase 2**: **DONE** (Commit `9253148`)
- **Phase 3**: **DONE** (Commit `0987314`)
- **Phase 4**: **DONE**
- **Phase 5 (Next)**: Backend Hardening & PostgreSQL Portability
  - Email sender abstraction (`EmailSender`: SMTP with Console fallback).
  - Storage abstraction (`Storage`: LocalDiskStorage + S3-compatible stub).
  - Timezone-aware UTC timestamps (`datetime.now(timezone.utc)` across models).
  - Check database migration & portability scripts (`scripts/check_db.py`).




