"""采购管理模型"""
from app.extensions import db
from .base import BaseModel
from datetime import datetime


class PurchaseOrder(BaseModel):
    """采购订单"""
    __tablename__ = 'purchase_orders'
    
    STATUS_DRAFT = 'draft'          # 草稿
    STATUS_PENDING = 'pending'      # 待审批
    STATUS_APPROVED = 'approved'    # 已审批
    STATUS_ORDERED = 'ordered'      # 已下单给供应商
    STATUS_PARTIAL = 'partial'      # 部分到货
    STATUS_RECEIVED = 'received'    # 已收货
    STATUS_CANCELLED = 'cancelled'  # 已取消
    
    po_no = db.Column(db.String(32), unique=True, index=True)  # 采购单号
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default=STATUS_DRAFT, index=True)
    
    # 审批信息
    submitted_at = db.Column(db.DateTime)
    submitted_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    # 预计到货日期
    expected_date = db.Column(db.Date)
    actual_receive_date = db.Column(db.DateTime)
    
    remark = db.Column(db.Text)
    
    # 关系
    supplier = db.relationship('Partner', foreign_keys=[supplier_id])
    warehouse = db.relationship('Warehouse')
    submitter = db.relationship('User', foreign_keys=[submitted_by])
    approver = db.relationship('User', foreign_keys=[approved_by])
    items = db.relationship('PurchaseOrderItem', backref='order', cascade='all, delete-orphan')
    
    @property
    def received_amount(self):
        """已收货金额"""
        return sum([item.received_qty * item.unit_price for item in self.items])
    
    @property
    def receive_progress(self):
        """收货进度百分比"""
        total_qty = sum([item.quantity for item in self.items])
        received_qty = sum([item.received_qty for item in self.items])
        if total_qty == 0:
            return 0
        return round(received_qty / total_qty * 100, 1)


class PurchaseOrderItem(BaseModel):
    """采购订单明细"""
    __tablename__ = 'purchase_order_items'
    
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float)  # 采购单价
    received_qty = db.Column(db.Integer, default=0)  # 已收货数量
    
    product = db.relationship('Product')
    
    @property
    def subtotal(self):
        return self.quantity * self.unit_price
    
    @property
    def pending_qty(self):
        """待收货数量"""
        return self.quantity - self.received_qty


class PurchasePriceHistory(BaseModel):
    """采购价格历史"""
    __tablename__ = 'purchase_price_history'
    
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    
    price = db.Column(db.Float)
    effective_date = db.Column(db.Date, default=datetime.utcnow)
    
    product = db.relationship('Product')
    supplier = db.relationship('Partner')


class SupplierPerformance(BaseModel):
    """供应商绩效"""
    __tablename__ = 'supplier_performance'
    
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'), unique=True)
    
    total_orders = db.Column(db.Integer, default=0)
    on_time_orders = db.Column(db.Integer, default=0)  # 准时交货订单数
    quality_pass_orders = db.Column(db.Integer, default=0)  # 质量合格订单数
    total_amount = db.Column(db.Float, default=0.0)  # 累计采购金额
    
    last_order_date = db.Column(db.DateTime)
    
    supplier = db.relationship('Partner')
    
    @property
    def on_time_rate(self):
        """准时交货率"""
        if self.total_orders == 0:
            return 100.0
        return round(self.on_time_orders / self.total_orders * 100, 1)
    
    @property
    def quality_rate(self):
        """质量合格率"""
        if self.total_orders == 0:
            return 100.0
        return round(self.quality_pass_orders / self.total_orders * 100, 1)
