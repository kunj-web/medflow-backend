# ---------------------------------------------------------------------------
# Stage 1 — dependency builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# System dependencies required for psycopg2 and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /venv

# Activate venv
ENV PATH="/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2 — development image
# Auto reload enabled via uvicorn --reload
# Source code is mounted via docker-compose volume
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /venv /venv

WORKDIR /app

# Source code is mounted via docker-compose
# No COPY needed here

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]


# ---------------------------------------------------------------------------
# Stage 3 — production runtime
# Non-root user
# No auto reload
# Source code baked into image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment
COPY --from=builder /venv /venv

WORKDIR /app

# Copy application source
COPY . .

# Create non-root user
RUN addgroup --system medflow && adduser --system --ingroup medflow medflow

USER medflow

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]