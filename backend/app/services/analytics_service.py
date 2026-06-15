from datetime import datetime, timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.models.biz import Partner, Product
from app.models.content import Article, ArticleComment, Attachment
from app.models.finance import CustomerCredit, PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder, SupplierPerformance
from app.models.stock import InventoryLog, Stock, Warehouse
from app.models.sys import AuditLog
from app.models.trade import Order
from app.utils.time import utcnow


def executive_analytics_payload():
    total_sales = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(Order.is_deleted == False).scalar()
    unpaid_amount = db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)).filter(Receivable.is_deleted == False).scalar()
    pending_purchase = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).count()
    active_alerts = StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE, is_deleted=False).count()
    articles_count = Article.query.filter_by(status='published', is_deleted=False).count()
    comments_count = ArticleComment.query.filter_by(is_deleted=False).count()

    today = utcnow().date()
    start_day = today - timedelta(days=20)
    sales_by_day = {
        str(day): float(value or 0)
        for day, value in db.session.query(func.date(Order.created_at), func.coalesce(func.sum(Order.total_amount), 0))
        .filter(
            Order.is_deleted == False,
            Order.created_at >= datetime.combine(start_day, datetime.min.time()),
        )
        .group_by(func.date(Order.created_at))
        .all()
    }
    cash_by_day = {
        str(day): float(value or 0)
        for day, value in db.session.query(func.date(Receivable.updated_at), func.coalesce(func.sum(Receivable.paid_amount), 0))
        .filter(
            Receivable.is_deleted == False,
            Receivable.updated_at >= datetime.combine(start_day, datetime.min.time()),
        )
        .group_by(func.date(Receivable.updated_at))
        .all()
    }
    sales_trend = []
    cash_collection_trend = []
    for days in range(20, -1, -1):
        day = today - timedelta(days=days)
        key = day.isoformat()
        sales_trend.append({'name': day.strftime('%m-%d'), 'value': sales_by_day.get(key, 0)})
        cash_collection_trend.append({'name': day.strftime('%m-%d'), 'value': cash_by_day.get(key, 0)})

    overdue_receivables = Receivable.query.filter(Receivable.is_deleted == False, Receivable.status == Receivable.STATUS_OVERDUE).count()
    frozen_credits = CustomerCredit.query.filter_by(is_frozen=True, is_deleted=False).count()
    risk_mix = [
        {'name': '库存预警', 'value': active_alerts},
        {'name': '采购审批', 'value': pending_purchase},
        {'name': '逾期应收', 'value': overdue_receivables},
        {'name': '信用冻结', 'value': frozen_credits},
    ]
    collaboration = [
        {'name': '公告', 'value': articles_count},
        {'name': '评论', 'value': comments_count},
        {'name': '通知', 'value': Notification.query.filter_by(is_deleted=False).count()},
        {'name': '文件', 'value': Attachment.query.filter_by(is_deleted=False).count()},
    ]
    top_customers = (
        db.session.query(Partner.name, func.coalesce(func.sum(Order.total_amount), 0))
        .join(Order, Order.customer_id == Partner.id)
        .filter(Order.is_deleted == False, Partner.is_deleted == False)
        .group_by(Partner.id)
        .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
        .limit(8)
        .all()
    )
    procurement_stages = (
        db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.is_deleted == False)
        .group_by(PurchaseOrder.status)
        .all()
    )
    aging_buckets = [
        {
            'name': '未到期',
            'value': float(db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)).filter(
                Receivable.is_deleted == False,
                Receivable.status != Receivable.STATUS_PAID,
                or_(Receivable.due_date == None, Receivable.due_date >= today),
            ).scalar() or 0),
        },
        {
            'name': '1-30天',
            'value': float(db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)).filter(
                Receivable.is_deleted == False,
                Receivable.status != Receivable.STATUS_PAID,
                Receivable.due_date < today,
                Receivable.due_date >= today - timedelta(days=30),
            ).scalar() or 0),
        },
        {
            'name': '31-60天',
            'value': float(db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)).filter(
                Receivable.is_deleted == False,
                Receivable.status != Receivable.STATUS_PAID,
                Receivable.due_date < today - timedelta(days=30),
                Receivable.due_date >= today - timedelta(days=60),
            ).scalar() or 0),
        },
        {
            'name': '60天以上',
            'value': float(db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)).filter(
                Receivable.is_deleted == False,
                Receivable.status != Receivable.STATUS_PAID,
                Receivable.due_date < today - timedelta(days=60),
            ).scalar() or 0),
        },
    ]
    action_queue = [
        {
            'title': '低库存补货',
            'module': '库存',
            'priority': 'high' if active_alerts else 'normal',
            'metric': f'{active_alerts} 项',
            'path': '/app/inventory/replenishment',
            'description': '根据安全库存、当前库存和供应商交期生成补货建议。',
        },
        {
            'title': '采购审批',
            'module': '采购',
            'priority': 'high' if pending_purchase else 'normal',
            'metric': f'{pending_purchase} 单',
            'path': '/app/procurement/orders',
            'description': '优先处理金额较高、影响收货入库的采购单。',
        },
        {
            'title': '应收跟进',
            'module': '财务',
            'priority': 'high' if unpaid_amount else 'normal',
            'metric': f'{float(unpaid_amount or 0):.0f}',
            'path': '/app/finance/receivables',
            'description': '按账龄和客户信用占用安排催款、收款或冻结动作。',
        },
        {
            'title': '经营日报',
            'module': '报表',
            'priority': 'normal',
            'metric': f'{GeneratedReport.query.filter_by(is_deleted=False).count()} 份',
            'path': '/app/reports',
            'description': '归档库存、采购、履约和应收指标，形成班次复盘材料。',
        },
    ]
    stock_by_warehouse = (
        db.session.query(
            Stock.warehouse_id.label('warehouse_id'),
            func.coalesce(func.sum(Stock.quantity), 0).label('stock_quantity'),
        )
        .filter(Stock.is_deleted == False)
        .group_by(Stock.warehouse_id)
        .subquery()
    )
    movement_by_warehouse = (
        db.session.query(
            InventoryLog.warehouse_id.label('warehouse_id'),
            func.count(InventoryLog.id).label('movement_count'),
        )
        .filter(InventoryLog.is_deleted == False)
        .group_by(InventoryLog.warehouse_id)
        .subquery()
    )
    warehouse_turnover = (
        db.session.query(
            Warehouse.name,
            func.coalesce(stock_by_warehouse.c.stock_quantity, 0),
            func.coalesce(movement_by_warehouse.c.movement_count, 0),
        )
        .outerjoin(stock_by_warehouse, stock_by_warehouse.c.warehouse_id == Warehouse.id)
        .outerjoin(movement_by_warehouse, movement_by_warehouse.c.warehouse_id == Warehouse.id)
        .filter(Warehouse.is_deleted == False)
        .order_by(func.coalesce(stock_by_warehouse.c.stock_quantity, 0).desc())
        .limit(8)
        .all()
    )
    supplier_score = (
        db.session.query(Partner.name, SupplierPerformance.on_time_orders, SupplierPerformance.total_orders, SupplierPerformance.quality_pass_orders)
        .join(SupplierPerformance, SupplierPerformance.supplier_id == Partner.id)
        .filter(Partner.is_deleted == False)
        .order_by(SupplierPerformance.total_amount.desc())
        .limit(6)
        .all()
    )
    inventory_risk_rank = (
        db.session.query(Product.name, Product.sku, Product.min_stock, func.coalesce(func.sum(Stock.quantity), 0).label('qty'))
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .having(func.coalesce(func.sum(Stock.quantity), 0) < Product.min_stock)
        .order_by((Product.min_stock - func.coalesce(func.sum(Stock.quantity), 0)).desc())
        .limit(8)
        .all()
    )
    order_status_flow = (
        db.session.query(Order.status, func.count(Order.id))
        .filter(Order.is_deleted == False)
        .group_by(Order.status)
        .all()
    )
    completed_orders = sum(count for status, count in order_status_flow if status in {Order.STATUS_DONE, Order.STATUS_SHIPPED, Order.STATUS_PAID})
    total_orders = sum(count for _status, count in order_status_flow)
    received_purchase = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status == PurchaseOrder.STATUS_RECEIVED).count()
    total_purchase = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).count()
    total_stock = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).filter(Stock.is_deleted == False).scalar()
    stock_capacity = db.session.query(func.coalesce(func.sum(Warehouse.capacity), 0)).filter(Warehouse.is_deleted == False).scalar()
    report_count = GeneratedReport.query.filter_by(is_deleted=False).count()
    unread_notifications = Notification.query.filter_by(is_deleted=False, is_read=False).count()
    inventory_log_count = InventoryLog.query.filter(InventoryLog.is_deleted == False).count()
    purchase_blocked = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING])).count()
    fulfillment_todo = Order.query.filter(Order.is_deleted == False, Order.status.in_([Order.STATUS_PENDING, Order.STATUS_PAID])).count()
    fulfillment_blocked = Order.query.filter(Order.is_deleted == False, Order.status == Order.STATUS_CANCEL).count()
    payment_count = PaymentRecord.query.filter(PaymentRecord.is_deleted == False).count()
    module_throughput = [
        {
            'name': '库存',
            'todo': active_alerts,
            'done': int(inventory_log_count),
            'blocked': len(inventory_risk_rank),
        },
        {
            'name': '采购',
            'todo': pending_purchase,
            'done': received_purchase,
            'blocked': purchase_blocked,
        },
        {
            'name': '履约',
            'todo': fulfillment_todo,
            'done': completed_orders,
            'blocked': fulfillment_blocked,
        },
        {
            'name': '财务',
            'todo': overdue_receivables,
            'done': payment_count,
            'blocked': frozen_credits,
        },
        {
            'name': '协作',
            'todo': unread_notifications,
            'done': articles_count + comments_count + report_count,
            'blocked': 0,
        },
    ]
    operational_efficiency = [
        {'name': '履约完成率', 'value': round(completed_orders / max(total_orders, 1) * 100, 1), 'target': 92},
        {'name': '采购闭环率', 'value': round(received_purchase / max(total_purchase, 1) * 100, 1), 'target': 88},
        {'name': '库存容量利用', 'value': round(float(total_stock or 0) / max(float(stock_capacity or 1), 1) * 100, 1), 'target': 76},
        {'name': '回款覆盖率', 'value': round((float(total_sales or 0) - float(unpaid_amount or 0)) / max(float(total_sales or 1), 1) * 100, 1), 'target': 86},
        {'name': '协作处理率', 'value': round((articles_count + comments_count + report_count) / max(articles_count + comments_count + report_count + unread_notifications, 1) * 100, 1), 'target': 90},
    ]
    return {
        'kpis': {
            'total_sales': float(total_sales or 0),
            'unpaid_amount': float(unpaid_amount or 0),
            'pending_purchase': pending_purchase,
            'active_alerts': active_alerts,
            'collaboration_items': articles_count + comments_count,
        },
        'sales_trend': sales_trend,
        'risk_mix': risk_mix,
        'collaboration': collaboration,
        'top_customers': [{'name': name or '未命名客户', 'value': float(value or 0)} for name, value in top_customers],
        'procurement_stages': [{'name': status or 'unknown', 'value': count} for status, count in procurement_stages],
        'aging_buckets': aging_buckets,
        'action_queue': action_queue,
        'warehouse_turnover': [
            {'name': name or '未命名仓', 'stock_quantity': int(quantity or 0), 'movement_count': int(moves or 0)}
            for name, quantity, moves in warehouse_turnover
        ],
        'supplier_score': [
            {
                'name': name or '未命名供应商',
                'on_time_rate': round((on_time or 0) / max(total or 1, 1) * 100, 1),
                'quality_rate': round((quality or 0) / max(total or 1, 1) * 100, 1),
            }
            for name, on_time, total, quality in supplier_score
        ],
        'inventory_risk_rank': [
            {
                'name': name,
                'sku': sku,
                'gap': max(int(min_stock or 0) - int(qty or 0), 0),
                'current_qty': int(qty or 0),
            }
            for name, sku, min_stock, qty in inventory_risk_rank
        ],
        'order_status_flow': [{'name': status or 'unknown', 'value': int(count or 0)} for status, count in order_status_flow],
        'cash_collection_trend': cash_collection_trend,
        'operational_efficiency': operational_efficiency,
        'module_throughput': module_throughput,
    }


