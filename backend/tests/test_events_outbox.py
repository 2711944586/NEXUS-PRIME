from app import create_app
from app.domains.inventory.application import InventoryApplicationService
from app.extensions import db
from app.models.events import DomainEvent
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.finance import CustomerCredit, Receivable
from app.models.jobs import BackgroundJob
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion
from app.models.stock import Stock, StockBalance, StockMovement, Warehouse
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTask
from app.platform.events import (
    DomainEventMessage,
    EventBus,
    EventDispatcher,
    EventHandlerRegistry,
    Outbox,
    default_handler_registry,
    register_default_handlers,
)
from app.platform.events.handlers import (
    create_replenishment_suggestion_for_stock_alert,
    create_sales_order_receivable,
    dispatch_report_requested,
    release_sales_order_stock,
    notify_purchase_order_approved,
    notify_payment_recorded,
    notify_receivable_created,
    notify_sales_order_cancelled,
    notify_quality_inspection_result,
    notify_inventory_movement,
    notify_purchase_order_created,
    notify_workflow_started,
    notify_workflow_task_outcome,
    receive_purchase_goods_stock,
    reserve_sales_order_stock,
)
from app.platform.jobs.background_jobs import create_background_job
from app.services.finance_service import FinanceService
from app.services.sales_service import SalesService


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def test_event_handler_registry_applies_handlers_idempotently():
    calls = []

    def handler(event):
        calls.append(event.event_type)

    registry = EventHandlerRegistry({"ExampleEvent": [handler, handler]})
    bus = EventBus()

    registry.apply_to_bus(bus)
    registry.apply_to_bus(bus)

    assert registry.handlers_for("ExampleEvent") == (handler,)
    assert bus.handlers_for("ExampleEvent") == (handler,)


def test_domain_event_message_can_be_published_without_database_row():
    event = DomainEventMessage(
        "ReportRequested",
        "Report",
        42,
        {"report_type": "daily"},
        metadata={"source": "unit-test"},
        tenant_id="tenant-a",
        created_by=7,
        trace_id="trace-1",
    )
    seen = []
    bus = EventBus()
    bus.subscribe("ReportRequested", lambda item: seen.append(item))

    bus.publish(event)

    assert seen == [event]
    assert event.event_id
    assert event.aggregate_id == "42"
    assert event.payload == {"report_type": "daily"}
    assert event.metadata == {"source": "unit-test"}
    assert event.tenant_id == "tenant-a"
    assert event.created_by == "7"
    assert event.trace_id == "trace-1"
    assert event.occurred_at is not None


def test_default_event_handler_registry_registers_core_handlers_once():
    bus = EventBus()

    register_default_handlers(bus)
    register_default_handlers(bus)

    assert create_sales_order_receivable in default_handler_registry.handlers_for("SalesOrderConfirmed")
    assert reserve_sales_order_stock in bus.handlers_for("SalesOrderConfirmed")
    assert create_sales_order_receivable in bus.handlers_for("SalesOrderConfirmed")
    assert len(bus.handlers_for("SalesOrderConfirmed")) == len(set(bus.handlers_for("SalesOrderConfirmed")))


def seed_sales_event_fixture():
    admin_role = Role(name="Admin", is_admin=True)
    permissions = [Permission(name="sales.write", description="销售履约")]
    admin_role.permissions.extend(permissions)
    db.session.add_all([admin_role, *permissions])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    category = Category(name="核心设备")
    supplier = Partner(name="测试供应商", type="supplier")
    customer = Partner(name="测试客户", type="customer")
    warehouse = Warehouse(name="主仓", location="A1")
    db.session.add_all([admin, category, supplier, customer, warehouse])
    db.session.flush()

    product = Product(
        sku="MFG-EVENT-001",
        name="事件测试物料",
        price=99,
        cost=40,
        category_id=category.id,
        supplier_id=supplier.id,
        min_stock=5,
        max_stock=100,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=20))
    db.session.commit()
    return customer, product


def test_outbox_adds_pending_domain_event():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        event = Outbox().add(
            "SalesOrderConfirmed",
            "Order",
            42,
            {"order_id": 42},
            tenant_id="tenant-a",
            created_by=7,
            trace_id="trace-1",
        )
        db.session.commit()

        stored = DomainEvent.query.one()
        assert stored.id == event.id
        assert stored.event_id
        assert stored.event_type == "SalesOrderConfirmed"
        assert stored.aggregate_type == "Order"
        assert stored.aggregate_id == "42"
        assert stored.payload == {"order_id": 42}
        assert stored.status == DomainEvent.STATUS_PENDING
        assert stored.retry_count == 0
        assert stored.created_by == "7"
        assert Outbox().pending() == [stored]

        db.session.remove()
        db.drop_all()


