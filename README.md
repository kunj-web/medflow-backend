# MedFlow — Hospital Operations Platform

API-first, multi-tenant hospital platform. Each hospital is fully isolated via `hospital_id` scoping on every query. The same backend serves web and mobile.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 + TypeScript |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| ORM | SQLAlchemy + Alembic |
| Auth | JWT — python-jose + argon2 (passlib) |
| Email | Resend |
| Push Notifications | Firebase Cloud Messaging (FCM) |
| File Storage | Supabase Storage (S3-compatible) |
| Testing | pytest + httpx + factory-boy |
| Deployment | Netlify (frontend) + Render (backend + DB) |

---

## Project Structure

```
medflow-backend/
├── app/
│   ├── core/
│   │   ├── config.py           # pydantic-settings, loads .env
│   │   ├── security.py         # JWT create/decode, argon2 hashing
│   │   └── dependencies.py     # get_db, get_current_user, require_role
│   ├── db/
│   │   ├── base.py             # declarative Base, HospitalScopedMixin
│   │   └── session.py          # engine + SessionLocal
│   ├── models/                 # SQLAlchemy models
│   │   ├── enums.py            # UserRole, AppointmentStatus, InvoiceStatus, …
│   │   ├── hospital.py         # Hospital, HospitalFeature
│   │   ├── user.py             # User (hashed_password field)
│   │   ├── doctor.py           # Doctor, DoctorSchedule, DoctorLeave
│   │   ├── patient.py          # Patient
│   │   ├── appointment.py      # Appointment
│   │   ├── invoice.py          # Invoice (line_items JSONB)
│   │   └── notification.py     # Notification, UserDevice
│   ├── schemas/                # Pydantic v2 — request / response
│   │   └── validators/         # phone, datetime, password, common validators
│   ├── repositories/           # data access only — no business logic
│   ├── services/               # all business logic lives here
│   └── routers/                # HTTP layer — thin, delegates to services
├── tests/
│   ├── conftest.py             # fixtures: db, client, hospital, *_headers
│   ├── factories/              # UserFactory, DoctorFactory, PatientFactory
│   ├── unit/services/          # service-layer unit tests
│   └── integration/            # full HTTP tests via AsyncClient
├── alembic/                    # migrations
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── pytest.ini
└── requirements.txt
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value before running anything.

```bash
cp .env.example .env
```

### `.env.example` — full reference

```env
# ── App ──────────────────────────────────────────────────────────────────────
SECRET_KEY=changeme-use-openssl-rand-hex-32
APP_ENV=development                  # development | production

# ── Database ──────────────────────────────────────────────────────────────────
# venv local:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medflow
# Docker (uncomment and use this instead when running via docker-compose):
# DATABASE_URL=postgresql://postgres:postgres@db:5432/medflow

# Test DB — used by pytest only (separate DB to avoid wiping dev data)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medflow_test

# ── Supabase Storage ──────────────────────────────────────────────────────────
# Create a project at supabase.com, then:
# Storage → New bucket → name it "hospital-assets" → set to Public
# Settings → Storage → S3 Access → generate access key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_S3_ACCESS_KEY=your-s3-access-key
SUPABASE_S3_SECRET_KEY=your-s3-secret-key
SUPABASE_BUCKET_NAME=hospital-assets

# ── Email (Resend) ────────────────────────────────────────────────────────────
# Create account at resend.com → API Keys → Create Key
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com    # must be a verified domain in Resend

