from sqlalchemy import func

from app.extensions import db
from app.models.notification import StockAlert
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock, Warehouse
from app.models.stocktake import StockTake
from app.models.trade import Order
from app.utils.time import utcnow


RECEIVING_STATUSES = [
    PurchaseOrder.STATUS_APPROVED,
    PurchaseOrder.STATUS_ORDERED,
    PurchaseOrder.STATUS_PARTIAL,
]
COUNTING_STATUSES = [StockTake.STATUS_DRAFT, StockTake.STATUS_IN_PROGRESS]
SHIPPING_STATUSES = [Order.STATUS_PENDING, Order.STATUS_PAID]


def mobile_terminal_payload():
    receiving = _receiving_tasks()
    counting = _counting_tasks()
    shipping = _shipping_tasks()
    alerts = _alert_tasks()
    scan_queue = _scan_queue(receiving, counting, shipping, alerts)
    lanes = _lanes(receiving, counting, shipping, alerts)
    devices = _device_sessions(lanes, scan_queue)
    p0 = sum(1 for item in scan_queue if item['priority'] == 'P0')
    p1 = sum(1 for item in scan_queue if item['priority'] == 'P1')
    completion_rate = _completion_rate(receiving, counting, shipping)
    sync_rate = _sync_rate(devices)
    total = len(scan_queue)

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'mobile_terminal_governance_contract',
        'summary': {
            'total_tasks': total,
            'receiving': len(receiving),
            'counting': len(counting),
            'shipping': len(shipping),
            'alerts': len(alerts),
            'p0': p0,
            'p1': p1,
            'completion_rate': completion_rate,
            'sync_rate': sync_rate,
            'active_devices': sum(1 for item in devices if item['status'] != 'offline'),
            'primary_owner': scan_queue[0]['owner'] if scan_queue else '现场主管',
            'next_action': scan_queue[0]['next_action'] if scan_queue else '保持收货、盘点、发货和异常复核同步。',
        },
        'lanes': lanes,
        'scan_queue': scan_queue,
        'device_sessions': devices,
        'warehouse_zones': _warehouse_zones(),
        'scan_flow': [
            {'step': '识别任务', 'detail': '按收货、盘点、发货和库存预警识别现场任务来源。'},
            {'step': '扫码校验', 'detail': '扫描单据、物料、库位或批次，校验业务状态和数量边界。'},
            {'step': '数量确认', 'detail': '写入实收、实盘、发货或异常备注，保留设备和人员上下文。'},
            {'step': '回写审计', 'detail': '把扫码结果写回库存、通知、任务队列和审计日志。'},
        ],
        'runbook': [
            {'step': '锁定 P0', 'detail': '先处理红色库存预警和超 SLA 的现场队列，避免现场阻塞扩散。'},
            {'step': '分派设备', 'detail': '按设备电量、同步延迟和任务类型分派 RF/PDA/叉车终端。'},
            {'step': '回到来源', 'detail': '从扫码任务直接进入采购、盘点、销售或物料详情处理原始单据。'},
            {'step': '创建任务', 'detail': '把队列项创建为通知任务，进入任务异常中心并写入审计。'},
        ],
        'service_boundary': [
            {'service': '移动扫码聚合 API', 'contract': 'Receiving + Counting + Shipping + Alerts -> MobileTerminalGovernance', 'owner': '现场主管', 'readiness': _boundary_status(scan_queue)},
            {'service': '收货执行服务', 'contract': 'PurchaseOrder -> ReceivingScanTask', 'owner': '收货组', 'readiness': _lane_status(lanes, 'receiving')},
            {'service': '盘点扫码服务', 'contract': 'StockTake -> CountingScanTask', 'owner': '盘点组', 'readiness': _lane_status(lanes, 'counting')},
            {'service': '发货确认服务', 'contract': 'Order -> ShippingScanTask', 'owner': '发货组', 'readiness': _lane_status(lanes, 'shipping')},
        ],
    }


