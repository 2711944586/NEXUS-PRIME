"""报表服务 - 定时生成与订阅"""
import json
import os
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy import func, and_
from app.extensions import db
from app.models.notification import ReportSubscription, GeneratedReport, Notification, StockAlert
from app.models.trade import Order
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product
from app.models.biz import Partner
from app.models.finance import Receivable, PaymentRecord
from app.models.purchase import PurchaseOrder
from app.models.content import Attachment
from app.utils.time import utcnow


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
        },
        'supplier_performance': {
            'name': '供应商绩效',
            'description': '供应商准点率、质检通过率、采购金额和待处理订单',
            'default_frequency': 'weekly'
        },
        'financial_overview': {
            'name': '财务总览',
            'description': '应收、回款、账龄和信用占用总览',
            'default_frequency': 'daily'
        },
        'customer_operations': {
            'name': '客户经营',
            'description': '客户订单金额、未收金额、信用风险和履约状态',
            'default_frequency': 'weekly'
        },
        'capacity_plan': {
            'name': '产能计划',
            'description': '库存水位、采购到货、履约压力和仓库负载',
            'default_frequency': 'weekly'
        },
        'maintenance_overview': {
            'name': '设备维护',
            'description': 'MRO 备件、库存预警、库位和维护任务概览',
            'default_frequency': 'weekly'
        },
        'quality_inspection': {
            'name': '质量检验',
            'description': '来料批次、供应商质量率、低水位物料和异常任务概览',
            'default_frequency': 'weekly'
        },
        'contract_collection': {
            'name': '合同回款',
            'description': '合同节点、应收账龄、客户信用和回款计划概览',
            'default_frequency': 'weekly'
        },
        'service_overview': {
            'name': '售后服务',
            'description': '客户服务工单、发货订单、备件库存和服务资料概览',
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
    def create_generated_report(report_type, params=None, generated_by=None, subscription_id=None):
        data, error = ReportService.generate_report(report_type, params)
        if error:
            return None, data, error

        values = {
            'subscription_id': subscription_id,
            'report_type': report_type,
            'report_name': ReportService.REPORT_TYPES.get(report_type, {}).get('name', report_type),
            'report_data': data,
            'generated_by': getattr(generated_by, 'id', generated_by),
            'generated_at': utcnow(),
        }
        report = GeneratedReport(**values)
        db.session.add(report)
        db.session.flush()
        return report, data, None
    
    @staticmethod
    def _generate_sales_daily(params):
        """生成销售日报"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # 今日数据
        today_stats = db.session.query(
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
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
            func.sum(OrderItem.quantity * OrderItem.price_snapshot).label('amount')
        ).join(OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id
        ).filter(
            func.date(Order.created_at) == today,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(Product.id).order_by(func.sum(OrderItem.quantity * OrderItem.price_snapshot).desc()).limit(5).all()
        
        return {
            'report_date': str(today),
            'summary': {
                'order_count': today_stats.order_count or 0,
                'total_amount': float(today_stats.total_amount or 0),
                'yesterday_amount': float(yesterday_stats.total_amount or 0),
                'growth_rate': round(
                    ((today_stats.total_amount or 0) - (yesterday_stats.total_amount or 1)) 
                    / (yesterday_stats.total_amount or 1) * 100, 2
                ) if yesterday_stats.total_amount else 0
            },
            'top_products': [
                {'name': p.name, 'quantity': p.qty, 'amount': float(p.amount or 0)}
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
            InventoryLog.move_type,
            func.count(InventoryLog.id).label('count'),
            func.sum(InventoryLog.qty_change).label('total_qty')
        ).filter(
            func.date(InventoryLog.created_at) == today
        ).group_by(InventoryLog.move_type).all()
        
        return {
            'report_date': str(today),
            'movements': [
                {'type': m.move_type, 'count': m.count, 'quantity': m.total_qty}
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
            func.sum(OrderItem.quantity * OrderItem.price_snapshot).label('total_amount')
        ).join(OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id
        ).filter(
            func.date(Order.created_at) >= week_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).group_by(Product.id
        ).order_by(func.sum(OrderItem.quantity * OrderItem.price_snapshot).desc()
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
    def _generate_supplier_performance(params):
        """生成供应商绩效报表"""
        from app.models.purchase import PurchaseOrder, SupplierPerformance

        rows = (
            db.session.query(SupplierPerformance, Partner)
            .join(Partner, Partner.id == SupplierPerformance.supplier_id)
            .filter(Partner.is_deleted == False)
            .order_by(SupplierPerformance.total_amount.desc())
            .limit(30)
            .all()
        )
        pending_map = dict(
            db.session.query(PurchaseOrder.supplier_id, func.count(PurchaseOrder.id))
            .filter(
                PurchaseOrder.is_deleted == False,
                PurchaseOrder.status.in_([PurchaseOrder.STATUS_PENDING, PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL])
            )
            .group_by(PurchaseOrder.supplier_id)
            .all()
        )
        suppliers = [
            {
                'supplier': partner.name,
                'contact_person': partner.contact_person,
                'total_orders': performance.total_orders,
                'on_time_rate': performance.on_time_rate,
                'quality_rate': performance.quality_rate,
                'total_amount': float(performance.total_amount or 0),
                'pending_orders': int(pending_map.get(performance.supplier_id, 0)),
                'last_order_date': performance.last_order_date.isoformat() if performance.last_order_date else None,
            }
            for performance, partner in rows
        ]
        avg_on_time = round(sum(item['on_time_rate'] for item in suppliers) / max(len(suppliers), 1), 1)
        avg_quality = round(sum(item['quality_rate'] for item in suppliers) / max(len(suppliers), 1), 1)
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'supplier_count': len(suppliers),
                'avg_on_time_rate': avg_on_time,
                'avg_quality_rate': avg_quality,
                'total_amount': sum(item['total_amount'] for item in suppliers),
                'pending_orders': sum(item['pending_orders'] for item in suppliers),
            },
            'suppliers': suppliers,
        }

    @staticmethod
    def _generate_financial_overview(params):
        """生成财务总览报表"""
        today = datetime.now().date()
        rows = Receivable.query.filter(Receivable.is_deleted == False).all()
        total = sum(float(item.total_amount or 0) for item in rows)
        paid = sum(float(item.paid_amount or 0) for item in rows)
        unpaid = sum(float(item.unpaid_amount or 0) for item in rows)
        overdue = [item for item in rows if item.overdue_days > 0 or item.status in {Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT}]
        aging = {'未到期': 0, '1-30天': 0, '31-60天': 0, '60天以上': 0}
        for item in rows:
            if item.overdue_days <= 0:
                aging['未到期'] += float(item.unpaid_amount or 0)
            elif item.overdue_days <= 30:
                aging['1-30天'] += float(item.unpaid_amount or 0)
            elif item.overdue_days <= 60:
                aging['31-60天'] += float(item.unpaid_amount or 0)
            else:
                aging['60天以上'] += float(item.unpaid_amount or 0)
        payments = (
            db.session.query(PaymentRecord.payment_date, func.coalesce(func.sum(PaymentRecord.amount), 0))
            .filter(PaymentRecord.is_deleted == False, PaymentRecord.payment_date >= today - timedelta(days=14))
            .group_by(PaymentRecord.payment_date)
            .order_by(PaymentRecord.payment_date.asc())
            .all()
        )
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_receivable': total,
                'paid_amount': paid,
                'unpaid_amount': unpaid,
                'overdue_count': len(overdue),
                'collection_rate': round((paid / max(total, 1)) * 100, 1),
            },
            'aging': [{'name': name, 'value': amount} for name, amount in aging.items()],
            'collection_trend': [{'name': str(day), 'value': float(amount or 0)} for day, amount in payments],
        }

    @staticmethod
    def _generate_customer_operations(params):
        """生成客户经营报表"""
        rows = (
            db.session.query(
                Partner,
                func.count(Order.id).label('order_count'),
                func.coalesce(func.sum(Order.total_amount), 0).label('order_amount')
            )
            .outerjoin(Order, Order.customer_id == Partner.id)
            .filter(Partner.is_deleted == False, Partner.type == Partner.TYPE_CUSTOMER)
            .group_by(Partner.id)
            .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
            .limit(30)
            .all()
        )
        receivable_map = dict(
            db.session.query(Receivable.customer_id, func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0))
            .filter(Receivable.is_deleted == False)
            .group_by(Receivable.customer_id)
            .all()
        )
        customers = [
            {
                'customer': partner.name,
                'contact_person': partner.contact_person,
                'credit_score': partner.credit_score,
                'order_count': int(order_count or 0),
                'order_amount': float(order_amount or 0),
                'unpaid_amount': float(receivable_map.get(partner.id, 0) or 0),
            }
            for partner, order_count, order_amount in rows
        ]
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'customer_count': len(customers),
                'order_amount': sum(item['order_amount'] for item in customers),
                'unpaid_amount': sum(item['unpaid_amount'] for item in customers),
                'avg_credit_score': round(sum(item['credit_score'] or 0 for item in customers) / max(len(customers), 1), 1),
            },
            'customers': customers,
        }

    @staticmethod
    def _generate_capacity_plan(params):
        """生成产能计划报表"""
        stock_total = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).filter(Stock.is_deleted == False).scalar()
        low_stock = (
            db.session.query(Product.name, Product.sku, Product.min_stock, func.coalesce(func.sum(Stock.quantity), 0).label('qty'))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .having(func.coalesce(func.sum(Stock.quantity), 0) <= Product.min_stock)
            .order_by((Product.min_stock - func.coalesce(func.sum(Stock.quantity), 0)).desc())
            .limit(20)
            .all()
        )
        purchase_status = (
            db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
            .filter(PurchaseOrder.is_deleted == False)
            .group_by(PurchaseOrder.status)
            .all()
        )
        order_status = (
            db.session.query(Order.status, func.count(Order.id))
            .filter(Order.is_deleted == False)
            .group_by(Order.status)
            .all()
        )
        warehouse_load = (
            db.session.query(Warehouse.name, Warehouse.capacity, func.coalesce(func.sum(Stock.quantity), 0))
            .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
            .filter(Warehouse.is_deleted == False)
            .group_by(Warehouse.id)
            .all()
        )
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'stock_quantity': int(stock_total or 0),
                'low_stock_count': len(low_stock),
                'pending_purchase': sum(count for status, count in purchase_status if status in {'draft', 'pending', 'approved', 'partial'}),
                'active_orders': sum(count for status, count in order_status if status in {'pending', 'paid', 'shipped'}),
            },
            'low_stock': [{'name': name, 'sku': sku, 'gap': max(int(min_stock or 0) - int(qty or 0), 0)} for name, sku, min_stock, qty in low_stock],
            'purchase_status': [{'name': status or 'unknown', 'value': int(count or 0)} for status, count in purchase_status],
            'order_status': [{'name': status or 'unknown', 'value': int(count or 0)} for status, count in order_status],
            'warehouse_load': [
                {'name': name, 'capacity': int(capacity or 0), 'stock_quantity': int(quantity or 0)}
                for name, capacity, quantity in warehouse_load
            ],
        }

    @staticmethod
    def _generate_maintenance_overview(params):
        """生成设备维护报表"""
        mro_products = (
            db.session.query(Product.name, Product.sku, Product.min_stock, func.coalesce(func.sum(Stock.quantity), 0).label('qty'))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .order_by(Product.name.asc())
            .limit(40)
            .all()
        )
        alerts = StockAlert.query.filter_by(is_deleted=False, status=StockAlert.STATUS_ACTIVE).count()
        stock_locations = (
            db.session.query(Warehouse.name, func.count(Stock.id))
            .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
            .filter(Warehouse.is_deleted == False)
            .group_by(Warehouse.id)
            .all()
        )
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'mro_item_count': len(mro_products),
                'active_alerts': alerts,
                'low_parts': len([item for item in mro_products if int(item.qty or 0) <= int(item.min_stock or 0)]),
            },
            'parts': [
                {'name': name, 'sku': sku, 'quantity': int(qty or 0), 'min_stock': int(min_stock or 0)}
                for name, sku, min_stock, qty in mro_products
            ],
            'stock_locations': [{'name': name or '未命名仓', 'value': int(count or 0)} for name, count in stock_locations],
        }

    @staticmethod
    def _generate_quality_inspection(params):
        """生成质量检验报表"""
        from app.models.purchase import SupplierPerformance

        supplier_rows = (
            db.session.query(SupplierPerformance, Partner)
            .join(Partner, Partner.id == SupplierPerformance.supplier_id)
            .filter(Partner.is_deleted == False)
            .order_by(SupplierPerformance.quality_rate.asc(), SupplierPerformance.on_time_rate.asc())
            .limit(30)
            .all()
        )
        low_stock = (
            db.session.query(Product.name, Product.sku, Product.min_stock, func.coalesce(func.sum(Stock.quantity), 0).label('qty'))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .having(func.coalesce(func.sum(Stock.quantity), 0) <= Product.min_stock)
            .order_by((Product.min_stock - func.coalesce(func.sum(Stock.quantity), 0)).desc())
            .limit(20)
            .all()
        )
        purchase_status = (
            db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
            .filter(PurchaseOrder.is_deleted == False)
            .group_by(PurchaseOrder.status)
            .all()
        )
        suppliers = [
            {
                'supplier': partner.name,
                'on_time_rate': performance.on_time_rate,
                'quality_rate': performance.quality_rate,
                'total_orders': performance.total_orders,
                'total_amount': float(performance.total_amount or 0),
            }
            for performance, partner in supplier_rows
        ]
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'supplier_count': len(suppliers),
                'quality_alerts': len([item for item in suppliers if float(item['quality_rate'] or 0) < 92]),
                'low_stock_count': len(low_stock),
                'purchase_batches': sum(int(count or 0) for _status, count in purchase_status),
                'avg_quality_rate': round(sum(float(item['quality_rate'] or 0) for item in suppliers) / max(len(suppliers), 1), 1),
            },
            'suppliers': suppliers,
            'low_stock': [{'name': name, 'sku': sku, 'quantity': int(qty or 0), 'min_stock': int(min_stock or 0)} for name, sku, min_stock, qty in low_stock],
            'purchase_status': [{'name': status or 'unknown', 'value': int(count or 0)} for status, count in purchase_status],
        }

    @staticmethod
    def _generate_contract_collection(params):
        """生成合同回款报表"""
        rows = Receivable.query.filter(Receivable.is_deleted == False).all()
        overdue = [item for item in rows if item.overdue_days > 0 or item.status in {Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT}]
        by_customer = {}
        for item in rows:
            customer = item.customer.name if item.customer else '未关联客户'
            by_customer.setdefault(customer, {'customer': customer, 'total_amount': 0.0, 'paid_amount': 0.0, 'unpaid_amount': 0.0, 'overdue_count': 0})
            by_customer[customer]['total_amount'] += float(item.total_amount or 0)
            by_customer[customer]['paid_amount'] += float(item.paid_amount or 0)
            by_customer[customer]['unpaid_amount'] += float(item.unpaid_amount or 0)
            if item in overdue:
                by_customer[customer]['overdue_count'] += 1
        aging = {'未到期': 0.0, '1-30天': 0.0, '31-60天': 0.0, '60天以上': 0.0}
        for item in rows:
            if item.overdue_days <= 0:
                aging['未到期'] += float(item.unpaid_amount or 0)
            elif item.overdue_days <= 30:
                aging['1-30天'] += float(item.unpaid_amount or 0)
            elif item.overdue_days <= 60:
                aging['31-60天'] += float(item.unpaid_amount or 0)
            else:
                aging['60天以上'] += float(item.unpaid_amount or 0)
        customers = sorted(by_customer.values(), key=lambda item: item['unpaid_amount'], reverse=True)[:30]
        total = sum(float(item.total_amount or 0) for item in rows)
        paid = sum(float(item.paid_amount or 0) for item in rows)
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'contract_count': len(rows),
                'total_amount': total,
                'paid_amount': paid,
                'unpaid_amount': total - paid,
                'overdue_count': len(overdue),
                'collection_rate': round((paid / max(total, 1)) * 100, 1),
            },
            'aging': [{'name': name, 'value': value} for name, value in aging.items()],
            'customers': customers,
        }

    @staticmethod
    def _generate_service_overview(params):
        """生成售后服务报表"""
        service_orders = Order.query.filter(
            Order.is_deleted == False,
            Order.status.in_([Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE])
        ).order_by(Order.created_at.desc()).limit(50).all()
        low_parts = (
            db.session.query(Product.name, Product.sku, Product.min_stock, func.coalesce(func.sum(Stock.quantity), 0).label('qty'))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .having(func.coalesce(func.sum(Stock.quantity), 0) <= Product.min_stock)
            .limit(20)
            .all()
        )
        attachments = Attachment.query.filter(Attachment.is_deleted == False).order_by(Attachment.created_at.desc()).limit(20).all()
        order_status = (
            db.session.query(Order.status, func.count(Order.id))
            .filter(Order.is_deleted == False)
            .group_by(Order.status)
            .all()
        )
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'service_order_count': len(service_orders),
                'low_part_count': len(low_parts),
                'service_file_count': len(attachments),
                'active_customer_count': len({item.customer_id for item in service_orders if item.customer_id}),
            },
            'orders': [
                {
                    'order_no': item.order_no,
                    'customer': item.customer.name if item.customer else '',
                    'status': item.status,
                    'amount': float(item.total_amount or 0),
                }
                for item in service_orders[:20]
            ],
            'low_parts': [{'name': name, 'sku': sku, 'quantity': int(qty or 0), 'min_stock': int(min_stock or 0)} for name, sku, min_stock, qty in low_parts],
            'files': [{'filename': item.filename, 'mimetype': item.mimetype, 'size': item.size} for item in attachments],
            'order_status': [{'name': status or 'unknown', 'value': int(count or 0)} for status, count in order_status],
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
                generated_at=utcnow()
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
            
            sub.last_sent = utcnow()
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
