# Architecture & Engineering Decisions (DECISIONS.md)

This log documents all architectural decisions, design choices, and documented test exceptions across the SVNIT ClubDocs platform.

---

## 1. Skipped Test Exceptions

### `test_postgres_concurrency.py::test_concurrency_numbering_postgres`
- **Status**: Skipped (`@pytest.mark.skip(reason="Docker/PostgreSQL not available")`)
- **Rationale**: Local development environment runs on native Windows without Docker Desktop or WSL 2. As defined in build constraints, live PostgreSQL services cannot be spawned locally.
- **Verification Strategy**:
  1. Concurrency isolation and atomic gap-free numbering logic is fully verified locally against SQLite WAL mode with 20 parallel worker threads (`test_concurrency_numbering_atomic_sqlite`).
  2. All table DDL and migrations are verified for PostgreSQL dialect compilation using `scripts/check_db.py` and `alembic upgrade head --sql` in offline mode.
  3. Live PostgreSQL concurrency can be executed in production CI/CD or staging containers with `POSTGRES_TEST_URL`.

### `tests/e2e/test_w3_slice_e2e.py`, `tests/test_w6b_e2e_browser.py`, `tests/test_w7_e2e_browser.py`
- **Status**: Skipped (`@pytest.mark.skip(reason="Legacy browser test for pre-Phase 3 tab UI; verified by scripts/verify_phase2_editor_selenium.py and scripts/verify_phase4_home_selenium.py")`)
- **Rationale**: These legacy test scripts were authored during earlier development iterations that depended on obsolete tab-state switching (`currentTab` buttons for "Dashboard", "Events", "Review") before the Phase 3 React Router declarative refactor (`/home`, `/documents`, `/templates`, `/settings/club`).
- **Verification Strategy**: Full real-browser Selenium automated verification is conducted using the two canonical suites:
  1. `scripts/verify_phase2_editor_selenium.py` (verifies TipTap 3 editor, native table cells, bold/chip insertion, and live LibreOffice preview).
  2. `scripts/verify_phase4_home_selenium.py` (verifies `/home` fast path, date/time/money pickers, AI draft confirmations, reference numbers, and multi-document ZIP batch download).

### `tests/live/test_gemini_live.py::test_gemini_live_draft_template`
- **Status**: Conditionally Skipped when Google Gemini Free Tier Quota is exceeded (`AIQuotaError: HTTP 429`)
- **Rationale**: Live tests run against Google's upstream Gemini API using the developer's provided key. When upstream per-day/per-minute request quotas are exhausted, the test detects the typed `AIQuotaError` and cleanly skips rather than asserting a fatal crash.
- **Verification Strategy**: The full model discovery, schema generation, fallback chain, and 400/404/429/503 exception handling is verified deterministically in offline unit tests with mock HTTP fixtures in `tests/test_gemini_format_and_fallback.py` and `tests/test_w5_ai_template.py`.

---

## 2. Architectural Decisions

### DEC-001: Timezone Normalization for Hybrid SQLite/PostgreSQL Compatibility
- **Decision**: Eradicate deprecated `datetime.utcnow()` and adopt `datetime.now(timezone.utc).replace(tzinfo=None)` as standard UTC timestamp provider.
- **Rationale**: Standard SQLAlchemy `DateTime` mappings on SQLite produce naive datetime strings. Python 3.12+ deprecated `utcnow()`. Using timezone-aware datetimes directly with SQLite causes `TypeError: can't compare offset-naive and offset-aware datetimes`. The naive UTC helper preserves exact UTC time semantics while enabling seamless zero-error comparisons on both SQLite and PostgreSQL.

### DEC-002: Dynamic Gemini Flash Model Discovery & Resilient Fallbacks
- **Decision**: Query Google Gemini API's `/v1beta/models` endpoint at runtime, filter for `generateContent` models containing `flash`, prioritize `.env` `GEMINI_MODEL`, and cache the choice for 1 hour.
- **Rationale**: Hardcoded model names like `gemini-2.5-flash` retire upstream, yielding unexpected 404 errors. Dynamic discovery ensures automatic zero-config compatibility with newer models (`gemini-3.8-flash`, `gemini-3.7-flash`, etc.). On 404 or 429 errors, candidate rotation seamlessly shifts to the next capable flash model.

### DEC-003: TipTap Real Editable Tables Replacing Atom Nodes
- **Decision**: Replace non-editable `atom: true` blobs (`infoTable`, `repeatingTable`, `signatureGrid`) with `@tiptap/extension-table` standard nodes (`Table`, `TableRow`, `TableHeader`, `TableCell`).
- **Rationale**: Users need to edit table cells inline, format text, and insert field chips. Tables are converted during compilation into structured Jinja tables in the generated DOCX and HTML templates.

### DEC-004: Fast-Path `/home` Document Creation Flow
- **Decision**: Single-page interactive document generator at `/home` that understands natural language prompt briefs (e.g. "TechNova on 15 Nov..."), extracts structured events, enforces review of AI drafts, validates numbers, and bundles multi-document batches into a single ZIP.
- **Rationale**: Greatly reduces club administrative friction by generating full document suites (permission letters, approval notes, budget summaries, prize money receipts) from a single brief.

### DEC-005: Security-First Document Compilation & Sandboxed Templating
- **Decision**: All user text is treated strictly as data. Jinja delimiters are escaped in user input; only the template compiler injects syntax. Rendering runs in `jinja2.sandbox.SandboxedEnvironment` with autoescape enabled.
- **Rationale**: Prevents template injection attacks and arbitrary code execution while allowing expressive templating.
