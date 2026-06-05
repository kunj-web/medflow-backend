import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.base import Base
from app.core.dependencies import get_db
from app.core.config import settings

# ─── Engine ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    test_url = settings.TEST_DATABASE_URL or settings.DATABASE_URL.replace(
        "/hospital_db", "/hospital_test"
    )
    _engine = create_engine(test_url)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)


@pytest.fixture(scope="function")
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()
    session.begin_nested()  # SAVEPOINT — commits inside won't escape this

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ─── HTTP Client ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Hospital fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def hospital(db):
    from app.models.hospital import Hospital
    h = Hospital(
        name="Test Hospital",
        primary_color="#0066CC",
        currency="INR",
        timezone="Asia/Kolkata",
    )
    db.add(h)
    db.flush()
    return h


# ─── Token helpers ────────────────────────────────────────────────────────────

@pytest.fixture
def admin_headers(db, hospital):
    from tests.factories.user_factory import UserFactory
    from app.models.enums import UserRole
    from app.core.security import create_token_pair
    user = UserFactory.create(db, hospital.id, role=UserRole.ADMIN)
    tokens = create_token_pair(str(user.id), "admin", str(hospital.id))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def doctor_headers(db, hospital):
    from tests.factories.user_factory import UserFactory
    from tests.factories.doctor_factory import DoctorFactory
    from app.models.enums import UserRole
    from app.core.security import create_token_pair
    user = UserFactory.create(db, hospital.id, role=UserRole.DOCTOR)
    doctor = DoctorFactory.create(db, hospital.id, user_id=user.id)
    tokens = create_token_pair(str(user.id), "doctor", str(hospital.id))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def patient_headers(db, hospital):
    from tests.factories.user_factory import UserFactory
    from tests.factories.patient_factory import PatientFactory
    from app.models.enums import UserRole
    from app.core.security import create_token_pair
    user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
    patient = PatientFactory.create(db, hospital.id, user_id=user.id)
    tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
    return {"Authorization": f"Bearer {tokens['access_token']}"}