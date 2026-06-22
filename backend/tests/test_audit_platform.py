import json

from app import create_app
from app.extensions import db
from app.models.sys import AuditLog
from app.platform.audit import AuditLog as PlatformAuditLog
from app.platform.audit import AuditService as PlatformAuditService


def test_legacy_audit_service_imports_platform_service():
    from app.services.audit_service import AuditService as LegacyAuditService

    assert LegacyAuditService is PlatformAuditService
    assert PlatformAuditLog is AuditLog


def test_audit_service_records_request_context_metadata():
    app = create_app("testing")

    @app.post("/api/v1/audit-platform-test/probe")
    def audit_probe():
        PlatformAuditService.record("audit-test", "probe", None, {"value": "ok"}, commit=True)
        return {"ok": True}

    with app.app_context():
        db.create_all()
        client = app.test_client()

        response = client.post(
            "/api/v1/audit-platform-test/probe",
            headers={
                "X-Request-ID": "audit-req-1",
                "X-Trace-ID": "audit-trace-1",
                "User-Agent": "audit-test-agent",
            },
        )

        assert response.status_code == 200
        audit = AuditLog.query.filter_by(module="audit-test", action="probe").one()
        details = json.loads(audit.details)
        assert details["value"] == "ok"
        assert details["_context"] == {
            "request_id": "audit-req-1",
            "trace_id": "audit-trace-1",
            "method": "POST",
            "path": "/api/v1/audit-platform-test/probe",
            "endpoint": "audit_probe",
            "user_agent": "audit-test-agent",
        }

        db.session.remove()
        db.drop_all()


def test_audit_service_without_request_context_keeps_plain_payload():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        PlatformAuditService.record("audit-test", "offline", None, {"value": "offline"}, commit=True)

        audit = AuditLog.query.filter_by(module="audit-test", action="offline").one()
        details = json.loads(audit.details)
        assert details == {"value": "offline"}
        assert audit.ip_address is None

        db.session.remove()
        db.drop_all()
