"""Pre-flight deployment verification script for SVNIT ClubDocs.

Verifies:
1. Dockerfile structure and multi-stage syntax.
2. Docker Compose configuration syntax and services.
3. Environment variable documentation completeness.
4. Absence of hardcoded production secrets in code/configs.
5. Absence of localhost URLs in production deployment configs.
6. Healthcheck endpoints response (/health, /health/liveness, /health/readiness).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_DIR = ROOT_DIR.parent  # Dockerfile, docker-compose.yml, vercel.json and docs/ live here
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import yaml
from fastapi.testclient import TestClient
from server.app.main import app


def check_dockerfile() -> tuple[bool, list[str]]:
    errors = []
    dockerfile_path = REPO_DIR / "Dockerfile"
    if not dockerfile_path.exists():
        return False, ["Dockerfile does not exist."]

    content = dockerfile_path.read_text(encoding="utf-8")

    # Check multi-stage
    if "FROM node:20-alpine AS frontend-builder" not in content:
        errors.append("Dockerfile missing node:20-alpine frontend builder stage.")
    if "FROM python:3.12-slim AS runtime" not in content:
        errors.append("Dockerfile missing python:3.12-slim runtime stage.")

    # Check LibreOffice & Fonts
    if "libreoffice-writer" not in content and "libreoffice-nogpu" not in content:
        errors.append("Dockerfile missing libreoffice installation.")
    if "fonts-dejavu-core" not in content or "fonts-liberation" not in content:
        errors.append("Dockerfile missing required typography font packages.")

    # Check dumb-init & non-root user
    if "dumb-init" not in content:
        errors.append("Dockerfile missing dumb-init process supervisor.")
    if "USER clubdocs" not in content:
        errors.append("Dockerfile must run under non-root user 'clubdocs'.")

    # Check HEALTHCHECK
    if "HEALTHCHECK" not in content or "health/liveness" not in content:
        errors.append("Dockerfile missing HEALTHCHECK instruction for /health/liveness.")

    return len(errors) == 0, errors


def check_docker_compose() -> tuple[bool, list[str]]:
    errors = []
    compose_path = REPO_DIR / "docker-compose.yml"
    if not compose_path.exists():
        return False, ["docker-compose.yml does not exist."]

    try:
        data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"docker-compose.yml YAML syntax error: {exc}"]

    services = data.get("services", {})
    if "app" not in services:
        errors.append("docker-compose.yml missing 'app' service.")
    if "postgres" not in services:
        errors.append("docker-compose.yml missing 'postgres' service.")
    if "redis" not in services:
        errors.append("docker-compose.yml missing 'redis' service.")

    # Check healthcheck dependencies
    app_service = services.get("app", {})
    depends_on = app_service.get("depends_on", {})
    if not isinstance(depends_on, dict) or "postgres" not in depends_on:
        errors.append("app service must declare healthcheck dependency on postgres.")

    # Check volume persistence
    volumes = data.get("volumes", {})
    if "postgres_data" not in volumes or "clubdocs_data" not in volumes:
        errors.append("docker-compose.yml missing required persistent volumes.")

    return len(errors) == 0, errors


def check_env_documentation() -> tuple[bool, list[str]]:
    errors = []
    env_example = ROOT_DIR / ".env.example"
    doc_path = REPO_DIR / "docs" / "DEPLOYMENT.md"

    if not env_example.exists():
        errors.append(".env.example missing.")
    if not doc_path.exists():
        errors.append("docs/DEPLOYMENT.md missing.")

    if errors:
        return False, errors

    doc_text = doc_path.read_text(encoding="utf-8")
    for line in env_example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.split("=")[0].strip()
        if key and key not in doc_text:
            errors.append(f"Environment variable '{key}' from .env.example is not documented in docs/DEPLOYMENT.md")

    return len(errors) == 0, errors


def check_no_hardcoded_secrets() -> tuple[bool, list[str]]:
    errors = []
    # Patterns for potential secrets: live Google API keys, private keys, AWS secret keys
    gemini_key_pattern = re.compile(r"AIza[0-9A-Za-z-_]{35}")
    aws_secret_pattern = re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]")

    scan_targets = [
        REPO_DIR / "Dockerfile",
        REPO_DIR / "docker-compose.yml",
        REPO_DIR / "vercel.json",
        ROOT_DIR / "server" / "app" / "core" / "config.py",
        ROOT_DIR / "server" / "app" / "main.py",
    ]

    for target in scan_targets:
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        if gemini_key_pattern.search(text):
            errors.append(f"Hardcoded Gemini API key detected in {target.relative_to(ROOT_DIR)}!")
        if aws_secret_pattern.search(text):
            errors.append(f"Hardcoded AWS secret key detected in {target.relative_to(ROOT_DIR)}!")

    return len(errors) == 0, errors


def check_production_configs_localhost() -> tuple[bool, list[str]]:
    errors = []
    vercel_path = REPO_DIR / "vercel.json"
    if vercel_path.exists():
        content = vercel_path.read_text(encoding="utf-8")
        if "localhost" in content or "127.0.0.1" in content:
            errors.append("vercel.json contains localhost destination URL. Production proxy must point to public API host.")

    return len(errors) == 0, errors


def check_health_endpoints() -> tuple[bool, list[str]]:
    errors = []
    client = TestClient(app)

    try:
        r_health = client.get("/health")
        if r_health.status_code != 200 or r_health.json().get("status") != "healthy":
            errors.append(f"/health returned unexpected response: {r_health.status_code} {r_health.text}")
    except Exception as exc:
        errors.append(f"/health call failed: {exc}")

    try:
        r_live = client.get("/health/liveness")
        if r_live.status_code != 200 or r_live.json().get("status") != "alive":
            errors.append(f"/health/liveness returned unexpected response: {r_live.status_code} {r_live.text}")
    except Exception as exc:
        errors.append(f"/health/liveness call failed: {exc}")

    try:
        r_ready = client.get("/health/readiness")
        if r_ready.status_code != 200 or r_ready.json().get("status") != "ready":
            errors.append(f"/health/readiness returned unexpected response: {r_ready.status_code} {r_ready.text}")
    except Exception as exc:
        errors.append(f"/health/readiness call failed: {exc}")

    return len(errors) == 0, errors


def run_all_checks() -> bool:
    print("=" * 70)
    print("      SVNIT ClubDocs Production Pre-Flight Deployment Check       ")
    print("=" * 70)

    checks = [
        ("Dockerfile multi-stage & security structure", check_dockerfile),
        ("Docker Compose production stack syntax", check_docker_compose),
        ("Environment variables documentation completeness", check_env_documentation),
        ("Absence of hardcoded production secrets", check_no_hardcoded_secrets),
        ("Absence of localhost in deployment routing configs", check_production_configs_localhost),
        ("Healthcheck endpoints (/health, /liveness, /readiness)", check_health_endpoints),
    ]

    all_ok = True
    for name, func in checks:
        ok, errs = func()
        if ok:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}")
            for e in errs:
                print(f"       -> {e}")
            all_ok = False

    print("=" * 70)
    if all_ok:
        print("[SUCCESS] All pre-flight deployment checks passed! System is production-ready.")
    else:
        print("[FAILURE] Pre-flight deployment checks failed. Please address errors above.")
    print("=" * 70)

    return all_ok


if __name__ == "__main__":
    if not run_all_checks():
        sys.exit(1)
    sys.exit(0)
