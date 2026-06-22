from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.finance import AccountStatement, CustomerCredit, PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReportSubscription
from app.models.stock import InventoryLog, StockMovement, Warehouse
from app.models.trade import Order, OrderItem
from app.platform.crud.permissions import can_user, resource_access_error
from app.platform.policy import PolicyDecision, policy
from app.platform.policy.data_scope import DataScopePolicy
from app.platform.policy.field_policy import FieldPolicy
from app.platform.policy.object_authorization import ObjectAuthorizationPolicy


def seed_policy_fixture():
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    permissions = [
        Permission(name="reports.generate", description="报表生成"),
        Permission(name="finance.payment", description="财务收款"),
        Permission(name="finance.credit.write", description="信用管理"),
    ]
    user_role.permissions.append(permissions[0])
    db.session.add_all([admin_role, user_role, *permissions])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123A!"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123A!"
    other = User(username="other", email="other@nexus.com", role=user_role)
    other.password = "other123A!"
    db.session.add_all([admin, member, other])
    db.session.flush()

    member_report = GeneratedReport(report_type="sales", report_name="成员报表", generated_by=member.id)
    admin_report = GeneratedReport(report_type="sales", report_name="管理员报表", generated_by=admin.id)
    subscription = ReportSubscription(
        user_id=member.id,
        report_type="inventory",
        report_name="成员订阅",
        frequency=ReportSubscription.FREQUENCY_DAILY,
    )
    notification = Notification(user_id=member.id, title="成员通知", content="todo")
    db.session.add_all([member_report, admin_report, subscription, notification])
    db.session.commit()
    return admin, member, other, member_report, admin_report, notification


def test_policy_engine_delegates_to_modular_policy_components():
    assert isinstance(policy.data_scope, DataScopePolicy)
    assert isinstance(policy.field_policy, FieldPolicy)
    assert isinstance(policy.object_authorization, ObjectAuthorizationPolicy)
    assert PolicyDecision(True).allowed is True


def test_policy_can_covers_permissions_admin_only_and_object_access():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        admin, member, other, member_report, admin_report, notification = seed_policy_fixture()

        assert policy.can(member, "permission:reports.generate").allowed is True
        assert can_user(member, "reports.generate") is True
        assert policy.can(member, "permission:finance.payment").allowed is False
        assert policy.can(admin, "ai.tool.query_receivables").allowed is True
        unknown_ai_tool = policy.can(admin, "ai.tool.drop_everything")
        assert unknown_ai_tool.allowed is False
        assert unknown_ai_tool.error == "unknown_ai_tool"

        denied = policy.can(member, "list", context={"admin_only": True})
        assert denied.allowed is False
        assert denied.error == "admin_required"
        assert policy.can(admin, "list", context={"admin_only": True}).allowed is True

        assert policy.can(member, "get", resource=member_report).allowed is True
        forbidden = policy.can(member, "get", resource=admin_report)
        assert forbidden.allowed is False
        assert forbidden.error == "forbidden"
        assert policy.can(member, "update", resource=notification).allowed is True
        assert policy.can(other, "update", resource=notification).allowed is False

        config = {"model": GeneratedReport, "admin_only": True}
        assert resource_access_error(config, "list", member) == ("需要管理员权限", "admin_required")

        db.session.remove()
        db.drop_all()


def test_policy_filter_query_applies_user_scope_for_reports_and_notifications():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _admin, member, _other, member_report, admin_report, notification = seed_policy_fixture()

        report_ids = {
            row.id
            for row in policy.filter_query(GeneratedReport.query, GeneratedReport, member).order_by(GeneratedReport.id.asc()).all()
        }
        notification_ids = {
            row.id
            for row in policy.filter_query(Notification.query, Notification, member).order_by(Notification.id.asc()).all()
        }

        assert member_report.id in report_ids
        assert admin_report.id not in report_ids
        assert notification_ids == {notification.id}

        db.session.remove()
        db.drop_all()


