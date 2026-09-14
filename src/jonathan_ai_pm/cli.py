import argparse
from datetime import UTC, datetime
from pathlib import Path

from jonathan_ai_pm.db import SessionLocal, engine
from jonathan_ai_pm.models import Base
from jonathan_ai_pm.portability import export_snapshot
from jonathan_ai_pm.schemas import SnapshotDocument
from jonathan_ai_pm.security import write_private_text
from jonathan_ai_pm.seed import load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(prog="jonathan-ai-pm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create the local database tables")
    seed_parser = subparsers.add_parser("seed-demo", help="Load fictional demo data")
    seed_parser.add_argument("--path", type=Path, default=Path("data/seed/demo-workspace.json"))
    backup_parser = subparsers.add_parser("backup", help="Write a private JSON snapshot")
    backup_parser.add_argument("--path", type=Path)
    backup_parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.command == "init-db":
        Base.metadata.create_all(engine)
    elif args.command == "seed-demo":
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            load_snapshot(session, args.path)
    elif args.command == "backup":
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = args.path or Path("backups") / f"jonathan-ai-pm-{timestamp}.snapshot.json"
        with SessionLocal() as session:
            snapshot = SnapshotDocument.model_validate(export_snapshot(session))
        write_private_text(path, snapshot.model_dump_json(indent=2), overwrite=args.force)
        print(path)


if __name__ == "__main__":
    main()