def test_sales_order_paid_transition_writes_confirmed_outbox_event():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 2}], "status": "pending"},
        )
        assert order.status_code == 201

        order_id = order.json["data"]["id"]
        created_event = DomainEvent.query.filter_by(event_type="SalesOrderCreated").one()
        assert created_event.aggregate_type == "Order"
        assert created_event.aggregate_id == str(order_id)
        assert created_event.status == DomainEvent.STATUS_PENDING
        assert created_event.created_by == str(User.query.filter_by(email="admin@nexus.com").one().id)
        assert created_event.payload["order_id"] == order_id
        assert created_event.payload["order_no"] == order.json["data"]["order_no"]
        assert created_event.payload["customer_id"] == customer.id
        assert created_event.payload["seller_id"] == User.query.filter_by(email="admin@nexus.com").one().id
        assert created_event.payload["status"] == "pending"
        assert created_event.payload["total_amount"] == 198.0
        assert created_event.payload["items"] == [
            {"item_id": created_event.payload["items"][0]["item_id"], "product_id": product.id, "quantity": 2, "price_snapshot": 99.0}
        ]

        transition = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"})
        assert transition.status_code == 200

        event = DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").one()
        assert event.aggregate_type == "Order"
        assert event.aggregate_id == str(order_id)
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.payload["order_id"] == order_id
        assert event.payload["previous_status"] == "pending"
        assert event.payload["status"] == "paid"
        assert event.payload["items"] == [
            {"item_id": event.payload["items"][0]["item_id"], "product_id": product.id, "quantity": 2, "price_snapshot": 99.0}
        ]

        repeated = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"})
        assert repeated.status_code == 200
        assert DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").count() == 1
        assert DomainEvent.query.filter_by(event_type="SalesOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_sales_order_cancel_transition_writes_cancelled_outbox_event_once():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 1}], "status": "pending"},
        )
        assert order.status_code == 201
        order_id = order.json["data"]["id"]

        cancelled = client.post(
            f"/api/v1/sales/orders/{order_id}/transition",
            headers=headers,
            json={"status": "cancelled"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json["data"]["status"] == "cancelled"

        event = DomainEvent.query.filter_by(event_type="SalesOrderCancelled").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "Order"
        assert event.aggregate_id == str(order_id)
        assert event.created_by == str(User.query.filter_by(email="admin@nexus.com").one().id)
        assert event.payload["order_id"] == order_id
        assert event.payload["order_no"] == order.json["data"]["order_no"]
        assert event.payload["previous_status"] == "pending"
        assert event.payload["status"] == "cancelled"
        assert event.payload["customer_id"] == customer.id
        assert event.payload["seller_id"] == User.query.filter_by(email="admin@nexus.com").one().id
        assert event.payload["total_amount"] == 99.0
        assert event.payload["items"] == [
            {"item_id": event.payload["items"][0]["item_id"], "product_id": product.id, "quantity": 1, "price_snapshot": 99.0}
        ]

        repeated = client.post(
            f"/api/v1/sales/orders/{order_id}/transition",
            headers=headers,
            json={"status": "cancelled"},
        )
        assert repeated.status_code == 200
        assert DomainEvent.query.filter_by(event_type="SalesOrderCancelled").count() == 1
        assert DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").count() == 0
        assert DomainEvent.query.filter_by(event_type="SalesOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_sales_order_cancelled_default_handler_releases_reserved_stock_idempotently():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 2}], "status": "pending"},
        )
        assert order.status_code == 201
        order_id = order.json["data"]["id"]
        order_no = order.json["data"]["order_no"]
        assert client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"}).status_code == 200

    runner = app.test_cli_runner()
    first = runner.invoke(args=["events-dispatch", "--limit", "5"])
    assert first.exit_code == 0, first.output
    assert "processed=2 published=2 failed=0" in first.output

    with app.app_context():
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 18
        assert balance.locked_qty == 2

        client = app.test_client()
        headers = login(client)
        cancelled = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "cancelled"})
        assert cancelled.status_code == 200

    second = runner.invoke(args=["events-dispatch", "--limit", "10"])
    assert second.exit_code == 0, second.output
    assert "processed=3 published=3 failed=0" in second.output

    with app.app_context():
        release = StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RELEASE,
        ).one()
        assert release.quantity == 2
        assert release.reason == f"销售订单取消释放预留 - {order_no}"
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 20
        assert balance.locked_qty == 0
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 20

        release_event = DomainEvent.query.filter_by(event_type="InventoryReleased").one()
        assert release_event.status == DomainEvent.STATUS_PENDING
        assert release_event.aggregate_type == "StockMovement"
        assert release_event.aggregate_id == str(release.id)
        assert release_event.payload["source_type"] == "sales_order"
        assert release_event.payload["source_id"] == str(order_id)
        assert release_event.payload["quantity"] == 2
        assert release_event.payload["direction"] == StockMovement.DIRECTION_RELEASE
        cancel_event = DomainEvent.query.filter_by(event_type="SalesOrderCancelled").one()
        assert cancel_event.status == DomainEvent.STATUS_PUBLISHED
        notification = Notification.query.filter_by(
            related_type="order",
            related_id=order_id,
            title=f"销售订单已取消 - {order_no}",
        ).one()
        assert notification.type == Notification.TYPE_WARNING
        assert notification.category == Notification.CATEGORY_ORDER

        replayed_release = release_sales_order_stock(cancel_event)
        replayed_notification = notify_sales_order_cancelled(cancel_event)
        assert replayed_release == []
        assert replayed_notification.id == notification.id
        assert StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RELEASE,
        ).count() == 1
        assert Notification.query.filter_by(related_type="order", related_id=order_id, title=f"销售订单已取消 - {order_no}").count() == 1
        assert StockBalance.query.filter_by(product_id=product.id).one().available_qty == 20
        assert StockBalance.query.filter_by(product_id=product.id).one().locked_qty == 0

        db.session.remove()
        db.drop_all()


