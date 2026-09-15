import argparse
from datetime import UTC, datetime
from pathlib import Path

from jonathan_ai_pm.config import get_settings
from jonathan_ai_pm.db import SessionLocal, engine
from jonathan_ai_pm.integrations import IntegrationMaintenanceService
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
    retention_parser = subparsers.add_parser(
        "prune-integration-data",
        help="Delete expired integration history using configured retention",
    )
    retention_parser.add_argument("--confirm", action="store_true")
    disconnect_parser = subparsers.add_parser(
        "disconnect-integration",
        help="Remove provider links while preserving operational records",
    )
    disconnect_parser.add_argument("source_system")
    disconnect_parser.add_argument("--scope")
    disconnect_parser.add_argument("--confirm", action="store_true")
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
    elif args.command == "prune-integration-data":
        if not args.confirm:
            parser.error("prune-integration-data requires --confirm")
        settings = get_settings()
        with SessionLocal() as session:
            result = IntegrationMaintenanceService(session).enforce_retention(
                sync_history_days=settings.integration_sync_history_retention_days,
                resolved_review_days=(
                    settings.integration_resolved_review_retention_days
                ),
            )
        print(
            f"sync_runs_deleted={result.sync_runs_deleted} "
            f"resolved_reviews_deleted={result.resolved_reviews_deleted}"
        )
    elif args.command == "disconnect-integration":
        if not args.confirm:
            parser.error("disconnect-integration requires --confirm")
        with SessionLocal() as session:
            result = IntegrationMaintenanceService(session).disconnect(
                args.source_system,
                external_scope=args.scope,
            )
        print(
            f"identities_deleted={result.identities_deleted} "
            f"reviews_deleted={result.reviews_deleted} "
            f"mappings_deleted={result.mappings_deleted} "
            f"sync_runs_anonymized={result.sync_runs_anonymized}"
        )


if __name__ == "__main__":
    main()
