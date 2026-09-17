from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from faroflow.config import get_settings
from faroflow.security import prepare_private_file


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        prepare_private_file(Path(url.removeprefix("sqlite:///")))

    engine_options = {}
    if url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    if url == "sqlite:///:memory:":
        engine_options["poolclass"] = StaticPool

    engine = create_engine(url, **engine_options)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
