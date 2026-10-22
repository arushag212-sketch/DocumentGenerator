# E2E Test Infra: DocumentGenerator Mobile Experience

## Test Philosophy
- Opaque-box, requirement-driven.
- Automated headless verification of viewport overflow (scrollWidth vs innerWidth), touch target bounding envelopes (>=44px), body scroll-locking state, and modal keyboard accessibility across target viewports: 320px, 360px, 375px, 390px, 414px, 480px, and desktop control (1280px).
- Verification mechanism: Node.js / Playwright / Puppeteer script or static AST + CSS layout verification runner that runs against the built bundle and source components.

## Feature Inventory & Test Coverage Goals
| # | Feature | Requirement | Tier 1 (Isolated) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|-------------|:-----------------:|:-----------------:|:---------------------:|:-------------------:|
| 1 | Navigation Hamburger & Close Targets | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 2 | Mobile Drawer Body Scroll Lock | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 3 | Drawer Navigation Links Pitch | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 4 | Landing Page Zero Overflow | R1 | ≥5 | ≥5 | ✓ | ✓ |
| 5 | Auth & Verify Zero Overflow | R1 | ≥5 | ≥5 | ✓ | ✓ |
| 6 | Dashboard & Charts Zero Overflow | R1 | ≥5 | ≥5 | ✓ | ✓ |
| 7 | Create & Batch Rows Zero Overflow | R1, R3 | ≥5 | ≥5 | ✓ | ✓ |
| 8 | Documents & Templates Zero Overflow | R1, R3 | ≥5 | ≥5 | ✓ | ✓ |
| 9 | Template Studio Palette Drawer | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 10| Result Page Constrained Preview | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 11| Data Tables Explicit Min-Width | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 12| Modal Dialog Keyboard Fit & Max Height | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 13| Strict Desktop Preservation (>=1024px) | R4 | ≥5 | ≥5 | ✓ | ✓ |

## Test Architecture
- Test Runner: `node frontend/scripts/verify-mobile-layout.mjs` or Playwright suite.
- Checks:
  1. Build validation: `npm --prefix frontend run build` exits with 0.
  2. Bounding box & touch target checks: Elements annotated or styled for navigation, hamburger, close, links must have min dimension >= 44px on mobile viewports.
  3. Window / Document scrollWidth <= window.innerWidth check at 320, 360, 375, 390, 414, 480 px.
  4. Modal dialog class checks: verify `max-h-[85vh]` (or `max-h-[90vh]`) and `overflow-y-auto` are present on modal dialog bodies.
  5. Desktop control: verify desktop breakpoints (`lg:`) preserve original desktop layout and classes.
