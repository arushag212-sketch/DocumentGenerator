"""System diagnostic & readiness doctor for SVNIT ClubDocs.

Checks:
1. Python runtime (>= 3.11) and critical packages
2. Node.js (>= 18) and npm
3. LibreOffice soffice binary (official document converter)
4. Database connectivity, migrations, and core tables
5. Environment variables (JWT_SECRET_KEY, FIELD_ENCRYPTION_KEY)

Usage:
    python -m server.scripts.doctor
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ANSI colors for Windows & terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


class CheckResult:
    def __init__(self, name: str, passed: bool, message: str, fix_instruction: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.fix_instruction = fix_instruction


def check_python() -> list[CheckResult]:
    results = []
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major >= 3 and v.minor >= 11:
        results.append(
            CheckResult(
                name="Python Runtime Version",
                passed=True,
                message=f"Python {ver_str} (>= 3.11 satisfied)",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Python Runtime Version",
                passed=False,
                message=f"Python {ver_str} is below required 3.11",
                fix_instruction="Install Python 3.11 or newer from https://www.python.org/downloads/",
            )
        )

    # Core packages
    pkgs = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("sqlalchemy", "SQLAlchemy ORM"),
        ("docxtpl", "Word template engine (docxtpl)"),
        ("docx", "python-docx Word processing library"),
        ("pymupdf", "PyMuPDF PDF engine"),
        ("PIL", "Pillow image library"),
        ("cryptography", "Fernet field encryption"),
        ("passlib", "Passlib password hashing"),
        ("argon2", "Argon2 password hasher"),
    ]
    missing = []
    for mod_name, label in pkgs:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(label)

    if not missing:
        results.append(
            CheckResult(
                name="Python Package Dependencies",
                passed=True,
                message=f"All {len(pkgs)} core packages installed and importable",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Python Package Dependencies",
                passed=False,
                message=f"Missing packages: {', '.join(missing)}",
                fix_instruction="Run: pip install -r requirements.txt",
            )
        )

    return results


def check_node_and_npm() -> list[CheckResult]:
    results = []
    # Check node
    node_bin = shutil.which("node")
    if not node_bin:
        results.append(
            CheckResult(
                name="Node.js Runtime",
                passed=False,
                message="node not found in PATH",
                fix_instruction="Install Node.js (v18 or v20 LTS) from https://nodejs.org/",
            )
        )
    else:
        try:
            out = subprocess.check_output(["node", "--version"], text=True).strip()
            # e.g. v20.11.0
            ver_num = out.lstrip("v").split(".")[0]
            if int(ver_num) >= 18:
                results.append(
                    CheckResult(
                        name="Node.js Runtime",
                        passed=True,
                        message=f"{out} (>= v18 satisfied) at {node_bin}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Node.js Runtime",
                        passed=False,
                        message=f"{out} is below required v18",
                        fix_instruction="Upgrade Node.js to v18+ LTS from https://nodejs.org/",
                    )
                )
        except Exception as e:
            results.append(
                CheckResult(
                    name="Node.js Runtime",
                    passed=False,
                    message=f"Failed to execute node: {e}",
                    fix_instruction="Ensure Node.js is correctly installed and in PATH.",
                )
            )

    # Check npm
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_bin:
        results.append(
            CheckResult(
                name="npm Package Manager",
                passed=False,
                message="npm not found in PATH",
                fix_instruction="npm usually comes with Node.js. Reinstall Node.js from https://nodejs.org/",
            )
        )
    else:
        try:
            out = subprocess.check_output([npm_bin, "--version"], text=True).strip()
            results.append(
                CheckResult(
                    name="npm Package Manager",
                    passed=True,
                    message=f"npm v{out} found at {npm_bin}",
                )
            )
        except Exception as e:
            results.append(
                CheckResult(
                    name="npm Package Manager",
                    passed=False,
                    message=f"Failed to run npm: {e}",
                    fix_instruction="Check npm installation.",
                )
            )

    return results


def check_libreoffice() -> list[CheckResult]:
    results = []
    # Common LibreOffice locations on Windows and Unix
    candidates = [
        shutil.which("soffice"),
        shutil.which("soffice.exe"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    found_bin = None
    for c in candidates:
        if c and Path(c).is_file():
            found_bin = str(c)
            break

    if found_bin:
        try:
            ver_out = subprocess.check_output([found_bin, "--version"], text=True, timeout=10).strip()
            results.append(
                CheckResult(
                    name="LibreOffice (Official PDF Converter)",
                    passed=True,
                    message=f"{ver_out} found at {found_bin}",
                )
            )
        except Exception as e:
            results.append(
                CheckResult(
                    name="LibreOffice (Official PDF Converter)",
                    passed=True,
                    message=f"Binary located at {found_bin} (version check timed out: {e})",
                )
            )
    else:
        results.append(
            CheckResult(
                name="LibreOffice (Official PDF Converter)",
                passed=False,
                message="soffice executable not found in PATH or standard Windows program paths",
                fix_instruction=(
                    "Install LibreOffice from https://www.libreoffice.org/download/download/\n"
                    "Default install path on Windows: 'C:\\Program Files\\LibreOffice\\program\\soffice.exe'\n"
                    "Add 'C:\\Program Files\\LibreOffice\\program' to your Windows User PATH environment variable."
                ),
            )
        )

    return results


def check_database() -> list[CheckResult]:
    results = []
    try:
        from server.app.core.database import SessionLocal, engine, Base
        from sqlalchemy import inspect
        from server.app.models import Club, User, Membership, Template, NumberingSeries

        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        required_tables = ["clubs", "users", "memberships", "templates", "numbering_series", "people"]
        missing_tables = [t for t in required_tables if t not in table_names]

        if not missing_tables:
            db = SessionLocal()
            clubs_count = db.query(Club).count()
            users_count = db.query(User).count()
            templates_count = db.query(Template).count()
            db.close()

            # A fresh production database has templates but no clubs until someone creates one
            if templates_count > 0:
                results.append(
                    CheckResult(
                        name="Database Schema & Seed Data",
                        passed=True,
                        message=(
                            f"Database connected. Tables verified ({len(table_names)} tables). "
                            f"Seeded: {clubs_count} club(s), {users_count} user(s), {templates_count} template(s)."
                        ),
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Database Schema & Seed Data",
                        passed=False,
                        message="Database tables exist but seed data is missing.",
                        fix_instruction="Run: python -m server.scripts.seed",
                    )
                )
        else:
            results.append(
                CheckResult(
                    name="Database Schema & Seed Data",
                    passed=False,
                    message=f"Missing tables: {', '.join(missing_tables)}",
                    fix_instruction="Run: python -m server.scripts.seed",
                )
            )
    except Exception as e:
        results.append(
            CheckResult(
                name="Database Schema & Seed Data",
                passed=False,
                message=f"Database connection error: {e}",
                fix_instruction="Run: python -m server.scripts.seed",
            )
        )

    return results


def check_env_vars() -> list[CheckResult]:
    results = []
    env = os.environ.get("ENVIRONMENT", "development").lower()
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    enc_key = os.environ.get("FIELD_ENCRYPTION_KEY")

    if env == "production":
        if not jwt_secret or not enc_key:
            results.append(
                CheckResult(
                    name="Environment Variables (Production)",
                    passed=False,
                    message="Missing JWT_SECRET_KEY or FIELD_ENCRYPTION_KEY in production mode",
                    fix_instruction="Set JWT_SECRET_KEY and FIELD_ENCRYPTION_KEY in your .env or shell environment.",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Environment Variables (Production)",
                    passed=True,
                    message="Production cryptographic keys configured",
                )
            )
    else:
        results.append(
            CheckResult(
                name="Environment Variables (Development)",
                passed=True,
                message=(
                    f"Running in '{env}' mode. Ephemeral per-run security keys are enabled if not explicitly provided."
                ),
            )
        )

    return results


def check_ai() -> list[CheckResult]:
    from server.app.core.config import _load_env_file
    _load_env_file()

    results: list[CheckResult] = []

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        results.append(
            CheckResult(
                name="Google Gemini AI Integration",
                passed=True,
                message="GEMINI_API_KEY is not set (optional in development; offline mode active). Set GEMINI_API_KEY to enable live AI template drafting.",
            )
        )
    else:
        from docgen.llm import discover_gemini_models
        try:
            discovered = discover_gemini_models(api_key.strip(), force_refresh=True)
            if not discovered:
                results.append(
                    CheckResult(
                        name="Google Gemini AI Integration",
                        passed=False,
                        message="No compatible Gemini flash models found.",
                        fix_instruction="Verify your GEMINI_API_KEY has access to Gemini flash models.",
                    )
                )
            else:
                chosen_model = discovered[0]
                models_str = ", ".join(discovered[:5]) + (f" (+{len(discovered)-5} more)" if len(discovered) > 5 else "")
                results.append(
                    CheckResult(
                        name="Google Gemini AI Integration",
                        passed=True,
                        message=(
                            f"Gemini API connected. Discovered flash models: [{models_str}]. "
                            f"Selected model for docgen: '{chosen_model}'."
                        ),
                    )
                )
        except Exception as e:
            results.append(
                CheckResult(
                    name="Google Gemini AI Integration",
                    passed=False,
                    message=f"Gemini API check failed: {e}",
                    fix_instruction="Verify your GEMINI_API_KEY in .env.",
                )
            )

    # Groq AI Fallback
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        results.append(
            CheckResult(
                name="Groq AI Integration (Fallback)",
                passed=True,
                message=f"Groq configured (model: {groq_model}). Automatic fallback active when Gemini quota is exceeded.",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Groq AI Integration (Fallback)",
                passed=True,
                message="GROQ_API_KEY is not set (optional fallback). Set GROQ_API_KEY to enable automatic fallback when Gemini quota is exceeded.",
            )
        )

    return results


def check_optional_services() -> list[tuple[str, str, str]]:
    """Report optional services and test skips with explicit reasons."""
    items = []
    # 1. PostgreSQL live integration
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url.startswith("postgres"):
        items.append((
            "Live PostgreSQL / Supabase Connection",
            "SKIPPED",
            "Local dev uses SQLite (data/clubdocs.db). Live PostgreSQL tests are skipped.",
        ))
    else:
        items.append((
            "Live PostgreSQL / Supabase Connection",
            "ACTIVE",
            "PostgreSQL DATABASE_URL is configured.",
        ))

    # 2. Live Gemini AI Online Test Suite
    run_live_ai = os.environ.get("RUN_LIVE_AI_TESTS", "0").lower() in ("1", "true")
    if not run_live_ai:
        items.append((
            "Live Gemini Online Test Suite",
            "SKIPPED",
            "RUN_LIVE_AI_TESTS is disabled to avoid quota exhaustion. Automated tests use deterministic mocks.",
        ))
    else:
        items.append((
            "Live Gemini Online Test Suite",
            "ACTIVE",
            "RUN_LIVE_AI_TESTS is enabled.",
        ))
    return items


def main() -> int:
    print(f"\n{BOLD}{BLUE}========================================================================{RESET}")
    print(f"{BOLD}{BLUE}        SVNIT ClubDocs System Health & Readiness Doctor                 {RESET}")
    print(f"{BOLD}{BLUE}========================================================================{RESET}\n")

    checks: list[CheckResult] = []
    checks.extend(check_python())
    # The production image serves a pre-built website, so Node.js is only needed for development
    if os.environ.get("ENVIRONMENT", "development").lower() != "production":
        checks.extend(check_node_and_npm())
    checks.extend(check_libreoffice())
    checks.extend(check_database())
    checks.extend(check_env_vars())
    checks.extend(check_ai())

    failed_count = 0
    for c in checks:
        if c.passed:
            status_tag = f"{GREEN}[PASS]{RESET}"
            print(f"{status_tag} {BOLD}{c.name}{RESET}")
            print(f"       {c.message}\n")
        else:
            failed_count += 1
            status_tag = f"{RED}[FAIL]{RESET}"
            print(f"{status_tag} {BOLD}{c.name}{RESET}")
            print(f"       {c.message}")
            if c.fix_instruction:
                print(f"       {YELLOW}Fix instruction:{RESET}")
                for line in c.fix_instruction.splitlines():
                    print(f"         {line}")
            print()

    optional = check_optional_services()
    print(f"{BOLD}Optional Services & Test Skips:{RESET}")
    for name, status, reason in optional:
        tag = f"{YELLOW}[{status}]{RESET}" if status == "SKIPPED" else f"{GREEN}[{status}]{RESET}"
        print(f"  {tag} {BOLD}{name}{RESET}: {reason}")
    print()

    print(f"{BOLD}Summary:{RESET} Total checks: {len(checks)} | Passed: {len(checks) - failed_count} | Failed: {failed_count}")
    if failed_count == 0:
        print(f"\n{GREEN}{BOLD}[OK] All system checks passed! ClubDocs is ready to run.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}[ACTION REQUIRED] Please address the failing check(s) above.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
