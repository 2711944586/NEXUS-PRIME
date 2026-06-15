"""Copy the local SQLite database into a migrated PostgreSQL database."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import MetaData, create_engine, delete, insert, select, text


DEFAULT_SKIP_TABLES = set()


def normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def chunks(rows: list[dict], size: int) -> Iterable[list[dict]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def reset_postgres_sequences(connection, tables) -> None:
    if connection.dialect.name != "postgresql":
        return

    for table in tables:
        pk_columns = []
        for column in table.primary_key.columns:
            try:
                if column.type.python_type is int:
                    pk_columns.append(column)
            except NotImplementedError:
                continue
        for column in pk_columns:
            table_name = table.name if not table.schema else f"{table.schema}.{table.name}"
            q_table = quote_identifier(table.name) if not table.schema else f"{quote_identifier(table.schema)}.{quote_identifier(table.name)}"
            q_column = quote_identifier(column.name)
            connection.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(:table_name, :column_name),
                        COALESCE((SELECT MAX({q_column}) FROM {q_table}), 1),
                        (SELECT MAX({q_column}) FROM {q_table}) IS NOT NULL
                    )
                    WHERE pg_get_serial_sequence(:table_name, :column_name) IS NOT NULL
                    """
                ),
                {"table_name": table_name, "column_name": column.name},
            )


def parse_table_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    default_source = root / "instance" / "nexus_prime.db"

    parser = argparse.ArgumentParser(description="Copy local SQLite data into PostgreSQL.")
    parser.add_argument("--source", default=str(default_source), help="SQLite database file path.")
    parser.add_argument("--target", default=os.getenv("DATABASE_URL", ""), help="Target PostgreSQL DATABASE_URL.")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows inserted per batch.")
    parser.add_argument("--only-tables", default="", help="Comma-separated table allow-list.")
    parser.add_argument("--skip-tables", default="", help="Comma-separated table skip-list.")
    parser.add_argument("--reset-target", action="store_true", help="Truncate target tables before copying.")
    parser.add_argument("--require-supabase", action="store_true", help="Fail unless the target URL looks like Supabase.")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise SystemExit(f"SQLite source does not exist: {source_path}")
    if not args.target:
        raise SystemExit("Target DATABASE_URL is required.")

    target_url = normalize_url(args.target)
    if args.require_supabase and "supabase.com" not in target_url and "pooler.supabase.com" not in target_url:
        raise SystemExit("Target DATABASE_URL does not look like a Supabase PostgreSQL connection string.")
    if not target_url.startswith("postgresql://"):
        raise SystemExit("Target DATABASE_URL must use PostgreSQL.")

    source_engine = create_engine(f"sqlite:///{source_path.as_posix()}")
    target_engine = create_engine(target_url, future=True, pool_pre_ping=True)

    source_meta = MetaData()
    target_meta = MetaData()
    source_meta.reflect(bind=source_engine)
    target_meta.reflect(bind=target_engine)

    only_tables = parse_table_filter(args.only_tables)
    skip_tables = DEFAULT_SKIP_TABLES | (parse_table_filter(args.skip_tables) or set())
    ordered_tables = [
        table
        for table in source_meta.sorted_tables
        if table.name in target_meta.tables
        and table.name not in skip_tables
        and (only_tables is None or table.name in only_tables)
    ]
    missing_tables = sorted(
        table.name
        for table in source_meta.sorted_tables
        if table.name not in target_meta.tables and (only_tables is None or table.name in only_tables)
    )

    if not ordered_tables:
        raise SystemExit("No matching tables found between SQLite and PostgreSQL.")

    copied: list[tuple[str, int]] = []
    with source_engine.connect() as source, target_engine.begin() as target:
        if args.reset_target:
            if target.dialect.name == "postgresql":
                table_names = ", ".join(
                    quote_identifier(table.name) if not table.schema else f"{quote_identifier(table.schema)}.{quote_identifier(table.name)}"
                    for table in reversed(ordered_tables)
                )
                target.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
            else:
                for table in reversed(ordered_tables):
                    target.execute(delete(target_meta.tables[table.name]))

        for source_table in ordered_tables:
            target_table = target_meta.tables[source_table.name]
            rows = [dict(row._mapping) for row in source.execute(select(source_table))]
            for batch in chunks(rows, max(args.batch_size, 1)):
                if batch:
                    target.execute(insert(target_table), batch)
            copied.append((source_table.name, len(rows)))

        reset_postgres_sequences(target, [target_meta.tables[table.name] for table in ordered_tables])

    print("NEXUS SQLite -> PostgreSQL sync completed.")
    for table_name, count in copied:
        print(f" - {table_name}: {count}")
    if missing_tables:
        print("Skipped tables not found on target:")
        for table_name in missing_tables:
            print(f" - {table_name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
