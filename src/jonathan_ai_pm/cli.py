import argparse
from pathlib import Path

from jonathan_ai_pm.db import SessionLocal, engine
from jonathan_ai_pm.models import Base
from jonathan_ai_pm.seed import load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(prog="jonathan-ai-pm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create the local database tables")
    seed_parser = subparsers.add_parser("seed-demo", help="Load fictional demo data")
    seed_parser.add_argument("--path", type=Path, default=Path("data/seed/demo-workspace.json"))
    args = parser.parse_args()

    if args.command == "init-db":
        Base.metadata.create_all(engine)
    elif args.command == "seed-demo":
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            load_snapshot(session, args.path)


if __name__ == "__main__":
    main()
