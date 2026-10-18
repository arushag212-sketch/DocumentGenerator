# SVNIT ClubDocs Production Deployment Guide

This document describes the operational architecture, deployment models, configuration parameters, and disaster recovery procedures for SVNIT ClubDocs.

---

## 1. Architecture Overview

ClubDocs supports two production deployment topologies:

1. **Self-Hosted Single VM (Recommended for Campus Intranet)**:
   - Orchestrated with Docker Compose.
   - Runs the multi-stage single-URL ClubDocs container (FastAPI + Vite-built React SPA + LibreOffice + Indian Fonts) alongside PostgreSQL 16 and Redis 7.
2. **Serverless / Managed Cloud**:
   - Frontend hosted on Vercel (`vercel.json` rewrites).
   - Backend API hosted on Render or Fly.io with Docker runtime (for LibreOffice headless PDF generation).
   - Database on Supabase Managed PostgreSQL.
   - Binary asset storage on AWS S3 or Cloudflare R2.

---

## 2. Deployment Model A: Self-Hosted Single VM (Docker Compose)

### Prerequisites
- Ubuntu 22.04 LTS or 24.04 LTS (minimum 2 vCPUs, 4 GB RAM, 20 GB SSD).
- Docker Engine (v24+) and Docker Compose (v2.20+).
- Inbound ports `80` and `443` open.

### Setup Instructions

1. **Clone the repository on the target server:**
   ```bash
   git clone https://github.com/svnit-clubdocs/clubdocs.git /opt/clubdocs
   cd /opt/clubdocs
   ```

2. **Configure production environment:**
   ```bash
   cp .env.example .env
   chmod 600 .env
   # Edit .env to set your secure secret keys, domain name, and GEMINI_API_KEY
   ```

3. **Build and launch the stack:**
   ```bash
   docker compose build --pull
   docker compose up -d
   ```

4. **Verify container health:**
   ```bash
   docker compose ps
   docker compose logs -f app
   curl -f http://localhost:8000/health/readiness
   ```

5. **Configure reverse proxy (Nginx / Caddy):**
   Point your domain (e.g. `clubdocs.svnit.ac.in`) with HTTPS certificates to `http://127.0.0.1:8000`.

---

## 3. Deployment Model B: Managed Multi-Cloud (Vercel + Render + Supabase)

### Backend (Render / Fly.io)
1. Deploy using the repository's `Dockerfile`.
2. Set Environment Variables in the provider dashboard:
   - `DATABASE_URL`: Your Supabase connection string (`postgresql://postgres.[project-ref]:[db-password]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require`).
   - `STORAGE_BACKEND`: `s3`
   - `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`.
   - `GEMINI_API_KEY`: API key for Gemini template drafting and extraction.
   - `SECRET_KEY`: High-entropy 64-character random string.
   - `APP_ENV`: `production`

### Frontend (Vercel)
1. Connect the repository to Vercel.
2. Set Framework Preset to **Vite**.
3. Vercel automatically detects `vercel.json` and proxies `/api/*` and `/health/*` requests to your managed backend URL.

---

## 4. Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` / `APP_ENV` | Yes | `production` | Environment mode (`development`, `test`, `production`). In production, non-ephemeral keys are strictly required. |
| `JWT_SECRET_KEY` / `SECRET_KEY` | Yes | - | Random 64-character hex key for HMAC signing of JWT session tokens and cryptographic hashes. |
| `FIELD_ENCRYPTION_KEY` / `ENCRYPTION_KEY` | Yes | - | 32-byte URL-safe base64 string for AES-256-GCM / Fernet encryption of sensitive PII (e.g. phone numbers). |
| `DATABASE_URL` | Yes | `sqlite:///data/clubdocs.db` | PostgreSQL (`postgresql://user:pass@host:5432/dbname`) or SQLite connection string. |
| `HOST` | No | `127.0.0.1` | Network interface host IP for backend server binding. |
| `PORT` | No | `8000` | Port number for HTTP service listener. |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000` | Comma-delimited list of permitted CORS origins. |
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key for AI document drafting and unstructured event extraction. |
| `GEMINI_MODEL` | No | Auto-discovered | Explicit Gemini model override (e.g. `gemini-3.8-flash`). Auto-discovers newest flash candidate if omitted. |
| `STORAGE_BACKEND` | No | `local` | Binary document storage provider: `local` or `s3`. |
| `STORAGE_LOCAL_ROOT`| No | `storage` | Local directory root when `STORAGE_BACKEND=local`. |
| `S3_BUCKET` | Cond. | - | Bucket name when `STORAGE_BACKEND=s3`. |
| `S3_ENDPOINT_URL` | No | - | S3 endpoint override for MinIO, Cloudflare R2, or Supabase Storage. |
| `S3_ACCESS_KEY` | Cond. | - | Access key for S3 compatible object storage. |
| `S3_SECRET_KEY` | Cond. | - | Secret key for S3 compatible object storage. |
| `SMTP_HOST` | No | - | SMTP hostname for outgoing emails (activation, password reset, invitations). If unset, defaults to Console fallback. |
| `SMTP_PORT` | No | `587` | SMTP port (587 for STARTTLS, 465 for TLS). |
| `SMTP_USER` | No | - | SMTP authentication username. |
| `SMTP_PASSWORD` | No | - | SMTP authentication password. |
| `FROM_EMAIL` | No | `noreply@svnit.ac.in` | Sender email address for system emails. |

---

## 5. Backup and Disaster Recovery

### PostgreSQL Backup & Restore
To perform an atomic, consistent database backup:
```bash
# Backup
docker compose exec -T postgres pg_dump -U clubdocs_user -d clubdocs -F c -b -v -f /var/lib/postgresql/data/backup_$(date +%Y%m%d_%H%M%S).dump

# Restore
docker compose exec -T postgres pg_restore -U clubdocs_user -d clubdocs --clean --if-exists /var/lib/postgresql/data/backup_20261019_000000.dump
```

### SQLite Backup & Restore (Local / Dev)
To safely backup an active SQLite database without lock contention:
```bash
# Backup using online sqlite3 backup API
python -c "
import sqlite3, shutil, datetime
src = sqlite3.connect('data/clubdocs.db')
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
dst = sqlite3.connect(f'data/backup_clubdocs_{ts}.db')
with dst:
    src.backup(dst)
src.close()
dst.close()
print(f'Backup created: data/backup_clubdocs_{ts}.db')
"
```

### Document Storage Assets Backup
Binary assets (generated DOCX, PDF, and club letterheads) stored on local disk should be backed up using `rsync` or tar archives:
```bash
tar -czvf storage_backup_$(date +%Y%m%d).tar.gz storage/
```
