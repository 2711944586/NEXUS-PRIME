from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_defines_required_dev_services():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    for service in ("postgres", "redis", "backend", "worker", "beat", "frontend"):
        assert f"  {service}:" in compose
    assert "dockerfile: Dockerfile.backend" in compose
    assert "dockerfile: Dockerfile.frontend" in compose
    assert '"celery", "-A", "app.platform.jobs.celery_app"' in compose
    assert '"events,reports,ai,celery"' in compose
    assert '"beat", "-l", "info", "--schedule", "/app/backend/.runtime/celerybeat-schedule"' in compose
    assert "postgresql+psycopg2://nexus:nexus@postgres:5432/nexus_prime" in compose
    assert "NEXUS_SENTRY_DSN" in compose
    assert "NEXUS_SENTRY_TRACES_SAMPLE_RATE" in compose
    assert "condition: service_healthy" in compose
    assert "backend-runtime:" in compose


def test_root_dev_entrypoints_cover_docker_and_local_modes():
    start_bat = (ROOT / "start-dev.bat").read_text(encoding="utf-8")
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "scripts\\dev.ps1" in start_bat
    assert "[switch]$Help" in dev_script
    assert "Show-DevHelp" in dev_script
    assert "[switch]$Docker" in dev_script
    assert "docker compose up" in dev_script
    assert "postgres, redis, backend, worker, beat, frontend" in dev_script
    assert "'config', '--quiet'" in dev_script
    assert "--project-directory" in dev_script
    assert "Assert-DockerComposeReady" in dev_script
    assert "Assert-DockerComposeConfig" in dev_script
    assert "-BackendPort" in dev_script
    assert "-FrontendPort" in dev_script
    assert "sentryDsn" in dev_script
    assert "sentryTracesSampleRate" in dev_script
    assert "dev:" in makefile
    assert "docker compose up -d" in makefile
    assert "worker:" in makefile
    assert "events,reports,ai,celery" in makefile
    assert "beat:" in makefile
    assert "celery -A app.platform.jobs.celery_app beat -l info" in makefile


def test_flask_events_worker_default_consumes_all_platform_queues():
    commands = (ROOT / "backend" / "app" / "commands.py").read_text(encoding="utf-8")

    assert "default='events,reports,ai,celery'" in commands


def test_env_examples_document_compose_runtime_boundaries():
    root_env = (ROOT / ".env.example").read_text(encoding="utf-8")
    backend_env = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")

    assert "DATABASE_URL=postgresql+psycopg2://nexus:nexus@postgres:5432/nexus_prime" in root_env
    assert "CELERY_BROKER_URL=redis://redis:6379/0" in root_env
    assert "NEXUS_API_BASE_URL=http://127.0.0.1:5000/api/v1" in root_env
    assert "CELERY_BROKER_URL=redis://localhost:6379/0" in backend_env
