# Project: DocumentGenerator Mobile Experience Improvement

## Architecture
DocumentGenerator is a React 18 single-page application built with TypeScript, Vite, Tailwind CSS, and React Router v6.
- Main layout shell: `frontend/src/components/layout/AppShell.tsx` (Sidebar for desktop `>= 1024px`, Mobile Header & Navigation Drawer for `< 1024px`).
- Route hierarchy (`frontend/src/App.tsx`):
  - Public routes: `/login`, `/register`, `/privacy`, `/terms`, `/verify`
  - Authenticated routes (wrapped in `AppShell`): `/dashboard`, `/home`, `/documents`, `/documents/new`, `/documents/:id`, `/templates`, `/settings`, `/profile`, `/help`, `/join-requests`, `/onboarding/*`
  - Dedicated full-screen studio routes: `/templates/:id`, `/editor/:id` (`TemplateEditorPage.tsx` -> `TemplateEditor.tsx`)
- Styling system: Tailwind CSS utilities with responsive modifiers (`sm:`, `md:`, `lg:`).

## Code Layout
- `frontend/src/components/layout/AppShell.tsx`: Navigation bar, mobile drawer, body scroll locking, touch targets.
- `frontend/src/pages/`: Page components (LandingPage, AuthPage, DashboardPage, DocumentsPage, DocumentDetailPage, TemplatesPage, SettingsPage, ProfilePage, HelpPage, VerifyPage, etc.).
- `frontend/src/components/brand/DocPreviewArt.tsx`: Landing page preview art and badges.
- `frontend/src/components/create/`: HomePage, ResultPage, BatchRowsPanel.
- `frontend/src/components/documents/`: DocumentsTab, DocumentCard.
- `frontend/src/components/templates/`: TemplateGalleryTab, TemplateWizardModal, TemplateImportModal.
- `frontend/src/components/settings/`: AdminTab, MembersTab, PeopleTab, AuditTab.
- `frontend/src/components/onboarding/`: GettingStarted, WelcomeTour.
- `frontend/src/components/TemplateEditor/`: TemplateEditor, PalettePanel, Toolbar, RightTabsPanel, Canvas.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Mobile Hamburger Touch Target (>=44px) | Expand `AppShell.tsx:289` hamburger button tap envelope from 32px to >=44px | M1 | Survey Explorer 1 |
| 2 | Mobile Drawer Close Button Touch Target (>=44px) | Expand `AppShell.tsx:274` close button tap envelope from 28px to >=44px | M1 | Survey Explorer 1 |
| 3 | Mobile Drawer Body Scroll Locking | Lock `document.body` scroll when `mobileOpen === true` and listen for Escape key in `AppShell.tsx` | M1 | Survey Explorer 1 |
| 4 | Mobile Navigation Links Pitch (>=44px) | Expand vertical pitch and tap target of sidebar nav links on mobile to >=44px | M1 | Survey Explorer 1 |
| 5 | Mobile Drawer Logout & Profile Targets (>=44px) | Expand profile avatar link and sign out button to >=44px tap envelope | M1 | Survey Explorer 1 |
| 6 | Mobile Drawer Max Width on 320px | Constrain mobile drawer width with `max-w-[calc(100vw-3rem)]` so backdrop is easily dismissable | M1 | Survey Explorer 1 |
| 7 | Landing Page Overhang & Padding Fixes | Constrain `DocPreviewArt.tsx` negative offsets (`-right-6`, `-left-3`), adjust 320px padding | M2 | Survey Explorer 2 |
| 8 | Auth & Verify Page Layouts | Adjust Auth card padding on 320px screens, responsive `grid-cols-1 sm:grid-cols-[8rem_1fr]` on VerifyPage with `break-all` | M2 | Survey Explorer 2 |
| 9 | Dashboard Page Stats Grid & Chart | Responsive stats grid `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`, scrollable `MonthlyChart` wrapper | M2 | Survey Explorer 2 |
| 10| HomePage Toggle & Badge Wrapping | Add `flex-wrap` to document type picker toggle and active template badge container | M2 | Survey Explorer 2 |
| 11| Documents & Templates Toolbar Wrapping | Add `flex-wrap` to action toolbars in `TemplateGalleryTab.tsx` and `DocumentsTab.tsx` modal header | M2 | Survey Explorer 2 |
| 12| Onboarding Tour Button Wrapping | Add `flex-col-reverse sm:flex-row` to `WelcomeTour.tsx` footer buttons | M2 | Survey Explorer 2 |
| 13| Template Studio Palette Panel Overlay Drawer | Render `PalettePanel.tsx` as slide-over/overlay drawer on `< 1024px` with backdrop, avoiding canvas compression | M3 | Survey Explorer 3 |
| 14| Template Studio RightTabsPanel Mobile Sheet Bug | Fix inverted conditional in `RightTabsPanel.tsx` (`!isOpen && isMobile`) so sheet collapses properly | M3 | Survey Explorer 3 |
| 15| Template Studio Mobile Zoom Auto-fit | Adjust canvas auto-fit zoom calculations for mobile screen widths in `TemplateEditor.tsx` | M3 | Survey Explorer 3 |
| 16| Document Result Page Constrained Preview Height | Constrain preview container height to `max-h-[38vh] sm:max-h-[45vh] lg:min-h-[640px] lg:max-h-[820px]` so editable form fields remain visible | M3 | Survey Explorer 3 |
| 17| Data Tables Explicit Minimum Widths | Add `min-w-[...]` to tables in `DocumentsTab.tsx`, `ResultPage.tsx`, `AuditTab.tsx`, and `PeopleTab.tsx` within `overflow-x-auto` | M3 | Survey Explorer 3 |
| 18| Dynamic Batch Rows Input Mobile Grid | Adapt `BatchRowsPanel.tsx` column mapping from `grid-cols-2` to `grid-cols-1 sm:grid-cols-2` | M3 | Survey Explorer 3 |
| 19| Modal Dialogs Scrollable Content (`max-h-[85vh]`) | Add `max-h-[85vh] overflow-y-auto` to modal dialog content areas across all 15+ modals | M3 | Survey Explorer 3 |
| 20| Modal Close Button Accessible Touch Targets | Ensure close buttons on modals meet >=44px tap envelope | M3 | Survey Explorer 3 |
| 21| Strict Desktop Layout Preservation (>= 1024px) | Verify all desktop screens remain identical with 0 visual/functional regression | M4 | ORIGINAL_REQUEST R4 |
| 22| TypeScript Compilation & Bundle Verification | `npm --prefix frontend run build` completes with 0 errors | M4 | ORIGINAL_REQUEST Build |
| 23| Automated Headless Viewport Test Suite | Automated test suite validating viewports (320px, 360px, 375px, 390px, 414px, 480px, 1280px) | E2E | Dual Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Design & implement automated mobile viewport test suite (Tiers 1-4) | none | DONE (TEST_READY.md published) |
| M1 | Global Navigation & Touch Targets | `AppShell.tsx`: Hamburger, close button, body scroll lock, resize unlock, link pitch, logout button | none | DONE |
| M2 | Main Pages Overflow Prevention | Landing, Auth, Verify, Dashboard, Create, Documents, Templates, Onboarding responsive fixes | M1 contracts | DONE |
| M3 | Complex Workspaces & Modals | Template Studio Palette Panel slide-over, RightTabsPanel bug fix, ResultPage preview height, tables `min-w`, modal `max-h-[85vh]` | M1 contracts | IN_PROGRESS |
| M4 | Final Acceptance & Hardening | Dual track validation: 100% E2E test pass, 0 TS build errors, strict desktop preservation, adversarial hardening (Tier 5) | E2E, M1, M2, M3 | PLANNED |

