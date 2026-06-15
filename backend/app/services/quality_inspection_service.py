from sqlalchemy import func

from app.extensions import db
from app.models.biz import Product
from app.models.content import Attachment
from app.models.notification import GeneratedReport, Notification, StockAlert
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, SupplierPerformance
from app.models.stock import InventoryLog, Stock
from app.utils.time import utcnow


def quality_inspection_payload():
    products = _product_stock_records(limit=48)
    purchase_lots = _inspection_lots(limit=18)
    suppliers = _supplier_quality(limit=18)
    alerts = _active_alerts(limit=18)
    documents = _document_set(limit=8)
    metrics = _quality_metrics(products, purchase_lots, suppliers, alerts, documents)
    lanes = _inspection_lanes(metrics)
    queue = _inspection_queue(products, purchase_lots, suppliers, alerts, lanes)
    defects = _defect_taxonomy(metrics, queue)
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'quality_inspection_contract',
        'summary': {
            'quality_score': metrics['quality_score'],
            'pending_lots': metrics['pending_lots'],
            'blocked_lots': metrics['blocked_lots'],
            'supplier_alerts': metrics['supplier_alerts'],
            'defects': metrics['defects'],
            'documents': metrics['documents'],
            'open_tasks': metrics['open_tasks'],
            'quality_reports': metrics['quality_reports'],
            'usage_decision_rate': metrics['usage_decision_rate'],
            'p0': p0,
            'p1': p1,
            'queue_count': len(queue),
            'primary_owner': queue[0]['owner'] if queue else '质量工程师',
            'next_action': queue[0]['action'] if queue else '保持来料、过程、出货和供应商质量例行抽检。',
        },
        'inspection_lanes': lanes,
        'inspection_queue': queue,
        'supplier_quality': suppliers,
        'defect_taxonomy': defects,
        'inspection_lots': purchase_lots,
        'document_set': documents,
        'quality_flow': [
            {'step': '生成检验批', 'detail': '按采购到货、库存预警、供应商质量波动和附件证据形成检验批队列。'},
            {'step': '记录结果', 'detail': '检验任务必须包含负责人、SLA、证据、样本范围和来源路径，便于回到业务单据。'},
            {'step': '使用决策', 'detail': '依据检验结果决定放行、让步接收、隔离、退供或复检，并更新质量评分。'},
            {'step': '缺陷闭环', 'detail': '缺陷进入通知任务和审计日志，供应商整改、短期遏制和长期预防必须留痕。'},
        ],
        'runbook': [
            {'step': '先锁定 P0', 'detail': '红色库存预警、低质量供应商和待放行采购批次优先，避免不合格物料进入生产或出货。'},
            {'step': '核对批次证据', 'detail': '回到采购单、物料详情、附件中心和库存流水，确认批次、样本、库位和供应商证据。'},
            {'step': '创建检验任务', 'detail': '把检验对象、负责人、SLA、证据和处理动作写入任务异常中心，形成跨模块闭环。'},
            {'step': '复盘质量层级', 'detail': '生成质量报表，复核缺陷类型、供应商质量率、使用决策和改进行动是否下降复发。'},
        ],
        'service_boundary': [
            {'service': '质量检验聚合 API', 'contract': 'Product + Stock + Purchase + Supplier + Evidence -> QualityInspectionPayload', 'owner': '质量经理', 'readiness': _boundary_status(queue)},
            {'service': '检验批服务', 'contract': 'PurchaseOrder + PurchaseOrderItem -> InspectionLot', 'owner': '来料检验', 'readiness': _lane_status(lanes, 'incoming-lots')},
            {'service': '缺陷与遏制服务', 'contract': 'StockAlert + Notification -> DefectContainmentQueue', 'owner': '质量工程师', 'readiness': _lane_status(lanes, 'defect-containment')},
            {'service': '供应商质量服务', 'contract': 'SupplierPerformance -> SupplierQualityScore', 'owner': '供应商质量工程师', 'readiness': _lane_status(lanes, 'supplier-quality')},
        ],
    }


