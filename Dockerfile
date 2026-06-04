# ---------------------------------------------------------------------------
# Stage 1 — dependency builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps for psycopg2 and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — dev image (auto-reload, runs as root, source mounted at runtime)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install

# watchfiles is the fastest file-watcher uvicorn supports on Linux
RUN pip install --no-cache-dir watchfiles

WORKDIR /app
# Source is volume-mounted by docker-compose — no COPY needed here

EXPOSE 8000

# --reload-dir scopes the watcher to app/ so changes to tests/ or alembic/
# don't trigger unnecessary restarts.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app"]

# ---------------------------------------------------------------------------
# Stage 3 — production runtime (non-root, no watchfiles, baked source)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install

WORKDIR /app
COPY . .

# Non-root user for security
RUN addgroup --system medflow && adduser --system --ingroup medflow medflow
USER medflow

EXPOSE 8000

# Production: Railway runs `alembic upgrade head` as a release command.
# This CMD is the fallback for non-Railway deployments.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]