# ── Firebase (FCM Push Notifications) ────────────────────────────────────────
# Firebase Console → Project Settings → Service Accounts → Generate new private key
# Save the downloaded JSON as firebase-credentials.json in the project root
# Then set the path here:
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# ── CORS ──────────────────────────────────────────────────────────────────────
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
```

### What each variable does

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | ✅ | Signs JWTs. Generate with `openssl rand -hex 32`. Never commit. |
| `APP_ENV` | ✅ | Controls debug mode and logging level. |
| `DATABASE_URL` | ✅ | Main app DB. Use `@localhost:5432` for venv, `@db:5432` for Docker. |
| `TEST_DATABASE_URL` | ✅ for tests | Separate DB. pytest creates and drops tables automatically. |
| `SUPABASE_URL` | ✅ | Your Supabase project URL. |
| `SUPABASE_S3_ACCESS_KEY` | ✅ | From Supabase Storage → S3 Access. |
| `SUPABASE_S3_SECRET_KEY` | ✅ | From Supabase Storage → S3 Access. |
| `SUPABASE_BUCKET_NAME` | ✅ | Must match the bucket you created in Supabase dashboard. |
| `RESEND_API_KEY` | ✅ | From resend.com dashboard. Emails silently fail if missing. |
| `EMAIL_FROM` | ✅ | Must be a Resend-verified sender domain. |
| `FIREBASE_CREDENTIALS_PATH` | ✅ | Path to the downloaded service account JSON file. |
| `CORS_ORIGINS` | ✅ | Comma-separated list of allowed frontend origins. |

---

## `.gitignore` — what is never committed

These files must exist locally but must never be pushed to the repository:

```
.env                        # all secrets
firebase-credentials.json   # Firebase service account private key
venv/                       # Python virtual environment
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
*.egg-info/
dist/
.DS_Store
```

> **If you clone this repo:** you must create `.env` and `firebase-credentials.json`
> yourself before the app will start. See the sections above for where to get each value.

---

## Local Setup — Option A: venv (recommended for development)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ running locally
- `pip`

### 1. Create the databases

```sql
-- run in psql or any Postgres client
CREATE DATABASE medflow;
CREATE DATABASE medflow_test;
```

Or via the command line:

```bash
createdb medflow
createdb medflow_test
```

### 2. Clone and set up the virtual environment

```bash
git clone https://github.com/your-org/medflow.git
cd medflow/medflow-backend

python -m venv venv

# macOS / Linux:
source venv/bin/activate

# Windows (PowerShell):
venv\Scripts\Activate.ps1

# Windows (cmd):
venv\Scripts\activate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Open .env and fill in every value — see Environment Variables section above
```

Make sure `DATABASE_URL` points to `@localhost:5432` (not `@db:5432`).

### 5. Add Firebase credentials

Download your Firebase service account JSON from:
**Firebase Console → Project Settings → Service Accounts → Generate new private key**

Save it as `firebase-credentials.json` in the `medflow-backend/` root (same folder as `Dockerfile`).

### 6. Run migrations

```bash
alembic upgrade head
```

### 7. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Local Setup — Option B: Docker

### Prerequisites
- Docker Desktop
- Docker Compose v2

### 1. Configure environment

```bash
cp .env.example .env
```

Open `.env` and make these specific changes for Docker:

```env
# Change this line:
DATABASE_URL=postgresql://postgres:postgres@db:5432/medflow
#                                             ^^
#                             'db' = the postgres service name in docker-compose.yml
#                             NOT localhost — containers talk to each other by service name

TEST_DATABASE_URL=postgresql://postgres:postgres@db:5432/medflow_test
```

All other variables stay the same as the venv setup.

### 2. Add Firebase credentials

Save `firebase-credentials.json` in `medflow-backend/` (Docker copies it in via the `Dockerfile`).

### 3. Start everything

```bash
docker-compose up --build
```

This starts:
- `db` — PostgreSQL 15 on port `5432`
- `api` — FastAPI on port `8000`

Migrations run automatically on container start.

### 4. Verify it's running

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Useful Docker commands

```bash
# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop everything
docker-compose down

# Stop and wipe the database volume (full reset)
docker-compose down -v

# Open a shell inside the api container
docker-compose exec api bash

# Run migrations manually inside container
docker-compose exec api alembic upgrade head

# Run tests inside container
docker-compose exec api pytest --cov=app --cov-report=term-missing
```

---

## Running Tests

Tests use a **separate database** (`medflow_test`). Tables are created and dropped automatically — your dev data is never touched.

```bash
# Make sure your venv is active and TEST_DATABASE_URL is set in .env

# All tests with coverage report
pytest --cov=app --cov-report=term-missing

# Unit tests only (fast, no HTTP)
pytest tests/unit/ -v

# Integration tests only (full HTTP via AsyncClient)
pytest tests/integration/ -v

# Single file
pytest tests/unit/services/test_billing_service.py -v