def select_quality_inspection_context(queue_item_id=None, product_id=None, supplier_id=None, purchase_id=None, title=None):
    payload = quality_inspection_payload()
    queue = payload['inspection_queue']
    item = None
    if queue_item_id:
        item = next((entry for entry in queue if entry['id'] == queue_item_id), None)
    if not item and product_id:
        item = next((entry for entry in queue if str(entry.get('product_id') or '') == str(product_id)), None)
    if not item and supplier_id:
        item = next((entry for entry in queue if str(entry.get('supplier_id') or '') == str(supplier_id)), None)
    if not item and purchase_id:
        item = next((entry for entry in queue if str(entry.get('purchase_id') or '') == str(purchase_id)), None)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and product_id:
        product = _product_by_id(product_id)
        if product:
            item = _queue_from_product(product)
    if not item and queue:
        item = queue[0]
    if not item:
        item = _fallback_queue_item()
    return payload, item


def _product_stock_records(limit=48):
    stock_totals = (
        db.session.query(
            Stock.product_id.label('product_id'),
            func.coalesce(func.sum(Stock.quantity), 0).label('total_stock'),
            func.count(Stock.id).label('warehouse_count'),
            func.max(Stock.shelf_location).label('location'),
        )
        .filter(Stock.is_deleted == False)
        .group_by(Stock.product_id)
        .subquery()
    )
    total_expr = func.coalesce(stock_totals.c.total_stock, 0)
    rows = (
        db.session.query(
            Product,
            total_expr.label('total_stock'),
            func.coalesce(stock_totals.c.warehouse_count, 0).label('warehouse_count'),
            stock_totals.c.location,
        )
        .outerjoin(stock_totals, stock_totals.c.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .order_by((total_expr - Product.min_stock).asc(), Product.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_product_record(product, total_stock, warehouse_count, location) for product, total_stock, warehouse_count, location in rows]


def _product_by_id(product_id):
    try:
        product = db.session.get(Product, int(product_id)) if product_id else None
    except (TypeError, ValueError):
        product = None
    if not product or product.is_deleted:
        return None
    total_stock = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).filter(
        Stock.is_deleted == False,
        Stock.product_id == product.id,
    ).scalar()
    warehouse_count = Stock.query.filter(Stock.is_deleted == False, Stock.product_id == product.id).count()
    location = db.session.query(func.max(Stock.shelf_location)).filter(
        Stock.is_deleted == False,
        Stock.product_id == product.id,
    ).scalar()
    return _product_record(product, total_stock, warehouse_count, location)


def _product_record(product, total_stock, warehouse_count, location):
    total_stock = int(total_stock or 0)
    min_stock = int(product.min_stock or 0)
    max_stock = int(product.max_stock or 0)
    gap = max(0, min_stock - total_stock)
    coverage = _percent(total_stock, max(min_stock, 1))
    if total_stock <= max(1, round(min_stock * 0.35)):
        priority = 'P0'
    elif total_stock <= min_stock:
        priority = 'P1'
    else:
        priority = 'P2'
    return {
        'id': product.id,
        'product_id': product.id,
        'sku': product.sku,
        'name': product.name,
        'supplier_id': product.supplier_id,
        'supplier': product.supplier.name if product.supplier else '供应商未维护',
        'category': product.category.name if product.category else '未分类',
        'total_stock': total_stock,
        'min_stock': min_stock,
        'max_stock': max_stock,
        'gap': gap,
        'coverage': coverage,
        'warehouse_count': int(warehouse_count or 0),
        'location': location or '待维护库位',
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': f'/app/inventory/products/{product.id}',
        'evidence': f'{product.sku} 当前库存 {total_stock}，安全线 {min_stock}，缺口 {gap}。',
        'action': '抽检来料批次、供应商质检记录和库存库位，决定放行、隔离或复检。',
    }


def _inspection_lots(limit=18):
    orders = (
        PurchaseOrder.query
        .filter(PurchaseOrder.is_deleted == False)
        .order_by(
            PurchaseOrder.status.asc(),
            PurchaseOrder.expected_date.asc().nullslast(),
            PurchaseOrder.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return [_lot_record(order) for order in orders]


def _lot_record(order):
    items = [item for item in order.items if not item.is_deleted]
    quantity = sum(int(item.quantity or 0) for item in items)
    received = sum(int(item.received_qty or 0) for item in items)
    progress = order.receive_progress
    open_statuses = {
        PurchaseOrder.STATUS_DRAFT,
        PurchaseOrder.STATUS_PENDING,
        PurchaseOrder.STATUS_APPROVED,
        PurchaseOrder.STATUS_ORDERED,
        PurchaseOrder.STATUS_PARTIAL,
    }
    blocked = order.status in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING}
    priority = 'P0' if blocked and quantity == 0 else 'P1' if order.status in open_statuses else 'P2'
    return {
        'id': f'lot-{order.id}',
        'purchase_id': order.id,
        'lot_code': f'IQC-{order.id:05d}',
        'reference': order.po_no,
        'supplier': order.supplier.name if order.supplier else '供应商未维护',
        'supplier_id': order.supplier_id,
        'warehouse': order.warehouse.name if order.warehouse else '待入库仓',
        'status': _status_from_priority(priority),
        'order_status': order.status,
        'progress': _bounded(progress),
        'quantity': quantity,
        'received_qty': received,
        'amount': float(order.total_amount or 0),
        'expected_date': order.expected_date.isoformat() if order.expected_date else None,
        'owner': '来料检验',
        'priority': priority,
        'decision': '待使用决策' if order.status in open_statuses else '已完成放行',
        'inspection_type': '来料检验',
        'path': f'/app/procurement/orders/{order.id}',
        'evidence': f'{order.po_no} {order.supplier.name if order.supplier else "供应商"}，{quantity} 件，收货进度 {progress}%。',
        'action': '核对采购明细、样本范围、收货数量和附件证据，完成使用决策。',
    }


def _supplier_quality(limit=18):
    rows = (
        db.session.query(SupplierPerformance)
        .join(SupplierPerformance.supplier)
        .filter(SupplierPerformance.is_deleted == False)
        .order_by(SupplierPerformance.quality_pass_orders.asc(), SupplierPerformance.total_amount.desc())
        .limit(limit)
        .all()
    )
    return [_supplier_record(item) for item in rows]


def _supplier_record(item):
    pending_orders = PurchaseOrder.query.filter(
        PurchaseOrder.supplier_id == item.supplier_id,
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_PENDING, PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL]),
    ).count()
    quality_rate = float(item.quality_rate or 0)
    on_time_rate = float(item.on_time_rate or 0)
    score = _bounded((quality_rate * 0.62) + (on_time_rate * 0.28) + max(0, 10 - pending_orders))
    priority = 'P0' if quality_rate < 86 or score < 82 else 'P1' if quality_rate < 94 or on_time_rate < 90 else 'P2'
    supplier = item.supplier
    name = supplier.name if supplier else f'供应商 {item.supplier_id}'
    return {
        'id': f'supplier-{item.supplier_id}',
        'supplier_id': item.supplier_id,
        'name': name,
        'contact': supplier.contact_person if supplier else None,
        'phone': supplier.phone if supplier else None,
        'on_time_rate': on_time_rate,
        'quality_rate': quality_rate,
        'total_orders': int(item.total_orders or 0),
        'quality_pass_orders': int(item.quality_pass_orders or 0),
        'pending_orders': int(pending_orders or 0),
        'score': score,
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': '/app/suppliers/performance',
        'evidence': f'{name} 质量率 {quality_rate}%，准点率 {on_time_rate}%，待处理采购 {pending_orders} 单。',
        'action': '抽查最近采购批次、不合格原因和整改承诺，必要时冻结新批次放行。',
    }


