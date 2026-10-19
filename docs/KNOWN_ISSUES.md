# SVNIT ClubDocs — Known Issues & Architectural Notes

This document logs known technical limitations, environment boundaries, and architectural workarounds with corresponding evidence.

---

## 1. Local Environment: Docker and WSL Unavailable

- **Description**: Docker and WSL are not installed or permitted in the local developer execution environment.
- **Evidence**:
  - The local development environment runs on native Windows PowerShell with SQLite database storage (`data/clubdocs.db`).
  - Running `docker` or `docker-compose` locally returns `CommandNotFoundException`.
- **Workaround & Verification**:
  - All local execution, tests, and database operations run on SQLite in WAL mode with foreign keys enabled.
  - PostgreSQL schema compatibility was verified through `scripts/check_db.py`, which validates all 21 models in `Base.metadata` and compiles DDL directly against the PostgreSQL dialect with exit code 0.
  - Offline Alembic migration compilation was verified via `alembic upgrade head --sql`.
  - The PostgreSQL live concurrency test (`test_concurrency_numbering_postgres`) is conditionally skipped when `DATABASE_URL` does not point to a live PostgreSQL server, as documented in `docs/DECISIONS.md`.

---

## 2. Gemini API Free-Tier Quota & Model Retirement

- **Description**: Google Gemini free-tier API keys are subject to strict upstream rate limits (15 Requests Per Minute) and model deprecations (e.g. `gemini-2.5-flash` retired with HTTP 404).
- **Evidence**:
  - Free-tier keys can encounter HTTP 429 ("Resource has been exhausted") during rapid automated test runs.
- **Workaround & Verification**:
  - Implemented dynamic model discovery in `docgen/llm.py` with 1-hour cache, prioritizing `GEMINI_MODEL`, `gemini-flash-latest`, and active non-preview flash models.
  - On 404, automatically clears cache and retries with the next active flash model.
  - On 429, performs automatic backoff across candidates.
  - In unit tests, all LLM calls use stubs. In `tests/live/test_gemini_live.py`, tests gracefully skip if the upstream account quota is fully depleted, preventing CI/test pipeline stalls.

---

## 3. Font Substitution in Cross-Platform PDF Generation

- **Description**: Standard institutional SVNIT letterheads and templates specify fonts like *Times New Roman* and *Calibri*. On Linux production containers without Microsoft TrueType Core Fonts, LibreOffice falls back to *Liberation Serif* or *Nimbus Roman*, which may cause slight sub-millimeter line wrap differences.
- **Evidence**:
  - Character metrics for *Liberation Serif* differ slightly from proprietary *Times New Roman*.
- **Workaround & Verification**:
  - Production `Dockerfile` installs `fonts-liberation`, `fonts-dejavu-core`, `fonts-noto`, and `fonts-indic`.
  - Document templates use standard margins and explicit table cell padding, avoiding brittle single-line overflow assumptions.
  - Documented in `docs/DEPLOYMENT.md` with font package installation guides.

---

## 4. Legacy Browser Tests Superceded by Modern Selenium Suites

- **Description**: Three legacy browser test files (`tests/e2e/test_w3_slice_e2e.py`, `tests/test_w6b_e2e_browser.py`, `tests/test_w7_e2e_browser.py`) were written during early prototypes to assert against old `#tab-events`, `#tab-dashboard`, and `#tab-new-document` DOM elements that were refactored out in Phase 3.
- **Evidence**:
  - In Phase 3, navigation was consolidated to `/home`, `/documents`, `/templates`, and `/settings/*` via React Router, reducing frontend code by over 3,000 lines.
- **Workaround & Verification**:
  - The legacy tests are marked with `@pytest.mark.skip(reason="Legacy pre-Phase 3 tab UI superseded by scripts/verify_phase2_editor_selenium.py and scripts/verify_phase4_home_selenium.py")`.
  - Full end-to-end browser flows are continuously verified via headless Chrome in `scripts/verify_phase2_editor_selenium.py` (7/7 steps passed) and `scripts/verify_phase4_home_selenium.py` (6/6 steps passed).

---

## 5. Multi-Threaded LibreOffice PDF Conversion on Windows

- **Description**: On Windows, concurrent calls to `soffice --headless` share the default user profile lock file, which can cause concurrent conversions (such as background gallery thumbnail generation during template editing) to fail or fall back to Microsoft Word COM.
- **Evidence**:
  - Running concurrent conversions produced `PermissionError: [WinError 32]` or COM RPC errors when Word COM was invoked across threads.
- **Workaround & Resolution**:
  - In `docgen/renderer.py`, every LibreOffice conversion invocation now passes `-env:UserInstallation=file:///<isolated_temp_dir>` using `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` and awaits filesystem write completion before checking `pdf_path.exists()`.
  - In `server/app/api/v1/documents.py`, `preview_template` includes an automatic 1-second retry on conversion failure.
  - As verified in `scripts/verify_part5_ai_selenium.py`, all concurrent conversions and live previews execute reliably using LibreOffice.

