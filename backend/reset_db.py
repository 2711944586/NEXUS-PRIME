from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

from app import create_app, db
from app.models import auth, biz, content, finance, notification, purchase, stock, stocktake, sys as sys_model, trade  # noqa: F401


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dangerous database reset helper with remote safeguards.")
    parser.add_argument("--i-understand-destroy-data", action="store_true", help="Required explicit acknowledgement.")
    parser.add_argument("--allow-remote", action="store_true", help="Permit resetting a non-local PostgreSQL database.")
    parser.add_argument("--expected-host", help="Require DATABASE_URL host to match this value.")
    return parser.parse_args()


def database_host(url: str) -> str:
    return urlparse(url).hostname or ""


def is_local_database(url: str) -> bool:
    host = database_host(url).lower()
    return url.startswith("sqlite:///") or host in {"", "localhost", "127.0.0.1", "::1"}


def main() -> int:
    args = parse_args()
    load_dotenv()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL is required.", file=sys.stderr)
        return 1
    if not args.i_understand_destroy_data:
        print("ERROR: pass --i-understand-destroy-data to run this destructive reset.", file=sys.stderr)
        return 2

    host = database_host(db_url)
    if args.expected_host and host != args.expected_host:
        print(f"ERROR: DATABASE_URL host {host!r} does not match --expected-host {args.expected_host!r}.", file=sys.stderr)
        return 3
    if not is_local_database(db_url) and not args.allow_remote:
        print("ERROR: refusing to reset a remote database without --allow-remote and --expected-host.", file=sys.stderr)
        return 4
    if args.allow_remote and not args.expected_host:
        print("ERROR: --allow-remote also requires --expected-host.", file=sys.stderr)
        return 5

    config_name = "development" if is_local_database(db_url) else "production"
    if db_url.startswith("sqlite:///"):
        os.environ.setdefault("ALLOW_PRODUCTION_SQLITE", "true")

    app = create_app(config_name)
    with app.app_context():
        print(f"Reset target: {host or 'sqlite-local'}")
        confirm = input("Type RESET NEXUS DATA to continue: ")
        if confirm != "RESET NEXUS DATA":
            print("Cancelled.")
            return 0

        if db.engine.dialect.name == "postgresql":
            db.session.execute(db.text("DROP SCHEMA public CASCADE;"))
            db.session.execute(db.text("CREATE SCHEMA public;"))
            db.session.execute(db.text("GRANT ALL ON SCHEMA public TO postgres;"))
            db.session.execute(db.text("GRANT ALL ON SCHEMA public TO public;"))
            db.session.commit()
        else:
            db.session.remove()
            db.drop_all()
        db.create_all()
        print("Database reset completed. Run Alembic migrations and seed commands before using the environment.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
