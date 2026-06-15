from sqlalchemy import func

from app.extensions import db
from app.models.biz import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.stock import Stock, Warehouse
from app.models.trade import Order, OrderItem
from app.utils.time import utcnow


ACTIVE_ORDER_STATUSES = [Order.STATUS_PENDING, Order.STATUS_PAID, Order.STATUS_SHIPPED]
OPEN_PURCHASE_STATUSES = [
    PurchaseOrder.STATUS_DRAFT,
    PurchaseOrder.STATUS_PENDING,
    PurchaseOrder.STATUS_APPROVED,
    PurchaseOrder.STATUS_ORDERED,
    PurchaseOrder.STATUS_PARTIAL,
]


def capacity_governance_payload():
    metrics = _capacity_metrics()
    work_centers = _work_centers(metrics)
    bottlenecks = _bottleneck_queue(work_centers)
    p0 = sum(1 for item in bottlenecks if item['priority'] == 'P0')
    p1 = sum(1 for item in bottlenecks if item['priority'] == 'P1')
    load = _average([item['load'] for item in work_centers])

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'capacity_governance_contract',
        'summary': {
            'load_score': load,
            'demand_units': metrics['demand_units'],
            'incoming_units': metrics['incoming_units'],
            'shortage_units': metrics['shortage_units'],
            'active_orders': metrics['active_orders'],
            'pending_purchase': metrics['pending_purchase'],
            'low_materials': metrics['low_materials'],
            'warehouse_utilization': metrics['warehouse_utilization'],
            'p0': p0,
            'p1': p1,
            'queue_count': len(bottlenecks),
            'primary_owner': bottlenecks[0]['owner'] if bottlenecks else '计划主管',
            'next_action': bottlenecks[0]['action'] if bottlenecks else '保持日计划、采购到货和履约窗口同步复核。',
        },
        'work_centers': work_centers,
        'shift_plan': _shift_plan(metrics, load),
        'bottleneck_queue': bottlenecks,
        'demand': _demand_records(),
        'supply': _supply_records(),
        'material_constraints': _material_constraints(),
        'load_curve': [
            {'name': '物料齐套', 'value': _center_load(work_centers, 'material-kitting')},
            {'name': '采购到货', 'value': _center_load(work_centers, 'procurement-inbound')},
            {'name': '仓库释放', 'value': _center_load(work_centers, 'warehouse-release')},
            {'name': '装配履约', 'value': _center_load(work_centers, 'assembly-fulfillment')},
        ],
        'runbook': [
            {'step': '锁定约束', 'detail': '先看 P0/P1 产能约束，确认缺料、到货、库容和履约窗口。'},
            {'step': '冻结排程窗口', 'detail': '把早班/中班/晚班负载和责任人固定到班次计划，避免插单挤占关键工位。'},
            {'step': '回到来源模块', 'detail': '进入采购、物料或销售履约模块处理到货、补货和发运动作。'},
            {'step': '派发复核任务', 'detail': '把约束、SLA、证据和下一步动作写入通知、任务队列和审计日志。'},
        ],
        'service_boundary': [
            {'service': '产能计划聚合 API', 'contract': 'Demand + Supply + Inventory -> CapacityGovernance', 'owner': '计划主管', 'readiness': _boundary_status(bottlenecks)},
            {'service': '需求承诺服务', 'contract': 'Order + OrderItem -> DemandWindow', 'owner': '销售履约', 'readiness': _center_status(work_centers, 'assembly-fulfillment')},
            {'service': '物料齐套服务', 'contract': 'Product + Stock -> MaterialConstraint', 'owner': '仓配计划', 'readiness': _center_status(work_centers, 'material-kitting')},
            {'service': '到货释放服务', 'contract': 'PurchaseOrder + PurchaseOrderItem -> InboundSupply', 'owner': '采购执行', 'readiness': _center_status(work_centers, 'procurement-inbound')},
        ],
    }


def select_capacity_review_context(item_id=None, title=None):
    payload = capacity_governance_payload()
    queue = payload['bottleneck_queue']
    centers = payload['work_centers']
    item = None
    if item_id:
        item = next((entry for entry in queue if entry['id'] == item_id or entry['work_center_id'] == item_id), None)
        if not item:
            center = next((entry for entry in centers if entry['id'] == item_id), None)
            if center:
                item = _queue_item(center)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and queue:
        item = queue[0]
    if not item and centers:
        item = _queue_item(centers[0])
    return payload, item