def test_policy_scopes_sales_finance_and_inventory_objects():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _admin, member, other, _member_report, _admin_report, _notification = seed_policy_fixture()
        category = Category(name="分类")
        supplier = Partner(name="供应商", type=Partner.TYPE_SUPPLIER)
        customer = Partner(name="客户", type=Partner.TYPE_CUSTOMER)
        warehouse = Warehouse(name="主仓")
        db.session.add_all([category, supplier, customer, warehouse])
        db.session.flush()
        product = Product(sku="POLICY-001", name="策略物料", category_id=category.id, supplier_id=supplier.id)
        db.session.add(product)
        db.session.flush()

        member_order = Order(order_no="SO-MEMBER", customer_id=customer.id, seller_id=member.id, total_amount=100)
        other_order = Order(order_no="SO-OTHER", customer_id=customer.id, seller_id=other.id, total_amount=200)
        db.session.add_all([member_order, other_order])
        db.session.flush()

        member_item = OrderItem(order_id=member_order.id, product_id=None, quantity=1, price_snapshot=100)
        other_receivable = Receivable(
            receivable_no="AR-OTHER",
            order_id=other_order.id,
            customer_id=customer.id,
            total_amount=200,
            paid_amount=0,
            status=Receivable.STATUS_PENDING,
        )
        member_payment = PaymentRecord(
            payment_no="PAY-MEMBER",
            receivable_id=None,
            customer_id=customer.id,
            amount=10,
            operator_id=member.id,
        )
        other_payment = PaymentRecord(
            payment_no="PAY-OTHER",
            receivable=other_receivable,
            customer_id=customer.id,
            amount=20,
            operator_id=other.id,
        )
        other_statement = AccountStatement(
            statement_no="ST-OTHER",
            customer_id=customer.id,
            generated_by=other.id,
        )
        member_movement = StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            direction=StockMovement.DIRECTION_RECEIVE,
            quantity=2,
            source_type="test",
            source_id="member",
            idempotency_key="test:member",
            created_by=member.id,
        )
        other_log = InventoryLog(
            transaction_code="INV-OTHER",
            move_type=InventoryLog.TYPE_IN,
            warehouse_id=warehouse.id,
            qty_change=5,
            balance_after=5,
            operator_id=other.id,
        )
        other_movement = StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            direction=StockMovement.DIRECTION_RECEIVE,
            quantity=1,
            source_type="test",
            source_id="1",
            idempotency_key="test:1",
            created_by=other.id,
        )
        credit = CustomerCredit(customer_id=customer.id, credit_limit=1000)
        db.session.add_all([
            member_item,
            other_receivable,
            member_payment,
            other_payment,
            other_statement,
            member_movement,
            other_log,
            other_movement,
            credit,
        ])
        db.session.commit()

        assert policy.can(member, "get", resource=member_order).allowed is True
        assert policy.can(member, "get", resource=other_order).allowed is False
        assert policy.can(member, "get", resource=member_item).allowed is True
        assert policy.can(member, "get", resource=other_receivable).allowed is False
        assert policy.can(member, "get", resource=member_payment).allowed is True
        assert policy.can(member, "get", resource=other_payment).allowed is False
        assert policy.can(member, "get", resource=other_statement).allowed is True
        assert policy.can(member, "get", resource=member_movement).allowed is True
        assert policy.can(member, "get", resource=other_log).allowed is False
        assert policy.can(member, "get", resource=other_movement).allowed is False
        assert policy.can(member, "get", resource=credit).allowed is False

        assert {row.id for row in policy.filter_query(Order.query, Order, member).all()} == {member_order.id}
        assert policy.filter_query(Receivable.query, Receivable, member).count() == 0
        assert policy.filter_query(PaymentRecord.query, PaymentRecord, member).count() == 1
        assert policy.filter_query(InventoryLog.query, InventoryLog, member).count() == 0
        assert {row.id for row in policy.filter_query(StockMovement.query, StockMovement, member).all()} == {member_movement.id}
        assert policy.filter_query(Order.query, Order, None).count() == 0

        finance_role = Role(name="Finance", is_admin=False)
        db.session.add(finance_role)
        finance_role.permissions.append(Permission.query.filter_by(name="finance.payment").one())
        finance_role.permissions.append(Permission.query.filter_by(name="finance.credit.write").one())
        member.role = finance_role
        db.session.commit()

        assert policy.filter_query(Receivable.query, Receivable, member).count() == 1
        assert policy.filter_query(PaymentRecord.query, PaymentRecord, member).count() == 2
        assert policy.can(member, "get", resource=other_receivable).allowed is True
        assert policy.can(member, "get", resource=other_payment).allowed is True
        assert policy.can(member, "get", resource=credit).allowed is True

        db.session.remove()
        db.drop_all()


def test_policy_filters_sensitive_fields_by_role():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _admin, member, _other, _member_report, _admin_report, _notification = seed_policy_fixture()
        product_payload = {"id": 1, "sku": "SKU-1", "price": 99, "cost": 40, "supplier_id": 7}
        receivable_payload = {"id": 2, "receivable_no": "AR-1", "total_amount": 100, "paid_amount": 25, "unpaid_amount": 75}
        credit_payload = {"id": 3, "credit_limit": 1000, "available_credit": 500, "usage_rate": 50}

        assert policy.filter_fields(member, Product, product_payload) == {"id": 1, "sku": "SKU-1", "price": 99}
        assert policy.filter_fields(member, Receivable, receivable_payload) == {"id": 2, "receivable_no": "AR-1"}
        assert policy.filter_fields(member, CustomerCredit, credit_payload) == {"id": 3}

        master_role = Role(name="MasterData", is_admin=False)
        master_permission = Permission(name="masterdata.write", description="主数据维护")
        db.session.add_all([master_role, master_permission])
        db.session.flush()
        master_role.permissions.append(master_permission)
        member.role = master_role
        db.session.commit()

        assert policy.filter_fields(member, Product, product_payload)["cost"] == 40

        db.session.remove()
        db.drop_all()
