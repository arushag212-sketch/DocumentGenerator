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

## Current Status & Next Steps
- **Phase 0**: **DONE** (Baseline recorded, reproduction completed, git commit created).
- **Phase 1 (Next)**: AI Robustness — Dynamic model discovery from models list endpoint, caching, fallback chain, and typed error handling.