def select_mobile_task_context(queue_item_id=None, task_type=None, title=None):
    payload = mobile_terminal_payload()
    queue = payload['scan_queue']
    item = None
    if queue_item_id:
        item = next((entry for entry in queue if entry['id'] == queue_item_id), None)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and task_type:
        item = next((entry for entry in queue if entry['type'] == task_type), None)
    if not item and queue:
        item = queue[0]
    if not item:
        item = _fallback_task()
    return payload, item


def _receiving_tasks():
    rows = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_(RECEIVING_STATUSES),
    ).order_by(PurchaseOrder.created_at.desc()).limit(10)
    return [
        _task(
            task_id=f'receiving-{item.id}',
            source_id=item.id,
            task_type='收货',
            source='purchase',
            title=item.po_no,
            owner='收货组',
            priority='P1' if item.status == PurchaseOrder.STATUS_PARTIAL else 'P2',
            status=item.status,
            warehouse=item.warehouse.name if item.warehouse else '待分仓',
            location=item.warehouse.location if item.warehouse else '收货口',
            path=f'/app/procurement/orders/{item.id}',
            progress=item.receive_progress,
            quantity=sum(max(0, line.quantity - line.received_qty) for line in item.items),
            evidence=f'{item.supplier.name if item.supplier else "供应商"} 到货进度 {item.receive_progress}%，待扫码确认。',
            next_action='扫描采购单、托盘和物料批次，确认实收数量并回写采购收货。',
            scan_code=f'PO:{item.po_no}',
            sla='4h' if item.status == PurchaseOrder.STATUS_PARTIAL else '1d',
        )
        for item in rows
    ]


def _counting_tasks():
    rows = StockTake.query.filter(
        StockTake.is_deleted == False,
        StockTake.status.in_(COUNTING_STATUSES),
    ).order_by(StockTake.created_at.desc()).limit(10)
    return [
        _task(
            task_id=f'counting-{item.id}',
            source_id=item.id,
            task_type='盘点',
            source='stocktake',
            title=item.take_no,
            owner='盘点组',
            priority='P1' if item.status == StockTake.STATUS_IN_PROGRESS else 'P2',
            status=item.status,
            warehouse=item.warehouse.name if item.warehouse else '待分仓',
            location=item.warehouse.location if item.warehouse else '库区',
            path=f'/app/stocktakes/{item.id}',
            progress=item.progress,
            quantity=max(0, (item.total_items or 0) - (item.counted_items or 0)),
            evidence=f'已盘 {item.counted_items or 0}/{item.total_items or 0} 项，差异 {item.variance_items or 0} 项。',
            next_action='扫描库位和物料条码，录入实盘数量，完成后生成差异调整。',
            scan_code=f'ST:{item.take_no}',
            sla='4h' if item.status == StockTake.STATUS_IN_PROGRESS else '1d',
        )
        for item in rows
    ]


def _shipping_tasks():
    rows = Order.query.filter(
        Order.is_deleted == False,
        Order.status.in_(SHIPPING_STATUSES),
    ).order_by(Order.created_at.desc()).limit(10)
    return [
        _task(
            task_id=f'shipping-{item.id}',
            source_id=item.id,
            task_type='发货',
            source='order',
            title=item.order_no,
            owner='发货组',
            priority='P1' if item.status == Order.STATUS_PAID else 'P2',
            status=item.status,
            warehouse='发货月台',
            location='Dock-02',
            path=f'/app/sales/orders/{item.id}',
            progress=80 if item.status == Order.STATUS_PAID else 35,
            quantity=sum(line.quantity for line in item.items),
            evidence=f'{item.customer.name if item.customer else "客户"} 订单 {item.status}，等待拣配或发货确认。',
            next_action='扫描销售单、箱码和库位，确认出库数量并推进订单状态。',
            scan_code=f'SO:{item.order_no}',
            sla='4h' if item.status == Order.STATUS_PAID else '1d',
        )
        for item in rows
    ]


