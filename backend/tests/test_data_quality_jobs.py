from app import create_app
from app.extensions import db
from app.models.auth import Role, User
from app.models.jobs import BackgroundJob


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_users():
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    db.session.add_all([admin_role, user_role])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123"
    db.session.add_all([admin, member])
    db.session.commit()
    return admin, member


def test_data_quality_scan_endpoint_runs_eager_and_exposes_job_status():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/operations/data-quality/scan", headers=headers, json={})

        assert response.status_code == 200
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["job"]["job_type"] == "data_quality.scan"
        assert payload["job"]["queue"] == "data-quality"
        assert payload["job"]["task_name"] == "nexus.data_quality.scan"
        assert payload["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert payload["result"]["source"] == "database_quality_contract"
        assert payload["result"]["summary"]["total_tests"] >= 8

        status = client.get(f"/api/v1/operations/data-quality/jobs/{payload['job_id']}", headers=headers)

        assert status.status_code == 200
        assert status.json["data"]["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert status.json["data"]["result"]["source"] == "database_quality_contract"

        db.session.remove()
        db.drop_all()


def test_data_quality_scan_endpoint_returns_accepted_when_worker_mode_is_enabled(monkeypatch):
    app = create_app("testing")
    app.config["CELERY_TASK_ALWAYS_EAGER"] = False

    class FakeAsyncResult:
        id = "queued-data-quality-task"

    from app.platform.jobs.tasks.data_quality import data_quality_scan_task

    def fake_apply_async(*_args, **_kwargs):
        return FakeAsyncResult()

    monkeypatch.setattr(data_quality_scan_task, "apply_async", fake_apply_async)

    with app.app_context():
        db.create_all()
        seed_users()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/operations/data-quality/scan", headers=headers, json={})

        assert response.status_code == 202
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["job"]["status"] == BackgroundJob.STATUS_PENDING
        job = BackgroundJob.query.filter_by(job_id=payload["job_id"]).one()
        assert job.celery_task_id == "queued-data-quality-task"
        assert job.queue == "data-quality"
        assert job.task_name == "nexus.data_quality.scan"

        db.session.remove()
        db.drop_all()


def test_data_quality_job_status_is_user_scoped():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_users()
        client = app.test_client()
        admin_headers = login(client)

        response = client.post("/api/v1/operations/data-quality/scan", headers=admin_headers, json={})
        job_id = response.json["data"]["job_id"]

        member_headers = login(client, email="member@nexus.com", password="member123")
        denied = client.get(f"/api/v1/operations/data-quality/jobs/{job_id}", headers=member_headers)

        assert denied.status_code == 403

        db.session.remove()
        db.drop_all()
