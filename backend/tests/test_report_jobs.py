from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.events import DomainEvent
from app.models.jobs import BackgroundJob
from app.models.notification import GeneratedReport


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_report_users():
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    permission = Permission(name="reports.generate", description="报表生成")
    admin_role.permissions.append(permission)
    db.session.add_all([admin_role, user_role, permission])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123"
    db.session.add_all([admin, member])
    db.session.commit()
    return admin, member


def test_report_generate_endpoint_keeps_legacy_payload_and_exposes_job_status():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        admin, _member = seed_report_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/reports/generate/sales_daily", headers=headers, json={"params": {}})

        assert response.status_code == 200
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert payload["report"]["report_type"] == "sales_daily"
        assert payload["data"] == payload["job"]["result"]["data"]
        assert GeneratedReport.query.count() == 1
        event = DomainEvent.query.filter_by(event_type="ReportRequested").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "BackgroundJob"
        assert event.aggregate_id == payload["job_id"]
        assert event.created_by == str(admin.id)
        assert event.payload["job_id"] == payload["job_id"]
        assert event.payload["report_type"] == "sales_daily"
        assert event.payload["params"] == {}
        assert event.payload["requested_by"] == admin.id
        assert event.payload["queue"] == "reports"
        assert event.payload["task_name"] == "nexus.reports.generate"

        job_response = client.get(f"/api/v1/reports/jobs/{payload['job_id']}", headers=headers)

        assert job_response.status_code == 200
        assert job_response.json["data"]["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert job_response.json["data"]["report"]["id"] == payload["report"]["id"]

        db.session.remove()
        db.drop_all()


def test_report_generate_rejects_unknown_type_without_creating_job():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_report_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/reports/generate/not_real", headers=headers, json={"params": {}})

        assert response.status_code == 400
        assert BackgroundJob.query.count() == 0
        assert DomainEvent.query.filter_by(event_type="ReportRequested").count() == 0
        assert GeneratedReport.query.count() == 0

        db.session.remove()
        db.drop_all()


def test_report_generate_returns_accepted_job_when_worker_mode_is_enabled(monkeypatch):
    app = create_app("testing")
    app.config["CELERY_TASK_ALWAYS_EAGER"] = False

    class FakeAsyncResult:
        id = "queued-report-task"

    from app.platform.jobs.tasks.reports import generate_report_task

    def fake_apply_async(*_args, **_kwargs):
        return FakeAsyncResult()

    monkeypatch.setattr(generate_report_task, "apply_async", fake_apply_async)

    with app.app_context():
        db.create_all()
        seed_report_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/reports/generate/sales_daily", headers=headers, json={"params": {}})

        assert response.status_code == 202
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["status"] == BackgroundJob.STATUS_PENDING
        job = BackgroundJob.query.filter_by(job_id=payload["job_id"]).one()
        assert job.celery_task_id == "queued-report-task"
        assert job.queue == "reports"
        event = DomainEvent.query.filter_by(event_type="ReportRequested").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "BackgroundJob"
        assert event.aggregate_id == payload["job_id"]
        assert event.payload["job_id"] == payload["job_id"]
        assert event.payload["report_type"] == "sales_daily"
        assert event.payload["params"] == {}
        assert GeneratedReport.query.count() == 0

        db.session.remove()
        db.drop_all()


def test_report_job_status_is_user_scoped():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_report_users()
        client = app.test_client()
        admin_headers = login(client)

        response = client.post("/api/v1/reports/generate/sales_daily", headers=admin_headers, json={"params": {}})
        job_id = response.json["data"]["job_id"]

        member_headers = login(client, email="member@nexus.com", password="member123")
        denied = client.get(f"/api/v1/reports/jobs/{job_id}", headers=member_headers)

        assert denied.status_code == 403

        db.session.remove()
        db.drop_all()


def test_report_job_stream_emits_done_event_for_completed_job():
    app = create_app("testing")
    app.config["REPORT_JOB_STREAM_INTERVAL_SECONDS"] = 0

    with app.app_context():
        db.create_all()
        seed_report_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/reports/generate/sales_daily", headers=headers, json={"params": {}})
        job_id = response.json["data"]["job_id"]

        stream = client.get(f"/api/v1/reports/jobs/{job_id}/stream", headers=headers)

        assert stream.status_code == 200
        assert stream.mimetype == "text/event-stream"
        body = stream.get_data(as_text=True)
        assert "event: done" in body
        assert f'"job_id":"{job_id}"' in body
        assert '"status":"success"' in body

        db.session.remove()
        db.drop_all()


def test_report_job_stream_is_user_scoped():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_report_users()
        client = app.test_client()
        admin_headers = login(client)

        response = client.post("/api/v1/reports/generate/sales_daily", headers=admin_headers, json={"params": {}})
        job_id = response.json["data"]["job_id"]

        member_headers = login(client, email="member@nexus.com", password="member123")
        denied = client.get(f"/api/v1/reports/jobs/{job_id}/stream", headers=member_headers)

        assert denied.status_code == 403

        db.session.remove()
        db.drop_all()
