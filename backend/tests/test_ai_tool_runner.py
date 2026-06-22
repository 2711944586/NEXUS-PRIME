import json

from app import create_app
from app.extensions import db
from app.models.ai import AiActionDraft
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.finance import Receivable
from app.models.notification import ReplenishmentSuggestion
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock, StockBalance, Warehouse
from app.models.sys import AuditLog
from app.models.trade import Order


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_ai_tool_fixture():
    permissions = {
        name: Permission(name=name, description=name)
        for name in [
            "finance.payment",
            "inventory.adjust",
            "purchase.write",
            "reports.generate",
            "sales.write",
        ]
    }
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    sales_role = Role(name="Sales", is_admin=False)
    finance_role = Role(name="Finance", is_admin=False)
    planner_role = Role(name="Planner", is_admin=False)
    sales_role.permissions.append(permissions["sales.write"])
    finance_role.permissions.append(permissions["finance.payment"])
    planner_role.permissions.extend([permissions["inventory.adjust"], permissions["purchase.write"]])
    admin_role.permissions.extend(permissions.values())
    db.session.add_all([admin_role, user_role, sales_role, finance_role, planner_role, *permissions.values()])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123"
    sales = User(username="sales", email="sales@nexus.com", role=sales_role)
    sales.password = "sales123"
    finance = User(username="finance", email="finance@nexus.com", role=finance_role)
    finance.password = "finance123"
    planner = User(username="planner", email="planner@nexus.com", role=planner_role)
    planner.password = "planner123"

    category = Category(name="AI 工具分类")
    supplier = Partner(name="AI 工具供应商", type=Partner.TYPE_SUPPLIER)
    customer = Partner(name="AI 工具客户", type=Partner.TYPE_CUSTOMER)
    warehouse = Warehouse(name="AI 工具主仓", location="A1")
    db.session.add_all([admin, member, sales, finance, planner, category, supplier, customer, warehouse])
    db.session.flush()

    product = Product(
        sku="AI-TOOL-001",
        name="AI 工具低库存物料",
        category_id=category.id,
        supplier_id=supplier.id,
        price=100,
        cost=40,
        min_stock=5,
        max_stock=20,
    )
    db.session.add(product)
    db.session.flush()

    db.session.add_all([
        Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=2),
        StockBalance(product_id=product.id, warehouse_id=warehouse.id, available_qty=2, locked_qty=0),
    ])

    sales_order = Order(
        order_no="SO-AI-SALES",
        customer_id=customer.id,
        seller_id=sales.id,
        total_amount=100,
        status=Order.STATUS_PENDING,
    )
    admin_order = Order(
        order_no="SO-AI-ADMIN",
        customer_id=customer.id,
        seller_id=admin.id,
        total_amount=200,
        status=Order.STATUS_PENDING,
    )
    db.session.add_all([sales_order, admin_order])
    db.session.flush()

    db.session.add_all([
        Receivable(
            receivable_no="AR-AI-SALES",
            order_id=sales_order.id,
            customer_id=customer.id,
            total_amount=100,
            paid_amount=0,
            status=Receivable.STATUS_PENDING,
        ),
        Receivable(
            receivable_no="AR-AI-ADMIN",
            order_id=admin_order.id,
            customer_id=customer.id,
            total_amount=200,
            paid_amount=50,
            status=Receivable.STATUS_PENDING,
        ),
    ])
    db.session.commit()
    return {
        "product": product,
        "warehouse": warehouse,
        "sales": sales,
        "finance": finance,
        "planner": planner,
    }


def test_ai_tool_denies_finance_query_without_permission_and_records_audit():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "member@nexus.com", "member123")

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "query_receivables", "params": {"limit": 5}},
        )

        assert response.status_code == 403
        assert response.json["error"] == "permission_denied"
        assert response.json["tool_result"]["allowed"] is False
        audit = AuditLog.query.filter_by(module="ai", action="tool_call").one()
        details = json.loads(audit.details)
        assert details["tool"] == "query_receivables"
        assert details["allowed"] is False
        assert details["error"] == "permission_denied"

        db.session.remove()
        db.drop_all()


def test_ai_tool_allows_finance_query_and_records_audit():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "finance@nexus.com", "finance123")

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "query_receivables", "params": {"limit": 5}},
        )

        assert response.status_code == 200
        payload = response.json["data"]
        assert payload["ok"] is True
        assert payload["data"]["count"] == 2
        assert {item["receivable_no"] for item in payload["data"]["items"]} == {"AR-AI-SALES", "AR-AI-ADMIN"}
        audit = AuditLog.query.filter_by(module="ai", action="tool_call").one()
        details = json.loads(audit.details)
        assert details["tool"] == "query_receivables"
        assert details["allowed"] is True
        assert details["result_count"] == 2

        db.session.remove()
        db.drop_all()


def test_ai_tool_sales_query_is_scoped_to_current_seller():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "sales@nexus.com", "sales123")

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "query_sales_orders", "params": {"limit": 10}},
        )

        assert response.status_code == 200
        items = response.json["data"]["data"]["items"]
        assert {item["order_no"] for item in items} == {"SO-AI-SALES"}
        assert all("total_amount" in item for item in items)

        db.session.remove()
        db.drop_all()