def _capacity_metrics():
    demand_units = db.session.query(func.coalesce(func.sum(OrderItem.quantity), 0)).join(Order, Order.id == OrderItem.order_id).filter(
        Order.is_deleted == False,
        Order.status.in_(ACTIVE_ORDER_STATUSES),
    ).scalar()
    active_orders = Order.query.filter(Order.is_deleted == False, Order.status.in_(ACTIVE_ORDER_STATUSES)).count()
    incoming_units = db.session.query(
        func.coalesce(func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_qty), 0)
    ).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_(OPEN_PURCHASE_STATUSES),
    ).scalar()
    pending_purchase = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_(OPEN_PURCHASE_STATUSES),
    ).count()
    total_stock = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).filter(Stock.is_deleted == False).scalar()
    total_capacity = db.session.query(func.coalesce(func.sum(Warehouse.capacity), 0)).filter(Warehouse.is_deleted == False).scalar()
    constraints = _material_constraints()
    shortage_units = sum(int(item['shortage_units'] or 0) for item in constraints)
    low_materials = len(constraints)
    return {
        'demand_units': int(demand_units or 0),
        'active_orders': int(active_orders or 0),
        'incoming_units': int(incoming_units or 0),
        'pending_purchase': int(pending_purchase or 0),
        'total_stock': int(total_stock or 0),
        'warehouse_capacity': int(total_capacity or 0),
        'warehouse_utilization': _percent(total_stock, max(total_capacity or 1, 1)),
        'shortage_units': int(shortage_units or 0),
        'low_materials': int(low_materials or 0),
    }


def _work_centers(m):
    demand_gap = max(0, m['demand_units'] - m['incoming_units'])
    return [
        _center(
            center_id='material-kitting',
            label='物料齐套',
            owner='仓配计划',
            load=min(98, 48 + m['low_materials'] * 9 + min(28, m['shortage_units'] * 0.8)),
            available_hours=max(4, 18 - m['low_materials']),
            required_hours=8 + m['low_materials'] * 2,
            path='/app/inventory/replenishment',
            evidence=f"{m['low_materials']} 项物料低于安全线，缺口 {m['shortage_units']} 件。",
            action='优先处理低水位物料和补货建议，确认齐套后释放排程。',
        ),
        _center(
            center_id='procurement-inbound',
            label='采购到货释放',
            owner='采购执行',
            load=min(98, 42 + m['pending_purchase'] * 8 + min(24, m['incoming_units'] * 0.18)),
            available_hours=max(3, 20 - m['pending_purchase']),
            required_hours=7 + m['pending_purchase'] * 1.8,
            path='/app/procurement/orders',
            evidence=f"{m['pending_purchase']} 张采购单待推进，未到货 {m['incoming_units']} 件。",
            action='复核待审批、已审批和部分到货采购单，释放采购到货窗口。',
        ),
        _center(
            center_id='warehouse-release',
            label='仓库释放能力',
            owner='仓库主管',
            load=min(98, 36 + m['warehouse_utilization'] * 0.55 + m['active_orders'] * 4),
            available_hours=max(5, 24 - round(m['warehouse_utilization'] / 8)),
            required_hours=9 + m['active_orders'] * 1.4,
            path='/app/inventory/stock',
            evidence=f"库存容量利用 {m['warehouse_utilization']}%，当前库存 {m['total_stock']} 件。",
            action='复核库位热区、调拨流水和出库释放能力，避免仓库瓶颈阻塞产线。',
        ),
        _center(
            center_id='assembly-fulfillment',
            label='装配履约窗口',
            owner='生产计划',
            load=min(98, 46 + m['active_orders'] * 7 + min(22, demand_gap * 0.12)),
            available_hours=max(4, 22 - m['active_orders']),
            required_hours=10 + m['active_orders'] * 2,
            path='/app/sales/orders',
            evidence=f"{m['active_orders']} 单处于履约窗口，需求 {m['demand_units']} 件，供给缺口 {demand_gap} 件。",
            action='按订单优先级匹配库存、采购到货和发运窗口，必要时调整班次计划。',
        ),
    ]


def _center(center_id, label, owner, load, available_hours, required_hours, path, evidence, action):
    load = round(float(load or 0), 1)
    available_hours = round(float(available_hours or 0), 1)
    required_hours = round(float(required_hours or 0), 1)
    hour_gap = round(required_hours - available_hours, 1)
    priority = 'P0' if load >= 88 or hour_gap >= 8 else 'P1' if load >= 68 or hour_gap > 0 else 'P2'
    status = 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'
    return {
        'id': center_id,
        'label': label,
        'owner': owner,
        'load': load,
        'available_hours': available_hours,
        'required_hours': required_hours,
        'hour_gap': hour_gap,
        'status': status,
        'priority': priority,
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'path': path,
        'evidence': evidence,
        'action': action,
        'runbook': [
            '确认计划需求、供给和库存约束是否一致',
            '进入来源模块释放采购、库存或履约动作',
            '创建产能复核任务并在当班任务队列闭环',
        ],
    }


