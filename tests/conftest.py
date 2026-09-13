import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jonathan_ai_pm.api import app
from jonathan_ai_pm.db import build_engine, get_session
from jonathan_ai_pm.models import Base


@pytest.fixture
def session() -> Session:
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def api_client(session: Session) -> TestClient:
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
