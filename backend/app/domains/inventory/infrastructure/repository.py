from sqlalchemy import func

from app.extensions import db
from app.models.biz import Product
from app.models.stock import Stock


class InventoryRepository:
    def product_stock_totals(self):
        return (
            db.session.query(
                Product,
                func.coalesce(func.sum(Stock.quantity), 0).label("total_stock"),
            )
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .all()
        )