def test_finance_receivable_creation_writes_receivable_created_event():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        admin = User.query.filter_by(email="admin@nexus.com").one()
        order = SalesService.create_order(customer.id, admin, [{"product_id": product.id, "quantity": 1}])
        db.session.add(order)
        db.session.flush()
        order_id = order.id
        order_no = order.order_no

        ok, receivable = FinanceService.create_receivable(order_id)
        assert ok is True
        db.session.commit()

        event = DomainEvent.query.filter_by(event_type="ReceivableCreated").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "Receivable"
        assert event.aggregate_id == str(receivable.id)
        assert event.payload["receivable_id"] == receivable.id
        assert event.payload["order_id"] == order_id
        assert event.payload["order_no"] == order_no
        assert event.payload["customer_id"] == customer.id
        assert event.payload["total_amount"] == 99.0
        assert event.created_by == str(admin.id)

        duplicate_ok, duplicate_message = FinanceService.create_receivable(order_id)
        assert duplicate_ok is False
        assert duplicate_message == "该订单已有应收记录"
        assert DomainEvent.query.filter_by(event_type="ReceivableCreated").count() == 1
        assert DomainEvent.query.filter_by(event_type="SalesOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_finance_payment_records_payment_recorded_event_and_releases_credit():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        admin = User.query.filter_by(email="admin@nexus.com").one()
        order = SalesService.create_order(customer.id, admin, [{"product_id": product.id, "quantity": 2}])
        db.session.add(order)
        db.session.flush()

        ok, receivable = FinanceService.create_receivable(order.id)
        assert ok is True
        db.session.flush()
        assert float(CustomerCredit.query.filter_by(customer_id=customer.id).one().used_credit) == 198.0

        payment_ok, payment = FinanceService.record_payment(
            receivable.id,
            50,
            "bank",
            admin,
            reference_no="BANK-001",
            remark="首笔回款",
        )
        assert payment_ok is True
        db.session.commit()

        event = DomainEvent.query.filter_by(event_type="PaymentRecorded").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "PaymentRecord"
        assert event.aggregate_id == str(payment.id)
        assert event.payload["payment_id"] == payment.id
        assert event.payload["payment_no"] == payment.payment_no
        assert event.payload["receivable_id"] == receivable.id
        assert event.payload["order_id"] == order.id
        assert event.payload["customer_id"] == customer.id
        assert event.payload["amount"] == 50.0
        assert event.payload["payment_method"] == "bank"
        assert event.payload["reference_no"] == "BANK-001"
        assert event.payload["receivable_status"] == Receivable.STATUS_PARTIAL
        assert event.payload["unpaid_amount"] == 148.0
        assert event.created_by == str(admin.id)
        assert float(CustomerCredit.query.filter_by(customer_id=customer.id).one().used_credit) == 148.0

        failed_ok, failed_message = FinanceService.record_payment(receivable.id, 999, "bank", admin)
        assert failed_ok is False
        assert "收款金额超过未付金额" in failed_message
        assert DomainEvent.query.filter_by(event_type="PaymentRecorded").count() == 1

        dispatcher = EventDispatcher()
        summary = dispatcher.dispatch_pending(limit=10)
        assert summary["processed"] == 3
        assert summary["published"] == 3
        assert summary["failed"] == 0
        assert DomainEvent.query.filter_by(event_type="PaymentRecorded").one().status == DomainEvent.STATUS_PUBLISHED
        assert DomainEvent.query.filter_by(event_type="SalesOrderCreated").one().status == DomainEvent.STATUS_PUBLISHED

        db.session.remove()
        db.drop_all()


def test_finance_default_handlers_create_idempotent_notifications():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        admin = User.query.filter_by(email="admin@nexus.com").one()
        order = SalesService.create_order(customer.id, admin, [{"product_id": product.id, "quantity": 2}])
        db.session.add(order)
        db.session.flush()

        ok, receivable = FinanceService.create_receivable(order.id)
        assert ok is True
        db.session.flush()
        payment_ok, payment = FinanceService.record_payment(
            receivable.id,
            50,
            "bank",
            admin,
            reference_no="BANK-001",
            remark="首笔回款",
        )
        assert payment_ok is True
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 3, "published": 3, "failed": 0}
        receivable_notification = Notification.query.filter_by(
            related_type="receivable",
            related_id=receivable.id,
            title=f"应收账款已生成 - {receivable.receivable_no}",
        ).one()
        assert receivable_notification.user_id == admin.id
        assert receivable_notification.type == Notification.TYPE_INFO
        assert receivable_notification.category == Notification.CATEGORY_ORDER
        assert order.order_no in receivable_notification.content
        assert "金额 198.00" in receivable_notification.content

        payment_notification = Notification.query.filter_by(
            related_type="payment",
            related_id=payment.id,
            title=f"收款已记录 - {payment.payment_no}",
        ).one()
        assert payment_notification.user_id == admin.id
        assert payment_notification.type == Notification.TYPE_SUCCESS
        assert payment_notification.category == Notification.CATEGORY_ORDER
        assert "本次收款 50.00" in payment_notification.content
        assert "剩余未收 148.00" in payment_notification.content

        receivable_event = DomainEvent.query.filter_by(event_type="ReceivableCreated").one()
        payment_event = DomainEvent.query.filter_by(event_type="PaymentRecorded").one()
        assert receivable_event.status == DomainEvent.STATUS_PUBLISHED
        assert payment_event.status == DomainEvent.STATUS_PUBLISHED

        replayed_receivable = notify_receivable_created(receivable_event)
        replayed_payment = notify_payment_recorded(payment_event)
        assert replayed_receivable.id == receivable_notification.id
        assert replayed_payment.id == payment_notification.id
        assert Notification.query.filter_by(related_type="receivable", related_id=receivable.id).count() == 1
        assert Notification.query.filter_by(related_type="payment", related_id=payment.id).count() == 1

        db.session.remove()
        db.drop_all()


def test_domain_event_state_transitions_and_event_bus_publish():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        event = Outbox().add("ReportRequested", "Report", "daily", {"report_type": "daily"})
        db.session.flush()

        seen = []
        bus = EventBus()
        bus.subscribe("ReportRequested", lambda item: seen.append(item.event_id))
        bus.publish(event)

        assert seen == [event.event_id]

        event.mark_failed("temporary error")
        assert event.status == DomainEvent.STATUS_FAILED
        assert event.retry_count == 1
        assert event.error_message == "temporary error"

        event.mark_pending_for_retry()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.retry_count == 1
        assert event.error_message is None
        assert event.published_at is None

        event.mark_failed("temporary error")
        event.mark_published()
        assert event.status == DomainEvent.STATUS_PUBLISHED
        assert event.published_at is not None
        assert event.error_message is None

        db.session.remove()
        db.drop_all()


def test_event_dispatcher_marks_success_and_failure():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        ok = Outbox().add("DispatchOk", "Test", "1", {"ok": True})
        failed = Outbox().add("DispatchFail", "Test", "2", {"ok": False})
        db.session.commit()

        bus = EventBus()
        seen = []
        bus.subscribe("DispatchOk", lambda event: seen.append(event.event_id))

        def fail_handler(_event):
            raise RuntimeError("boom")

        bus.subscribe("DispatchFail", fail_handler)
        summary = EventDispatcher(bus=bus, store=Outbox()).dispatch_pending(limit=10)

        assert summary == {"processed": 2, "published": 1, "failed": 1}
        assert seen == [ok.event_id]
        assert db.session.get(DomainEvent, ok.id).status == DomainEvent.STATUS_PUBLISHED
        failed_event = db.session.get(DomainEvent, failed.id)
        assert failed_event.status == DomainEvent.STATUS_FAILED
        assert failed_event.retry_count == 1
        assert failed_event.error_message == "boom"

        db.session.remove()
        db.drop_all()


def test_failed_event_can_be_requeued_and_dispatched():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        event = Outbox().add("RetryMe", "Test", "1", {})
        db.session.commit()

        bus = EventBus()
        attempts = {"count": 0}

        def flaky(_event):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary outage")

        bus.subscribe("RetryMe", flaky)
        dispatcher = EventDispatcher(bus=bus, store=Outbox())

        first = dispatcher.dispatch_pending(limit=10)
        assert first == {"processed": 1, "published": 0, "failed": 1}
        failed_event = db.session.get(DomainEvent, event.id)
        assert failed_event.status == DomainEvent.STATUS_FAILED
        assert failed_event.retry_count == 1
        assert failed_event.error_message == "temporary outage"

        retry = dispatcher.retry_failed(limit=10)
        assert retry["retried"] == 1
        assert db.session.get(DomainEvent, event.id).status == DomainEvent.STATUS_PENDING

        second = dispatcher.dispatch_pending(limit=10)
        assert second == {"processed": 1, "published": 1, "failed": 0}
        published = db.session.get(DomainEvent, event.id)
        assert published.status == DomainEvent.STATUS_PUBLISHED
        assert published.retry_count == 1
        assert attempts["count"] == 2

        db.session.remove()
        db.drop_all()


