from app import create_app
from app.extensions import db
from app.models.auth import User
from app.models.biz import Product
from app.models.events import DomainEvent
from app.models.stock import InventoryLog, Stock, Warehouse
from app.models.stocktake import StockTake, StockTakeItem
from app.services.stocktake_service import StockTakeService


def seed_stocktake_context():
    user = User(username="stocktake-user", email="stocktake@nexus.com", is_admin=True)
    user.password = "stocktake123"
    warehouse = Warehouse(name="Stocktake Warehouse", location="A1")
    product = Product(
        sku="STOCKTAKE-EVENT-001",
        name="Stocktake Event Item",
        cost=5,
        min_stock=2,
        max_stock=100,
    )
    db.session.add_all([user, warehouse, product])
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=10))
    db.session.commit()
    return user, warehouse, product


def test_stocktake_start_and_complete_write_outbox_events_once():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        user, warehouse, product = seed_stocktake_context()

        ok, stocktake = StockTakeService.create_stocktake(
            warehouse.id,
            StockTake.TYPE_CYCLE,
            [],
            user,
            remark="event flow",
        )
        assert ok is True
        db.session.flush()
        stocktake_id = stocktake.id
        item = StockTakeItem.query.filter_by(take_id=stocktake_id).one()
        assert item.product_id == product.id

        started, message = StockTakeService.start_stocktake(stocktake_id, user)
        db.session.commit()

        assert started is True
        assert message == "盘点已开始"
        submitted_event = DomainEvent.query.filter_by(event_type="StocktakeSubmitted").one()
        assert submitted_event.status == DomainEvent.STATUS_PENDING
        assert submitted_event.aggregate_type == "StockTake"
        assert submitted_event.aggregate_id == str(stocktake_id)
        assert submitted_event.created_by == str(user.id)
        assert submitted_event.payload["stocktake_id"] == stocktake_id
        assert submitted_event.payload["take_no"] == stocktake.take_no
        assert submitted_event.payload["warehouse_id"] == warehouse.id
        assert submitted_event.payload["status"] == StockTake.STATUS_IN_PROGRESS
        assert submitted_event.payload["total_items"] == 1
        assert submitted_event.payload["counted_items"] == 0
        assert submitted_event.payload["started_by"] == user.id
        assert submitted_event.payload["items"][0]["system_qty"] == 10
        assert submitted_event.payload["items"][0]["actual_qty"] is None

        repeated_start, _ = StockTakeService.start_stocktake(stocktake_id, user)
        db.session.commit()
        assert repeated_start is False
        assert DomainEvent.query.filter_by(event_type="StocktakeSubmitted").count() == 1

        ok, counted_item = StockTakeService.input_count(stocktake_id, item.id, 12, user, "counted")
        assert ok is True
        assert counted_item.variance_qty == 2

        completed, complete_message = StockTakeService.complete_stocktake(stocktake_id, user, auto_adjust=True)
        db.session.commit()

        assert completed is True
        assert complete_message == "盘点已完成"
        assert db.session.get(StockTake, stocktake_id).status == StockTake.STATUS_COMPLETED
        assert Stock.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity == 12
        assert InventoryLog.query.filter_by(transaction_code=stocktake.take_no, move_type=InventoryLog.TYPE_CHECK).count() == 1

        approved_event = DomainEvent.query.filter_by(event_type="StocktakeApproved").one()
        assert approved_event.status == DomainEvent.STATUS_PENDING
        assert approved_event.aggregate_type == "StockTake"
        assert approved_event.aggregate_id == str(stocktake_id)
        assert approved_event.created_by == str(user.id)
        assert approved_event.payload["stocktake_id"] == stocktake_id
        assert approved_event.payload["status"] == StockTake.STATUS_COMPLETED
        assert approved_event.payload["counted_items"] == 1
        assert approved_event.payload["variance_items"] == 1
        assert approved_event.payload["approved_by"] == user.id
        assert approved_event.payload["auto_adjust"] is True
        assert approved_event.payload["items"][0]["actual_qty"] == 12
        assert approved_event.payload["items"][0]["variance_qty"] == 2
        assert approved_event.payload["items"][0]["variance_value"] == 10.0

        repeated_complete, _ = StockTakeService.complete_stocktake(stocktake_id, user, auto_adjust=True)
        db.session.commit()
        assert repeated_complete is False
        assert DomainEvent.query.filter_by(event_type="StocktakeApproved").count() == 1

        db.session.remove()
        db.drop_all()