def _shift_plan(m, load):
    return [
        _shift('day-kitting', '早班齐套', '08:00-12:00', '仓配计划', max(0, load - 7), '低水位物料、补货建议和采购到货前置复核。'),
        _shift('mid-release', '中班释放', '13:00-18:00', '生产计划', load, '按订单优先级释放装配、库位和发运窗口。'),
        _shift('night-reconcile', '晚班校准', '19:00-23:00', '运营调度', min(98, load - 5 + m['pending_purchase'] * 1.2), '盘点差异、采购承诺和第二天班次计划校准。'),
    ]


def _shift(shift_id, label, window, owner, load, focus):
    load = max(0, min(100, round(float(load or 0), 1)))
    status = 'blocked' if load >= 88 else 'attention' if load >= 70 else 'ready'
    return {'id': shift_id, 'label': label, 'window': window, 'owner': owner, 'load': load, 'focus': focus, 'status': status}


def _bottleneck_queue(centers):
    items = [_queue_item(center) for center in centers if center['priority'] in {'P0', 'P1'}]
    if not items and centers:
        items = [_queue_item(max(centers, key=lambda center: float(center['load'] or 0)))]
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    items.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -float(item['load'] or 0), item['id']))
    return items


def _queue_item(center):
    return {
        'id': f"{center['id']}-review",
        'work_center_id': center['id'],
        'title': f"{center['label']}产能复核",
        'owner': center['owner'],
        'priority': center['priority'],
        'sla': center['sla'],
        'status': center['status'],
        'path': center['path'],
        'load': center['load'],
        'hour_gap': center['hour_gap'],
        'evidence': center['evidence'],
        'action': center['action'],
        'runbook': center['runbook'],
        'created_at': utcnow().isoformat(),
    }


def _demand_records():
    return [
        {
            'id': item.id,
            'title': item.order_no,
            'customer': item.customer.name if item.customer else '客户未维护',
            'status': item.status,
            'amount': float(item.total_amount or 0),
            'units': sum(line.quantity for line in item.items),
            'path': f'/app/sales/orders/{item.id}',
        }
        for item in Order.query.filter(
            Order.is_deleted == False,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        ).order_by(Order.created_at.desc()).limit(8)
    ]


def _supply_records():
    return [
        {
            'id': item.id,
            'title': item.po_no,
            'supplier': item.supplier.name if item.supplier else '供应商未维护',
            'warehouse': item.warehouse.name if item.warehouse else '仓库未维护',
            'status': item.status,
            'amount': float(item.total_amount or 0),
            'progress': item.receive_progress,
            'path': f'/app/procurement/orders/{item.id}',
        }
        for item in PurchaseOrder.query.filter(
            PurchaseOrder.is_deleted == False,
            PurchaseOrder.status.in_(OPEN_PURCHASE_STATUSES),
        ).order_by(PurchaseOrder.created_at.asc()).limit(8)
    ]


def _material_constraints():
    stock_sum = func.coalesce(func.sum(Stock.quantity), 0)
    rows = (
        db.session.query(
            Product.id,
            Product.sku,
            Product.name,
            Product.min_stock,
            Product.max_stock,
            stock_sum.label('total_stock'),
        )
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id, Product.sku, Product.name, Product.min_stock, Product.max_stock)
        .having(stock_sum <= func.coalesce(Product.min_stock, 0))
        .order_by((func.coalesce(Product.min_stock, 0) - stock_sum).desc())
        .limit(8)
        .all()
    )
    return [
        {
            'id': row.id,
            'sku': row.sku,
            'name': row.name,
            'total_stock': int(row.total_stock or 0),
            'min_stock': int(row.min_stock or 0),
            'shortage_units': max(0, int(row.min_stock or 0) - int(row.total_stock or 0)),
            'path': f'/app/inventory/products/{row.id}',
        }
        for row in rows
    ]


def _center_load(centers, center_id):
    item = next((entry for entry in centers if entry['id'] == center_id), None)
    return item['load'] if item else 0


def _center_status(centers, center_id):
    item = next((entry for entry in centers if entry['id'] == center_id), None)
    return item['status'] if item else 'attention'


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    return 'attention' if queue else 'ready'


def _average(values):
    values = [float(item or 0) for item in values]
    return round(sum(values) / max(len(values), 1), 1)


def _percent(value, total):
    total = float(total or 0)
    if total <= 0:
        return 0
    return round((float(value or 0) / total) * 100, 1)
