from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from cuentafaro import __version__
from cuentafaro.config import get_settings

BACKUP_GLOB = "cuentafaro-*.db"
BACKUP_STAMP = re.compile(r"^cuentafaro-\d{8}T\d{6}Z\.db$")


def _sqlite_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(database_url.removeprefix("sqlite:///"))


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _run_alembic_upgrade(database_url: str) -> None:
    from alembic import command as alembic_command
    from alembic.config import Config

    config = Config(str(_project_root() / "alembic.ini"))
    config.set_main_option("script_location", str(_project_root() / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    alembic_command.upgrade(config, "head")


def _run_seed_demo(_arguments: argparse.Namespace) -> int:
    from cuentafaro.db import get_session_factory
    from cuentafaro.seed import load_seed_document, persist_demo_seed, validate_seed_document

    document = load_seed_document()
    validate_seed_document(document)
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            result = persist_demo_seed(session, document)
    except ValueError as error:
        print(str(error))
        return 0
    print("Seed demo persistido en la base local:")
    for collection, count in result["counts"].items():
        print(f"  {collection}: {count}")
    if result["skipped"]:
        print(f"  omitidos (fuera del modelo de Fase 1): {', '.join(result['skipped'])}")
    return 0


def _run_backup(arguments: argparse.Namespace) -> int:
    from cuentafaro.security import _apply_private_mode

    settings = get_settings()
    source = _sqlite_path(settings.database_url)
    target_dir = Path(arguments.path)
    target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _apply_private_mode(target_dir, 0o700)
    if source is None or not source.exists():
        print(f"No se encontró la base de datos local para respaldar: {source}")
        return 1

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"cuentafaro-{stamp}.db"
    shutil.copy2(source, target)
    _apply_private_mode(target, 0o600)
    print(f"Backup creado: {target}")
    return 0


def _run_snapshots(arguments: argparse.Namespace) -> int:
    target_dir = Path(arguments.path)
    if not target_dir.exists():
        print(f"No existe el directorio de backups: {target_dir}")
        return 1
    snapshots = sorted(
        (path for path in target_dir.glob(BACKUP_GLOB) if BACKUP_STAMP.match(path.name)),
        key=lambda path: path.name,
        reverse=True,
    )
    if not snapshots:
        print("No hay snapshots.")
        return 1
    for snapshot in snapshots:
        stamp = snapshot.stat().st_mtime
        created = datetime.fromtimestamp(stamp, UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"{snapshot.name}  {snapshot.stat().st_size:>12} bytes  {created}")
    return 0


def _run_restore(arguments: argparse.Namespace) -> int:
    from cuentafaro.security import _apply_private_mode

    source = Path(arguments.path)
    if not source.exists():
        print(f"No existe el snapshot: {source}")
        return 1
    if not BACKUP_STAMP.match(source.name):
        print(f"El archivo no parece un snapshot válido: {source.name}")
        return 1
    try:
        with sqlite3.connect(source) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                print(f"Snapshot corrupto: PRAGMA integrity_check = {integrity}")
                return 1
    except sqlite3.DatabaseError as error:
        print(f"Snapshot inválido: {error}")
        return 1

    settings = get_settings()
    target = _sqlite_path(settings.database_url)
    if target is None:
        print("El restore solo soporta bases SQLite locales.")
        return 1
    ensure_target_dir = target.parent if target.parent else Path(".")
    ensure_target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _apply_private_mode(ensure_target_dir, 0o700)
    shutil.copy2(source, target)
    _apply_private_mode(target, 0o600)
    print(f"Restaurado: {target}")
    try:
        _run_alembic_upgrade(settings.database_url)
        print("Migraciones aplicadas; la base está lista.")
    except Exception as error:  # pragma: no cover
        print(f"Advertencia: no se pudieron aplicar migraciones: {error}")
    return 0


def _run_version(_arguments: argparse.Namespace) -> int:
    print(f"cuentafaro {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cuentafaro", description="CuentaFaro CLI")
    parser.add_argument("--version", action="version", version=f"cuentafaro {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed-demo", help="Carga datos sintéticos de demostración")
    seed_parser.set_defaults(func=_run_seed_demo)

    backup_parser = subparsers.add_parser("backup", help="Crea una copia de la base local")
    backup_parser.add_argument("--path", type=Path, default=Path("backups"))
    backup_parser.set_defaults(func=_run_backup)

    snapshots_parser = subparsers.add_parser("snapshots", help="Lista los backups disponibles")
    snapshots_parser.add_argument("--path", type=Path, default=Path("backups"))
    snapshots_parser.set_defaults(func=_run_snapshots)

    restore_parser = subparsers.add_parser("restore", help="Restaura la base desde un snapshot")
    restore_parser.add_argument("--path", type=Path, required=True)
    restore_parser.set_defaults(func=_run_restore)

    subparsers.add_parser("version", help="Muestra la versión").set_defaults(func=_run_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if getattr(arguments, "command", None) is None:
        parser.print_help()
        return 0
    return arguments.func(arguments)


if __name__ == "__main__":
    sys.exit(main())
