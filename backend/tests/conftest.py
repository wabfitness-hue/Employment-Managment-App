"""
Test configuration — uses an in-memory SQLite DB so tests run without Docker.
SQLAlchemy models are DB-agnostic; full PostgreSQL-specific features
(JSONB, UUID server defaults) are tested in the migration file separately.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.company import Company
from app.models.id_prefix import IdPrefix, PersonType
from app.models.app_user import AppUser, UserRole
from app.models.person import Person, PersonStatus
from app.models.contract import Contract, ContractType
from app.models.audit_log import AuditLog
from app.models.card_event import CardEvent, CardEventType
from app.models.import_job import ImportJob, ImportSource, ImportStatus

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        SQLALCHEMY_TEST_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # SQLite does not enforce FK by default
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="function")
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """The rate limiter keeps in-memory state at module level (Redis fallback);
    clear it before each test so lockouts don't leak across tests."""
    from app.core import rate_limit
    rate_limit._attempts.clear()
    rate_limit._lockouts.clear()
    yield


@pytest.fixture
def client():
    """HTTP test client with its own isolated in-memory SQLite DB per test."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool
    from app.main import create_app
    from app.database import get_db
    from app.models import Base

    client_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(client_engine, "connect")
    def set_fk(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=client_engine)

    ClientSession = sessionmaker(bind=client_engine)
    test_session = ClientSession()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_session

    with TestClient(app) as c:
        yield c

    test_session.close()
    client_engine.dispose()


@pytest.fixture
def main_company(db):
    company = Company(
        name="Acme Corporation",
        is_main_company=True,
        card_background_colour="#1E40AF",
        card_text_colour="#FFFFFF",
    )
    db.add(company)
    db.flush()
    return company


@pytest.fixture
def contractor_company(db):
    company = Company(
        name="BuildRight Ltd",
        is_main_company=False,
        card_background_colour="#EA580C",
        card_text_colour="#FFFFFF",
    )
    db.add(company)
    db.flush()
    return company


@pytest.fixture
def super_admin(db):
    user = AppUser(
        email="admin@acme.com",
        display_name="Super Admin",
        password_hash="$2b$12$fakehashfortest",
        role=UserRole.super_admin,
        mfa_enabled=True,
        mfa_secret="JBSWY3DPEHPK3PXP",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def dir_prefix(db, super_admin):
    prefix = IdPrefix(
        prefix="DIR",
        label="Director",
        applies_to=PersonType.employee,
        next_sequence=1,
        created_by=super_admin.id,
    )
    db.add(prefix)
    db.flush()
    return prefix


@pytest.fixture
def ctr_prefix(db, super_admin):
    prefix = IdPrefix(
        prefix="CTR",
        label="Contractor",
        applies_to=PersonType.contractor,
        next_sequence=1,
        created_by=super_admin.id,
    )
    db.add(prefix)
    db.flush()
    return prefix
