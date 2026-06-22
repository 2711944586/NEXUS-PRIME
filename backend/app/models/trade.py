from app.extensions import db
from .base import BaseModel

_MONEY = db.Numeric(18, 4)

class Order(BaseModel):
    __tablename__ = 'trade_orders'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_SHIPPED = 'shipped'
    STATUS_DONE = 'done'
    STATUS_CANCEL = 'cancelled'

    order_no = db.Column(db.String(32), unique=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    seller_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    total_amount = db.Column(_MONEY, default=0)
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    customer = db.relationship('Partner', foreign_keys=[customer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

class OrderItem(BaseModel):
    __tablename__ = 'trade_order_items'
    order_id = db.Column(db.Integer, db.ForeignKey('trade_orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    quantity = db.Column(db.Integer, default=1)
    price_snapshot = db.Column(_MONEY)
    product = db.relationship('Product')

    @property
    def subtotal(self):
        return float(self.quantity * (self.price_snapshot or 0))
