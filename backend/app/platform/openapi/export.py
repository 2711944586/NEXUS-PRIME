from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

from .schema import build_openapi_schema


def write_openapi_schema(app: Flask, output: str | Path) -> Path:
    """Write the runtime OpenAPI contract for the current Flask app."""
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = build_openapi_schema(app)
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