def manufacturing_workflow_board_payload():
    """Build the cross-module daily operating workflow for the Angular cockpit."""
    today = utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())

    low_stock_rows = (
        db.session.query(
            Product.name,
            Product.sku,
            Product.min_stock,
            func.coalesce(func.sum(Stock.quantity), 0).label('total_stock'),
        )
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .having(func.coalesce(func.sum(Stock.quantity), 0) <= func.coalesce(Product.min_stock, 0))
        .order_by((func.coalesce(Product.min_stock, 0) - func.coalesce(func.sum(Stock.quantity), 0)).desc())
        .limit(6)
        .all()
    )
    active_alerts = StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE, is_deleted=False).count()
    low_stock_count = max(active_alerts, len(low_stock_rows))

    suggestions_total = ReplenishmentSuggestion.query.filter(ReplenishmentSuggestion.is_deleted == False).count()
    suggestions_pending = ReplenishmentSuggestion.query.filter_by(status=ReplenishmentSuggestion.STATUS_PENDING, is_deleted=False).count()
    suggestions_done = ReplenishmentSuggestion.query.filter(
        ReplenishmentSuggestion.is_deleted == False,
        ReplenishmentSuggestion.status.in_([
            ReplenishmentSuggestion.STATUS_ACCEPTED,
            ReplenishmentSuggestion.STATUS_ORDERED,
        ]),
    ).count()

    purchase_total = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).count()
    purchase_pending = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING]),
    ).count()
    purchase_received = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_RECEIVED, is_deleted=False).count()
    pending_purchase_rows = (
        PurchaseOrder.query
        .filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING]))
        .order_by(PurchaseOrder.total_amount.desc(), PurchaseOrder.created_at.asc())
        .limit(4)
        .all()
    )

    receiving_rows = (
        PurchaseOrder.query
        .filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_([PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL]))
        .order_by(PurchaseOrder.expected_date.asc(), PurchaseOrder.updated_at.asc())
        .limit(6)
        .all()
    )
    receiving_progress = round(sum(order.receive_progress for order in receiving_rows) / max(len(receiving_rows), 1))

    fulfillment_open = Order.query.filter(
        Order.is_deleted == False,
        Order.status.in_([Order.STATUS_PENDING, Order.STATUS_PAID]),
    ).count()
    fulfillment_done = Order.query.filter(
        Order.is_deleted == False,
        Order.status.in_([Order.STATUS_SHIPPED, Order.STATUS_DONE]),
    ).count()
    fulfillment_total = Order.query.filter(Order.is_deleted == False).count()
    open_order_rows = (
        Order.query
        .filter(Order.is_deleted == False, Order.status.in_([Order.STATUS_PENDING, Order.STATUS_PAID]))
        .order_by(Order.total_amount.desc(), Order.created_at.asc())
        .limit(4)
        .all()
    )

    total_receivable = db.session.query(func.coalesce(func.sum(Receivable.total_amount), 0)).filter(Receivable.is_deleted == False).scalar()
    paid_receivable = db.session.query(func.coalesce(func.sum(Receivable.paid_amount), 0)).filter(Receivable.is_deleted == False).scalar()
    overdue_rows = (
        Receivable.query
        .filter(Receivable.is_deleted == False, Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT]))
        .order_by(Receivable.due_date.asc())
        .limit(5)
        .all()
    )
    overdue_amount = sum(float(item.unpaid_amount or 0) for item in overdue_rows)

    reports_today = GeneratedReport.query.filter(
        GeneratedReport.is_deleted == False,
        GeneratedReport.generated_at >= start_of_day,
    ).count()
    report_total = GeneratedReport.query.filter_by(is_deleted=False).count()
    recent_reports = (
        GeneratedReport.query
        .filter_by(is_deleted=False)
        .order_by(GeneratedReport.generated_at.desc())
        .limit(4)
        .all()
    )

    audit_today = AuditLog.query.filter(AuditLog.is_deleted == False, AuditLog.created_at >= start_of_day).count()
    audit_total = AuditLog.query.filter_by(is_deleted=False).count()
    evidence_files = Attachment.query.filter_by(is_deleted=False).count()
    unread_notifications = Notification.query.filter_by(is_deleted=False, is_read=False).count()
    payments_today = PaymentRecord.query.filter(
        PaymentRecord.is_deleted == False,
        PaymentRecord.payment_date >= today,
    ).count()

    stages = [
        {
            'key': 'inventory-signal',
            'code': '01',
            'label': '库存信号',
            'owner': '仓配运营',
            'path': '/app/inventory/replenishment',
            'value': f'{low_stock_count} 项',
            'detail': '安全库存、库位水位和补货建议的入口。',
            'progress': clamp_progress(100 - low_stock_count * 7),
            'status': 'attention' if low_stock_count else 'complete',
            'next_action': '生成补货建议' if low_stock_count else '复核库位热区',
            'sla': '15 分钟内分派',
            'records': [
                {
                    'label': name or sku or '未命名物料',
                    'metric': f'缺口 {max(int(min_stock or 0) - int(total_stock or 0), 0)}',
                    'meta': f'{sku or "-"} · 当前 {int(total_stock or 0)}',
                    'path': '/app/inventory/replenishment',
                }
                for name, sku, min_stock, total_stock in low_stock_rows[:3]
            ],
        },
        {
            'key': 'replenishment',
            'code': '02',
            'label': '补货建议',
            'owner': '计划员',
            'path': '/app/inventory/replenishment',
            'value': f'{suggestions_pending} 条',
            'detail': '把低库存对象转成可审批采购草稿。',
            'progress': ratio_progress(suggestions_done, suggestions_total),
            'status': 'attention' if suggestions_pending else 'ready',
            'next_action': '接受建议并转采购',
            'sla': '当班完成',
            'records': [],
        },
        {
            'key': 'procurement-approval',
            'code': '03',
            'label': '采购审批',
            'owner': '采购主管',
            'path': '/app/procurement/orders',
            'value': f'{purchase_pending} 单',
            'detail': '金额、供应商、收货仓和补货来源共同决定优先级。',
            'progress': ratio_progress(purchase_received, purchase_total),
            'status': 'attention' if purchase_pending else 'complete',
            'next_action': '审批下一张采购单',
            'sla': '2 小时内审批',
            'records': [
                {
                    'label': item.po_no,
                    'metric': money_compact(item.total_amount),
                    'meta': item.supplier.name if item.supplier else '未绑定供应商',
                    'path': f'/app/procurement/orders/{item.id}',
                }
                for item in pending_purchase_rows
            ],
        },
        {
            'key': 'receiving',
            'code': '04',
            'label': '收货入库',
            'owner': '仓库月台',
            'path': '/app/procurement/orders',
            'value': f'{len(receiving_rows)} 单',
            'detail': '已批准采购进入到货、质检、入库和供应商绩效回写。',
            'progress': receiving_progress,
            'status': 'attention' if receiving_rows else 'ready',
            'next_action': '推进到货收货',
            'sla': '到货当天确认',
            'records': [
                {
                    'label': item.po_no,
                    'metric': f'{int(item.receive_progress)}%',
                    'meta': item.warehouse.name if item.warehouse else '未绑定仓库',
                    'path': f'/app/procurement/orders/{item.id}',
                }
                for item in receiving_rows[:3]
            ],
        },
        {
            'key': 'fulfillment',
            'code': '05',
            'label': '销售履约',
            'owner': '履约调度',
            'path': '/app/sales/orders',
            'value': f'{fulfillment_open} 单',
            'detail': '订单经过信用校验、库存锁定、发货和签收。',
            'progress': ratio_progress(fulfillment_done, fulfillment_total),
            'status': 'attention' if fulfillment_open else 'complete',
            'next_action': '推进发货出库',
            'sla': '客户窗口前发货',
            'records': [
                {
                    'label': item.order_no,
                    'metric': money_compact(item.total_amount),
                    'meta': item.customer.name if item.customer else '未绑定客户',
                    'path': f'/app/sales/orders/{item.id}',
                }
                for item in open_order_rows
            ],
        },
        {
            'key': 'cash-collection',
            'code': '06',
            'label': '应收回款',
            'owner': '财务风控',
            'path': '/app/finance/receivables',
            'value': money_compact(overdue_amount),
            'detail': '回款动作释放信用额度，并把风险写回客户画像。',
            'progress': ratio_progress(float(paid_receivable or 0), float(total_receivable or 0)),
            'status': 'blocked' if overdue_amount > 0 else 'complete',
            'next_action': '处理逾期应收',
            'sla': 'T+1 跟进',
            'records': [
                {
                    'label': item.receivable_no,
                    'metric': money_compact(item.unpaid_amount),
                    'meta': item.customer.name if item.customer else '未绑定客户',
                    'path': f'/app/finance/receivables/{item.id}',
                }
                for item in overdue_rows[:3]
            ],
        },
        {
            'key': 'reporting',
            'code': '07',
            'label': '报表归档',
            'owner': '经营分析',
            'path': '/app/reports',
            'value': f'{reports_today} 份',
            'detail': '库存、采购、履约、应收和客户经营日报归档。',
            'progress': 100 if reports_today else min(78, report_total * 6),
            'status': 'complete' if reports_today else 'attention',
            'next_action': '生成经营日报',
            'sla': '每日 08:30 前',
            'records': [
                {
                    'label': item.report_name,
                    'metric': item.report_type or 'report',
                    'meta': item.generated_at.strftime('%m-%d %H:%M') if item.generated_at else '未生成时间',
                    'path': f'/app/reports/{item.id}',
                }
                for item in recent_reports[:3]
            ],
        },
        {
            'key': 'audit',
            'code': '08',
            'label': '审计追溯',
            'owner': '系统治理',
            'path': '/app/system/audit',
            'value': f'{audit_today} 条',
            'detail': '关键动作、文件、权限和接口调用进入可追溯日志。',
            'progress': 100 if audit_today else min(88, audit_total),
            'status': 'complete' if audit_today else 'ready',
            'next_action': '复核异常日志',
            'sla': '实时留痕',
            'records': [],
        },
    ]

    bottlenecks = sorted(
        [
            build_bottleneck(stage)
            for stage in stages
            if stage['status'] in {'attention', 'blocked'}
        ],
        key=lambda item: item['rank'],
    )[:5]
    handoffs = [
        {'from': stages[index]['label'], 'to': stages[index + 1]['label'], 'value': max(1, stages[index + 1]['progress']), 'label': stages[index + 1]['next_action']}
        for index in range(len(stages) - 1)
    ]
    health_score = clamp_progress(round(sum(stage['progress'] for stage in stages) / max(len(stages), 1)))
    blocked_count = sum(1 for stage in stages if stage['status'] == 'blocked')
    attention_count = sum(1 for stage in stages if stage['status'] == 'attention')
    next_stage = next((stage for stage in stages if stage['status'] in {'blocked', 'attention'}), stages[0])
    action_queue = build_workflow_action_queue(stages, bottlenecks)
    execution_events = build_workflow_execution_events()
    role_command_center = build_role_command_center(
        stages,
        {
            'low_stock_count': low_stock_count,
            'suggestions_pending': suggestions_pending,
            'purchase_pending': purchase_pending,
            'receiving_open': len(receiving_rows),
            'fulfillment_open': fulfillment_open,
            'overdue_amount': overdue_amount,
            'reports_today': reports_today,
            'audit_today': audit_today,
            'health_score': health_score,
            'open_action_count': len(action_queue),
        },
    )
    data_contracts = build_workflow_data_contracts(
        {
            'stages': len(stages),
            'events': len(execution_events),
            'services': 4,
            'checks': 4,
            'reports': report_total,
            'audit': audit_total,
        }
    )

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'manufacturing-workflow-board',
        'summary': {
            'title': '每日制造经营作战流',
            'health_score': health_score,
            'active_stages': len(stages),
            'attention_count': attention_count,
            'blocked_count': blocked_count,
            'next_action': next_stage['next_action'],
            'next_path': next_stage['path'],
            'cadence': '库存、采购、履约、回款、归档同屏复盘',
            'shift_window': '08:30-18:00',
            'commander': '制造运营负责人',
            'evidence_count': evidence_files + report_total + audit_total,
            'open_action_count': len(action_queue),
        },
        'stages': stages,
        'handoffs': handoffs,
        'bottlenecks': bottlenecks,
        'action_queue': action_queue,
        'service_boundaries': [
            {
                'name': '制造经营聚合 API',
                'owner': '运营中台',
                'surface': '/api/v1/manufacturing/*',
                'contract': '只读聚合库存、采购、履约、应收、报表和审计数据。',
                'deploy_unit': 'backend Flask API',
                'readiness': 'ready',
            },
            {
                'name': '库存与补货服务边界',
                'owner': '仓配运营',
                'surface': '/products, /stock, /replenishment',
                'contract': '低库存、补货建议、库位水位和库存流水可独立拆分。',
                'deploy_unit': 'inventory module',
                'readiness': 'attention' if low_stock_count or suggestions_pending else 'ready',
            },
            {
                'name': '采购履约服务边界',
                'owner': '采购与履约',
                'surface': '/purchase-orders, /orders',
                'contract': '采购审批、收货入库、客户订单和发货状态形成跨域事件。',
                'deploy_unit': 'procurement + sales modules',
                'readiness': 'attention' if purchase_pending or fulfillment_open else 'ready',
            },
            {
                'name': '财务风控服务边界',
                'owner': '财务风控',
                'surface': '/receivables, /credits, /payments',
                'contract': '应收账龄、收款记录和信用占用支撑风险闭环。',
                'deploy_unit': 'finance module',
                'readiness': 'blocked' if overdue_amount > 0 else 'ready',
            },
        ],
        'deployment_checks': [
            {
                'key': 'auth',
                'label': '认证与审计链路',
                'status': 'ready' if audit_today else 'attention',
                'owner': '系统治理',
                'evidence': f'今日审计 {audit_today} 条 / 历史 {audit_total} 条',
            },
            {
                'key': 'evidence',
                'label': '报表与文件证据',
                'status': 'ready' if report_total or evidence_files else 'attention',
                'owner': '经营分析',
                'evidence': f'报表 {report_total} 份 / 文件 {evidence_files} 个',
            },
            {
                'key': 'notifications',
                'label': '通知待办水位',
                'status': 'attention' if unread_notifications else 'ready',
                'owner': '协同中台',
                'evidence': f'未读通知 {unread_notifications} 条',
            },
            {
                'key': 'cash',
                'label': '回款写入能力',
                'status': 'ready' if payments_today or not overdue_amount else 'attention',
                'owner': '财务风控',
                'evidence': f'今日收款 {payments_today} 笔',
            },
        ],
        'role_views': [
            {'role': '运营负责人', 'focus': '健康分、阻塞阶段、当班下一步动作'},
            {'role': '仓配与采购', 'focus': '低库存、补货建议、采购审批、收货入库'},
            {'role': '财务与经营分析', 'focus': '应收风险、信用释放、报表归档和审计追溯'},
        ],
        'role_command_center': role_command_center,
        'execution_events': execution_events,
        'data_contracts': data_contracts,
    }


