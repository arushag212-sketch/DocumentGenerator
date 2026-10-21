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

# Hosts such as Render pass the port in $PORT. Each worker plus LibreOffice needs memory, so the
# worker count is configurable: use WEB_CONCURRENCY=1 on a 512 MB free instance.
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
echo "Launching FastAPI server on 0.0.0.0:${PORT} (${WORKERS} workers)..."
exec uvicorn server.app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${WORKERS}" --proxy-headers --forwarded-allow-ips='*'
