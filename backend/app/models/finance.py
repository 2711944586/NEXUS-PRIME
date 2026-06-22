"""财务相关模型"""
from datetime import datetime

from app.extensions import db
from app.utils.time import utcnow
from .base import BaseModel

_MONEY = db.Numeric(18, 4)


class CustomerCredit(BaseModel):
    __tablename__ = 'finance_customer_credit'
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'), unique=True)
    credit_limit = db.Column(_MONEY, default=0)
    used_credit = db.Column(_MONEY, default=0)
    warning_threshold = db.Column(db.Numeric(5, 2), default=80)
    is_frozen = db.Column(db.Boolean, default=False)
    frozen_reason = db.Column(db.String(256))
    frozen_at = db.Column(db.DateTime)
    frozen_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    customer = db.relationship('Partner')
    frozen_operator = db.relationship('User', foreign_keys=[frozen_by])

    @property
    def available_credit(self):
        return float(max(0, (self.credit_limit or 0) - (self.used_credit or 0)))

    @property
    def usage_rate(self):
        if not self.credit_limit:
            return 0
        return round(float(self.used_credit or 0) / float(self.credit_limit) * 100, 1)

    @property
    def is_warning(self):
        return self.usage_rate >= float(self.warning_threshold or 80)


class Receivable(BaseModel):
    __tablename__ = 'finance_receivables'
    STATUS_PENDING = 'pending'
    STATUS_PARTIAL = 'partial'
    STATUS_PAID = 'paid'
    STATUS_OVERDUE = 'overdue'
    STATUS_BAD_DEBT = 'bad_debt'

    receivable_no = db.Column(db.String(32), unique=True, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('trade_orders.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    total_amount = db.Column(_MONEY)
    paid_amount = db.Column(_MONEY, default=0)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    remark = db.Column(db.Text)
    order = db.relationship('Order')
    customer = db.relationship('Partner')
    payments = db.relationship('PaymentRecord', backref='receivable', cascade='all, delete-orphan')

    @property
    def unpaid_amount(self):
        return float((self.total_amount or 0) - (self.paid_amount or 0))

    @property
    def overdue_days(self):
        if not self.due_date or self.status == self.STATUS_PAID:
            return 0
        today = datetime.now().date()
        return max(0, (today - self.due_date).days) if today > self.due_date else 0

    @property
    def age_bucket(self):
        d = self.overdue_days
        if d == 0: return 'current'
        if d <= 30: return '0-30'
        if d <= 60: return '31-60'
        if d <= 90: return '61-90'
        return '90+'


class PaymentRecord(BaseModel):
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
    amount = db.Column(_MONEY)
    payment_method = db.Column(db.String(20), default=METHOD_BANK)
    payment_date = db.Column(db.Date, default=lambda: utcnow().date())
    reference_no = db.Column(db.String(64))
    operator_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    remark = db.Column(db.Text)
    customer = db.relationship('Partner')
    operator = db.relationship('User')


class AccountStatement(BaseModel):
    __tablename__ = 'finance_statements'
    statement_no = db.Column(db.String(32), unique=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    opening_balance = db.Column(_MONEY, default=0)
    sales_amount = db.Column(_MONEY, default=0)
    payment_amount = db.Column(_MONEY, default=0)
    closing_balance = db.Column(_MONEY, default=0)
    generated_at = db.Column(db.DateTime, default=utcnow)
    generated_by = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    confirmed = db.Column(db.Boolean, default=False)
    confirmed_at = db.Column(db.DateTime)
    customer = db.relationship('Partner')
    generator = db.relationship('User')
