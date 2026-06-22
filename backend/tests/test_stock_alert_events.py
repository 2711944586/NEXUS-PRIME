from app import create_app
from app.extensions import db
from app.models.biz import Product
from app.models.events import DomainEvent
from app.models.notification import StockAlert
from app.models.stock import Stock, Warehouse
from app.services.stock_alert_service import StockAlertService


def test_stock_alert_creation_writes_stock_below_safety_event_once():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        product = Product(
            sku="LOW-STOCK-EVENT-001",
            name="Low Stock Event Item",
            min_stock=10,
            max_stock=100,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

        created = StockAlertService.check_all_stock_alerts()
        db.session.commit()

        assert created == 1
        alert = StockAlert.query.one()
        assert alert.product_id == product_id
        assert alert.status == StockAlert.STATUS_ACTIVE
        assert alert.alert_level == StockAlert.LEVEL_RED
        assert alert.current_qty == 0
        assert alert.min_qty == 10

        event = DomainEvent.query.filter_by(event_type="StockBelowSafetyLine").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "StockAlert"
        assert event.aggregate_id == str(alert.id)
        assert event.payload == {
            "alert_id": alert.id,
            "product_id": product_id,
            "product_sku": "LOW-STOCK-EVENT-001",
            "product_name": "Low Stock Event Item",
            "current_qty": 0,
            "min_qty": 10,
            "suggested_qty": 10,
            "alert_level": StockAlert.LEVEL_RED,
        }

        repeated = StockAlertService.check_all_stock_alerts()
        db.session.commit()

        assert repeated == 0
        assert StockAlert.query.count() == 1
        assert DomainEvent.query.filter_by(event_type="StockBelowSafetyLine").count() == 1

        warehouse = Warehouse(name="Recovery Warehouse", location="A1")
        db.session.add(warehouse)
        db.session.flush()
        db.session.add(Stock(product_id=product_id, warehouse_id=warehouse.id, quantity=15))
        db.session.commit()
        db.session.expire_all()

        recovered = StockAlertService.check_all_stock_alerts()
        db.session.commit()

        assert recovered == 0
        assert StockAlert.query.one().status == StockAlert.STATUS_RESOLVED
        assert DomainEvent.query.filter_by(event_type="StockBelowSafetyLine").count() == 1

        db.session.remove()
        db.drop_all()
