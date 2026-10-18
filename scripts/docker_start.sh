#!/bin/bash
set -e

echo "Starting SVNIT ClubDocs Container Services..."

# Run health doctor
echo "Running system doctor check..."
python -m server.scripts.doctor || echo "Doctor reported non-fatal notices."

# Run database migrations or seed fresh database
echo "Verifying database tables and seeding..."
python -m server.scripts.seed || echo "Seed check completed."

# Launch FastAPI application via Uvicorn with 4 workers
echo "Launching FastAPI server on 0.0.0.0:8000 (4 workers)..."
exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*'
