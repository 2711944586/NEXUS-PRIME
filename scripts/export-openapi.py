from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the NEXUS PRIME OpenAPI schema.")
    parser.add_argument("--output", type=Path, default=ROOT / "backend" / "openapi.json")
    parser.add_argument("--config", default=os.environ.get("FLASK_CONFIG", "testing"))
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND_DIR.resolve()))
    os.environ.setdefault("FLASK_CONFIG", args.config)

    from app import create_app  # type: ignore
    from app.platform.openapi import write_openapi_schema  # type: ignore

    app = create_app(args.config)
    output = write_openapi_schema(app, args.output)
    print(f"OpenAPI schema exported to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