def erp_control_tower_payload():
    """Build the top-level ERP control tower contract used by the Angular cockpit."""
    executive = executive_analytics_payload()
    workflow = manufacturing_workflow_board_payload()
    kpis = executive['kpis']
    workflow_summary = workflow['summary']

    total_sales = float(kpis.get('total_sales') or 0)
    unpaid_amount = float(kpis.get('unpaid_amount') or 0)
    active_alerts = int(kpis.get('active_alerts') or 0)
    pending_purchase = int(kpis.get('pending_purchase') or 0)
    collaboration_items = int(kpis.get('collaboration_items') or 0)

    products = Product.query.filter_by(is_deleted=False).count()
    partners = Partner.query.filter_by(is_deleted=False).count()
    warehouses = Warehouse.query.filter_by(is_deleted=False).count()
    orders = Order.query.filter_by(is_deleted=False).count()
    purchases = PurchaseOrder.query.filter_by(is_deleted=False).count()
    receivables = Receivable.query.filter_by(is_deleted=False).count()
    reports = GeneratedReport.query.filter_by(is_deleted=False).count()
    attachments = Attachment.query.filter_by(is_deleted=False).count()
    audits = AuditLog.query.filter_by(is_deleted=False).count()
    notifications = Notification.query.filter_by(is_deleted=False).count()
    open_notifications = Notification.query.filter_by(is_deleted=False, is_read=False).count()
    replenishment_pending = ReplenishmentSuggestion.query.filter_by(
        status=ReplenishmentSuggestion.STATUS_PENDING,
        is_deleted=False,
    ).count()

    total_records = (
        products + partners + warehouses + orders + purchases + receivables +
        reports + attachments + audits + notifications
    )
    evidence_count = int(workflow_summary.get('evidence_count') or 0)
    action_count = int(workflow_summary.get('open_action_count') or len(workflow.get('action_queue', [])))
    workflow_health = int(workflow_summary.get('health_score') or 0)
    cash_pressure = round(unpaid_amount / max(total_sales, 1) * 100, 1) if total_sales else (100 if unpaid_amount else 0)
    control_score = clamp_progress(workflow_health - min(18, active_alerts * 2) - min(14, pending_purchase) - min(18, cash_pressure / 4))

    domains = [
        {
            'key': 'master-data',
            'label': '主数据底座',
            'owner': '数据治理',
            'path': '/app/data-quality',
            'metric': f'{products} 物料 / {partners} 往来单位',
            'score': clamp_progress(86 + min(8, warehouses)),
            'status': 'ready' if products and partners and warehouses else 'attention',
            'evidence': f'{warehouses} 个仓库、{attachments} 个附件作为主数据证据',
        },
        {
            'key': 'supply-chain',
            'label': '供应链计划',
            'owner': '供应链计划长',
            'path': '/app/procurement/orders',
            'metric': f'{active_alerts} 预警 / {pending_purchase} 待审批',
            'score': clamp_progress(94 - active_alerts * 4 - pending_purchase * 3),
            'status': 'attention' if active_alerts or pending_purchase or replenishment_pending else 'ready',
            'evidence': f'{replenishment_pending} 条补货建议 / {purchases} 张采购单',
        },
        {
            'key': 'manufacturing-flow',
            'label': '制造履约闭环',
            'owner': '制造运营',
            'path': '/app/operations',
            'metric': f'{workflow_summary["active_stages"]} 阶段 / {workflow_health}% 健康',
            'score': workflow_health,
            'status': 'blocked' if workflow_summary.get('blocked_count') else ('attention' if workflow_summary.get('attention_count') else 'ready'),
            'evidence': workflow_summary.get('cadence', '制造经营作战流'),
        },
        {
            'key': 'cash-risk',
            'label': '现金与信用',
            'owner': '财务风控',
            'path': '/app/finance/receivables',
            'metric': money_compact(unpaid_amount),
            'score': clamp_progress(96 - cash_pressure),
            'status': 'blocked' if unpaid_amount else 'ready',
            'evidence': f'{receivables} 笔应收 / {reports} 份经营归档',
        },
        {
            'key': 'collaboration',
            'label': '协同与审计',
            'owner': '系统治理',
            'path': '/app/tasks',
            'metric': f'{open_notifications} 未读 / {audits} 审计',
            'score': clamp_progress(92 - min(24, open_notifications * 2)),
            'status': 'attention' if open_notifications else 'ready',
            'evidence': f'{collaboration_items} 条公告评论 / {notifications} 条通知',
        },
    ]

    readiness_items = []
    for service in workflow.get('service_boundaries', []):
        readiness_items.append({
            'name': service['name'],
            'owner': service['owner'],
            'surface': service['surface'],
            'contract': service['contract'],
            'runtime': service['deploy_unit'],
            'readiness': service['readiness'],
            'path': '/app/settings',
        })
    readiness_items.extend([
        {
            'name': '前端 Angular 控制台',
            'owner': '体验工程',
            'surface': '/app/* routes',
            'contract': '独立 Angular SPA 通过 /api/v1/* 消费后端合同。',
            'runtime': 'frontend build artifact',
            'readiness': 'ready',
            'path': '/app/settings',
        },
        {
            'name': 'Flask API 边界',
            'owner': '后端平台',
            'surface': '/api/v1/*',
            'contract': '认证、业务资源、聚合洞察、文件与报表能力独立暴露。',
            'runtime': 'backend Flask service',
            'readiness': 'ready',
            'path': '/app/settings',
        },
    ])

    evidence_ledger = [
        {
            'label': '业务对象',
            'value': total_records,
            'unit': '条记录',
            'description': '物料、伙伴、仓库、订单、采购、应收、通知和审计的运行底账。',
            'path': '/app/metrics',
        },
        {
            'label': '证据链',
            'value': evidence_count,
            'unit': '份留痕',
            'description': '附件、报表、审计日志与工作流事件共同证明业务动作。',
            'path': '/app/reports',
        },
        {
            'label': '开放动作',
            'value': action_count,
            'unit': '个待办',
            'description': '库存、采购、履约、回款和归档动作由后端聚合生成。',
            'path': workflow_summary.get('next_path') or '/app/tasks',
        },
        {
            'label': '服务边界',
            'value': len(readiness_items),
            'unit': '个边界',
            'description': '前端 SPA、后端 API 和业务域聚合可以独立部署与演进。',
            'path': '/app/settings',
        },
    ]

    action_queue = [
        {
            'id': item['key'],
            'title': item['title'],
            'owner': item['owner'],
            'priority': item['priority'],
            'path': item['path'],
            'metric': item['metric'],
            'due': item['due'],
            'evidence': item['evidence'],
            'domain': item.get('stage_key', 'workflow'),
        }
        for item in workflow.get('action_queue', [])
    ]
    if not action_queue:
        action_queue = [
            {
                'id': 'archive-review',
                'title': '复核经营日报与审计链路',
                'owner': '经营分析',
                'priority': 'P2',
                'path': '/app/reports',
                'metric': f'{reports} 份',
                'due': '当班复核',
                'evidence': f'{audits} 条审计记录',
                'domain': 'reporting',
            }
        ]

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'erp-control-tower',
        'summary': {
            'title': 'Nexus Prime ERP 控制塔',
            'control_score': control_score,
            'health_score': workflow_health,
            'total_records': total_records,
            'revenue': total_sales,
            'cash_exposure': unpaid_amount,
            'open_actions': action_count,
            'risk_count': active_alerts + pending_purchase + int(1 if unpaid_amount else 0) + open_notifications,
            'evidence_count': evidence_count,
            'service_boundaries': len(readiness_items),
            'next_action': workflow_summary.get('next_action') or '复核经营闭环',
            'next_path': workflow_summary.get('next_path') or '/app/overview',
            'cadence': workflow_summary.get('cadence') or '库存、采购、履约、回款、归档同屏复盘',
        },
        'domain_health': domains,
        'action_queue': action_queue[:6],
        'readiness': readiness_items[:8],
        'evidence_ledger': evidence_ledger,
        'workflow': {
            'stages': workflow.get('stages', []),
            'handoffs': workflow.get('handoffs', []),
            'bottlenecks': workflow.get('bottlenecks', []),
        },
    }


