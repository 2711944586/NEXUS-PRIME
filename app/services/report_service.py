"""报表服务 - 定时生成与订阅"""
import json
import os
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy import func, and_
from app.extensions import db
from app.models.notification import ReportSubscription, GeneratedReport, Notification
from app.models.trade import Order
from app.models.stock import Stock, InventoryLog
from app.models.biz import Product
from app.models.biz import Partner
from app.models.finance import Receivable, PaymentRecord


class ReportService:
    """报表服务"""
    
    # 可用报表类型
    REPORT_TYPES = {
        'sales_daily': {
            'name': '销售日报',
            'description': '每日销售汇总，包含订单数、销售额、毛利等',
            'default_frequency': 'daily'
        },
        'sales_weekly': {
            'name': '销售周报',
            'description': '每周销售分析，包含趋势对比',
            'default_frequency': 'weekly'
        },
        'sales_monthly': {
            'name': '销售月报',
            'description': '月度销售汇总与分析',
            'default_frequency': 'monthly'
        },
        'inventory_summary': {
            'name': '库存汇总',
            'description': '当前库存状态，包含预警商品',
            'default_frequency': 'daily'
        },
        'inventory_movement': {
            'name': '库存变动',
            'description': '库存出入明细',
            'default_frequency': 'daily'
        },
        'receivable_aging': {
            'name': '应收账龄',
            'description': '应收账款账龄分析',
            'default_frequency': 'weekly'
        },
        'customer_ranking': {
            'name': '客户排名',
            'description': '客户销售额排名',
            'default_frequency': 'monthly'
        },
        'product_ranking': {
            'name': '商品排名',
            'description': '商品销量/销售额排名',
            'default_frequency': 'weekly'
        }
    }
    
    @staticmethod
    def get_available_reports():
        """获取可用报表列表"""
        return ReportService.REPORT_TYPES
    
    @staticmethod
    def create_subscription(user_id, report_type, frequency, send_hour=8, 
                           send_weekday=1, send_day=1, params=None):
        """创建报表订阅"""
        if report_type not in ReportService.REPORT_TYPES:
            return False, f"未知的报表类型: {report_type}"
        
        # 检查是否已订阅
        existing = ReportSubscription.query.filter_by(
            user_id=user_id,
            report_type=report_type,
            is_active=True
        ).first()
        
        if existing:
            return False, "您已订阅此报表"
        
        subscription = ReportSubscription(
            user_id=user_id,
            report_type=report_type,
            report_name=ReportService.REPORT_TYPES[report_type]['name'],
            frequency=frequency,
            send_hour=send_hour,
            send_weekday=send_weekday,
            send_day=send_day,
            params=params
        )
        db.session.add(subscription)
        db.session.commit()
        
        return True, subscription
    
    @staticmethod
    def cancel_subscription(subscription_id, user_id):
        """取消订阅"""
        subscription = ReportSubscription.query.filter_by(
            id=subscription_id,
            user_id=user_id
        ).first()
        
        if not subscription:
            return False, "订阅不存在"
        
        subscription.is_active = False
        db.session.commit()
        return True, "已取消订阅"
    
    @staticmethod
    def get_user_subscriptions(user_id):
        """获取用户订阅列表"""
        return ReportSubscription.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
    
    @staticmethod
    def should_generate(subscription):
        """检查是否应该生成报表"""
        now = datetime.now()
        
        # 检查时间
        if now.hour != subscription.send_hour:
            return False
        
        # 检查上次发送时间
        if subscription.last_sent:
            if subscription.frequency == 'daily':
                if subscription.last_sent.date() >= now.date():
                    return False
            elif subscription.frequency == 'weekly':
                if (now - subscription.last_sent).days < 7:
                    return False
                if now.weekday() != subscription.send_weekday:
                    return False
            elif subscription.frequency == 'monthly':
                if subscription.last_sent.month == now.month:
                    return False
                if now.day != subscription.send_day:
                    return False
        else:
            # 首次发送
            if subscription.frequency == 'weekly' and now.weekday() != subscription.send_weekday:
                return False
            if subscription.frequency == 'monthly' and now.day != subscription.send_day:
                return False
        
        return True
    
    @staticmethod
    def generate_report(report_type, params=None):
        """生成报表数据"""
        generator = getattr(ReportService, f'_generate_{report_type}', None)
        if not generator:
            return None, f"报表生成器不存在: {report_type}"
        
        try:
            data = generator(params)
            return data, None
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def _generate_sales_daily(params):
        """生成销售日报"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # 今日数据
        today_stats = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount'),
            func.sum(Order.total_amount - Order.total_cost).label('profit')
        ).filter(
            func.date(Order.created_at) == today,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        # 昨日数据（对比）
        yesterday_stats = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
        ).filter(
            func.date(Order.created_at) == yesterday,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        # 热销商品TOP5
        from app.models.trade import OrderItem
        top_products = db.session.query(
            Product.name,
            func.sum(OrderItem.quantity).label('qty'),
            func.sum(OrderItem.subtotal).label('amount')
        ).join(OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id
        ).filter(
            func.date(Order.created_at) == today,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(Product.id).order_by(func.sum(OrderItem.subtotal).desc()).limit(5).all()
        
        return {
            'report_date': str(today),
            'summary': {
                'order_count': today_stats.order_count or 0,
                'total_amount': float(today_stats.total_amount or 0),
                'profit': float(today_stats.profit or 0),
                'yesterday_amount': float(yesterday_stats.total_amount or 0),
                'growth_rate': round(
                    ((today_stats.total_amount or 0) - (yesterday_stats.total_amount or 1)) 
                    / (yesterday_stats.total_amount or 1) * 100, 2
                ) if yesterday_stats.total_amount else 0
            },
            'top_products': [
                {'name': p.name, 'quantity': p.qty, 'amount': float(p.amount)}
                for p in top_products
            ]
        }
    
    @staticmethod
    def _generate_sales_weekly(params):
        """生成销售周报"""
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)
        
        # 本周数据
        this_week = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
        ).filter(
            func.date(Order.created_at) >= week_start,
            func.date(Order.created_at) <= today,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        # 上周数据
        last_week = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
        ).filter(
            func.date(Order.created_at) >= last_week_start,
            func.date(Order.created_at) < week_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        # 每日趋势
        daily_trend = db.session.query(
            func.date(Order.created_at).label('date'),
            func.sum(Order.total_amount).label('amount')
        ).filter(
            func.date(Order.created_at) >= week_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(func.date(Order.created_at)).all()
        
        return {
            'week_start': str(week_start),
            'week_end': str(today),
            'summary': {
                'order_count': this_week.order_count or 0,
                'total_amount': float(this_week.total_amount or 0),
                'last_week_amount': float(last_week.total_amount or 0),
                'wow_growth': round(
                    ((this_week.total_amount or 0) - (last_week.total_amount or 1)) 
                    / (last_week.total_amount or 1) * 100, 2
                ) if last_week.total_amount else 0
            },
            'daily_trend': [
                {'date': str(d.date), 'amount': float(d.amount or 0)}
                for d in daily_trend
            ]
        }
    
    @staticmethod
    def _generate_sales_monthly(params):
        """生成销售月报"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        # 本月数据
        this_month = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount'),
            func.count(func.distinct(Order.customer_id)).label('customer_count')
        ).filter(
            func.date(Order.created_at) >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        # 上月数据
        last_month = db.session.query(
            func.sum(Order.total_amount).label('total_amount')
        ).filter(
            func.date(Order.created_at) >= last_month_start,
            func.date(Order.created_at) <= last_month_end,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).first()
        
        return {
            'month': month_start.strftime('%Y-%m'),
            'summary': {
                'order_count': this_month.order_count or 0,
                'total_amount': float(this_month.total_amount or 0),
                'customer_count': this_month.customer_count or 0,
                'avg_order_value': round(
                    (this_month.total_amount or 0) / (this_month.order_count or 1), 2
                ),
                'last_month_amount': float(last_month.total_amount or 0),
                'mom_growth': round(
                    ((this_month.total_amount or 0) - (last_month.total_amount or 1)) 
                    / (last_month.total_amount or 1) * 100, 2
                ) if last_month.total_amount else 0
            }
        }
    
    @staticmethod
    def _generate_inventory_summary(params):
        """生成库存汇总"""
        # 库存汇总
        stocks = db.session.query(
            Product.name,
            Product.sku,
            Product.min_stock,
            func.sum(Stock.quantity).label('total_qty')
        ).outerjoin(Stock, Stock.product_id == Product.id
        ).filter(Product.is_deleted == False
        ).group_by(Product.id).all()
        
        total_items = len(stocks)
        warning_items = [s for s in stocks if s.min_stock and (s.total_qty or 0) <= s.min_stock]
        zero_items = [s for s in stocks if not s.total_qty or s.total_qty == 0]
        
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_products': total_items,
                'warning_count': len(warning_items),
                'zero_stock_count': len(zero_items)
            },
            'warning_items': [
                {'name': s.name, 'sku': s.sku, 'quantity': s.total_qty or 0, 'min_stock': s.min_stock}
                for s in warning_items[:20]
            ]
        }
    
    @staticmethod
    def _generate_inventory_movement(params):
        """生成库存变动"""
        today = datetime.now().date()
        
        movements = db.session.query(
            InventoryLog.type,
            func.count(InventoryLog.id).label('count'),
            func.sum(InventoryLog.quantity).label('total_qty')
        ).filter(
            func.date(InventoryLog.created_at) == today
        ).group_by(InventoryLog.type).all()
        
        return {
            'report_date': str(today),
            'movements': [
                {'type': m.type, 'count': m.count, 'quantity': m.total_qty}
                for m in movements
            ]
        }
    
    @staticmethod
    def _generate_receivable_aging(params):
        """生成应收账龄"""
        receivables = Receivable.query.filter(
            Receivable.status.in_([Receivable.STATUS_PENDING, Receivable.STATUS_PARTIAL, Receivable.STATUS_OVERDUE])
        ).all()
        
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
        
        total_amount = sum(a['amount'] for a in aging.values())
        
        return {
            'generated_at': datetime.now().isoformat(),
            'total_receivable': total_amount,
            'aging': aging
        }
    
    @staticmethod
    def _generate_customer_ranking(params):
        """生成客户排名"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        rankings = db.session.query(
            Partner.name,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
        ).join(Order, Order.customer_id == Partner.id
        ).filter(
            func.date(Order.created_at) >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(Partner.id
        ).order_by(func.sum(Order.total_amount).desc()
        ).limit(20).all()
        
        return {
            'period': month_start.strftime('%Y-%m'),
            'rankings': [
                {
                    'rank': i + 1,
                    'customer': r.name,
                    'order_count': r.order_count,
                    'total_amount': float(r.total_amount or 0)
                }
                for i, r in enumerate(rankings)
            ]
        }
    
    @staticmethod
    def _generate_product_ranking(params):
        """生成商品排名"""
        today = datetime.now().date()
        week_start = today - timedelta(days=7)
        
        from app.models.trade import OrderItem
        
        rankings = db.session.query(
            Product.name,
            Product.sku,
            func.sum(OrderItem.quantity).label('total_qty'),
            func.sum(OrderItem.subtotal).label('total_amount')
        ).join(OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id
        ).filter(
            func.date(Order.created_at) >= week_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(Product.id
        ).order_by(func.sum(OrderItem.subtotal).desc()
        ).limit(20).all()
        
        return {
            'period_start': str(week_start),
            'period_end': str(today),
            'rankings': [
                {
                    'rank': i + 1,
                    'name': r.name,
                    'sku': r.sku,
                    'quantity': r.total_qty,
                    'amount': float(r.total_amount or 0)
                }
                for i, r in enumerate(rankings)
            ]
        }
    
    @staticmethod
    def process_subscriptions():
        """处理所有订阅（定时任务调用）"""
        subscriptions = ReportSubscription.query.filter_by(is_active=True).all()
        
        generated_count = 0
        
        for sub in subscriptions:
            if not ReportService.should_generate(sub):
                continue
            
            data, error = ReportService.generate_report(sub.report_type, sub.params)
            
            if error:
                continue
            
            # 保存报表
            report = GeneratedReport(
                subscription_id=sub.id,
                report_type=sub.report_type,
                report_name=sub.report_name,
                report_data=data,
                generated_at=datetime.utcnow()
            )
            db.session.add(report)
            
            # 发送通知
            notification = Notification(
                user_id=sub.user_id,
                title=f"报表已生成 - {sub.report_name}",
                content=f"您订阅的{sub.report_name}已生成，请查看。",
                type=Notification.TYPE_INFO,
                category=Notification.CATEGORY_SYSTEM,
                related_type='report',
                related_id=report.id
            )
            db.session.add(notification)
            
            sub.last_sent = datetime.utcnow()
            report.sent_count += 1
            
            generated_count += 1
        
        db.session.commit()
        return generated_count
    
    @staticmethod
    def get_user_reports(user_id, limit=20):
        """获取用户的历史报表"""
        # 获取用户订阅的报表类型
        subscribed_types = db.session.query(ReportSubscription.report_type).filter(
            ReportSubscription.user_id == user_id,
            ReportSubscription.is_active == True
        ).all()
        subscribed_types = [t[0] for t in subscribed_types]
        
        if not subscribed_types:
            # 如果没有订阅，返回用户自己生成的报表
            return GeneratedReport.query.filter(
                GeneratedReport.generated_by == user_id
            ).order_by(GeneratedReport.generated_at.desc()).limit(limit).all()
        
        # 返回订阅类型的报表或用户生成的报表
        from sqlalchemy import or_
        return GeneratedReport.query.filter(
            or_(
                GeneratedReport.report_type.in_(subscribed_types),
                GeneratedReport.generated_by == user_id
            )
        ).order_by(GeneratedReport.generated_at.desc()).limit(limit).all()
