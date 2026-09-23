"""Configuración y aislamiento de la base de datos local (CF1-01)."""

from sqlalchemy import text

from cuentafaro.db import create_engine_and_session, ensure_sqlite_dir


def test_ensure_sqlite_dir_creates_parent(tmp_path) -> None:
    target = tmp_path / "nested" / "deep" / "app.db"
    ensure_sqlite_dir(f"sqlite:///{target}")
    assert target.parent.exists()


def test_sqlite_foreign_keys_enabled(tmp_path) -> None:
    db_file = tmp_path / "app.db"
    engine, _ = create_engine_and_session(f"sqlite:///{db_file}")
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1
    engine.dispose()