def test_events_retry_failed_cli_requeues_filtered_events():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        target = Outbox().add("RetryTarget", "Test", "1", {})
        other = Outbox().add("RetryOther", "Test", "2", {})
        db.session.commit()
        target.mark_failed("target failure")
        other.mark_failed("other failure")
        db.session.commit()
        target_id = target.id
        other_id = other.id

    runner = app.test_cli_runner()
    result = runner.invoke(args=["events-retry-failed", "--event-type", "RetryTarget", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "retried=1" in result.output

    with app.app_context():
        assert db.session.get(DomainEvent, target_id).status == DomainEvent.STATUS_PENDING
        assert db.session.get(DomainEvent, other_id).status == DomainEvent.STATUS_FAILED
        db.session.remove()
        db.drop_all()


def test_events_dispatch_cli_consumes_pending_events():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        event = Outbox().add("NoHandlers", "Test", "1", {})
        db.session.commit()
        event_id = event.id

    runner = app.test_cli_runner()
    result = runner.invoke(args=["events-dispatch", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "processed=1 published=1 failed=0" in result.output

    with app.app_context():
        assert db.session.get(DomainEvent, event_id).status == DomainEvent.STATUS_PUBLISHED
        db.session.remove()
        db.drop_all()


def test_quality_inspection_default_handlers_create_idempotent_notifications():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        admin_role = Role(name="QualityAdmin", is_admin=True)
        admin = User(username="quality-admin", email="quality-admin@nexus.com", role=admin_role, is_admin=True)
        passed_source = Notification(
            user=admin,
            title="质量检验任务 - 入库批次抽检",
            content="原始质检任务",
            category=Notification.CATEGORY_APPROVAL,
            related_type="quality_inspection",
        )
        failed_source = Notification(
            user=admin,
            title="质量检验任务 - 入库批次抽检",
            content="原始质检任务",
            category=Notification.CATEGORY_APPROVAL,
            related_type="quality_inspection",
        )
        db.session.add_all([admin_role, admin, passed_source, failed_source])
        db.session.flush()

        passed_event = Outbox().add(
            "QualityInspectionPassed",
            "QualityInspectionTask",
            passed_source.id,
            {
                "notification_id": passed_source.id,
                "queue_item_id": "purchase-1001-inspection",
                "title": "入库批次抽检",
                "owner": "质量工程师",
                "priority": "P2",
                "sla": "2d",
                "path": "/app/quality",
                "decision": "放行",
                "result": "passed",
                "evidence": "抽检合格率达标。",
                "action": "归档质检记录并放行。",
            },
        )
        failed_event = Outbox().add(
            "QualityInspectionFailed",
            "QualityInspectionTask",
            failed_source.id,
            {
                "notification_id": failed_source.id,
                "queue_item_id": "purchase-1002-inspection",
                "title": "入库批次抽检",
                "owner": "质量经理",
                "priority": "P0",
                "sla": "4h",
                "path": "/app/quality",
                "decision": "隔离复核",
                "result": "failed",
                "evidence": "关键尺寸异常。",
                "action": "冻结批次并发起供应商整改。",
            },
            created_by=admin.id,
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 2, "published": 2, "failed": 0}
        passed_result = Notification.query.filter_by(
            related_type="quality_inspection_result",
            related_id=passed_source.id,
            title="质量检验通过 - 入库批次抽检",
        ).one()
        assert passed_result.user_id == admin.id
        assert passed_result.type == Notification.TYPE_SUCCESS
        assert passed_result.category == Notification.CATEGORY_APPROVAL
        assert "质检结果：通过" in passed_result.content
        assert "来源：/app/quality" in passed_result.content

        failed_result = Notification.query.filter_by(
            related_type="quality_inspection_result",
            related_id=failed_source.id,
            title="质量检验未通过 - 入库批次抽检",
        ).one()
        assert failed_result.user_id == admin.id
        assert failed_result.type == Notification.TYPE_ALERT
        assert "关键尺寸异常" in failed_result.content
        assert "冻结批次" in failed_result.content

        assert db.session.get(DomainEvent, passed_event.id).status == DomainEvent.STATUS_PUBLISHED
        assert db.session.get(DomainEvent, failed_event.id).status == DomainEvent.STATUS_PUBLISHED

        repeat = EventDispatcher().dispatch_pending(limit=10)
        assert repeat == {"processed": 0, "published": 0, "failed": 0}
        replayed_passed = notify_quality_inspection_result(db.session.get(DomainEvent, passed_event.id))
        replayed_failed = notify_quality_inspection_result(db.session.get(DomainEvent, failed_event.id))
        assert replayed_passed.id == passed_result.id
        assert replayed_failed.id == failed_result.id
        assert Notification.query.filter_by(related_type="quality_inspection_result").count() == 2

        db.session.remove()
        db.drop_all()


def test_purchase_goods_received_default_handler_receives_stock_idempotently():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        admin_role = Role(name="ProcurementAdmin", is_admin=True)
        admin = User(username="procurement-admin", email="procurement-admin@nexus.com", role=admin_role, is_admin=True)
        category = Category(name="采购物料")
        supplier = Partner(name="事件供应商", type="supplier")
        warehouse = Warehouse(name="收货仓", location="R1")
        db.session.add_all([admin_role, admin, category, supplier, warehouse])
        db.session.flush()
        product = Product(
            sku="PO-EVENT-001",
            name="采购事件物料",
            price=88,
            cost=32,
            category_id=category.id,
            supplier_id=supplier.id,
        )
        db.session.add(product)
        db.session.flush()

        event = Outbox().add(
            "PurchaseGoodsReceived",
            "PurchaseOrder",
            9001,
            {
                "purchase_order_id": 9001,
                "po_no": "PO-EVENT-9001",
                "supplier_id": supplier.id,
                "warehouse_id": warehouse.id,
                "status": "partial",
                "received_by": admin.id,
                "received_lines": [
                    {
                        "item_id": 7001,
                        "product_id": product.id,
                        "warehouse_id": warehouse.id,
                        "receive_qty": 4,
                        "received_qty": 4,
                        "pending_qty": 6,
                    }
                ],
            },
            created_by=admin.id,
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        movement = StockMovement.query.filter_by(
            source_type="purchase_order",
            source_id="9001",
            direction=StockMovement.DIRECTION_RECEIVE,
        ).one()
        assert movement.quantity == 4
        assert movement.idempotency_key == f"purchase-order:9001:item:7001:received:4:{StockMovement.DIRECTION_RECEIVE}:{product.id}:{warehouse.id}"
        assert movement.reason == "采购入库 - PO-EVENT-9001"
        balance = StockBalance.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one()
        assert balance.available_qty == 4
        assert balance.locked_qty == 0
        assert Stock.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity == 4
        inventory_event = DomainEvent.query.filter_by(event_type="PurchaseGoodsReceived").one()
        assert inventory_event.status == DomainEvent.STATUS_PUBLISHED

        replayed = receive_purchase_goods_stock(db.session.get(DomainEvent, event.id))
        assert [item.id for item in replayed] == [movement.id]
        assert StockMovement.query.filter_by(
            source_type="purchase_order",
            source_id="9001",
            direction=StockMovement.DIRECTION_RECEIVE,
        ).count() == 1
        assert StockBalance.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one().available_qty == 4
        assert Stock.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity == 4

        db.session.remove()
        db.drop_all()


def test_inventory_movement_default_handlers_create_idempotent_notifications():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        role = Role(name="InventoryOperator", is_admin=False)
        operator = User(username="inventory-operator", email="inventory-operator@nexus.com", role=role)
        category = Category(name="库存事件物料")
        supplier = Partner(name="库存事件供应商", type="supplier")
        warehouse = Warehouse(name="库存事件仓", location="I1")
        db.session.add_all([role, operator, category, supplier, warehouse])
        db.session.flush()
        product = Product(
            sku="INV-EVENT-001",
            name="库存事件测试物料",
            price=90,
            cost=45,
            category_id=category.id,
            supplier_id=supplier.id,
        )
        db.session.add(product)
        db.session.flush()
        db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=10))
        db.session.flush()

        service = InventoryApplicationService()
        items = [{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": 2}]
        reserved = service.reserve_stock("sales_order", "SO-NOTIFY-1", items, "SO-NOTIFY-1", created_by=operator, reason="订单确认")
        released = service.release_stock("sales_order", "SO-NOTIFY-1", items, "SO-NOTIFY-1-release", created_by=operator, reason="订单取消")
        deducted = service.deduct_stock("sales_order", "SO-NOTIFY-2", items, "SO-NOTIFY-2-ship", created_by=operator, reason="订单出库")
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 3, "published": 3, "failed": 0}
        reserved_notification = Notification.query.filter_by(
            related_type="stock_movement",
            related_id=reserved[0].id,
            title="库存已预留 - sales_order #SO-NOTIFY-1",
        ).one()
        assert reserved_notification.user_id == operator.id
        assert reserved_notification.type == Notification.TYPE_INFO
        assert reserved_notification.category == Notification.CATEGORY_STOCK
        assert "可用库存：10 -> 8" in reserved_notification.content
        assert "锁定库存：0 -> 2" in reserved_notification.content

        released_notification = Notification.query.filter_by(
            related_type="stock_movement",
            related_id=released[0].id,
            title="库存预留已释放 - sales_order #SO-NOTIFY-1",
        ).one()
        assert released_notification.user_id == operator.id
        assert released_notification.type == Notification.TYPE_WARNING
        assert "可用库存：8 -> 10" in released_notification.content
        assert "锁定库存：2 -> 0" in released_notification.content

        deducted_notification = Notification.query.filter_by(
            related_type="stock_movement",
            related_id=deducted[0].id,
            title="库存已扣减 - sales_order #SO-NOTIFY-2",
        ).one()
        assert deducted_notification.user_id == operator.id
        assert deducted_notification.type == Notification.TYPE_SUCCESS
        assert "可用库存：10 -> 8" in deducted_notification.content
        assert "锁定库存：0 -> 0" in deducted_notification.content

        reserved_event = DomainEvent.query.filter_by(event_type="InventoryReserved").one()
        released_event = DomainEvent.query.filter_by(event_type="InventoryReleased").one()
        deducted_event = DomainEvent.query.filter_by(event_type="InventoryDeducted").one()
        assert reserved_event.status == DomainEvent.STATUS_PUBLISHED
        assert released_event.status == DomainEvent.STATUS_PUBLISHED
        assert deducted_event.status == DomainEvent.STATUS_PUBLISHED

        assert notify_inventory_movement(reserved_event).id == reserved_notification.id
        assert notify_inventory_movement(released_event).id == released_notification.id
        assert notify_inventory_movement(deducted_event).id == deducted_notification.id
        assert Notification.query.filter_by(related_type="stock_movement").count() == 3

        db.session.remove()
        db.drop_all()


def test_stock_below_safety_default_handler_creates_replenishment_suggestion_idempotently():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        category = Category(name="补货物料")
        supplier = Partner(name="补货供应商", type="supplier")
        db.session.add_all([category, supplier])
        db.session.flush()
        product = Product(
            sku="LOW-STOCK-HANDLER-001",
            name="低库存事件物料",
            price=120,
            cost=60,
            min_stock=12,
            max_stock=120,
            category_id=category.id,
            supplier_id=supplier.id,
        )
        db.session.add(product)
        db.session.flush()

        event = Outbox().add(
            "StockBelowSafetyLine",
            "StockAlert",
            501,
            {
                "alert_id": 501,
                "product_id": product.id,
                "product_sku": product.sku,
                "product_name": product.name,
                "current_qty": 3,
                "min_qty": 12,
                "suggested_qty": 24,
                "alert_level": "red",
            },
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        suggestion = ReplenishmentSuggestion.query.one()
        assert suggestion.product_id == product.id
        assert suggestion.supplier_id == supplier.id
        assert suggestion.current_qty == 3
        assert suggestion.suggested_qty == 24
        assert suggestion.safety_stock == 12
        assert suggestion.status == ReplenishmentSuggestion.STATUS_PENDING
        assert db.session.get(DomainEvent, event.id).status == DomainEvent.STATUS_PUBLISHED

        replayed = create_replenishment_suggestion_for_stock_alert(db.session.get(DomainEvent, event.id))
        assert replayed.id == suggestion.id
        assert ReplenishmentSuggestion.query.count() == 1

        repeat = EventDispatcher().dispatch_pending(limit=10)
        assert repeat == {"processed": 0, "published": 0, "failed": 0}
        assert ReplenishmentSuggestion.query.count() == 1

        db.session.remove()
        db.drop_all()


def test_report_requested_default_handler_generates_pending_report_job_once():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        job = create_background_job(
            "report.generate",
            {"report_type": "sales_daily", "params": {}},
            queue="reports",
            task_name="nexus.reports.generate",
        )
        event = Outbox().add(
            "ReportRequested",
            "BackgroundJob",
            job.job_id,
            {
                "job_id": job.job_id,
                "report_type": "sales_daily",
                "params": {},
                "requested_by": None,
                "queue": "reports",
                "task_name": "nexus.reports.generate",
            },
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        stored = BackgroundJob.query.filter_by(job_id=job.job_id).one()
        assert stored.status == BackgroundJob.STATUS_SUCCESS
        assert stored.celery_task_id == f"event-{event.event_id}"
        assert stored.resource_type == "generated_report"
        assert stored.resource_id
        assert stored.result["report_type"] == "sales_daily"
        assert GeneratedReport.query.count() == 1
        assert db.session.get(DomainEvent, event.id).status == DomainEvent.STATUS_PUBLISHED

        replayed = dispatch_report_requested(db.session.get(DomainEvent, event.id))
        assert replayed.job_id == job.job_id
        assert GeneratedReport.query.count() == 1
        assert BackgroundJob.query.filter_by(job_id=job.job_id).one().resource_id == stored.resource_id

        db.session.remove()
        db.drop_all()


def test_purchase_order_approved_default_handler_creates_idempotent_notification():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        role = Role(name="PurchaseApprover", is_admin=False)
        approver = User(username="purchase-approver", email="purchase-approver@nexus.com", role=role)
        db.session.add_all([role, approver])
        db.session.flush()

        event = Outbox().add(
            "PurchaseOrderApproved",
            "PurchaseOrder",
            802,
            {
                "purchase_order_id": 802,
                "po_no": "PO-EVENT-802",
                "supplier_id": 301,
                "warehouse_id": 18,
                "status": "approved",
                "total_amount": 460.0,
                "approved_by": approver.id,
                "approved_at": "2026-06-21T12:00:00",
                "remark": "同意采购",
                "items": [
                    {"item_id": 1, "product_id": 11, "quantity": 3, "received_qty": 0, "unit_price": 120.0},
                    {"item_id": 2, "product_id": 12, "quantity": 2, "received_qty": 0, "unit_price": 50.0},
                ],
            },
            created_by=approver.id,
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        notification = Notification.query.filter_by(
            related_type="purchase_order",
            related_id=802,
            title="采购单已批准 - PO-EVENT-802",
        ).one()
        assert notification.user_id == approver.id
        assert notification.type == Notification.TYPE_SUCCESS
        assert notification.category == Notification.CATEGORY_APPROVAL
        assert "金额 460.00" in notification.content
        assert "共 2 条明细" in notification.content
        assert "仓库 18" in notification.content
        assert db.session.get(DomainEvent, event.id).status == DomainEvent.STATUS_PUBLISHED

        replayed = notify_purchase_order_approved(db.session.get(DomainEvent, event.id))
        assert replayed.id == notification.id
        assert Notification.query.filter_by(related_type="purchase_order", related_id=802).count() == 1

        db.session.remove()
        db.drop_all()


def test_purchase_order_created_default_handler_creates_idempotent_notification():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        role = Role(name="PurchaseCreator", is_admin=False)
        creator = User(username="purchase-creator", email="purchase-creator@nexus.com", role=role)
        db.session.add_all([role, creator])
        db.session.flush()

        event = Outbox().add(
            "PurchaseOrderCreated",
            "PurchaseOrder",
            701,
            {
                "purchase_order_id": 701,
                "po_no": "PO-EVENT-701",
                "supplier_id": 301,
                "warehouse_id": 18,
                "status": "draft",
                "total_amount": 320.0,
                "created_by": creator.id,
                "expected_date": "2026-07-01",
                "remark": "补货采购",
                "items": [
                    {"item_id": 1, "product_id": 11, "quantity": 3, "received_qty": 0, "unit_price": 80.0},
                    {"item_id": 2, "product_id": 12, "quantity": 2, "received_qty": 0, "unit_price": 40.0},
                ],
            },
            created_by=creator.id,
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        notification = Notification.query.filter_by(
            related_type="purchase_order",
            related_id=701,
            title="采购单已创建 - PO-EVENT-701",
        ).one()
        assert notification.user_id == creator.id
        assert notification.type == Notification.TYPE_INFO
        assert notification.category == Notification.CATEGORY_APPROVAL
        assert "金额 320.00" in notification.content
        assert "共 2 条明细" in notification.content
        assert "目标仓库：18" in notification.content
        assert "预计到货：2026-07-01" in notification.content
        assert "提交审批" in notification.content
        assert db.session.get(DomainEvent, event.id).status == DomainEvent.STATUS_PUBLISHED

        replayed = notify_purchase_order_created(db.session.get(DomainEvent, event.id))
        assert replayed.id == notification.id
        assert Notification.query.filter_by(related_type="purchase_order", related_id=701).count() == 1

        db.session.remove()
        db.drop_all()


def test_workflow_default_handlers_create_idempotent_notifications():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        role = Role(name="WorkflowEventRole", is_admin=False)
        applicant = User(username="workflow-applicant", email="workflow-applicant@nexus.com", role=role)
        approver = User(username="workflow-approver", email="workflow-approver@nexus.com", role=role)
        db.session.add_all([role, applicant, approver])
        db.session.flush()

        definition = WorkflowDefinition(
            process_key="purchase_order_approval",
            name="采购审批",
            config={"default_assignee_id": approver.id},
        )
        db.session.add(definition)
        db.session.flush()
        instance = WorkflowInstance(
            definition_id=definition.id,
            business_type="purchase_order",
            business_id="PO-EVENT-1001",
            applicant_id=applicant.id,
            status=WorkflowInstance.STATUS_RUNNING,
            current_node_key="approval",
            variables={"amount": 512.0},
        )
        db.session.add(instance)
        db.session.flush()
        task = WorkflowTask(
            instance_id=instance.id,
            node_key="approval",
            title="采购审批 #PO-EVENT-1001",
            assignee_id=approver.id,
            status=WorkflowTask.STATUS_PENDING,
        )
        db.session.add(task)
        db.session.flush()

        started_event = Outbox().add(
            "WorkflowStarted",
            "WorkflowInstance",
            instance.id,
            {
                "workflow_instance_id": instance.id,
                "workflow_task_id": task.id,
                "definition_id": definition.id,
                "process_key": definition.process_key,
                "business_type": instance.business_type,
                "business_id": instance.business_id,
                "applicant_id": applicant.id,
                "assignee_id": approver.id,
                "node_key": task.node_key,
                "task_title": task.title,
                "task_status": WorkflowTask.STATUS_PENDING,
                "instance_status": WorkflowInstance.STATUS_RUNNING,
                "current_node_key": "approval",
                "variables": instance.variables,
            },
            created_by=applicant.id,
        )
        approved_event = Outbox().add(
            "WorkflowTaskApproved",
            "WorkflowTask",
            task.id,
            {
                "workflow_instance_id": instance.id,
                "workflow_task_id": task.id,
                "process_key": definition.process_key,
                "business_type": instance.business_type,
                "business_id": instance.business_id,
                "node_key": task.node_key,
                "task_title": task.title,
                "task_status": WorkflowTask.STATUS_APPROVED,
                "instance_status": WorkflowInstance.STATUS_APPROVED,
                "assignee_id": approver.id,
                "action_by": approver.id,
                "comment": "同意",
            },
            created_by=approver.id,
        )
        rejected_event = Outbox().add(
            "WorkflowTaskRejected",
            "WorkflowTask",
            task.id,
            {
                "workflow_instance_id": instance.id,
                "workflow_task_id": task.id,
                "process_key": definition.process_key,
                "business_type": instance.business_type,
                "business_id": instance.business_id,
                "node_key": task.node_key,
                "task_title": task.title,
                "task_status": WorkflowTask.STATUS_REJECTED,
                "instance_status": WorkflowInstance.STATUS_REJECTED,
                "assignee_id": approver.id,
                "action_by": approver.id,
                "comment": "资料不足",
            },
            created_by=approver.id,
        )
        db.session.commit()

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 3, "published": 3, "failed": 0}
        started_notification = Notification.query.filter_by(
            related_type="workflow_task",
            related_id=task.id,
            title="新的工作流待办 - 采购审批 #PO-EVENT-1001",
        ).one()
        assert started_notification.user_id == approver.id
        assert started_notification.type == Notification.TYPE_INFO
        assert started_notification.category == Notification.CATEGORY_APPROVAL
        assert "待办任务已分配给你" in started_notification.content
        assert "purchase_order #PO-EVENT-1001" in started_notification.content

        approved_notification = Notification.query.filter_by(
            related_type="workflow_task",
            related_id=task.id,
            title="工作流已批准 - 采购审批 #PO-EVENT-1001",
        ).one()
        assert approved_notification.user_id == applicant.id
        assert approved_notification.type == Notification.TYPE_SUCCESS
        assert "意见：同意" in approved_notification.content

        rejected_notification = Notification.query.filter_by(
            related_type="workflow_task",
            related_id=task.id,
            title="工作流已驳回 - 采购审批 #PO-EVENT-1001",
        ).one()
        assert rejected_notification.user_id == applicant.id
        assert rejected_notification.type == Notification.TYPE_ALERT
        assert "资料不足" in rejected_notification.content
        assert db.session.get(DomainEvent, started_event.id).status == DomainEvent.STATUS_PUBLISHED
        assert db.session.get(DomainEvent, approved_event.id).status == DomainEvent.STATUS_PUBLISHED
        assert db.session.get(DomainEvent, rejected_event.id).status == DomainEvent.STATUS_PUBLISHED

        replayed_started = notify_workflow_started(db.session.get(DomainEvent, started_event.id))
        replayed_approved = notify_workflow_task_outcome(db.session.get(DomainEvent, approved_event.id))
        replayed_rejected = notify_workflow_task_outcome(db.session.get(DomainEvent, rejected_event.id))
        assert replayed_started.id == started_notification.id
        assert replayed_approved.id == approved_notification.id
        assert replayed_rejected.id == rejected_notification.id
        assert Notification.query.filter_by(related_type="workflow_task", related_id=task.id).count() == 3

        db.session.remove()
        db.drop_all()


def test_sales_order_confirmed_default_handler_creates_notification():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 1}], "status": "pending"},
        )
        order_id = order.json["data"]["id"]
        transition = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"})
        assert transition.status_code == 200

    runner = app.test_cli_runner()
    result = runner.invoke(args=["events-dispatch", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "processed=2 published=2 failed=0" in result.output

    with app.app_context():
        created_event = DomainEvent.query.filter_by(event_type="SalesOrderCreated").one()
        assert created_event.status == DomainEvent.STATUS_PUBLISHED
        event = DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").one()
        assert event.status == DomainEvent.STATUS_PUBLISHED
        reservation = StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RESERVE,
        ).one()
        assert reservation.quantity == 1
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 19
        assert balance.locked_qty == 1
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 20
        notification = Notification.query.filter_by(related_type="order", related_id=order_id).one()
        assert notification.category == Notification.CATEGORY_ORDER
        assert notification.type == Notification.TYPE_SUCCESS
        assert notification.user_id == User.query.filter_by(email="admin@nexus.com").first().id
        receivable = Receivable.query.filter_by(order_id=order_id).one()
        assert receivable.customer_id == customer.id
        assert float(receivable.total_amount) == 99.0
        assert receivable.status == Receivable.STATUS_PENDING
        credit = CustomerCredit.query.filter_by(customer_id=customer.id).one()
        assert float(credit.used_credit) == 99.0

    repeat = runner.invoke(args=["events-dispatch", "--limit", "5"])

    assert repeat.exit_code == 0, repeat.output
    assert "processed=2 published=2 failed=0" in repeat.output

    with app.app_context():
        inventory_event = DomainEvent.query.filter_by(event_type="InventoryReserved").one()
        assert inventory_event.status == DomainEvent.STATUS_PUBLISHED
        assert inventory_event.aggregate_type == "StockMovement"
        assert inventory_event.aggregate_id == str(reservation.id)
        assert inventory_event.created_by == str(User.query.filter_by(email="admin@nexus.com").first().id)
        assert inventory_event.payload["stock_movement_id"] == reservation.id
        assert inventory_event.payload["product_id"] == product.id
        assert inventory_event.payload["warehouse_id"] == reservation.warehouse_id
        assert inventory_event.payload["direction"] == StockMovement.DIRECTION_RESERVE
        assert inventory_event.payload["quantity"] == 1
        assert inventory_event.payload["source_type"] == "sales_order"
        assert inventory_event.payload["source_id"] == str(order_id)
        assert inventory_event.payload["reason"].startswith("销售订单确认预留")
        receivable_event = DomainEvent.query.filter_by(event_type="ReceivableCreated").one()
        assert receivable_event.status == DomainEvent.STATUS_PUBLISHED
        assert receivable_event.aggregate_type == "Receivable"
        assert receivable_event.payload["order_id"] == order_id
        assert receivable_event.payload["customer_id"] == customer.id
        assert receivable_event.payload["total_amount"] == 99.0
        assert Notification.query.filter_by(related_type="order", related_id=order_id).count() == 1
        assert StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RESERVE,
        ).count() == 1
        event = DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").one()
        replayed = create_sales_order_receivable(event)
        assert replayed.order_id == order_id
        assert Receivable.query.filter_by(order_id=order_id).count() == 1
        assert float(CustomerCredit.query.filter_by(customer_id=customer.id).one().used_credit) == 99.0
        assert DomainEvent.query.filter_by(event_type="InventoryReserved").count() == 1
        db.session.remove()
        db.drop_all()


def test_duplicate_sales_order_confirmed_events_do_not_duplicate_stock_or_receivable():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 2}], "status": "pending"},
        )
        assert order.status_code == 201
        order_id = order.json["data"]["id"]
        order_no = order.json["data"]["order_no"]
        assert client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"}).status_code == 200

        original_event = DomainEvent.query.filter_by(event_type="SalesOrderConfirmed").one()
        duplicate_event = Outbox().add(
            "SalesOrderConfirmed",
            "Order",
            order_id,
            dict(original_event.payload),
            created_by=original_event.created_by,
        )
        db.session.commit()
        duplicate_event_id = duplicate_event.id

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 3, "published": 3, "failed": 0}
        assert DomainEvent.query.filter_by(event_type="SalesOrderConfirmed", status=DomainEvent.STATUS_PUBLISHED).count() == 2
        assert db.session.get(DomainEvent, duplicate_event_id).status == DomainEvent.STATUS_PUBLISHED
        reservation = StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RESERVE,
        ).one()
        assert reservation.quantity == 2
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 18
        assert balance.locked_qty == 2
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 20
        assert Receivable.query.filter_by(order_id=order_id).count() == 1
        assert Notification.query.filter_by(
            related_type="order",
            related_id=order_id,
            title=f"销售订单已确认 - {order_no}",
        ).count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryReserved").count() == 1
        assert DomainEvent.query.filter_by(event_type="ReceivableCreated").count() == 1

        repeat = EventDispatcher().dispatch_pending(limit=10)

        assert repeat == {"processed": 2, "published": 2, "failed": 0}
        assert StockMovement.query.filter_by(
            source_type="sales_order",
            source_id=str(order_id),
            direction=StockMovement.DIRECTION_RESERVE,
        ).count() == 1
        assert Receivable.query.filter_by(order_id=order_id).count() == 1
        assert Notification.query.filter_by(related_type="order", related_id=order_id, title=f"销售订单已确认 - {order_no}").count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryReserved").count() == 1
        assert DomainEvent.query.filter_by(event_type="ReceivableCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_sales_order_confirmed_reservation_is_consumed_on_ship():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        customer, product = seed_sales_event_fixture()
        client = app.test_client()
        headers = login(client)

        order = client.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 2}], "status": "pending"},
        )
        order_id = order.json["data"]["id"]
        assert client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "paid"}).status_code == 200

    runner = app.test_cli_runner()
    result = runner.invoke(args=["events-dispatch", "--limit", "5"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 18
        assert balance.locked_qty == 2
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 20

        client = app.test_client()
        headers = login(client)
        shipped = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "shipped"})
        assert shipped.status_code == 200

        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 18
        assert balance.locked_qty == 0
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 18
        assert StockMovement.query.filter_by(source_id=str(order_id), direction=StockMovement.DIRECTION_RESERVE).count() == 1
        deduct_movement = StockMovement.query.filter_by(source_id=str(order_id), direction=StockMovement.DIRECTION_DEDUCT).one()
        assert deduct_movement.before_available_qty == 18
        assert deduct_movement.after_available_qty == 18
        assert deduct_movement.before_locked_qty == 2
        assert deduct_movement.after_locked_qty == 0
        deducted_event = DomainEvent.query.filter_by(event_type="InventoryDeducted").one()
        assert deducted_event.status == DomainEvent.STATUS_PENDING
        assert deducted_event.aggregate_type == "StockMovement"
        assert deducted_event.aggregate_id == str(deduct_movement.id)
        assert deducted_event.created_by == str(User.query.filter_by(email="admin@nexus.com").first().id)
        assert deducted_event.payload["stock_movement_id"] == deduct_movement.id
        assert deducted_event.payload["product_id"] == product.id
        assert deducted_event.payload["warehouse_id"] == deduct_movement.warehouse_id
        assert deducted_event.payload["direction"] == StockMovement.DIRECTION_DEDUCT
        assert deducted_event.payload["quantity"] == 2
        assert deducted_event.payload["source_type"] == "sales_order"
        assert deducted_event.payload["source_id"] == str(order_id)
        assert deducted_event.payload["reason"].startswith("销售出库")

        repeated_ship = client.post(f"/api/v1/sales/orders/{order_id}/transition", headers=headers, json={"status": "shipped"})
        assert repeated_ship.status_code == 200
        assert StockMovement.query.filter_by(source_id=str(order_id), direction=StockMovement.DIRECTION_DEDUCT).count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryDeducted").count() == 1
        balance = StockBalance.query.filter_by(product_id=product.id).one()
        assert balance.available_qty == 18
        assert balance.locked_qty == 0
        assert Stock.query.filter_by(product_id=product.id).one().quantity == 18

        db.session.remove()
        db.drop_all()
