import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    raw = database_url.replace("sqlite:///", "", 1)
    if raw == ":memory:":
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parents[1] / candidate
    return candidate


def _quick_check(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("pragma journal_mode=wal")
        conn.execute("begin immediate")
        conn.execute("rollback")
        result = conn.execute("pragma quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {result}")
        users = conn.execute("select count(*) from auth_users").fetchone()[0]
        products = conn.execute("select count(*) from biz_products").fetchone()[0]
        orders = conn.execute("select count(*) from trade_orders").fetchone()[0]
        min_users = int(os.environ.get("NEXUS_DB_BOOTSTRAP_MIN_USERS", "0") or "0")
        min_orders = int(os.environ.get("NEXUS_DB_BOOTSTRAP_MIN_ORDERS", "0") or "0")
        if users < min_users or orders < min_orders:
            raise RuntimeError(
                "SQLite bootstrap data is smaller than expected: "
                f"users={users} min_users={min_users}, sales_orders={orders} min_orders={min_orders}"
            )
        size_mb = path.stat().st_size / 1024 / 1024
        print(
            "SQLite bootstrap ready: "
            f"path={path} size_mb={size_mb:.1f} users={users}, products={products}, sales_orders={orders}"
        )
    finally:
        conn.close()


def main() -> int:
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    source_url = os.environ.get("NEXUS_DB_BOOTSTRAP_URL", "").strip()
    if not source_url:
        return 0

    database_url = os.environ.get("DATABASE_URL", "")
    target = _sqlite_path_from_url(database_url)
    if target is None:
        print("NEXUS_DB_BOOTSTRAP_URL is set but DATABASE_URL is not a file SQLite URL", file=sys.stderr)
        return 2

    force = os.environ.get("NEXUS_DB_BOOTSTRAP_FORCE", "").lower() in {"1", "true", "yes", "on"}
    if target.exists() and target.stat().st_size > 1024 * 1024 and not force:
        _quick_check(target)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=target.name, suffix=".download", dir=target.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    extracted_path = tmp_path.with_suffix(".sqlite")
    try:
        print(f"Downloading SQLite bootstrap data from {source_url}")
        with urllib.request.urlopen(source_url, timeout=180) as response, tmp_path.open("wb") as out:
            shutil.copyfileobj(response, out)

        if source_url.endswith(".gz"):
            with gzip.open(tmp_path, "rb") as gz, extracted_path.open("wb") as out:
                shutil.copyfileobj(gz, out)
            os.replace(extracted_path, target)
        else:
            os.replace(tmp_path, target)

        _quick_check(target)
        return 0
    finally:
        for path in (tmp_path, extracted_path):
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
