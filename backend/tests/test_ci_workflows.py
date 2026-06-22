from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_workflow(name):
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_backend_workflow_runs_migration_tests_and_contract_check():
    workflow = read_workflow("backend.yml")

    assert "postgres:16-alpine" in workflow
    assert "redis:7-alpine" in workflow
    assert "python-version: \"3.13\"" in workflow
    assert "FLASK_CONFIG: development" in workflow
    assert "python -m flask db upgrade" in workflow
    assert "python -m pytest -q" in workflow
    assert "scripts/check-openapi-sync.py" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_frontend_workflow_runs_unit_build_and_openapi_check():
    workflow = read_workflow("frontend.yml")

    assert "node-version: \"24\"" in workflow
    assert "npm ci" in workflow
    assert "npm test -- --watch=false" in workflow
    assert "npm run build" in workflow
    assert "npm run api:check" in workflow
    assert "npm run audit:charts" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_e2e_workflow_runs_playwright_smoke_and_uploads_report():
    workflow = read_workflow("e2e.yml")

    assert "npx playwright install --with-deps chromium" in workflow
    assert "npm run e2e" in workflow
    assert "output/playwright/e2e-report" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_security_workflow_runs_dependency_and_secret_scans():
    workflow = read_workflow("security.yml")

    assert "python-version: \"3.13\"" in workflow
    assert "node-version: \"24\"" in workflow
    assert "pip-audit" in workflow
    assert "python -m pip_audit -r backend/requirements.txt" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "actions/dependency-review-action@v4" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "trufflesecurity/trufflehog" in workflow
    assert "--only-verified" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "security-reports" in workflow


def test_playwright_smoke_uses_mocked_api_and_runtime_config():
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")
    spec = (ROOT / "frontend" / "e2e" / "smoke.spec.ts").read_text(encoding="utf-8")

    assert "NEXUS_LOCAL_API_BASE_URL" in config
    assert "'/api/v1'" in config
    assert "**/api/v1/auth/csrf" in spec
    assert "**/api/v1/auth/register-policy" in spec
    assert "expect(apiBase).toMatch(/\\/api\\/v1$/)" in spec
