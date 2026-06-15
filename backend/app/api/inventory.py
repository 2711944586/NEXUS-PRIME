from sqlalchemy import func

from app.extensions import db
from app.models.biz import Product
from app.models.stock import Stock

from . import api_bp
from .auth import jwt_required
from .responses import api_success


@api_bp.get('/inventory/health')
@jwt_required
def inventory_health():
    rows = (
        db.session.query(
            Product,
            func.coalesce(func.sum(Stock.quantity), 0).label('total_stock')
        )
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .all()
    )
    risk_items = []
    out_of_stock = 0
    low_stock = 0
    stock_quantity = 0
    for product, total_stock in rows:
        total = int(total_stock or 0)
        stock_quantity += total
        if total <= 0:
            out_of_stock += 1
        if total <= (product.min_stock or 0):
            low_stock += 1
            risk_items.append({
                'id': product.id,
                'sku': product.sku,
                'name': product.name,
                'total_stock': total,
                'min_stock': product.min_stock or 0,
            })
    return api_success({
        'total_products': len(rows),
        'low_stock_products': low_stock,
        'out_of_stock_products': out_of_stock,
        'stock_quantity': stock_quantity,
        'risk_items': risk_items[:10],
    }, '库存健康度')
