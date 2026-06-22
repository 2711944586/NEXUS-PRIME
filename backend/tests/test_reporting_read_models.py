from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.events import DomainEvent
from app.models.finance import Receivable
from app.models.stock import Stock, StockBalance, StockMovement, Warehouse
from app.domains.reporting.application import project_reporting_event
from app.domains.reporting.models import ReportingMetricDaily, ReportingProjectionState
from app.platform.events import EventDispatcher, Outbox
from app.utils.time import utcnow


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_sales_fixture():
    role = Role(name="ReportingAdmin", is_admin=True)
    permissions = [
        Permission(name="sales.write", description="销售履约"),
        Permission(name="reports.generate", description="报表生成"),
    ]
    role.permissions.extend(permissions)
    user = User(username="admin", email="admin@nexus.com", role=role, is_admin=True)
    user.password = "admin123"
    category = Category(name="报表测试分类")
    supplier = Partner(name="报表测试供应商", type="supplier")
    customer = Partner(name="报表测试客户", type="customer")
    warehouse = Warehouse(name="报表测试仓", location="R1")
    db.session.add_all([role, *permissions, user, category, supplier, customer, warehouse])
    db.session.flush()

    product = Product(
        sku="READ-MODEL-001",
        name="Read Model 物料",
        price=120,
        cost=60,
        category_id=category.id,
        supplier_id=supplier.id,
        min_stock=5,
        max_stock=100,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=20))
    db.session.commit()
    return user, customer, product


def metric(name, dimension_type="global", dimension_id="all"):
    return ReportingMetricDaily.query.filter_by(
        metric_name=name,
        dimension_type=dimension_type,
        dimension_id=str(dimension_id),
        is_deleted=False,
    ).one()


def test_reporting_projection_is_idempotent_for_single_domain_event():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        event = Outbox().add(
            "PaymentRecorded",
            "PaymentRecord",
            901,
            {
                "payment_id": 901,
                "customer_id": 77,
                "amount": 88.5,
            },
            tenant_id="tenant-a",
            created_by=1,
        )
        db.session.commit()

        first = project_reporting_event(event)
        second = project_reporting_event(event)
        db.session.commit()

        assert first.id == second.id
        assert ReportingProjectionState.query.count() == 1
        assert ReportingMetricDaily.query.count() == 3
        assert float(metric("payment_recorded_amount").value) == 88.5
        assert metric("payment_recorded_amount").count == 1
        assert float(metric("payment_recorded_amount", "customer", 77).value) == 88.5
        assert metric("payment_recorded_count").count == 1

        db.session.remove()
        db.drop_all()


def test_reporting_read_model_projects_sales_confirmed_dispatch_without_breaking_existing_handlers():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _user, customer, product = seed_sales_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 2}], "status": "pending"},
        )
        assert order.status_code == 201
        order_id = order.json["data"]["id"]
        assert client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"}).status_code == 200

        first_summary = EventDispatcher().dispatch_pending(limit=10)
        second_summary = EventDispatcher().dispatch_pending(limit=10)

        assert first_summary == {"processed": 2, "published": 2, "failed": 0}
        assert second_summary == {"processed": 2, "published": 2, "failed": 0}
        assert DomainEvent.query.filter_by(event_type="SalesOrderCreated").one().status == DomainEvent.STATUS_PUBLISHED
        assert DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").one().status == DomainEvent.STATUS_PUBLISHED
        assert Receivable.query.filter_by(order_id=order_id).count() == 1
        assert StockMovement.query.filter_by(source_type="sales_order", source_id=str(order_id), direction=StockMovement.DIRECTION_RESERVE).count() == 1
        assert StockBalance.query.filter_by(product_id=product.id).one().locked_qty == 2

        assert float(metric("sales_order_created_amount").value) == 240.0
        assert metric("sales_order_created_count").count == 1
        assert float(metric("sales_order_confirmed_amount").value) == 240.0
        assert metric("sales_order_confirmed_count").count == 1
        assert float(metric("inventory_reserved_quantity", "product", product.id).value) == 2.0
        assert float(metric("receivable_created_amount", "customer", customer.id).value) == 240.0
        assert ReportingProjectionState.query.count() == 4

        repeat = EventDispatcher().dispatch_pending(limit=10)
        assert repeat == {"processed": 0, "published": 0, "failed": 0}
        assert metric("sales_order_confirmed_count").count == 1

        db.session.remove()
        db.drop_all()


def test_reporting_daily_metrics_are_registered_as_read_only_resource():
    app = create_app("testing")

    with app.test_request_context("/"):
        from app.api.routes import resource_config

        config = resource_config("reporting-daily-metrics")
        assert config["model"] is ReportingMetricDaily
        assert config["create"] == []
        assert config["update"] == []
        assert config["permission"] == "reports.generate"
        assert config["read_permissions"] == ["reports.generate"]


def test_reporting_daily_metrics_require_report_permission_for_read_access():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        report_permission = Permission(name="reports.generate", description="报表生成")
        analyst_role = Role(name="ReportAnalyst")
        member_role = Role(name="ReportMember")
        analyst_role.permissions.append(report_permission)
        analyst = User(username="analyst", email="analyst@nexus.com", role=analyst_role)
        analyst.password = "analyst123"
        member = User(username="member", email="member@nexus.com", role=member_role)
        member.password = "member123"
        metric_row = ReportingMetricDaily(
            tenant_id="default",
            metric_date=utcnow().date(),
            metric_name="sales_order_confirmed_amount",
            dimension_type="global",
            dimension_id="all",
            value=240,
            count=1,
            attributes={},
        )
        db.session.add_all([report_permission, analyst_role, member_role, analyst, member, metric_row])
        db.session.commit()

        analyst_client = app.test_client()
        member_client = app.test_client()
        analyst_headers = login(analyst_client, "analyst@nexus.com", "analyst123")
        member_headers = login(member_client, "member@nexus.com", "member123")

        allowed = analyst_client.get("/api/v1/reporting-daily-metrics?page=1&page_size=5", headers=analyst_headers)
        assert allowed.status_code == 200
        assert allowed.json["data"]["pagination"]["total"] == 1

        hidden = member_client.get("/api/v1/reporting-daily-metrics?page=1&page_size=5", headers=member_headers)
        assert hidden.status_code == 403
        assert hidden.json["error"] == "permission_denied"

        denied = member_client.get(f"/api/v1/reporting-daily-metrics/{metric_row.id}", headers=member_headers)
        assert denied.status_code == 403
        assert denied.json["error"] in {"permission_denied", "forbidden"}

        db.session.remove()
        db.drop_all()