def ratio_progress(done, total):
    if not total:
        return 100 if done else 0
    return clamp_progress(round(float(done or 0) / max(float(total or 0), 1) * 100))


def clamp_progress(value):
    return max(0, min(100, int(round(value or 0))))


def money_compact(value):
    amount = float(value or 0)
    if amount >= 100000000:
        return f'¥{amount / 100000000:.1f}亿'
    if amount >= 10000:
        return f'¥{amount / 10000:.1f}万'
    return f'¥{amount:.0f}'


def build_bottleneck(stage):
    rank_map = {'blocked': 1, 'attention': 2, 'ready': 3, 'complete': 4}
    return {
        'key': stage['key'],
        'label': stage['label'],
        'status': stage['status'],
        'rank': rank_map.get(stage['status'], 9),
        'metric': stage['value'],
        'action': stage['next_action'],
        'path': stage['path'],
        'owner': stage['owner'],
    }


def build_workflow_action_queue(stages, bottlenecks):
    blocked_keys = {item['key'] for item in bottlenecks if item['status'] == 'blocked'}
    attention_keys = {item['key'] for item in bottlenecks if item['status'] == 'attention'}
    queue = []
    for stage in stages:
        if stage['status'] == 'complete':
            continue
        if stage['key'] in blocked_keys:
            priority = 'P0'
            due = '立即处理'
        elif stage['key'] in attention_keys:
            priority = 'P1'
            due = stage['sla']
        else:
            priority = 'P2'
            due = '当班复核'
        first_record = stage['records'][0] if stage['records'] else None
        queue.append({
            'key': f"action-{stage['key']}",
            'stage_key': stage['key'],
            'priority': priority,
            'title': stage['next_action'],
            'owner': stage['owner'],
            'path': stage['path'],
            'metric': stage['value'],
            'due': due,
            'evidence': first_record['meta'] if first_record else stage['detail'],
            'handoff': f"{stage['label']} -> {stage['next_action']}",
        })
    return queue[:6]