def test_ai_tool_replenishment_returns_draft_without_creating_business_records():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "planner@nexus.com", "planner123")
        before_purchase_count = PurchaseOrder.query.count()
        before_suggestion_count = ReplenishmentSuggestion.query.count()

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "generate_replenishment_draft", "params": {"limit": 5}},
        )

        assert response.status_code == 200
        data = response.json["data"]["data"]
        assert data["mutates_core_records"] is False
        assert data["persists_ai_draft"] is True
        assert data["draft_id"]
        assert data["draft"]["status"] == "draft"
        assert data["draft"]["requires_human_confirmation"] is True
        assert data["lines"][0]["product_sku"] == "AI-TOOL-001"
        assert data["lines"][0]["suggested_qty"] == 18
        draft = db.session.get(AiActionDraft, data["draft_id"])
        assert draft is not None
        assert draft.status == AiActionDraft.STATUS_DRAFT
        assert draft.draft_type == "replenishment"
        assert draft.payload["lines"][0]["product_sku"] == "AI-TOOL-001"
        assert PurchaseOrder.query.count() == before_purchase_count
        assert ReplenishmentSuggestion.query.count() == before_suggestion_count

        db.session.remove()
        db.drop_all()


def test_ai_replenishment_draft_requires_human_confirmation_before_business_record():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "planner@nexus.com", "planner123")

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "generate_replenishment_draft", "params": {"limit": 5}},
        )
        assert response.status_code == 200
        draft_id = response.json["data"]["data"]["draft_id"]
        assert ReplenishmentSuggestion.query.count() == 0
        assert PurchaseOrder.query.count() == 0

        listed = client.get("/api/v1/ai/drafts?status=draft", headers=headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json["data"]["items"]] == [draft_id]

        confirmed = client.post(
            f"/api/v1/ai/drafts/{draft_id}/confirm",
            headers=headers,
            json={"note": "确认转入补货中心"},
        )

        assert confirmed.status_code == 200
        payload = confirmed.json["data"]
        assert payload["draft"]["status"] == AiActionDraft.STATUS_CONFIRMED
        assert payload["created_purchase_order"] is False
        assert payload["requires_next_human_confirmation"] is True
        assert ReplenishmentSuggestion.query.count() == 1
        suggestion = ReplenishmentSuggestion.query.one()
        assert suggestion.status == ReplenishmentSuggestion.STATUS_PENDING
        assert suggestion.suggested_qty == 18
        assert suggestion.purchase_order_id is None
        assert PurchaseOrder.query.count() == 0

        audit_actions = [row.action for row in AuditLog.query.filter_by(module="ai").order_by(AuditLog.id.asc()).all()]
        assert "draft_created" in audit_actions
        assert "tool_call" in audit_actions
        assert "draft_confirmed" in audit_actions

        db.session.remove()
        db.drop_all()


def test_ai_draft_confirmation_requires_purchase_permission():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        planner_headers = login(client, "planner@nexus.com", "planner123")
        response = client.post(
            "/api/v1/ai/tools/run",
            headers=planner_headers,
            json={"tool": "generate_replenishment_draft", "params": {"limit": 5}},
        )
        draft_id = response.json["data"]["data"]["draft_id"]

        member_headers = login(client, "member@nexus.com", "member123")
        denied = client.post(
            f"/api/v1/ai/drafts/{draft_id}/confirm",
            headers=member_headers,
            json={"note": "越权确认"},
        )

        assert denied.status_code == 403
        assert denied.json["error"] == "permission_denied"
        assert db.session.get(AiActionDraft, draft_id).status == AiActionDraft.STATUS_DRAFT
        assert ReplenishmentSuggestion.query.count() == 0
        assert PurchaseOrder.query.count() == 0

        db.session.remove()
        db.drop_all()


def test_ai_draft_can_be_rejected_without_creating_business_records():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "planner@nexus.com", "planner123")
        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "generate_replenishment_draft", "params": {"limit": 5}},
        )
        draft_id = response.json["data"]["data"]["draft_id"]

        rejected = client.post(
            f"/api/v1/ai/drafts/{draft_id}/reject",
            headers=headers,
            json={"note": "暂不执行"},
        )

        assert rejected.status_code == 200
        assert rejected.json["data"]["draft"]["status"] == AiActionDraft.STATUS_REJECTED
        assert ReplenishmentSuggestion.query.count() == 0
        assert PurchaseOrder.query.count() == 0
        assert AuditLog.query.filter_by(module="ai", action="draft_rejected").count() == 1

        db.session.remove()
        db.drop_all()


def test_ai_tool_unknown_tool_is_rejected_and_audited():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_tool_fixture()
        client = app.test_client()
        headers = login(client, "admin@nexus.com", "admin123")

        response = client.post(
            "/api/v1/ai/tools/run",
            headers=headers,
            json={"tool": "drop_everything", "params": {}},
        )

        assert response.status_code == 400
        assert response.json["error"] == "unknown_ai_tool"
        audit = AuditLog.query.filter_by(module="ai", action="tool_call").one()
        details = json.loads(audit.details)
        assert details["tool"] == "drop_everything"
        assert details["ok"] is False
        assert details["error"] == "unknown_ai_tool"

        db.session.remove()
        db.drop_all()
