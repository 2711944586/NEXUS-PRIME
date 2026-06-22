from app import create_app
from app.extensions import db
from app.models.events import DomainEvent
from app.platform.events import Outbox
from app.platform.observability import reset_metrics, tracing_status


def make_app():
    app = create_app("testing")
    reset_metrics()
    return app


def test_request_context_headers_are_generated_for_public_api():
    app = make_app()

    with app.app_context():
        db.create_all()
        client = app.test_client()

        response = client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]
        assert response.headers["X-Trace-ID"]
        assert response.headers["X-Request-ID"] == response.headers["X-Trace-ID"]
        assert "X-Response-Time-Ms" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        db.session.remove()
        db.drop_all()


def test_request_context_headers_are_propagated_and_sanitized():
    app = make_app()

    with app.app_context():
        db.create_all()
        client = app.test_client()

        response = client.get(
            "/api/v1/health/live",
            headers={
                "X-Request-ID": "req 123!*bad",
                "X-Trace-ID": "trace-456/ok",
            },
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "req-123-bad"
        assert response.headers["X-Trace-ID"] == "trace-456/ok"

        db.session.remove()
        db.drop_all()


def test_metrics_endpoint_reports_http_and_domain_event_counts():
    app = make_app()

    with app.app_context():
        db.create_all()
        db.session.add_all([
            DomainEvent(
                event_type="SalesOrderConfirmed",
                aggregate_type="Order",
                aggregate_id="1",
                payload={"order_id": 1},
                status=DomainEvent.STATUS_PENDING,
            ),
            DomainEvent(
                event_type="ReportRequested",
                aggregate_type="ReportJob",
                aggregate_id="job-1",
                payload={"report_type": "sales_daily"},
                status=DomainEvent.STATUS_FAILED,
                error_message="boom",
            ),
        ])
        db.session.commit()

        client = app.test_client()
        assert client.get("/api/v1/health/live").status_code == 200
        response = client.get("/api/v1/observability/metrics")

        assert response.status_code == 200
        metrics = response.json["data"]["metrics"]
        assert metrics["domain_event_pending_total"] == 1
        assert metrics["domain_event_failed_total"] == 1
        assert metrics["celery_task_duration_seconds"] == []
        assert metrics["celery_task_failed_total"] == []
        assert metrics["domain_event_worker_total"] == {}
        assert metrics["tracing"]["enabled"] is False
        assert metrics["tracing"]["configured"] is False
        assert {
            (item["method"], item["path"], item["status_code"])
            for item in metrics["http_request_total"]
        } >= {
            ("GET", "/api/v1/health/live", 200),
        }

        db.session.remove()
        db.drop_all()


def test_tracing_is_disabled_by_default():
    app = make_app()

    assert tracing_status()["enabled"] is False
    assert tracing_status()["configured"] is False
    assert tracing_status()["reason"] == "disabled"
    assert app.config["OTEL_SERVICE_NAME"] == "nexus-prime-backend"


def test_tracing_enabled_without_dependencies_degrades_safely(monkeypatch):
    import builtins
    from app.platform.observability.tracing import configure_tracing

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("opentelemetry"):
            raise ImportError("otel missing in test")
        return real_import(name, globals, locals, fromlist, level)

    app = make_app()
    app.config["OTEL_TRACES_ENABLED"] = True
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    status = configure_tracing(app, db=db)

    assert status["enabled"] is True
    assert status["configured"] is False
    assert status["reason"].startswith("missing_dependency:")


def test_tracing_enabled_installs_request_span_when_dependencies_exist():
    from app.platform.observability.tracing import configure_tracing

    app = make_app()
    app.config["OTEL_TRACES_ENABLED"] = True

    status = configure_tracing(app, db=db)

    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["reason"] == "configured"

    with app.app_context():
        db.create_all()
        response = app.test_client().get("/api/v1/health/live")

        assert response.status_code == 200

        db.session.remove()
        db.drop_all()


def test_outbox_inherits_trace_id_from_request_context():
    app = make_app()

    @app.get("/api/v1/observability-test/outbox")
    def write_event_for_trace_test():
        Outbox().add("TraceProbe", "Probe", "1", {"ok": True})
        db.session.commit()
        return {"status": "ok"}

    with app.app_context():
        db.create_all()
        client = app.test_client()

        response = client.get(
            "/api/v1/observability-test/outbox",
            headers={"X-Request-ID": "req-outbox", "X-Trace-ID": "trace-outbox"},
        )

        assert response.status_code == 200
        event = DomainEvent.query.filter_by(event_type="TraceProbe").one()
        assert event.trace_id == "trace-outbox"

        db.session.remove()
        db.drop_all()
