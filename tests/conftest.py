import os
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./.pytest_cache/medflow_test.db")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite+pysqlite:///./.pytest_cache/medflow_test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.dependencies import get_db
from app.db.base import Base
from app.main import app


@pytest.fixture(scope="session")
def engine():
    test_url = settings.sqlalchemy_test_database_url
    url = make_url(test_url)
    kwargs = {}
    if url.drivername.startswith("sqlite"):
        if url.database:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_engine(test_url, **kwargs)
    yield _engine
    Base.metadata.drop_all(_engine)


@pytest.fixture(scope="function")
def db(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    yield session

    session.close()


@pytest_asyncio.fixture(scope="function")
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


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


@pytest.fixture
def admin_headers(db, hospital):
    from app.core.security import create_token_pair
    from app.models.enums import AccountStatus, UserRole
    from tests.factories.user_factory import UserFactory

    user = UserFactory.create(
        db,
        role=UserRole.WEBSITE_ADMIN,
        is_super_admin=True,
    )
    tokens = create_token_pair(
        str(user.id),
        UserRole.WEBSITE_ADMIN.value,
        AccountStatus.ACTIVE.value,
        True,
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def doctor_headers(db, hospital):
    from app.core.security import create_token_pair
    from app.models.enums import AccountStatus, UserRole
    from tests.factories.doctor_factory import DoctorFactory
    from tests.factories.user_factory import UserFactory

    user = UserFactory.create(db, hospital.id, role=UserRole.DOCTOR)
    DoctorFactory.create(db, hospital.id, user_id=user.id)
    tokens = create_token_pair(
        str(user.id), UserRole.DOCTOR.value, AccountStatus.ACTIVE.value
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def patient_headers(db, hospital):
    from app.core.security import create_token_pair
    from app.models.enums import AccountStatus, UserRole
    from tests.factories.patient_factory import PatientFactory
    from tests.factories.user_factory import UserFactory

    user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
    PatientFactory.create(db, hospital.id, user_id=user.id)
    tokens = create_token_pair(
        str(user.id), UserRole.PATIENT.value, AccountStatus.ACTIVE.value
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}