def build_role_command_center(stages, metrics):
    stage_map = {stage['key']: stage for stage in stages}
    operating_stage = next((stage for stage in stages if stage['status'] in {'blocked', 'attention'}), stages[0])
    supply_attention = metrics['low_stock_count'] + metrics['suggestions_pending'] + metrics['purchase_pending'] + metrics['receiving_open']
    finance_attention = 1 if metrics['overdue_amount'] else 0
    return [
        {
            'role': '运营负责人',
            'owner': '制造运营负责人',
            'workload': metrics['open_action_count'],
            'primary_metric': f"{metrics['health_score']}% 闭环健康",
            'readiness': 'blocked' if operating_stage['status'] == 'blocked' else ('attention' if metrics['open_action_count'] else 'ready'),
            'next_action': operating_stage['next_action'],
            'path': operating_stage['path'],
            'evidence': f"{len(stages)} 个阶段 / {metrics['open_action_count']} 个开放动作",
            'domains': ['库存', '采购', '履约', '财务', '审计'],
        },
        {
            'role': '仓配与采购',
            'owner': '供应链计划长',
            'workload': supply_attention,
            'primary_metric': f"{metrics['low_stock_count']} 低库存 / {metrics['purchase_pending']} 审批",
            'readiness': 'attention' if supply_attention else 'ready',
            'next_action': stage_map.get('inventory-signal', operating_stage)['next_action'],
            'path': stage_map.get('inventory-signal', operating_stage)['path'],
            'evidence': f"{metrics['suggestions_pending']} 条补货建议 / {metrics['receiving_open']} 单收货",
            'domains': ['补货建议', '采购审批', '收货入库'],
        },
        {
            'role': '履约调度',
            'owner': '交付经理',
            'workload': metrics['fulfillment_open'],
            'primary_metric': f"{metrics['fulfillment_open']} 单待履约",
            'readiness': 'attention' if metrics['fulfillment_open'] else 'ready',
            'next_action': stage_map.get('fulfillment', operating_stage)['next_action'],
            'path': stage_map.get('fulfillment', operating_stage)['path'],
            'evidence': stage_map.get('fulfillment', operating_stage)['detail'],
            'domains': ['信用校验', '库存锁定', '发货签收'],
        },
        {
            'role': '财务风控',
            'owner': '应收负责人',
            'workload': finance_attention,
            'primary_metric': money_compact(metrics['overdue_amount']),
            'readiness': 'blocked' if metrics['overdue_amount'] else 'ready',
            'next_action': stage_map.get('cash-collection', operating_stage)['next_action'],
            'path': stage_map.get('cash-collection', operating_stage)['path'],
            'evidence': '逾期账龄、收款记录和信用占用同步复核',
            'domains': ['应收账龄', '信用释放', '收款记录'],
        },
        {
            'role': '经营分析',
            'owner': '数据治理员',
            'workload': metrics['reports_today'] + metrics['audit_today'],
            'primary_metric': f"{metrics['reports_today']} 报表 / {metrics['audit_today']} 审计",
            'readiness': 'ready' if metrics['reports_today'] or metrics['audit_today'] else 'attention',
            'next_action': stage_map.get('reporting', operating_stage)['next_action'],
            'path': '/app/reports',
            'evidence': '报表、附件、审计和通知作为上线前证据链',
            'domains': ['报表归档', '审计追溯', '部署证据'],
        },
    ]


