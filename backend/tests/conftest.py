import tempfile
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.pipeline import Pipeline
from app.services.pipeline_seed import seed_pipelines


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan for tests — skip Alembic migrations and pipeline seed."""
    yield


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Replace lifespan so TestClient doesn't try to connect to PostgreSQL
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_token(client):
    """Create initial admin user and return token."""
    response = client.post(
        "/api/auth/setup",
        json={
            "email": "admin@legacy.com",
            "full_name": "Admin User",
            "password": "testpassword123",
        },
    )
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def seeded_stages(db_session):
    """Seed default pipelines and stages into the test database."""
    seed_pipelines(db_session)
    return db_session


@pytest.fixture()
def leads_pipeline(seeded_stages, db_session):
    """Return the Leads pipeline object."""
    return db_session.query(Pipeline).filter(Pipeline.slug == "leads").first()


@pytest.fixture()
def sales_pipeline(seeded_stages, db_session):
    """Return the Sales pipeline object."""
    return db_session.query(Pipeline).filter(Pipeline.slug == "sales").first()


@pytest.fixture()
def jobs_pipeline(seeded_stages, db_session):
    """Return the Jobs pipeline object."""
    return db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()


@pytest.fixture()
def temp_upload_dir(monkeypatch):
    """Provide a temporary upload directory for document tests."""
    from app.config import settings

    tmpdir = tempfile.mkdtemp()
    monkeypatch.setattr(settings, "upload_dir", tmpdir)
    yield tmpdir
    # Cleanup
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)
