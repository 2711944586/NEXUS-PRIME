from app.extensions import db
from .base import BaseModel

class Warehouse(BaseModel):
    """仓库"""
    __tablename__ = 'stock_warehouses'
    name = db.Column(db.String(64))
    location = db.Column(db.String(128))
    capacity = db.Column(db.Integer, default=10000) # 最大库容量

class Stock(BaseModel):
    """
    实时库存表 (关联表 Product <-> Warehouse)
    记录某商品在某仓库的数量
    """
    __tablename__ = 'stock_quantities'
    __table_args__ = (
        db.UniqueConstraint('product_id', 'warehouse_id', name='uq_stock_product_warehouse'),
    )
    
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    quantity = db.Column(db.Integer, default=0)
    
    # 货架位置 (WMS 高级功能)
    shelf_location = db.Column(db.String(32)) # e.g., "A-01-03"
    
    # 关系
    product = db.relationship('Product', backref='stocks')
    warehouse = db.relationship('Warehouse', backref='stocks')

class InventoryLog(BaseModel):
    """
    库存审计流水 (核心表)
    记录每一次库存变动的详情，用于复式记账审计
    """
    __tablename__ = 'stock_logs'
    
    TYPE_IN = 'inbound'   # 入库
    TYPE_OUT = 'outbound' # 出库
    TYPE_MOVE = 'move'    # 调拨
    TYPE_CHECK = 'check'  # 盘点盈亏
    
    transaction_code = db.Column(db.String(32), index=True) # 关联的单据号
    move_type = db.Column(db.String(20))
    
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    
    qty_change = db.Column(db.Integer) # 变动数量 (+10, -5)
    balance_after = db.Column(db.Integer) # 变动后结余 (快照)
    
    operator_id = db.Column(db.Integer, db.ForeignKey('auth_users.id')) # 操作人
    remark = db.Column(db.String(255))
    
    operator = db.relationship('User')
    product = db.relationship('Product')
    warehouse = db.relationship('Warehouse')


class StockBalance(BaseModel):
    __tablename__ = 'stock_balances'
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'product_id', 'warehouse_id', name='uq_stock_balance_tenant_product_warehouse'),
    )

    tenant_id = db.Column(db.String(128), nullable=False, default='default')
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'), nullable=False)
    available_qty = db.Column(db.Integer, nullable=False, default=0)
    locked_qty = db.Column(db.Integer, nullable=False, default=0)
    damaged_qty = db.Column(db.Integer, nullable=False, default=0)
    in_transit_qty = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=1)

    product = db.relationship('Product')
    warehouse = db.relationship('Warehouse')


class StockMovement(BaseModel):
    __tablename__ = 'stock_movements'
    __table_args__ = (
        db.UniqueConstraint('idempotency_key', name='uq_stock_movements_idempotency_key'),
    )

    DIRECTION_RESERVE = 'reserve'
    DIRECTION_RELEASE = 'release'
    DIRECTION_DEDUCT = 'deduct'
    DIRECTION_RECEIVE = 'receive'
    DIRECTION_ADJUST = 'adjust'

    tenant_id = db.Column(db.String(128), nullable=False, default='default')
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'), nullable=False)
    direction = db.Column(db.String(32), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    before_available_qty = db.Column(db.Integer, nullable=False, default=0)
    after_available_qty = db.Column(db.Integer, nullable=False, default=0)
    before_locked_qty = db.Column(db.Integer, nullable=False, default=0)
    after_locked_qty = db.Column(db.Integer, nullable=False, default=0)
    source_type = db.Column(db.String(128), nullable=False)
    source_id = db.Column(db.String(128), nullable=False)
    idempotency_key = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))

    product = db.relationship('Product')
    warehouse = db.relationship('Warehouse')
    creator = db.relationship('User')
