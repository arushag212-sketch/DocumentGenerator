#!/bin/bash
set -Eeuo pipefail

echo "Starting SVNIT ClubDocs Container Services..."

# Apply versioned schema changes before any application/doctor query.  This is
# safe to run on every container start and avoids create_all/partial schemas.
echo "Applying database migrations..."
python -m alembic upgrade head

# Seed only idempotent system fixtures.  In production the seed module skips
# demo clubs, users, passwords, and platform admins entirely.
echo "Seeding safe system fixtures..."
if [[ "${ENVIRONMENT:-development}" == "production" ]]; then
    python -m server.scripts.seed --no-demo-users
else
    python -m server.scripts.seed --no-clean
fi

# Run health doctor after migrations and seed; notices are diagnostic only.
echo "Running system doctor check..."
python -m server.scripts.doctor || echo "Doctor reported non-fatal notices."

# Launch FastAPI application via Uvicorn with 4 workers
echo "Launching FastAPI server on 0.0.0.0:8000 (4 workers)..."
exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*'
