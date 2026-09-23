from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cuentafaro.audit import install_audit_listener
from cuentafaro.config import get_settings
from cuentafaro.security import prepare_private_file


def ensure_sqlite_dir(database_url: str) -> None:
    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
        prepare_private_file(Path(path))


def create_engine_and_session(
    database_url: str | None = None,
) -> tuple[Engine, sessionmaker]:
    url = database_url or get_settings().database_url
    ensure_sqlite_dir(url)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    install_audit_listener(session_factory)
    return engine, session_factory


@lru_cache
def get_session_factory() -> sessionmaker:
    _engine, session_factory = create_engine_and_session()
    return session_factory


def get_session() -> Session:
    return get_session_factory()()