## Interface Contracts
### AppShell ↔ Routed Pages
- `AppShell` wraps all authenticated pages in `<main className="flex-1 min-w-0 overflow-x-hidden">`.
- Mobile navigation drawer operates via `mobileOpen` boolean state and locks `document.body.style.overflow = 'hidden'`.
- Window resize listener resets `mobileOpen` to `false` when `window.innerWidth >= 1024`, unlocking body scroll.
- All navigation links in the drawer must have a minimum tap target height of 44px on mobile (`py-2.5 lg:py-2 min-h-[44px] lg:min-h-0`).

### Template Studio ↔ Canvas
- On viewports `< 1024px`, `PalettePanel` renders fixed positioned (`fixed inset-y-0 left-0 z-50`) with an overlay backdrop (`fixed inset-0 bg-slate-900/40 z-40`), not taking flex space from `Canvas`.
- On desktop `>= 1024px`, `PalettePanel` renders inline as `w-72 lg:w-80 flex-shrink-0 border-r border-slate-200`.

### Modals ↔ Viewports
- Modal overlays: `fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/50 backdrop-blur-xs`.
- Modal dialog containers: `w-full max-w-[...] max-h-[85vh] sm:max-h-[90vh] flex flex-col bg-white rounded-xl shadow-2xl`.
- Modal body: `overflow-y-auto flex-1 p-4 sm:p-6`.
- Modal footer/actions: `flex-shrink-0 p-4 border-t border-slate-100 flex items-center justify-end gap-2`.
