from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from cuentafaro.config import get_settings
from cuentafaro.security import prepare_private_file

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

try:
    from cuentafaro.models import Base

    target_metadata = Base.metadata
except ImportError:  # migrations run before the domain models module exists
    target_metadata = None


def _ensure_sqlite_dir(database_url: str) -> None:
    if database_url.startswith("sqlite:///"):
        prepare_private_file(Path(database_url.removeprefix("sqlite:///")))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    _ensure_sqlite_dir(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = section.get("sqlalchemy.url") or get_settings().database_url
    _ensure_sqlite_dir(section["sqlalchemy.url"])
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
