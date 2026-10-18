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
        ("selenium", "Selenium browser automation"),
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

            if clubs_count > 0 and templates_count > 0:
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

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        return [
            CheckResult(
                name="Google Gemini AI Integration",
                passed=True,
                message="GEMINI_API_KEY is not set (optional in development; offline mode active). Set GEMINI_API_KEY to enable live AI template drafting.",
            )
        ]

    configured_model = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    import requests

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key.strip(),
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        return [
            CheckResult(
                name="Google Gemini AI Integration",
                passed=False,
                message=f"Network error connecting to Gemini API: {e}",
                fix_instruction="Check internet connectivity and ensure generativelanguage.googleapis.com is reachable.",
            )
        ]

    if resp.status_code != 200:
        err_msg = ""
        try:
            err_msg = resp.json().get("error", {}).get("message", "")
        except Exception:
            err_msg = resp.text[:200]
        return [
            CheckResult(
                name="Google Gemini AI Integration",
                passed=False,
                message=f"Gemini API returned HTTP {resp.status_code}: {err_msg}",
                fix_instruction="Verify that your GEMINI_API_KEY is active and valid at https://aistudio.google.com/.",
            )
        ]

    try:
        data = resp.json()
        models = data.get("models", [])
        model_names = [m.get("name", "") for m in models]
        target_name = f"models/{configured_model}" if not configured_model.startswith("models/") else configured_model

        is_in_list = any(m == target_name or m == configured_model for m in model_names)
        if is_in_list:
            return [
                CheckResult(
                    name="Google Gemini AI Integration",
                    passed=True,
                    message=f"Gemini API connected successfully. Configured model '{configured_model}' is available ({len(models)} models listed).",
                )
            ]
        else:
            avail_sample = [m.replace("models/", "") for m in model_names if "gemini" in m][:5]
            return [
                CheckResult(
                    name="Google Gemini AI Integration",
                    passed=False,
                    message=f"Gemini API connected, but configured model '{configured_model}' was not found in available models.",
                    fix_instruction=f"Set GEMINI_MODEL in .env to a supported model (e.g. gemini-2.5-flash). Available models: {', '.join(avail_sample)}",
                )
            ]
    except Exception as e:
        return [
            CheckResult(
                name="Google Gemini AI Integration",
                passed=False,
                message=f"Failed to parse Gemini models list: {e}",
                fix_instruction="Check Google Generative Language API status.",
            )
        ]


def main() -> int:
    print(f"\n{BOLD}{BLUE}========================================================================{RESET}")
    print(f"{BOLD}{BLUE}        SVNIT ClubDocs System Health & Readiness Doctor                 {RESET}")
    print(f"{BOLD}{BLUE}========================================================================{RESET}\n")

    checks: list[CheckResult] = []
    checks.extend(check_python())
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

    print(f"{BOLD}Summary:{RESET} Total checks: {len(checks)} | Passed: {len(checks) - failed_count} | Failed: {failed_count}")
    if failed_count == 0:
        print(f"\n{GREEN}{BOLD}[OK] All system checks passed! ClubDocs is ready to run.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}[ACTION REQUIRED] Please address the failing check(s) above.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
