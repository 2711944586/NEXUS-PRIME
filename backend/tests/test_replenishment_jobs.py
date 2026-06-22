from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.jobs import BackgroundJob
from app.models.notification import ReplenishmentSuggestion
from app.models.stock import Stock, Warehouse


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_replenishment_fixture():
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    permission = Permission(name="purchase.write", description="采购创建")
    admin_role.permissions.append(permission)
    db.session.add_all([admin_role, user_role, permission])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123"
    category = Category(name="补货测试分类")
    supplier = Partner(name="补货测试供应商", type=Partner.TYPE_SUPPLIER)
    warehouse = Warehouse(name="补货测试仓", location="R1")
    db.session.add_all([admin, member, category, supplier, warehouse])
    db.session.flush()

    product = Product(
        sku="REPLENISH-001",
        name="补货任务测试物料",
        category_id=category.id,
        supplier_id=supplier.id,
        min_stock=10,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=0))
    db.session.commit()
    return admin, member, product


def test_replenishment_generate_job_runs_eager_and_exposes_status():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _admin, _member, product = seed_replenishment_fixture()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/inventory/replenishment-suggestions/generate-job", headers=headers, json={})

        assert response.status_code == 200
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["job"]["job_type"] == "replenishment.generate"
        assert payload["job"]["queue"] == "replenishment"
        assert payload["job"]["task_name"] == "nexus.replenishment.generate"
        assert payload["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert payload["created"] == 1
        assert payload["result"]["alerts_created"] == 1
        assert ReplenishmentSuggestion.query.filter_by(product_id=product.id).count() == 1

        status = client.get(f"/api/v1/inventory/replenishment-suggestions/jobs/{payload['job_id']}", headers=headers)

        assert status.status_code == 200
        assert status.json["data"]["job"]["status"] == BackgroundJob.STATUS_SUCCESS
        assert status.json["data"]["result"]["created"] == 1

        db.session.remove()
        db.drop_all()


def test_replenishment_legacy_generate_endpoint_still_returns_created_count():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _admin, _member, product = seed_replenishment_fixture()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/replenishment-suggestions/generate", headers=headers, json={})

        assert response.status_code == 200
        assert response.json["data"] == {"created": 1}
        assert ReplenishmentSuggestion.query.filter_by(product_id=product.id).count() == 1
        assert BackgroundJob.query.count() == 0

        db.session.remove()
        db.drop_all()


def test_replenishment_generate_job_returns_accepted_when_worker_mode_is_enabled(monkeypatch):
    app = create_app("testing")
    app.config["CELERY_TASK_ALWAYS_EAGER"] = False

    class FakeAsyncResult:
        id = "queued-replenishment-task"

    from app.platform.jobs.tasks.replenishment import replenishment_generate_task

    def fake_apply_async(*_args, **_kwargs):
        return FakeAsyncResult()

    monkeypatch.setattr(replenishment_generate_task, "apply_async", fake_apply_async)

    with app.app_context():
        db.create_all()
        seed_replenishment_fixture()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/inventory/replenishment-suggestions/generate-job", headers=headers, json={})

        assert response.status_code == 202
        payload = response.json["data"]
        assert payload["job_id"]
        assert payload["job"]["status"] == BackgroundJob.STATUS_PENDING
        job = BackgroundJob.query.filter_by(job_id=payload["job_id"]).one()
        assert job.celery_task_id == "queued-replenishment-task"
        assert job.queue == "replenishment"
        assert job.task_name == "nexus.replenishment.generate"
        assert ReplenishmentSuggestion.query.count() == 0

        db.session.remove()
        db.drop_all()


def test_replenishment_generation_job_status_is_user_scoped():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_replenishment_fixture()
        client = app.test_client()
        admin_headers = login(client)

        response = client.post("/api/v1/inventory/replenishment-suggestions/generate-job", headers=admin_headers, json={})
        job_id = response.json["data"]["job_id"]

        member_headers = login(client, email="member@nexus.com", password="member123")
        denied = client.get(f"/api/v1/inventory/replenishment-suggestions/jobs/{job_id}", headers=member_headers)

        assert denied.status_code == 403

        db.session.remove()
        db.drop_all()