def _active_alerts(limit=18):
    rows = (
        StockAlert.query
        .filter(StockAlert.is_deleted == False, StockAlert.status == StockAlert.STATUS_ACTIVE)
        .order_by(StockAlert.alert_level.desc(), StockAlert.current_qty.asc(), StockAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': item.id,
            'product_id': item.product_id,
            'title': item.product.name if item.product else f'库存预警 #{item.id}',
            'sku': item.product.sku if item.product else str(item.id),
            'supplier_id': item.product.supplier_id if item.product else None,
            'supplier': item.product.supplier.name if item.product and item.product.supplier else '供应商未维护',
            'warehouse': item.warehouse.name if item.warehouse else '仓库',
            'level': item.alert_level,
            'current_qty': int(item.current_qty or 0),
            'min_qty': int(item.min_qty or 0),
            'suggested_qty': int(item.suggested_qty or 0),
            'priority': 'P0' if item.alert_level == StockAlert.LEVEL_RED else 'P1',
            'path': f'/app/inventory/products/{item.product_id}' if item.product_id else '/app/quality',
        }
        for item in rows
    ]


def _document_set(limit=8):
    attachments = [
        {
            'id': f'file-{item.id}',
            'title': item.filename or f'质量附件 #{item.id}',
            'type': item.mimetype or 'application/octet-stream',
            'size': int(item.size or 0),
            'status': 'ready',
            'path': f'/app/files/{item.id}',
            'evidence': '附件已归档，可作为检验记录、供应商整改或 CoA 证据。',
        }
        for item in Attachment.query.filter(Attachment.is_deleted == False).order_by(Attachment.created_at.desc()).limit(limit // 2).all()
    ]
    reports = [
        {
            'id': f'report-{item.id}',
            'title': item.report_name or f'质量报表 #{item.id}',
            'type': item.report_type or 'quality_report',
            'size': 0,
            'status': 'ready',
            'path': f'/app/reports/{item.id}',
            'evidence': '报表已生成，可用于质量复盘和供应商绩效会议。',
        }
        for item in GeneratedReport.query.filter(
            GeneratedReport.is_deleted == False,
            GeneratedReport.report_type.in_(['quality_inspection', 'supplier_performance', 'inventory']),
        ).order_by(GeneratedReport.generated_at.desc()).limit(limit - len(attachments)).all()
    ]
    return [*attachments, *reports][:limit]


def _quality_metrics(products, lots, suppliers, alerts, documents):
    low_products = [item for item in products if item['priority'] in {'P0', 'P1'}]
    blocked_lots = [item for item in lots if item['priority'] == 'P0']
    pending_lots = [item for item in lots if item['priority'] in {'P0', 'P1'}]
    supplier_alerts = [item for item in suppliers if item['priority'] in {'P0', 'P1'}]
    red_alerts = [item for item in alerts if item['priority'] == 'P0']
    open_tasks = Notification.query.filter(
        Notification.is_deleted == False,
        Notification.is_read == False,
        Notification.related_type == 'quality_inspection',
    ).count()
    audit_events = InventoryLog.query.filter(InventoryLog.is_deleted == False).count()
    quality_reports = GeneratedReport.query.filter(
        GeneratedReport.is_deleted == False,
        GeneratedReport.report_type == 'quality_inspection',
    ).count()
    defects = len(red_alerts) + len(supplier_alerts) + max(0, len(pending_lots) - len(blocked_lots))
    usage_decision_rate = _bounded(100 - len(pending_lots) * 4 + min(12, quality_reports * 1.2))
    avg_supplier_score = _average([item['score'] for item in suppliers]) if suppliers else 92
    quality_score = _bounded(
        avg_supplier_score
        - len(red_alerts) * 9
        - len(blocked_lots) * 6
        - len(pending_lots) * 1.1
        - len(low_products) * 0.35
        - len(supplier_alerts) * 4
        - open_tasks * 1.5
        + min(6, len(documents) * 0.6)
        + min(3, quality_reports * 0.4)
    )
    return {
        'quality_score': quality_score,
        'pending_lots': len(pending_lots),
        'blocked_lots': len(blocked_lots),
        'supplier_alerts': len(supplier_alerts),
        'defects': defects,
        'documents': len(documents),
        'open_tasks': int(open_tasks or 0),
        'quality_reports': int(quality_reports or 0),
        'usage_decision_rate': usage_decision_rate,
        'low_products': len(low_products),
        'red_alerts': len(red_alerts),
        'audit_events': int(audit_events or 0),
    }


def _inspection_lanes(m):
    return [
        _lane('incoming-lots', '来料检验批', '来料检验', m['pending_lots'], m['blocked_lots'], max(0, m['pending_lots'] - m['blocked_lots']), 100 - m['pending_lots'] * 7 - m['blocked_lots'] * 9, '/app/procurement/orders', f"{m['pending_lots']} 个采购批次等待检验或使用决策。", '抽样、记录结果并完成放行/隔离决策。'),
        _lane('in-process', '过程质量', '质量工程师', m['low_products'], m['red_alerts'], max(0, m['low_products'] - m['red_alerts']), 96 - m['low_products'] * 4, '/app/inventory/products', f"{m['low_products']} 项物料低于质量复核水位。", '确认过程批次、库位和最近库存流水。'),
        _lane('supplier-quality', '供应商质量', '供应商质量工程师', m['supplier_alerts'], sum(1 for _ in range(m['supplier_alerts']) if m['supplier_alerts'] > 2), max(0, m['supplier_alerts'] - 1), 100 - m['supplier_alerts'] * 8, '/app/suppliers/performance', f"{m['supplier_alerts']} 家供应商进入观察或整改。", '核对质量率、准点率、缺陷类型和供应商 CAPA。'),
        _lane('defect-containment', '缺陷遏制', '质量经理', m['defects'], m['red_alerts'], max(0, m['defects'] - m['red_alerts']), 100 - m['defects'] * 6 - m['open_tasks'] * 3, '/app/tasks', f"{m['defects']} 个缺陷/风险对象，{m['open_tasks']} 个质量任务未闭环。", '先隔离风险批次，再推动整改和复检。'),
    ]


def _lane(lane_id, label, owner, active_count, p0, p1, score, path, evidence, action):
    score = _bounded(score)
    priority = 'P0' if p0 else 'P1' if p1 or score < 88 else 'P2'
    return {
        'id': lane_id,
        'label': label,
        'owner': owner,
        'active_count': int(active_count or 0),
        'p0': int(p0 or 0),
        'p1': int(p1 or 0),
        'score': score,
        'status': _status_from_priority(priority),
        'priority': priority,
        'path': path,
        'metric': f'{score}% / {int(active_count or 0)} 项',
        'evidence': evidence,
        'action': action,
    }


def _inspection_queue(products, lots, suppliers, alerts, lanes):
    items = []
    for alert in alerts[:6]:
        items.append(_queue_from_alert(alert))
    for lot in lots:
        if lot['priority'] in {'P0', 'P1'}:
            items.append(_queue_from_lot(lot))
        if len(items) >= 10:
            break
    for supplier in suppliers:
        if supplier['priority'] in {'P0', 'P1'}:
            items.append(_queue_from_supplier(supplier))
        if len(items) >= 12:
            break
    for product in products:
        if product['priority'] in {'P0', 'P1'}:
            items.append(_queue_from_product(product))
        if len(items) >= 14:
            break
    if not items and lots:
        items.append(_queue_from_lot(lots[0]))
    if not items and suppliers:
        items.append(_queue_from_supplier(suppliers[0]))
    if not items and products:
        items.append(_queue_from_product(products[0]))
    if not items and lanes:
        items.append(_queue_from_lane(min(lanes, key=lambda item: item['score'])))
    if not items:
        items.append(_fallback_queue_item())
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    deduped = {}
    for item in items:
        deduped.setdefault(item['id'], item)
    result = list(deduped.values())
    result.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -float(item.get('risk_score') or 0), item['id']))
    return result[:14]


