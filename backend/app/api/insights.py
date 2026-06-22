from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import cache, db
from app.models.auth import User
from app.models.biz import Category, Product
from app.models.finance import Receivable
from app.models.notification import Notification, StockAlert
from app.models.purchase import PurchaseOrder
from app.models.stock import InventoryLog, Stock, Warehouse
from app.models.trade import Order
from app.services.analytics_service import erp_control_tower_payload, executive_analytics_payload, manufacturing_workflow_board_payload
from app.utils.time import utcnow

from . import api_bp
from .auth import jwt_required
from .responses import api_success


@api_bp.get('/dashboard/summary')
@jwt_required
@cache.cached(timeout=120, key_prefix='dashboard_summary')
def dashboard_summary():
    order_amount = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    stock_qty = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).scalar()
    return api_success({
        'users': User.query.count(),
        'products': Product.query.filter_by(is_deleted=False).count(),
        'orders': Order.query.filter_by(is_deleted=False).count(),
        'order_amount': float(order_amount or 0),
        'stock_quantity': int(stock_qty or 0),
        'alerts': StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE).count(),
        'notifications_unread': Notification.query.filter_by(is_read=False).count(),
    }, '仪表盘汇总')


@api_bp.get('/dashboard/charts')
@jwt_required
@cache.cached(timeout=300, key_prefix='dashboard_charts')
def dashboard_charts():
    status_rows = db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    category_rows = (
        db.session.query(Category.name, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .all()
    )
    stock_rows = (
        db.session.query(Warehouse.name, func.coalesce(func.sum(Stock.quantity), 0))
        .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
        .group_by(Warehouse.id)
        .all()
    )
    today = utcnow().date()
    sales_trend = []
    for days in range(13, -1, -1):
        day = today - timedelta(days=days)
        next_day = day + timedelta(days=1)
        amount = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
            Order.is_deleted == False,
            Order.created_at >= datetime.combine(day, datetime.min.time()),
            Order.created_at < datetime.combine(next_day, datetime.min.time())
        ).scalar()
        sales_trend.append({'name': day.strftime('%m-%d'), 'value': float(amount or 0)})

    receivable_rows = (
        db.session.query(Receivable.status, func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0))
        .filter(Receivable.is_deleted == False)
        .group_by(Receivable.status)
        .all()
    )
    return api_success({
        'orders_by_status': [{'name': k or 'unknown', 'value': v} for k, v in status_rows],
        'products_by_category': [{'name': k or '未分类', 'value': v} for k, v in category_rows],
        'stock_by_warehouse': [{'name': k or '未命名仓库', 'value': int(v or 0)} for k, v in stock_rows],
        'sales_trend': sales_trend,
        'receivables_by_status': [{'name': k or 'unknown', 'value': float(v or 0)} for k, v in receivable_rows],
    }, '图表数据')


@api_bp.get('/analytics/executive')
@jwt_required
def executive_analytics():
    return api_success(executive_analytics_payload(), '经营分析数据')


@api_bp.get('/erp/control-tower')
@jwt_required
def erp_control_tower():
    return api_success(erp_control_tower_payload(), 'ERP 控制塔数据')


@api_bp.get('/overview/control-tower')
@jwt_required
def overview_control_tower():
    return erp_control_tower()


@api_bp.get('/manufacturing/command-center')
@jwt_required
def manufacturing_command_center():
    order_amount = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(Order.is_deleted == False).scalar()
    stock_qty = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).filter(Stock.is_deleted == False).scalar()
    low_stock_rows = (
        db.session.query(
            Product.id,
            Product.name,
            Product.sku,
            Product.min_stock,
            func.coalesce(func.sum(Stock.quantity), 0).label('total_stock')
        )
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .having(func.coalesce(func.sum(Stock.quantity), 0) <= func.coalesce(Product.min_stock, 0))
        .limit(12)
        .all()
    )
    low_stock = len(low_stock_rows)
    pending_purchase = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).count()
    overdue_amount = (
        db.session.query(func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0))
        .filter(Receivable.is_deleted == False, Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT]))
        .scalar()
    )
    warehouse_heat = (
        db.session.query(Warehouse.name, func.coalesce(func.sum(Stock.quantity), 0), func.count(Stock.id))
        .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
        .filter(Warehouse.is_deleted == False)
        .group_by(Warehouse.id)
        .all()
    )
    flows = [
        {'from': '供应商', 'to': '工厂仓', 'value': PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).count()},
        {'from': '工厂仓', 'to': '区域仓', 'value': InventoryLog.query.filter_by(move_type=InventoryLog.TYPE_MOVE, is_deleted=False).count()},
        {'from': '区域仓', 'to': '客户', 'value': Order.query.filter(Order.is_deleted == False, Order.status.in_([Order.STATUS_SHIPPED, Order.STATUS_DONE])).count()},
    ]
    risks = []
    for _id, name, sku, min_stock, total_stock in low_stock_rows[:8]:
        risks.append({
            'type': '库存水位',
            'level': 'critical' if int(total_stock or 0) <= 0 else 'warning',
            'title': name,
            'description': f'{sku} 当前 {int(total_stock or 0)}，安全线 {min_stock or 0}',
        })
    for receivable in Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).order_by(Receivable.due_date.asc()).limit(5):
        risks.append({
            'type': '应收逾期',
            'level': 'critical' if receivable.overdue_days > 60 else 'warning',
            'title': receivable.customer.name if receivable.customer else receivable.receivable_no,
            'description': f'未收 {receivable.unpaid_amount:.2f}，逾期 {receivable.overdue_days} 天',
        })
    return api_success({
        'kpis': {
            'order_amount': float(order_amount or 0),
            'stock_quantity': int(stock_qty or 0),
            'low_stock_products': low_stock,
            'pending_purchase': pending_purchase,
            'overdue_amount': float(overdue_amount or 0),
        },
        'warehouse_heat': [
            {'name': name or '未命名仓', 'stock_quantity': int(quantity or 0), 'slot_count': int(slot_count or 0)}
            for name, quantity, slot_count in warehouse_heat
        ],
        'flows': flows,
        'risks': risks[:12],
    }, '制造仓配指挥数据')


@api_bp.get('/overview/command-center')
@jwt_required
def overview_command_center():
    return manufacturing_command_center()


@api_bp.get('/manufacturing/workflow-board')
@jwt_required
def manufacturing_workflow_board():
    return api_success(manufacturing_workflow_board_payload(), '制造经营作战流')


@api_bp.get('/overview/workflow-board')
@jwt_required
def overview_workflow_board():
    return manufacturing_workflow_board()
