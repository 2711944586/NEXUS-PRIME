"""通知与报表订阅模型"""
from app.extensions import db
from .base import BaseModel
from datetime import datetime


class Notification(BaseModel):
    """系统通知"""
    __tablename__ = 'sys_notifications'
    
    TYPE_INFO = 'info'
    TYPE_WARNING = 'warning'
    TYPE_ALERT = 'alert'
    TYPE_SUCCESS = 'success'
    
    CATEGORY_STOCK = 'stock'        # 库存预警
    CATEGORY_ORDER = 'order'        # 订单通知
    CATEGORY_APPROVAL = 'approval'  # 审批通知
    CATEGORY_SYSTEM = 'system'      # 系统通知
    CATEGORY_REPORT = 'report'      # 报表通知
    
    user_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'), index=True)
    
    title = db.Column(db.String(128))
    content = db.Column(db.Text)
    
    type = db.Column(db.String(20), default=TYPE_INFO)
    category = db.Column(db.String(20), default=CATEGORY_SYSTEM)
    
    # 关联对象
    related_type = db.Column(db.String(32))  # product, order, purchase_order 等
    related_id = db.Column(db.Integer)
    
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    # 是否已发送邮件
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime)
    
    user = db.relationship('User')


class StockAlert(BaseModel):
    """库存预警记录"""
    __tablename__ = 'stock_alerts'
    
    LEVEL_YELLOW = 'yellow'  # 黄色预警
    LEVEL_RED = 'red'        # 红色紧急
    
    STATUS_ACTIVE = 'active'      # 活跃
    STATUS_RESOLVED = 'resolved'  # 已解决
    STATUS_IGNORED = 'ignored'    # 已忽略
    
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    
    alert_level = db.Column(db.String(20), default=LEVEL_YELLOW)
    status = db.Column(db.String(20), default=STATUS_ACTIVE, index=True)
    
    current_qty = db.Column(db.Integer)
    min_qty = db.Column(db.Integer)
    suggested_qty = db.Column(db.Integer)  # 建议补货数量
    
    # 解决信息
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    resolution_note = db.Column(db.Text)
    
    product = db.relationship('Product')
    warehouse = db.relationship('Warehouse')
    resolver = db.relationship('User')


class ReplenishmentSuggestion(BaseModel):
    """补货建议"""
    __tablename__ = 'stock_replenishment_suggestions'
    
    STATUS_PENDING = 'pending'      # 待处理
    STATUS_ACCEPTED = 'accepted'    # 已接受
    STATUS_REJECTED = 'rejected'    # 已拒绝
    STATUS_ORDERED = 'ordered'      # 已下单
    
    product_id = db.Column(db.Integer, db.ForeignKey('biz_products.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('stock_warehouses.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    
    current_qty = db.Column(db.Integer)
    suggested_qty = db.Column(db.Integer)
    
    # 预测依据
    avg_daily_sales = db.Column(db.Float)  # 日均销量
    lead_time_days = db.Column(db.Integer, default=7)  # 采购周期
    safety_stock = db.Column(db.Integer)  # 安全库存
    
    status = db.Column(db.String(20), default=STATUS_PENDING)
    
    # 处理信息
    processed_at = db.Column(db.DateTime)
    processed_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    
    product = db.relationship('Product')
    warehouse = db.relationship('Warehouse')
    supplier = db.relationship('Partner')


class ReportSubscription(BaseModel):
    """报表订阅"""
    __tablename__ = 'report_subscriptions'
    
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    
    REPORT_SALES_DAILY = 'sales_daily'
    REPORT_SALES_WEEKLY = 'sales_weekly'
    REPORT_INVENTORY = 'inventory'
    REPORT_RECEIVABLE = 'receivable'
    REPORT_PERFORMANCE = 'performance'
    
    user_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    report_type = db.Column(db.String(32))
    frequency = db.Column(db.String(20), default=FREQUENCY_DAILY)
    
    # 发送设置
    send_email = db.Column(db.Boolean, default=True)
    send_notification = db.Column(db.Boolean, default=True)
    
    # 发送时间
    send_hour = db.Column(db.Integer, default=8)  # 发送小时 (0-23)
    send_weekday = db.Column(db.Integer, default=1)  # 周几发送 (1-7, 仅周报)
    send_day = db.Column(db.Integer, default=1)  # 几号发送 (1-28, 仅月报)
    
    is_active = db.Column(db.Boolean, default=True)
    last_sent_at = db.Column(db.DateTime)
    
    user = db.relationship('User')


class GeneratedReport(BaseModel):
    """生成的报表"""
    __tablename__ = 'generated_reports'
    
    report_type = db.Column(db.String(32))
    report_name = db.Column(db.String(128))
    
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    
    # 报表数据 (JSON)
    report_data = db.Column(db.JSON)
    
    # 文件路径 (PDF)
    file_path = db.Column(db.String(256))
    
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    # 是否已发送
    sent_count = db.Column(db.Integer, default=0)
    
    generator = db.relationship('User')
