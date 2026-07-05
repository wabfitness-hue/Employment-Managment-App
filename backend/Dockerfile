# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps for psycopg2, Pillow, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Runtime-only system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application source
COPY . .

# Photo storage — mounted as volume at runtime; directory must exist
RUN mkdir -p /app/photos && chown -R appuser:appuser /app/photos /app

USER appuser

EXPOSE 8000

# Startup: run Alembic migrations then launch Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers"]