def _queue_from_alert(alert):
    priority = alert['priority']
    return {
        'id': f"alert-{alert['id']}-inspection",
        'source': 'stock_alert',
        'source_id': alert['id'],
        'product_id': alert['product_id'],
        'supplier_id': alert.get('supplier_id'),
        'purchase_id': None,
        'title': f"{alert['title']}质量遏制复核",
        'lot_code': f"QHOLD-{alert['id']:05d}",
        'product_name': alert['title'],
        'supplier': alert['supplier'],
        'owner': '质量经理' if priority == 'P0' else '质量工程师',
        'priority': priority,
        'status': _status_from_priority(priority),
        'sla': '2h' if priority == 'P0' else '4h',
        'risk_score': 94 if priority == 'P0' else 78,
        'decision': '先隔离后复检',
        'path': alert['path'],
        'evidence': f"{alert['warehouse']} {alert['title']} 当前 {alert['current_qty']}，安全线 {alert['min_qty']}，建议补货 {alert['suggested_qty']}。",
        'action': '冻结该物料新批次放行，完成抽检、库位复核和供应商质量追溯。',
        'checklist': ['锁定库存批次和库位', '抽样复测关键质量项', '确认供应商最近质量率', '记录使用决策和整改动作'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_lot(lot):
    priority = lot['priority']
    return {
        'id': f"purchase-{lot['purchase_id']}-inspection",
        'source': 'purchase_lot',
        'source_id': lot['purchase_id'],
        'product_id': None,
        'supplier_id': lot.get('supplier_id'),
        'purchase_id': lot['purchase_id'],
        'title': f"{lot['reference']}来料检验与使用决策",
        'lot_code': lot['lot_code'],
        'product_name': lot['reference'],
        'supplier': lot['supplier'],
        'owner': '来料检验',
        'priority': priority,
        'status': lot['status'],
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'risk_score': _bounded(100 - lot['progress'] + (24 if priority == 'P0' else 10 if priority == 'P1' else 0)),
        'decision': lot['decision'],
        'path': lot['path'],
        'evidence': lot['evidence'],
        'action': lot['action'],
        'checklist': ['核对采购明细和样本范围', '记录检验结果和偏差', '选择放行/隔离/退供决策', '回写任务和审计证据'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_supplier(supplier):
    priority = supplier['priority']
    return {
        'id': f"supplier-{supplier['supplier_id']}-inspection",
        'source': 'supplier_quality',
        'source_id': supplier['supplier_id'],
        'product_id': None,
        'supplier_id': supplier['supplier_id'],
        'purchase_id': None,
        'title': f"{supplier['name']}供应商质量整改复核",
        'lot_code': f"SQE-{supplier['supplier_id']:05d}",
        'product_name': supplier['name'],
        'supplier': supplier['name'],
        'owner': '供应商质量工程师',
        'priority': priority,
        'status': supplier['status'],
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'risk_score': _bounded(100 - supplier['score'] + supplier['pending_orders'] * 4),
        'decision': '供应商 CAPA',
        'path': supplier['path'],
        'evidence': supplier['evidence'],
        'action': supplier['action'],
        'checklist': ['抽查最近采购批次', '确认缺陷原因和遏制动作', '要求供应商整改承诺', '复检后更新供应商质量评分'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_product(product):
    priority = product['priority']
    return {
        'id': f"product-{product['product_id']}-inspection",
        'source': 'product_stock',
        'source_id': product['product_id'],
        'product_id': product['product_id'],
        'supplier_id': product.get('supplier_id'),
        'purchase_id': None,
        'title': f"{product['name']}来料与库存质量复核",
        'lot_code': f"MAT-{product['product_id']:05d}",
        'product_name': product['name'],
        'supplier': product['supplier'],
        'owner': '质量工程师',
        'priority': priority,
        'status': product['status'],
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'risk_score': _bounded(100 - product['coverage'] + product['gap'] * 2),
        'decision': '待抽检',
        'path': product['path'],
        'evidence': product['evidence'],
        'action': product['action'],
        'checklist': ['确认 SKU、供应商和库位', '抽查来料批次和库存状态', '记录检验结果', '决定放行、隔离或复检'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_lane(lane):
    return {
        'id': f"{lane['id']}-inspection",
        'source': 'inspection_lane',
        'source_id': lane['id'],
        'product_id': None,
        'supplier_id': None,
        'purchase_id': None,
        'title': f"{lane['label']}质量复核",
        'lot_code': lane['id'].upper(),
        'product_name': lane['label'],
        'supplier': lane['owner'],
        'owner': lane['owner'],
        'priority': lane['priority'],
        'status': lane['status'],
        'sla': '1d',
        'risk_score': _bounded(100 - lane['score']),
        'decision': '质量复核',
        'path': lane['path'],
        'evidence': lane['evidence'],
        'action': lane['action'],
        'checklist': ['确认风险来源', '补齐检验证据', '完成使用决策', '回写审计'],
        'created_at': utcnow().isoformat(),
    }


def _fallback_queue_item():
    return {
        'id': 'quality-daily-inspection',
        'source': 'daily_inspection',
        'source_id': None,
        'product_id': None,
        'supplier_id': None,
        'purchase_id': None,
        'title': '质量日常抽检复核',
        'lot_code': 'DAILY-IQC',
        'product_name': '日常抽检',
        'supplier': '质量工程师',
        'owner': '质量工程师',
        'priority': 'P2',
        'status': 'ready',
        'sla': '3d',
        'risk_score': 22,
        'decision': '例行放行',
        'path': '/app/quality',
        'evidence': '当前没有高优先级质量风险，建议保持抽检和供应商复盘节奏。',
        'action': '复核质量报表、附件证据和供应商质量率。',
        'checklist': ['抽查当日批次', '核对质量附件', '归档检验记录', '更新供应商质量评分'],
        'created_at': utcnow().isoformat(),
    }


def _defect_taxonomy(m, queue):
    buckets = [
        ('material-defect', '来料规格偏差', '供应商/物料', m['red_alerts'] + m['low_products'], '来料与库存风险可能影响生产放行。', '质量工程师', '/app/inventory/products'),
        ('supplier-deviation', '供应商质量波动', '供应商', m['supplier_alerts'], '质量率或准点率低于门槛，需要供应商 CAPA。', '供应商质量工程师', '/app/suppliers/performance'),
        ('lot-release', '检验批待决策', '检验批', m['pending_lots'], '检验批未完成使用决策会阻塞入库或生产。', '来料检验', '/app/procurement/orders'),
        ('evidence-gap', '质量证据缺口', '文档', max(0, 6 - m['documents']), '检验记录、CoA、整改附件或报表证据不足。', '质量经理', '/app/files'),
    ]
    queue_priority = {item['source']: item['priority'] for item in queue}
    return [
        _defect(defect_id, label, defect_type, count, impact, owner, path, queue_priority)
        for defect_id, label, defect_type, count, impact, owner, path in buckets
    ]


def _defect(defect_id, label, defect_type, count, impact, owner, path, queue_priority):
    count = int(count or 0)
    priority = 'P0' if count >= 6 else 'P1' if count > 0 else 'P2'
    if defect_id == 'supplier-deviation' and queue_priority.get('supplier_quality') == 'P0':
        priority = 'P0'
    return {
        'id': defect_id,
        'label': label,
        'type': defect_type,
        'count': count,
        'impact': impact,
        'owner': owner,
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': path,
        'evidence': f'{label} 当前 {count} 项。',
        'action': '创建质量复核任务，完成遏制、原因分析、整改和复检。',
    }


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    if any(item['priority'] == 'P1' for item in queue):
        return 'attention'
    return 'ready'


def _lane_status(lanes, lane_id):
    lane = next((item for item in lanes if item['id'] == lane_id), None)
    return lane['status'] if lane else 'attention'


def _status_from_priority(priority):
    return 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'


def _percent(value, base):
    return _bounded((float(value or 0) / max(float(base or 1), 1)) * 100)


def _average(values):
    values = [float(item or 0) for item in values]
    return round(sum(values) / max(len(values), 1), 1)


def _bounded(value):
    return round(max(0, min(100, float(value or 0))), 1)