def _alert_tasks():
    rows = (
        db.session.query(StockAlert, Warehouse.name, Warehouse.location)
        .outerjoin(Warehouse, Warehouse.id == StockAlert.warehouse_id)
        .filter(StockAlert.is_deleted == False, StockAlert.status == StockAlert.STATUS_ACTIVE)
        .order_by(StockAlert.alert_level.desc(), StockAlert.current_qty.asc(), StockAlert.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        _task(
            task_id=f'alert-{alert.id}',
            source_id=alert.id,
            task_type='预警',
            source='stock_alert',
            title=alert.product.name if alert.product else f'库存预警 #{alert.id}',
            owner='仓库主管',
            priority='P0' if alert.alert_level == StockAlert.LEVEL_RED else 'P1',
            status=alert.status,
            warehouse=warehouse_name or '仓库',
            location=location or '低水位库位',
            path=f'/app/inventory/products/{alert.product_id}',
            progress=_percent(alert.current_qty or 0, max(alert.min_qty or 1, 1)),
            quantity=max(0, int(alert.min_qty or 0) - int(alert.current_qty or 0)),
            evidence=f'当前库存 {alert.current_qty or 0}，安全线 {alert.min_qty or 0}，建议补货 {alert.suggested_qty or 0}。',
            next_action='扫描库位和现存批次，确认真实库存后转补货或调拨。',
            scan_code=f'STK:{alert.product.sku if alert.product else alert.id}',
            sla='2h' if alert.alert_level == StockAlert.LEVEL_RED else '4h',
        )
        for alert, warehouse_name, location in rows
    ]


def _task(task_id, source_id, task_type, source, title, owner, priority, status, warehouse, location, path, progress, quantity, evidence, next_action, scan_code, sla):
    priority = priority if priority in {'P0', 'P1', 'P2'} else 'P2'
    readiness = 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'
    return {
        'id': task_id,
        'source_id': source_id,
        'type': task_type,
        'source': source,
        'title': title,
        'owner': owner,
        'priority': priority,
        'status': status,
        'readiness': readiness,
        'warehouse': warehouse,
        'location': location,
        'path': path,
        'progress': _bounded(progress),
        'quantity': int(quantity or 0),
        'evidence': evidence,
        'next_action': next_action,
        'scan_code': scan_code,
        'sla': sla,
        'created_at': utcnow().isoformat(),
        'checklist': [
            '扫描单据或任务码',
            '扫描物料、库位或箱码',
            '确认数量和异常备注',
            '提交并写入审计',
        ],
    }


def _scan_queue(receiving, counting, shipping, alerts):
    items = [*alerts, *counting, *receiving, *shipping]
    if not items:
        items = [_fallback_task()]
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    items.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item['sla'], item['id']))
    return items


def _fallback_task():
    return _task(
        task_id='field-audit-sample',
        source_id=None,
        task_type='巡检',
        source='field_audit',
        title='现场抽样巡检',
        owner='现场主管',
        priority='P2',
        status='ready',
        warehouse='主仓',
        location='巡检路线',
        path='/app/inventory/stock',
        progress=100,
        quantity=0,
        evidence='当前没有阻塞任务，保留一个抽样巡检任务保持移动端流程可执行。',
        next_action='按库区抽样扫描库位、物料和批次，确认移动端链路可用。',
        scan_code='FIELD:AUDIT',
        sla='3d',
    )


def _lanes(receiving, counting, shipping, alerts):
    return [
        _lane('receiving', '收货扫码', '收货组', receiving, '/app/procurement/orders', '采购单、托盘和批次'),
        _lane('counting', '盘点录入', '盘点组', counting, '/app/stocktakes', '盘点单、库位和实盘数量'),
        _lane('shipping', '发货确认', '发货组', shipping, '/app/sales/orders', '销售单、箱码和出库库位'),
        _lane('exceptions', '异常复核', '仓库主管', alerts, '/app/inventory/replenishment', '低水位库位和补货建议'),
    ]


def _lane(lane_id, label, owner, tasks, path, scan_target):
    p0 = sum(1 for item in tasks if item['priority'] == 'P0')
    p1 = sum(1 for item in tasks if item['priority'] == 'P1')
    avg_progress = _average([item['progress'] for item in tasks]) if tasks else 100
    status = 'blocked' if p0 else 'attention' if p1 or tasks else 'ready'
    return {
        'id': lane_id,
        'label': label,
        'owner': owner,
        'active_count': len(tasks),
        'p0': p0,
        'p1': p1,
        'progress': avg_progress,
        'status': status,
        'path': path,
        'scan_target': scan_target,
        'metric': f'{len(tasks)} 项 / {avg_progress}% 完成度',
    }


