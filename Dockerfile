# ==============================================================================
# SVNIT ClubDocs Production Multi-Stage Container Image
# Stage 1: Build React SPA with Vite
# Stage 2: Python 3.12 Runtime with LibreOffice, Indian Fonts, and Dumb-Init
# ==============================================================================

# --- Stage 1: Build Frontend SPA ---
FROM node:20.18.0-alpine AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Public Google client ID for the sign-in button (Render passes service env vars as build args)
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

# --- Stage 2: Production Runtime ---
FROM python:3.12.8-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    STORAGE_LOCAL_ROOT=/app/storage

# Install LibreOffice (writer), true-type Indian/Devanagari fonts, curl, dumb-init
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-mono \
    fonts-noto-ui-core \
    fonts-noto-hinted \
    fonts-indic \
    fonts-gargi \
    curl \
    dumb-init \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with wheel cache
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /build/dist /app/web/dist

# Copy application backend, template engine, and migrations
COPY backend/docgen /app/docgen
COPY backend/server /app/server
COPY backend/scripts /app/scripts
COPY backend/assets /app/assets
COPY backend/templates /app/templates
COPY backend/config /app/config
COPY backend/demo /app/demo
COPY backend/alembic.ini /app/alembic.ini
COPY backend/pyproject.toml /app/pyproject.toml

# Ensure runtime directories exist
RUN mkdir -p /app/data /app/storage /app/outputs

# Pre-render built-in template thumbnails at build time
RUN cd /app && python -m scripts.prerender_thumbnails || echo "Warning: prerender_thumbnails failed, continuing build"

# Create non-root system user and configure permissions
RUN groupadd -r clubdocs && useradd -r -g clubdocs -d /app -s /bin/bash clubdocs \
    && chown -R clubdocs:clubdocs /app \
    && chmod +x /app/scripts/docker_start.sh

USER clubdocs

# Container Healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/liveness || exit 1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "/app/scripts/docker_start.sh"]
