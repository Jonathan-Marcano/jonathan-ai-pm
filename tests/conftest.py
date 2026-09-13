import pytest
from sqlalchemy.orm import Session

from jonathan_ai_pm.db import build_engine
from jonathan_ai_pm.models import Base


@pytest.fixture
def session() -> Session:
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
