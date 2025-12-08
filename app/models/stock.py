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