from __future__ import annotations

import argparse
import filecmp
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SCHEMA = ROOT / "backend" / "openapi.json"
FRONTEND_SCHEMA = ROOT / "frontend" / "src" / "app" / "core" / "api" / "generated" / "schema.d.ts"
FRONTEND_DIR = ROOT / "frontend"


def default_backend_python() -> str:
    candidates = [
        ROOT / "venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / "venv" / "bin" / "python",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def compare_file(actual: Path, expected: Path, label: str) -> str | None:
    if not actual.exists():
        return f"{label} is missing: {actual}"
    if not filecmp.cmp(actual, expected, shallow=False):
        return f"{label} is out of sync. Regenerate it from the current backend contract."
    return None


def write_report(path: Path | None, report: dict[str, object]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that backend/openapi.json and the generated frontend OpenAPI types are synchronized."
    )
    parser.add_argument("--config", default=os.environ.get("FLASK_CONFIG", "testing"))
    parser.add_argument("--python", default=default_backend_python())
    parser.add_argument("--npx", default="npx.cmd" if os.name == "nt" else "npx")
    parser.add_argument("--json-output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    report: dict[str, object] = {
        "ok": False,
        "config": args.config,
        "artifacts": {
            "backend": str(BACKEND_SCHEMA.relative_to(ROOT)),
            "frontend": str(FRONTEND_SCHEMA.relative_to(ROOT)),
        },
        "checks": [],
        "failures": [],
    }

    with tempfile.TemporaryDirectory(prefix="nexus-openapi-sync-") as tmp:
        temp_dir = Path(tmp)
        temp_openapi = temp_dir / "openapi.json"
        temp_schema = temp_dir / "schema.d.ts"
        env = os.environ.copy()
        env.setdefault("FLASK_CONFIG", args.config)

        export_result = run(
            [args.python, str(ROOT / "scripts" / "export-openapi.py"), "--output", str(temp_openapi), "--config", args.config],
            ROOT,
            env,
        )
        report["checks"].append({"name": "export-openapi", "returncode": export_result.returncode})
        if export_result.returncode != 0:
            print(export_result.stdout, end="")
            report["failures"].append({
                "stage": "export-openapi",
                "message": "OpenAPI export failed.",
                "output": export_result.stdout,
            })
            write_report(args.json_output, report)
            return export_result.returncode

        typegen_result = run(
            [args.npx, "openapi-typescript", str(temp_openapi), "-o", str(temp_schema)],
            FRONTEND_DIR,
            env,
        )
        report["checks"].append({"name": "openapi-typescript", "returncode": typegen_result.returncode})
        if typegen_result.returncode != 0:
            print(typegen_result.stdout, end="")
            report["failures"].append({
                "stage": "openapi-typescript",
                "message": "Frontend OpenAPI type generation failed.",
                "output": typegen_result.stdout,
            })
            write_report(args.json_output, report)
            return typegen_result.returncode

        comparisons = [
            ("backend/openapi.json", compare_file(BACKEND_SCHEMA, temp_openapi, "backend/openapi.json")),
            (
                "frontend/src/app/core/api/generated/schema.d.ts",
                compare_file(FRONTEND_SCHEMA, temp_schema, "frontend generated OpenAPI schema.d.ts"),
            ),
        ]
        report["checks"].extend(
            {"name": label, "synchronized": failure is None}
            for label, failure in comparisons
        )
        failures = [failure for _, failure in comparisons if failure]
        if failures:
            for failure in failures:
                print(failure)
                report["failures"].append({"stage": "compare", "message": failure})
            print()
            print("Run these commands to refresh the checked-in contract artifacts:")
            print(f"{args.python} scripts\\export-openapi.py --output backend\\openapi.json")
            print("cd frontend")
            print("npm run api:generate")
            write_report(args.json_output, report)
            return 1

        report["ok"] = True
        print("OpenAPI contract artifacts are synchronized.")
        write_report(args.json_output, report)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
