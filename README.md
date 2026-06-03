# Hospital Platform — Phase 1 Boilerplate

## Stack
| Layer | Tech |
|---|---|
| Frontend | Next.js 14 + TypeScript |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| ORM | SQLAlchemy + Alembic |
| Auth | JWT (python-jose + passlib) |
| Email | Resend |
| Push Notifications | Firebase Cloud Messaging |
| File Storage | Cloudflare R2 |
| Testing | pytest + httpx + factory-boy |
| Deployment | Vercel (frontend) + Railway (backend + DB) |

---

## Backend Setup

```bash
cd backend

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Run migrations
alembic upgrade head

# 5. Start server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Running Tests

```bash
cd backend

# All tests with coverage
pytest --cov=app --cov-report=term-missing

# Unit tests only (fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific file
pytest tests/unit/services/test_appointment_service.py -v
```

Coverage must stay above **80%** — build fails below this.

---

## Database Migrations

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          # settings from .env
│   │   ├── security.py        # JWT, password hashing
│   │   └── dependencies.py    # DB session, role guards
│   ├── models/
│   │   ├── enums.py           # all Enum definitions
│   │   ├── hospital.py
│   │   ├── user.py
│   │   ├── patient.py
│   │   ├── doctor.py
│   │   ├── appointment.py
│   │   ├── invoice.py
│   │   └── notification.py
│   ├── schemas/               # Pydantic — request/response
│   ├── repositories/          # data access layer
│   ├── services/              # business logic layer
│   └── routers/               # HTTP layer
├── tests/
│   ├── conftest.py            # shared fixtures
│   ├── factories/             # test data builders
│   ├── unit/                  # service + repo tests
│   └── integration/           # full HTTP tests
└── alembic/                   # migrations
```

---

## API Endpoints (Phase 1)

### Public
```
GET  /api/v1/config/hospital/{hospital_id}   # frontend bootstrap
GET  /health
```

### Auth
```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
```

### Appointments
```
POST /api/v1/appointments                           # patient
GET  /api/v1/appointments                           # admin/staff
GET  /api/v1/appointments/queue/today               # admin/staff/doctor
GET  /api/v1/appointments/{id}                      # all roles
POST /api/v1/appointments/{id}/cancel               # patient/staff/admin
POST /api/v1/appointments/{id}/reschedule           # patient/staff/admin
```

### Notifications
```
GET  /api/v1/notifications/me
POST /api/v1/notifications/me/read-all
POST /api/v1/notifications/device/register
```

---

## Architecture Principles Enforced

- **No N+1 queries** — `lazy="raise"` on all relationships, explicit `joinedload`
- **Repository pattern** — Router → Service → Repository → DB
- **Pagination** — all list endpoints return `PaginatedResponse`
- **Soft deletes** — `deleted_at` on every table, no hard deletes
- **Atomic transactions** — services commit, repositories flush only
- **Enums everywhere** — no magic strings for status/role fields
- **Indexes** — defined in models, carry through migrations
- **Strict schemas** — separate Create / Update / Response per entity