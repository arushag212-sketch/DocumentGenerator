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

## Current Status & Next Steps
- **Phase 0**: **DONE**
- **Phase 1**: **DONE**
- **Phase 2 (Next)**: Rebuild TipTap Template Editor — Replace non-editable atom table nodes with editable TipTap tables (`@tiptap/extension-table`, `TableRow`, `TableCell`, `TableHeader`), eliminate `editor.isEmpty -> setContent` wipe bug, add slash menu, bubble menu, fields panel, A4 page layout, autosave indicator, and schema compiler updates.