def build_workflow_execution_events():
    def timestamp(value):
        if not value:
            return utcnow()
        if hasattr(value, 'hour'):
            return value
        return datetime.combine(value, datetime.min.time())

    def event(key, at, module, title, detail, severity, actor, metric, path, evidence):
        event_at = timestamp(at)
        return {
            'id': key,
            'at': event_at.isoformat(),
            'module': module,
            'title': title,
            'detail': detail,
            'severity': severity,
            'actor': actor,
            'metric': metric,
            'path': path,
            'evidence': evidence,
            '_sort_at': event_at,
        }

    events = []
    for alert in StockAlert.query.filter_by(is_deleted=False).order_by(StockAlert.created_at.desc()).limit(4).all():
        product_name = alert.product.name if alert.product else '未命名物料'
        warehouse_name = alert.warehouse.name if alert.warehouse else '未绑定仓'
        events.append(event(
            f'stock-alert-{alert.id}',
            alert.created_at,
            '库存',
            f'{product_name} 低库存预警',
            f'{warehouse_name} 当前 {alert.current_qty or 0} / 安全 {alert.min_qty or 0}',
            'blocked' if alert.alert_level == StockAlert.LEVEL_RED and alert.status == StockAlert.STATUS_ACTIVE else 'attention',
            '仓配运营',
            f'建议 {alert.suggested_qty or 0}',
            '/app/inventory/replenishment',
            alert.status,
        ))

    for suggestion in ReplenishmentSuggestion.query.filter_by(is_deleted=False).order_by(ReplenishmentSuggestion.updated_at.desc()).limit(3).all():
        product_name = suggestion.product.name if suggestion.product else '未命名物料'
        supplier_name = suggestion.supplier.name if suggestion.supplier else '未绑定供应商'
        events.append(event(
            f'replenishment-{suggestion.id}',
            suggestion.updated_at,
            '补货',
            f'{product_name} 补货建议',
            f'{supplier_name} · 当前 {suggestion.current_qty or 0} / 建议 {suggestion.suggested_qty or 0}',
            'attention' if suggestion.status == ReplenishmentSuggestion.STATUS_PENDING else 'ready',
            '计划员',
            suggestion.status,
            '/app/inventory/replenishment',
            f'lead time {suggestion.lead_time_days or 7} 天',
        ))

    for purchase in PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).order_by(PurchaseOrder.updated_at.desc()).limit(4).all():
        supplier_name = purchase.supplier.name if purchase.supplier else '未绑定供应商'
        events.append(event(
            f'purchase-{purchase.id}',
            purchase.updated_at,
            '采购',
            f'{purchase.po_no} {purchase.status}',
            supplier_name,
            'attention' if purchase.status in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING} else 'ready',
            '采购主管',
            money_compact(purchase.total_amount),
            f'/app/procurement/orders/{purchase.id}',
            f'收货进度 {int(purchase.receive_progress or 0)}%',
        ))

    for order in Order.query.filter(Order.is_deleted == False).order_by(Order.updated_at.desc()).limit(4).all():
        customer_name = order.customer.name if order.customer else '未绑定客户'
        events.append(event(
            f'order-{order.id}',
            order.updated_at,
            '履约',
            f'{order.order_no} {order.status}',
            customer_name,
            'attention' if order.status in {Order.STATUS_PENDING, Order.STATUS_PAID} else 'complete',
            '履约调度',
            money_compact(order.total_amount),
            f'/app/sales/orders/{order.id}',
            '订单、库存锁定、发货状态联动',
        ))

    for receivable in Receivable.query.filter(Receivable.is_deleted == False).order_by(Receivable.updated_at.desc()).limit(4).all():
        customer_name = receivable.customer.name if receivable.customer else '未绑定客户'
        events.append(event(
            f'receivable-{receivable.id}',
            receivable.updated_at,
            '应收',
            f'{receivable.receivable_no} {receivable.status}',
            customer_name,
            'blocked' if receivable.status in {Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT} else 'attention',
            '财务风控',
            money_compact(receivable.unpaid_amount),
            f'/app/finance/receivables/{receivable.id}',
            f'账龄 {receivable.age_bucket}',
        ))

    for payment in PaymentRecord.query.filter(PaymentRecord.is_deleted == False).order_by(PaymentRecord.created_at.desc()).limit(3).all():
        customer_name = payment.customer.name if payment.customer else '未绑定客户'
        events.append(event(
            f'payment-{payment.id}',
            payment.created_at,
            '回款',
            f'{payment.payment_no or "收款记录"} 已写入',
            customer_name,
            'complete',
            '出纳',
            money_compact(payment.amount),
            '/app/finance/receivables',
            payment.payment_method or 'bank',
        ))

    for report in GeneratedReport.query.filter_by(is_deleted=False).order_by(GeneratedReport.generated_at.desc()).limit(4).all():
        events.append(event(
            f'report-{report.id}',
            report.generated_at,
            '报表',
            report.report_name or '经营报表',
            report.report_type or 'report',
            'complete',
            '经营分析',
            '已归档',
            f'/app/reports/{report.id}',
            f'发送 {report.sent_count or 0} 次',
        ))

    for audit in AuditLog.query.filter_by(is_deleted=False).order_by(AuditLog.created_at.desc()).limit(4).all():
        events.append(event(
            f'audit-{audit.id}',
            audit.created_at,
            '审计',
            audit.action or 'audit',
            audit.module or 'system',
            'ready',
            '系统治理',
            '已留痕',
            '/app/system/audit',
            (audit.details or '审计日志').strip()[:80],
        ))

    events.sort(key=lambda item: item['_sort_at'], reverse=True)
    for item in events:
        item.pop('_sort_at', None)
    return events[:12]