# Single test
pytest tests/unit/services/test_billing_service.py::TestPartialPayment::test_full_payment_marks_paid -v
```

Coverage must stay **≥ 80%** — enforce this in CI with:

```bash
pytest --cov=app --cov-fail-under=80
```

---

## Database Migrations

```bash
# After changing any model, generate a migration:
alembic revision --autogenerate -m "describe what changed"

# Apply all pending migrations:
alembic upgrade head

# Roll back one migration:
alembic downgrade -1

# See migration history:
alembic history

# See current applied migration:
alembic current
```

> Always review the auto-generated migration file before applying.
> Alembic occasionally misses column type changes or index renames.

---

## API Reference

### Public (no auth)
```
GET  /health
GET  /api/v1/config/hospital/{hospital_id}   # frontend bootstrap — branding, features
```

### Auth
```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
```

### Doctors `[admin]`
```
POST /api/v1/doctors
GET  /api/v1/doctors
GET  /api/v1/doctors/{id}
PUT  /api/v1/doctors/{id}
PUT  /api/v1/doctors/{id}/schedule
GET  /api/v1/doctors/{id}/slots?date=YYYY-MM-DD
```

### Patients `[admin, staff]`
```
POST /api/v1/patients
GET  /api/v1/patients?search=
GET  /api/v1/patients/{id}
PUT  /api/v1/patients/{id}
GET  /api/v1/patients/{id}/appointments
```

### Appointments
```
POST /api/v1/appointments                        # [patient]
GET  /api/v1/appointments                        # [admin, staff]
GET  /api/v1/appointments/queue/today            # [admin, staff, doctor]
GET  /api/v1/appointments/{id}                   # [all roles]
POST /api/v1/appointments/{id}/cancel            # [patient, staff, admin]
POST /api/v1/appointments/{id}/reschedule        # [patient, staff, admin]
```

### Invoices `[admin, staff]`
```
POST /api/v1/invoices
GET  /api/v1/invoices
GET  /api/v1/invoices/{id}
POST /api/v1/invoices/{id}/issue
POST /api/v1/invoices/{id}/pay
POST /api/v1/invoices/{id}/cancel
```

### Notifications
```
GET  /api/v1/notifications/me                    # [current user]
POST /api/v1/notifications/me/read-all           # [current user]
POST /api/v1/notifications/device/register       # [current user]
```

### Hospital Admin `[admin]`
```
GET  /api/v1/admin/hospital
PUT  /api/v1/admin/hospital
POST /api/v1/admin/hospital/logo
```

---

## Architecture Principles

| Principle | Implementation |
|---|---|
| Multi-tenancy | Every model has `hospital_id`. Every query filters by it from the JWT. No data bleeds between hospitals. |
| Repository pattern | Router → Service → Repository → DB. Repositories do only DB queries. Services do only business logic. |
| No N+1 queries | `lazy="raise"` on all relationships. Explicit `joinedload` in repositories. |
| Soft deletes | `deleted_at` on every table. Never hard delete. All queries filter `deleted_at.is_(None)`. |
| Atomic transactions | Services call `db.commit()`. Repositories call `db.flush()` only. |
| Pagination | All list endpoints return `{ data, total, page, page_size, total_pages }`. |
| Enums everywhere | No magic strings for status or role fields. |
| Auth dict access | `get_current_user` returns a plain dict. Always use `current_user["hospital_id"]` — never dot notation. |

---

## Common Issues

**`ModuleNotFoundError` on startup**
→ Virtual environment is not activated. Run `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\Activate.ps1` (Windows).

**`sqlalchemy.exc.OperationalError: could not connect to server`**
→ PostgreSQL is not running, or `DATABASE_URL` has the wrong host/port/credentials.

**`ValueError: Firebase app not initialized`**
→ `firebase-credentials.json` is missing or `FIREBASE_CREDENTIALS_PATH` points to the wrong path.

**`alembic.util.exc.CommandError: Can't locate revision`**
→ Run `alembic upgrade head` to apply all pending migrations in order.

**Tests fail with `could not connect to server`**
→ `TEST_DATABASE_URL` is not set in `.env`, or the `medflow_test` database doesn't exist yet. Run `createdb medflow_test`.

**Docker: `connection refused` on `@localhost:5432`**
→ Inside Docker, the database host must be `db` (the service name), not `localhost`. Check your `DATABASE_URL` in `.env`.