def _device_sessions(lanes, scan_queue):
    queue_count = len(scan_queue)
    return [
        _device('RF-01', '收货 RF 枪', '收货组', _lane_count(lanes, 'receiving'), 88 - min(24, queue_count * 2), 2 + queue_count, '收货口'),
        _device('PDA-07', '盘点 PDA', '盘点组', _lane_count(lanes, 'counting'), 76 - min(18, queue_count), 4 + queue_count, 'A 区'),
        _device('FORK-03', '叉车终端', '发货组', _lane_count(lanes, 'shipping'), 69 - min(12, queue_count), 5 + queue_count, '发货月台'),
        _device('SUP-10', '主管平板', '现场主管', _lane_count(lanes, 'exceptions'), 92 - min(16, queue_count), 3 + queue_count, '现场巡检'),
    ]


def _device(device_id, label, owner, task_count, battery, latency_ms, zone):
    battery = _bounded(battery)
    latency_ms = int(max(1, latency_ms))
    status = 'blocked' if battery < 20 or latency_ms > 30 else 'attention' if battery < 45 or task_count >= 6 else 'ready'
    return {
        'id': device_id,
        'label': label,
        'owner': owner,
        'task_count': int(task_count or 0),
        'battery': battery,
        'sync_latency_ms': latency_ms,
        'zone': zone,
        'status': status,
        'last_sync': utcnow().isoformat(),
    }


def _warehouse_zones():
    rows = (
        db.session.query(
            Warehouse.id,
            Warehouse.name,
            Warehouse.location,
            Warehouse.capacity,
            func.coalesce(func.sum(Stock.quantity), 0).label('quantity'),
            func.count(Stock.id).label('slot_count'),
        )
        .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
        .filter(Warehouse.is_deleted == False)
        .group_by(Warehouse.id, Warehouse.name, Warehouse.location, Warehouse.capacity)
        .order_by(func.coalesce(func.sum(Stock.quantity), 0).desc())
        .limit(6)
        .all()
    )
    return [
        {
            'id': row.id,
            'label': row.name,
            'location': row.location or '库区',
            'quantity': int(row.quantity or 0),
            'capacity': int(row.capacity or 0),
            'utilization': _percent(row.quantity or 0, max(row.capacity or 1, 1)),
            'slot_count': int(row.slot_count or 0),
            'status': 'blocked' if _percent(row.quantity or 0, max(row.capacity or 1, 1)) >= 92 else 'attention' if _percent(row.quantity or 0, max(row.capacity or 1, 1)) >= 76 else 'ready',
        }
        for row in rows
    ]


def _completion_rate(receiving, counting, shipping):
    values = [item['progress'] for item in [*receiving, *counting, *shipping]]
    return _average(values) if values else 100


def _sync_rate(devices):
    if not devices:
        return 100
    ready_score = sum(100 if item['status'] == 'ready' else 78 if item['status'] == 'attention' else 48 for item in devices)
    return round(ready_score / len(devices), 1)


def _lane_count(lanes, lane_id):
    item = next((entry for entry in lanes if entry['id'] == lane_id), None)
    return item['active_count'] if item else 0


def _lane_status(lanes, lane_id):
    item = next((entry for entry in lanes if entry['id'] == lane_id), None)
    return item['status'] if item else 'attention'


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    if any(item['priority'] == 'P1' for item in queue):
        return 'attention'
    return 'ready'


def _bounded(value):
    return max(0, min(100, round(float(value or 0), 1)))


def _percent(value, total):
    total = float(total or 0)
    if total <= 0:
        return 0
    return _bounded(float(value or 0) / total * 100)


def _average(values):
    values = [float(item or 0) for item in values]
    if not values:
        return 0
    return round(sum(values) / len(values), 1)
