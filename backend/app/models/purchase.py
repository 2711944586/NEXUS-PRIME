"""采购管理模型"""
from sqlalchemy import func, select
from sqlalchemy.ext.hybrid import hybrid_property

from app.extensions import db
from app.utils.time import utcnow
from .base import BaseModel

_MONEY = db.Numeric(18, 4)


class PurchaseOrder(BaseModel):
    __tablename__ = 'purchase_orders'
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_ORDERED = 'ordered'
    STATUS_PARTIAL = 'partial'
    STATUS_RECEIVED = 'received'
    STATUS_CANCELLED = 'cancelled'

    po_no = db.Column(db.String(32), unique=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    total_amount = db.Column(_MONEY, default=0)
    status = db.Column(db.String(20), default=STATUS_DRAFT, index=True)
    submitted_at = db.Column(db.DateTime)
    submitted_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    expected_date = db.Column(db.Date)
    actual_receive_date = db.Column(db.DateTime)
    remark = db.Column(db.Text)
    supplier = db.relationship('Partner', foreign_keys=[supplier_id])
    warehouse = db.relationship('Warehouse')
    submitter = db.relationship('User', foreign_keys=[submitted_by])
    approver = db.relationship('User', foreign_keys=[approved_by])
    items = db.relationship('PurchaseOrderItem', backref='order', cascade='all, delete-orphan')

    @hybrid_property
    def received_amount(self):
        return float(sum((i.received_qty or 0) * float(i.unit_price or 0) for i in self.items))

    @received_amount.expression
    def received_amount(cls):
        return (
            select(func.coalesce(func.sum(PurchaseOrderItem.received_qty * PurchaseOrderItem.unit_price), 0))
            .where(PurchaseOrderItem.order_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def receive_progress(self):
        total = sum(i.quantity or 0 for i in self.items)
        received = sum(i.received_qty or 0 for i in self.items)
        return round(received / total * 100, 1) if total else 0

    @receive_progress.expression
    def receive_progress(cls):
        total_q = select(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).where(PurchaseOrderItem.order_id == cls.id).correlate(cls).scalar_subquery()
        rcvd_q = select(func.coalesce(func.sum(PurchaseOrderItem.received_qty), 0)).where(PurchaseOrderItem.order_id == cls.id).correlate(cls).scalar_subquery()
        return func.round(func.cast(rcvd_q, db.Numeric) / func.nullif(total_q, 0) * 100, 1)


class PurchaseOrderItem(BaseModel):
    __tablename__ = 'purchase_order_items'
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(_MONEY)
    received_qty = db.Column(db.Integer, default=0)
    product = db.relationship('Product')

    @property
    def subtotal(self):
        return float(self.quantity * (self.unit_price or 0))

    @property
    def pending_qty(self):
        return (self.quantity or 0) - (self.received_qty or 0)


class PurchasePriceHistory(BaseModel):
    __tablename__ = 'purchase_price_history'
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    price = db.Column(_MONEY)
    effective_date = db.Column(db.Date, default=lambda: utcnow().date())
    product = db.relationship('Product')
    supplier = db.relationship('Partner')


class SupplierPerformance(BaseModel):
    __tablename__ = 'supplier_performance'
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'), unique=True)
    total_orders = db.Column(db.Integer, default=0)
    on_time_orders = db.Column(db.Integer, default=0)
    quality_pass_orders = db.Column(db.Integer, default=0)
    total_amount = db.Column(_MONEY, default=0)
    last_order_date = db.Column(db.DateTime)
    supplier = db.relationship('Partner')

    @property
    def on_time_rate(self):
        return round(self.on_time_orders / self.total_orders * 100, 1) if self.total_orders else 100.0

    @property
    def quality_rate(self):
        return round(self.quality_pass_orders / self.total_orders * 100, 1) if self.total_orders else 100.0
