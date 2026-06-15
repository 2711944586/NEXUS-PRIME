"""财务相关模型 - 应收账款、收款记录"""
from app.extensions import db
from .base import BaseModel
from datetime import datetime, timedelta


class CustomerCredit(BaseModel):
    """客户信用额度"""
    __tablename__ = 'finance_customer_credit'
    
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'), unique=True)
    
    credit_limit = db.Column(db.Float, default=0.0)  # 信用额度
    used_credit = db.Column(db.Float, default=0.0)   # 已用额度
    warning_threshold = db.Column(db.Float, default=80.0)  # 预警阈值百分比
    
    is_frozen = db.Column(db.Boolean, default=False)  # 是否冻结
    frozen_reason = db.Column(db.String(256))
    frozen_at = db.Column(db.DateTime)
    frozen_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    customer = db.relationship('Partner')
    frozen_operator = db.relationship('User', foreign_keys=[frozen_by])
    
    @property
    def available_credit(self):
        """可用额度"""
        return max(0, self.credit_limit - self.used_credit)
    
    @property
    def usage_rate(self):
        """使用率百分比"""
        if self.credit_limit == 0:
            return 0
        return round(self.used_credit / self.credit_limit * 100, 1)
    
    @property
    def is_warning(self):
        """是否达到预警"""
        return self.usage_rate >= self.warning_threshold


class Receivable(BaseModel):
    """应收账款"""
    __tablename__ = 'finance_receivables'
    
    STATUS_PENDING = 'pending'      # 待收款
    STATUS_PARTIAL = 'partial'      # 部分收款
    STATUS_PAID = 'paid'            # 已收款
    STATUS_OVERDUE = 'overdue'      # 已逾期
    STATUS_BAD_DEBT = 'bad_debt'    # 坏账
    
    receivable_no = db.Column(db.String(32), unique=True, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('trade_orders.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    
    total_amount = db.Column(db.Float)  # 应收金额
    paid_amount = db.Column(db.Float, default=0.0)  # 已收金额
    
    due_date = db.Column(db.Date)  # 到期日
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    
    remark = db.Column(db.Text)
    
    # 关系
    order = db.relationship('Order')
    customer = db.relationship('Partner')
    payments = db.relationship('PaymentRecord', backref='receivable', cascade='all, delete-orphan')
    
    @property
    def unpaid_amount(self):
        """未收金额"""
        return self.total_amount - self.paid_amount
    
    @property
    def overdue_days(self):
        """逾期天数"""
        if not self.due_date or self.status == self.STATUS_PAID:
            return 0
        today = datetime.now().date()
        if today > self.due_date:
            return (today - self.due_date).days
        return 0
    
    @property
    def age_bucket(self):
        """账龄分类"""
        days = self.overdue_days
        if days == 0:
            return 'current'  # 未到期
        elif days <= 30:
            return '0-30'
        elif days <= 60:
            return '31-60'
        elif days <= 90:
            return '61-90'
        else:
            return '90+'


class PaymentRecord(BaseModel):
    """收款记录"""
    __tablename__ = 'finance_payments'
    
    METHOD_CASH = 'cash'
    METHOD_BANK = 'bank'
    METHOD_WECHAT = 'wechat'
    METHOD_ALIPAY = 'alipay'
    METHOD_CHECK = 'check'
    METHOD_OTHER = 'other'
    
    payment_no = db.Column(db.String(32), unique=True, index=True)
    receivable_id = db.Column(db.Integer, db.ForeignKey('finance_receivables.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    
    amount = db.Column(db.Float)
    payment_method = db.Column(db.String(20), default=METHOD_BANK)
    payment_date = db.Column(db.Date, default=datetime.utcnow)
    
    reference_no = db.Column(db.String(64))  # 银行流水号等
    operator_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    remark = db.Column(db.Text)
    
    customer = db.relationship('Partner')
    operator = db.relationship('User')


class AccountStatement(BaseModel):
    """对账单"""
    __tablename__ = 'finance_statements'
    
    statement_no = db.Column(db.String(32), unique=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    
    opening_balance = db.Column(db.Float, default=0.0)  # 期初余额
    sales_amount = db.Column(db.Float, default=0.0)     # 本期销售
    payment_amount = db.Column(db.Float, default=0.0)   # 本期收款
    closing_balance = db.Column(db.Float, default=0.0)  # 期末余额
    
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    
    confirmed = db.Column(db.Boolean, default=False)  # 客户是否确认
    confirmed_at = db.Column(db.DateTime)
    
    customer = db.relationship('Partner')
    generator = db.relationship('User')
