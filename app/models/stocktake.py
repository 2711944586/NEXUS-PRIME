"""盘点相关模型"""
from app.extensions import db
from .base import BaseModel
from datetime import datetime


class StockTake(BaseModel):
    """盘点单"""
    __tablename__ = 'stock_takes'
    
    TYPE_FULL = 'full'          # 全盘
    TYPE_PARTIAL = 'partial'    # 抽盘
    TYPE_CYCLE = 'cycle'        # 循环盘点
    
    STATUS_DRAFT = 'draft'          # 草稿
    STATUS_IN_PROGRESS = 'in_progress'  # 盘点中
    STATUS_COMPLETED = 'completed'  # 已完成
    STATUS_APPROVED = 'approved'    # 已审批
    STATUS_CANCELLED = 'cancelled'  # 已取消
    
    take_no = db.Column(db.String(32), unique=True, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    
    take_type = db.Column(db.String(20), default=TYPE_FULL)
    status = db.Column(db.String(20), default=STATUS_DRAFT, index=True)
    
    # 盘点范围（抽盘时使用）
    category_ids = db.Column(db.JSON)  # 指定分类
    product_ids = db.Column(db.JSON)   # 指定产品
    
    # 时间信息
    planned_date = db.Column(db.Date)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # 操作人员
    created_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    approved_at = db.Column(db.DateTime)
    
    # 统计
    total_items = db.Column(db.Integer, default=0)
    counted_items = db.Column(db.Integer, default=0)
    variance_items = db.Column(db.Integer, default=0)  # 差异项数
    
    remark = db.Column(db.Text)
    
    # 关系
    warehouse = db.relationship('Warehouse')
    creator = db.relationship('User', foreign_keys=[created_by])
    approver = db.relationship('User', foreign_keys=[approved_by])
    items = db.relationship('StockTakeItem', backref='stock_take', cascade='all, delete-orphan')
    
    @property
    def progress(self):
        """盘点进度百分比"""
        if self.total_items == 0:
            return 0
        return round(self.counted_items / self.total_items * 100, 1)
    
    @property
    def total_variance_qty(self):
        """总差异数量"""
        return sum([item.variance_qty for item in self.items])
    
    @property
    def total_variance_value(self):
        """总差异金额"""
        return sum([item.variance_value for item in self.items])


class StockTakeItem(BaseModel):
    """盘点明细"""
    __tablename__ = 'stock_take_items'
    
    take_id = db.Column(db.Integer, db.ForeignKey('stock_takes.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    
    system_qty = db.Column(db.Integer, default=0)   # 系统数量
    actual_qty = db.Column(db.Integer)              # 实盘数量（null表示未盘）
    unit_cost = db.Column(db.Float, default=0.0)    # 单位成本
    
    shelf_location = db.Column(db.String(32))       # 货位
    counted_at = db.Column(db.DateTime)
    counted_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    remark = db.Column(db.Text)
    
    product = db.relationship('Product')
    counter = db.relationship('User')
    
    @property
    def is_counted(self):
        """是否已盘点"""
        return self.actual_qty is not None
    
    @property
    def variance_qty(self):
        """差异数量"""
        if self.actual_qty is None:
            return 0
        return self.actual_qty - self.system_qty
    
    @property
    def variance_value(self):
        """差异金额"""
        return self.variance_qty * self.unit_cost
    
    @property
    def variance_type(self):
        """差异类型"""
        if self.variance_qty > 0:
            return 'surplus'  # 盘盈
        elif self.variance_qty < 0:
            return 'loss'     # 盘亏
        else:
            return 'match'    # 相符


class StockTakeHistory(BaseModel):
    """盘点历史记录（用于追溯）"""
    __tablename__ = 'stock_take_history'
    
    take_id = db.Column(db.Integer, db.ForeignKey('stock_takes.id'))
    action = db.Column(db.String(32))  # created, started, item_counted, completed, approved
    
    operator_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    details = db.Column(db.JSON)  # 详情
    
    operator = db.relationship('User')