def build_workflow_data_contracts(metrics):
    return [
        {
            'surface': 'GET /api/v1/manufacturing/command-center',
            'consumer': 'Shell / 运营总览 / 分析台',
            'provider': 'analytics_service.executive command aggregation',
            'payload': 'KPI、仓库热力、流向网络、风险墙',
            'readiness': 'ready',
            'evidence': f"{metrics['stages']} 阶段工作流可与总览 KPI 互证",
        },
        {
            'surface': 'GET /api/v1/manufacturing/workflow-board',
            'consumer': '运营总览作战流',
            'provider': 'analytics_service.manufacturing_workflow_board_payload',
            'payload': '阶段、动作、角色、事件、服务边界、部署检查',
            'readiness': 'ready' if metrics['events'] else 'attention',
            'evidence': f"{metrics['events']} 条事件 / {metrics['services']} 个服务边界 / {metrics['checks']} 个部署检查",
        },
        {
            'surface': 'GET /api/v1/health/ready',
            'consumer': '部署平台与发布检查',
            'provider': 'health_service',
            'payload': '数据库、存储、AI 超时、运行时可写性',
            'readiness': 'ready',
            'evidence': '上线前 readiness probe 已拆出',
        },
        {
            'surface': 'POST /api/v1/reports/generate/*',
            'consumer': '报表中心 / 经营复盘',
            'provider': 'report_service',
            'payload': '经营日报、质量、维护、财务与服务报告',
            'readiness': 'ready' if metrics['reports'] else 'attention',
            'evidence': f"{metrics['reports']} 份报表 / {metrics['audit']} 条审计记录",
        },
    ]
