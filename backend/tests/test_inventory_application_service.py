import pytest

from app import create_app
from app.domains.inventory.application import InventoryApplicationService
from app.domains.inventory.application.inventory_application_service import _locked
from app.extensions import db
from app.models.biz import Category, Partner, Product
from app.models.events import DomainEvent
from app.models.stock import InventoryLog, Stock, StockBalance, StockMovement, Warehouse


def seed_inventory_fixture():
    category = Category(name="库存分类")
    supplier = Partner(name="库存供应商", type="supplier")
    warehouse = Warehouse(name="主仓", location="A1")
    db.session.add_all([category, supplier, warehouse])
    db.session.flush()
    product = Product(
        sku="INV-APP-001",
        name="库存应用服务物料",
        price=100,
        cost=50,
        category_id=category.id,
        supplier_id=supplier.id,
        min_stock=5,
        max_stock=100,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=10))
    db.session.commit()
    return product, warehouse


def test_inventory_application_service_reserve_release_and_deduct_are_idempotent():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        product, warehouse = seed_inventory_fixture()
        service = InventoryApplicationService()

        items = [{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": 3}]
        reserved = service.reserve_stock("sales_order", "SO-1", items, "SO-1", reason="订单确认")
        db.session.commit()

        assert len(reserved) == 1
        balance = StockBalance.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one()
        assert balance.available_qty == 7
        assert balance.locked_qty == 3
        assert Stock.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity == 10
        assert StockMovement.query.count() == 1
        event = DomainEvent.query.filter_by(event_type="InventoryReserved").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "StockMovement"
        assert event.aggregate_id == str(reserved[0].id)
        assert event.created_by is None
        assert event.payload["stock_movement_id"] == reserved[0].id
        assert event.payload["product_id"] == product.id
        assert event.payload["warehouse_id"] == warehouse.id
        assert event.payload["direction"] == StockMovement.DIRECTION_RESERVE
        assert event.payload["quantity"] == 3
        assert event.payload["before_available_qty"] == 10
        assert event.payload["after_available_qty"] == 7
        assert event.payload["before_locked_qty"] == 0
        assert event.payload["after_locked_qty"] == 3
        assert event.payload["source_type"] == "sales_order"
        assert event.payload["source_id"] == "SO-1"
        assert event.payload["idempotency_key"] == reserved[0].idempotency_key
        assert event.payload["reason"] == "订单确认"

        repeated = service.reserve_stock("sales_order", "SO-1", items, "SO-1", reason="重复事件")
        db.session.commit()

        assert repeated[0].id == reserved[0].id
        assert StockMovement.query.count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryReserved").count() == 1
        assert StockBalance.query.one().available_qty == 7
        assert StockBalance.query.one().locked_qty == 3

        released = service.release_stock("sales_order", "SO-1", items, "SO-1-release", reason="订单取消释放")
        db.session.commit()

        assert released[0].direction == StockMovement.DIRECTION_RELEASE
        assert StockBalance.query.one().available_qty == 10
        assert StockBalance.query.one().locked_qty == 0
        assert Stock.query.one().quantity == 10
        released_event = DomainEvent.query.filter_by(event_type="InventoryReleased").one()
        assert released_event.status == DomainEvent.STATUS_PENDING
        assert released_event.aggregate_type == "StockMovement"
        assert released_event.aggregate_id == str(released[0].id)
        assert released_event.payload["stock_movement_id"] == released[0].id
        assert released_event.payload["product_id"] == product.id
        assert released_event.payload["warehouse_id"] == warehouse.id
        assert released_event.payload["direction"] == StockMovement.DIRECTION_RELEASE
        assert released_event.payload["quantity"] == 3
        assert released_event.payload["before_available_qty"] == 7
        assert released_event.payload["after_available_qty"] == 10
        assert released_event.payload["before_locked_qty"] == 3
        assert released_event.payload["after_locked_qty"] == 0
        assert released_event.payload["source_type"] == "sales_order"
        assert released_event.payload["source_id"] == "SO-1"
        assert released_event.payload["idempotency_key"] == released[0].idempotency_key
        assert released_event.payload["reason"] == "订单取消释放"

        repeated_release = service.release_stock("sales_order", "SO-1", items, "SO-1-release", reason="重复释放")
        db.session.commit()

        assert repeated_release[0].id == released[0].id
        assert StockMovement.query.filter_by(direction=StockMovement.DIRECTION_RELEASE).count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryReleased").count() == 1
        assert StockBalance.query.one().available_qty == 10
        assert StockBalance.query.one().locked_qty == 0

        deducted = service.deduct_stock("sales_order", "SO-1", items, "SO-1-ship", reason="订单出库")
        db.session.commit()

        assert deducted[0].direction == StockMovement.DIRECTION_DEDUCT
        assert StockBalance.query.one().available_qty == 7
        assert StockBalance.query.one().locked_qty == 0
        assert Stock.query.one().quantity == 7
        assert InventoryLog.query.count() == 3
        deducted_event = DomainEvent.query.filter_by(event_type="InventoryDeducted").one()
        assert deducted_event.status == DomainEvent.STATUS_PENDING
        assert deducted_event.aggregate_type == "StockMovement"
        assert deducted_event.aggregate_id == str(deducted[0].id)
        assert deducted_event.payload["stock_movement_id"] == deducted[0].id
        assert deducted_event.payload["product_id"] == product.id
        assert deducted_event.payload["warehouse_id"] == warehouse.id
        assert deducted_event.payload["direction"] == StockMovement.DIRECTION_DEDUCT
        assert deducted_event.payload["quantity"] == 3
        assert deducted_event.payload["before_available_qty"] == 10
        assert deducted_event.payload["after_available_qty"] == 7
        assert deducted_event.payload["before_locked_qty"] == 0
        assert deducted_event.payload["after_locked_qty"] == 0
        assert deducted_event.payload["source_type"] == "sales_order"
        assert deducted_event.payload["source_id"] == "SO-1"
        assert deducted_event.payload["idempotency_key"] == deducted[0].idempotency_key
        assert deducted_event.payload["reason"] == "订单出库"

        repeated_deduct = service.deduct_stock("sales_order", "SO-1", items, "SO-1-ship", reason="重复出库")
        db.session.commit()

        assert repeated_deduct[0].id == deducted[0].id
        assert StockMovement.query.filter_by(direction=StockMovement.DIRECTION_DEDUCT).count() == 1
        assert DomainEvent.query.filter_by(event_type="InventoryDeducted").count() == 1
        assert StockBalance.query.one().available_qty == 7
        assert StockBalance.query.one().locked_qty == 0

        with pytest.raises(ValueError, match="库存数量必须大于 0"):
            service.release_stock("sales_order", "SO-2", [{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": 0}], "bad")

        db.session.remove()
        db.drop_all()


def test_inventory_application_service_rejects_negative_stock_and_records_receive():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        product, warehouse = seed_inventory_fixture()
        service = InventoryApplicationService()

        with pytest.raises(ValueError, match="库存不足"):
            service.deduct_stock(
                "sales_order",
                "SO-OVER",
                [{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": 99}],
                "SO-OVER",
            )
        db.session.rollback()
        assert StockMovement.query.count() == 0
        assert Stock.query.one().quantity == 10

        received = service.receive_stock(
            "purchase_order",
            "PO-1",
            [{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": 5}],
            "PO-1",
            reason="采购到货",
        )
        db.session.commit()

        assert received[0].direction == StockMovement.DIRECTION_RECEIVE
        balance = StockBalance.query.one()
        assert balance.available_qty == 15
        assert balance.locked_qty == 0
        assert Stock.query.one().quantity == 15
        assert InventoryLog.query.one().move_type == InventoryLog.TYPE_IN

        db.session.remove()
        db.drop_all()


def test_inventory_lock_helper_uses_row_level_lock_outside_sqlite(monkeypatch):
    app = create_app("testing")

    class FakeDialect:
        def __init__(self, name):
            self.name = name

    class FakeBind:
        def __init__(self, name):
            self.dialect = FakeDialect(name)

    class FakeQuery:
        def __init__(self):
            self.locked = False

        def with_for_update(self):
            self.locked = True
            return self

    with app.app_context():
        postgres_query = FakeQuery()
        monkeypatch.setattr(db.session, "get_bind", lambda: FakeBind("postgresql"))

        assert _locked(postgres_query) is postgres_query
        assert postgres_query.locked is True

        sqlite_query = FakeQuery()
        monkeypatch.setattr(db.session, "get_bind", lambda: FakeBind("sqlite"))

        assert _locked(sqlite_query) is sqlite_query
        assert sqlite_query.locked is False
