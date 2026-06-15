"""Inspect deployment database state before destructive or seed operations."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import MetaData, create_engine, func, select


DEFAULT_TABLES = (
    "auth_users",
    "biz_products",
    "stock_quantities",
    "purchase_orders",
    "trade_orders",
    "finance_receivables",
    "cms_articles",
    "sys_audit_logs",
)


def normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def parse_tables(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a target SQL database already contains NEXUS data.")
    parser.add_argument("--url", required=True, help="Target DATABASE_URL.")
    parser.add_argument("--tables", default=",".join(DEFAULT_TABLES), help="Comma-separated tables used for row-count checks.")
    parser.add_argument("--require-empty", action="store_true", help="Exit non-zero when any checked table contains rows.")
    args = parser.parse_args()

    url = normalize_url(args.url)
    if not url.startswith("postgresql://"):
        raise SystemExit("Only PostgreSQL deployment databases are supported by this check.")

    engine = create_engine(url, future=True, pool_pre_ping=True)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    requested_tables = parse_tables(args.tables)
    counts: dict[str, int] = {}
    missing: list[str] = []

    with engine.connect() as connection:
        for table_name in requested_tables:
            table = metadata.tables.get(table_name)
            if table is None:
                missing.append(table_name)
                continue
            counts[table_name] = int(connection.execute(select(func.count()).select_from(table)).scalar() or 0)

    total = sum(counts.values())
    print(f"NEXUS database checked tables: {len(counts)} present, {len(missing)} missing, {total} rows")
    for table_name, count in sorted(counts.items()):
        print(f" - {table_name}: {count}")
    if missing:
        print("Missing checked tables:")
        for table_name in missing:
            print(f" - {table_name}")

    if args.require_empty and total > 0:
        print("Refusing to seed: deployment database is not empty.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
