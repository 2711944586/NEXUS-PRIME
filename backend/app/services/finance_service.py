"""财务服务 - 应收账款、信用管理"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, and_
from app.extensions import db
from app.models.finance import CustomerCredit, Receivable, PaymentRecord, AccountStatement
from app.models.trade import Order
from app.models.biz import Partner
from app.models.notification import Notification
from app.platform.policy import policy
from app.utils.time import utcnow


def query_with_lock(query):
    dialect_name = db.session.get_bind().dialect.name
    if not dialect_name.startswith('sqlite'):
        return query.with_for_update()
    return query


def money_value(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class FinanceService:
    """财务服务"""
    
    # ============== 信用管理 ==============
    
    @staticmethod
    def get_or_create_credit(customer_id):
        """获取或创建客户信用记录"""
        credit = CustomerCredit.query.filter_by(customer_id=customer_id).first()
        if not credit:
            credit = CustomerCredit(
                customer_id=customer_id,
                credit_limit=10000.0  # 默认额度
            )
            db.session.add(credit)
        return credit
    
    @staticmethod
    def set_credit_limit(customer_id, limit, user=None):
        """设置信用额度"""
        credit = FinanceService.get_or_create_credit(customer_id)
        credit.credit_limit = limit
        return True, "信用额度已更新"
    
    @staticmethod
    def check_credit(customer_id, amount):
        """
        检查信用额度是否足够
        返回: (is_allowed, message)
        """
        credit = FinanceService.get_or_create_credit(customer_id)
        
        if credit.is_frozen:
            return False, f"客户信用已冻结: {credit.frozen_reason}"

        available_credit = money_value(credit.credit_limit) - money_value(credit.used_credit)
        if available_credit < money_value(amount):
            return False, f"信用额度不足，可用额度: ¥{float(max(Decimal('0'), available_credit)):.2f}"
        
        return True, "信用检查通过"
    
    @staticmethod
    def use_credit(customer_id, amount):
        """使用信用额度"""
        credit = FinanceService.get_or_create_credit(customer_id)
        credit.used_credit = money_value(credit.used_credit) + money_value(amount)
        
        # 检查是否需要预警
        if credit.is_warning:
            FinanceService.send_credit_warning(credit)
    
    @staticmethod
    def release_credit(customer_id, amount):
        """释放信用额度（收款后）"""
        credit = FinanceService.get_or_create_credit(customer_id)
        credit.used_credit = max(Decimal("0"), money_value(credit.used_credit) - money_value(amount))
    
    @staticmethod
    def freeze_credit(customer_id, reason, user):
        """冻结客户信用"""
        credit = FinanceService.get_or_create_credit(customer_id)
        credit.is_frozen = True
        credit.frozen_reason = reason
        credit.frozen_at = utcnow()
        credit.frozen_by = user.id
        return True, "客户信用已冻结"
    
    @staticmethod
    def unfreeze_credit(customer_id):
        """解冻客户信用"""
        credit = FinanceService.get_or_create_credit(customer_id)
        credit.is_frozen = False
        credit.frozen_reason = None
        credit.frozen_at = None
        credit.frozen_by = None
        return True, "客户信用已解冻"
    
    @staticmethod
    def send_credit_warning(credit):
        """发送信用预警通知"""
        from app.models.auth import User
        
        admins = User.query.filter_by(is_admin=True, is_deleted=False).all()
        customer = db.session.get(Partner, credit.customer_id)
        
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title=f"信用预警 - {customer.name}",
                content=f"客户 {customer.name} 信用使用率达到 {credit.usage_rate}%，已超过预警阈值 {credit.warning_threshold}%",
                type=Notification.TYPE_WARNING,
                category=Notification.CATEGORY_ORDER,
                related_type='customer',
                related_id=credit.customer_id
            )
            db.session.add(notification)
    
    # ============== 应收账款 ==============
    
    @staticmethod
    def generate_receivable_no():
        """生成应收单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"AR-{date_str}-{random_str}"
    
    @staticmethod
    def create_receivable(order_id, due_days=30):
        """从订单创建应收账款"""
        order = db.session.get(Order, order_id)
        if not order:
            return False, "订单不存在"
        
        # 检查是否已存在
        existing = Receivable.query.filter_by(order_id=order_id).first()
        if existing:
            return False, "该订单已有应收记录"
        
        due_date = datetime.now().date() + timedelta(days=due_days)
        
        receivable = Receivable(
            receivable_no=FinanceService.generate_receivable_no(),
            order_id=order_id,
            customer_id=order.customer_id,
            total_amount=order.total_amount,
            due_date=due_date
        )
        db.session.add(receivable)
        db.session.flush()
        
        # 占用信用额度
        FinanceService.use_credit(order.customer_id, order.total_amount)

        from app.platform.events import outbox

        outbox.add(
            "ReceivableCreated",
            "Receivable",
            receivable.id,
            {
                "receivable_id": receivable.id,
                "receivable_no": receivable.receivable_no,
                "order_id": order.id,
                "order_no": order.order_no,
                "customer_id": order.customer_id,
                "total_amount": float(receivable.total_amount or 0),
                "due_date": receivable.due_date.isoformat() if receivable.due_date else None,
            },
            created_by=order.seller_id,
        )
        
        return True, receivable
    
    @staticmethod
    def generate_payment_no():
        """生成收款单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"PAY-{date_str}-{random_str}"
    
    @staticmethod
    def record_payment(receivable_id, amount, payment_method, user, reference_no=None, remark=None):
        """记录收款"""
        receivable = query_with_lock(Receivable.query.filter_by(id=receivable_id)).first()
        if not receivable:
            return False, "应收记录不存在"
        
        if amount <= 0:
            return False, "收款金额必须大于0"
        
        if amount > receivable.unpaid_amount:
            return False, f"收款金额超过未付金额 ¥{receivable.unpaid_amount:.2f}"
        
        try:
            payment = PaymentRecord(
                payment_no=FinanceService.generate_payment_no(),
                receivable_id=receivable_id,
                customer_id=receivable.customer_id,
                amount=amount,
                payment_method=payment_method,
                payment_date=datetime.now().date(),
                reference_no=reference_no,
                operator_id=user.id,
                remark=remark
            )
            db.session.add(payment)
            db.session.flush()
            
            receivable.paid_amount += amount
            
            # 更新状态
            if receivable.unpaid_amount <= 0:
                receivable.status = Receivable.STATUS_PAID
            else:
                receivable.status = Receivable.STATUS_PARTIAL
            
            # 释放信用额度
            FinanceService.release_credit(receivable.customer_id, amount)

            from app.platform.events import outbox

            outbox.add(
                "PaymentRecorded",
                "PaymentRecord",
                payment.id,
                {
                    "payment_id": payment.id,
                    "payment_no": payment.payment_no,
                    "receivable_id": receivable.id,
                    "receivable_no": receivable.receivable_no,
                    "order_id": receivable.order_id,
                    "customer_id": receivable.customer_id,
                    "amount": float(payment.amount or 0),
                    "payment_method": payment.payment_method,
                    "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                    "reference_no": payment.reference_no,
                    "receivable_status": receivable.status,
                    "unpaid_amount": float(receivable.unpaid_amount),
                },
                created_by=user.id if user else None,
            )
            
            return True, payment
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def update_overdue_status():
        """更新逾期状态"""
        today = datetime.now().date()
        
        overdue_receivables = Receivable.query.filter(
            Receivable.status.in_([Receivable.STATUS_PENDING, Receivable.STATUS_PARTIAL]),
            Receivable.due_date < today
        ).all()
        
        for r in overdue_receivables:
            r.status = Receivable.STATUS_OVERDUE
        
        return len(overdue_receivables)
    
    @staticmethod
    def get_aging_analysis(customer_id=None, user=None):
        """账龄分析"""
        query = Receivable.query.filter(
            Receivable.status.in_([Receivable.STATUS_PENDING, Receivable.STATUS_PARTIAL, Receivable.STATUS_OVERDUE])
        )
        if user is not None:
            query = policy.filter_query(query, Receivable, user)
        
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        receivables = query.all()
        
        aging = {
            'current': {'count': 0, 'amount': 0},
            '0-30': {'count': 0, 'amount': 0},
            '31-60': {'count': 0, 'amount': 0},
            '61-90': {'count': 0, 'amount': 0},
            '90+': {'count': 0, 'amount': 0}
        }
        
        for r in receivables:
            bucket = r.age_bucket
            aging[bucket]['count'] += 1
            aging[bucket]['amount'] += r.unpaid_amount
        
        return aging
    
    # ============== 对账单 ==============
    
    @staticmethod
    def generate_statement_no():
        """生成对账单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"STM-{date_str}-{random_str}"
    
    @staticmethod
    def generate_statement(customer_id, period_start, period_end, user):
        """生成对账单"""
        customer = db.session.get(Partner, customer_id)
        if not customer:
            return False, "客户不存在"
        
        # 期初余额（上期期末）
        prev_statement = AccountStatement.query.filter(
            AccountStatement.customer_id == customer_id,
            AccountStatement.period_end < period_start
        ).order_by(AccountStatement.period_end.desc()).first()
        
        opening_balance = prev_statement.closing_balance if prev_statement else 0
        
        # 本期销售
        sales = db.session.query(func.sum(Order.total_amount)).filter(
            Order.customer_id == customer_id,
            Order.created_at >= period_start,
            Order.created_at <= period_end,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).scalar() or 0
        
        # 本期收款
        payments = db.session.query(func.sum(PaymentRecord.amount)).filter(
            PaymentRecord.customer_id == customer_id,
            PaymentRecord.payment_date >= period_start,
            PaymentRecord.payment_date <= period_end
        ).scalar() or 0
        
        # 期末余额
        closing_balance = opening_balance + sales - payments
        
        statement = AccountStatement(
            statement_no=FinanceService.generate_statement_no(),
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            sales_amount=sales,
            payment_amount=payments,
            closing_balance=closing_balance,
            generated_by=user.id
        )
        db.session.add(statement)
        return True, statement
