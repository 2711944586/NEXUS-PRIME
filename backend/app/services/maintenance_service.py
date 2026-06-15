from sqlalchemy import func

from app.extensions import db
from app.models.biz import Product
from app.models.content import Attachment
from app.models.notification import Notification, StockAlert
from app.models.stock import InventoryLog, Stock
from app.utils.time import utcnow


def maintenance_reliability_payload():
    spare_parts = _spare_parts(limit=40)
    alerts = _active_alerts(limit=12)
    documents = _documents(limit=6)
    metrics = _maintenance_metrics(spare_parts, alerts)
    asset_lines = _asset_lines(metrics)
    queue = _workorder_queue(spare_parts, alerts, asset_lines)
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'maintenance_reliability_contract',
        'summary': {
            'health_score': metrics['health_score'],
            'spare_parts': metrics['spare_parts'],
            'low_spares': metrics['low_spares'],
            'active_alerts': metrics['active_alerts'],
            'red_alerts': metrics['red_alerts'],
            'documents': metrics['documents'],
            'audit_events': metrics['audit_events'],
            'open_workorders': metrics['open_workorders'],
            'p0': p0,
            'p1': p1,
            'queue_count': len(queue),
            'primary_owner': queue[0]['owner'] if queue else '设备主管',
            'next_action': queue[0]['action'] if queue else '保持点检、备件、库位和维护资料同步复核。',
        },
        'asset_lines': asset_lines,
        'workorder_queue': queue,
        'spare_parts': spare_parts,
        'technician_roster': _technician_roster(queue, metrics),
        'downtime_windows': _downtime_windows(asset_lines, metrics),
        'documents': documents,
        'maintenance_flow': [
            {'step': '识别风险', 'detail': '聚合低水位备件、库存预警、维护资料和库存审计流水。'},
            {'step': '锁定资产', 'detail': '把风险映射到关键产线、MRO 备件、点检资料和库位维护四个责任面。'},
            {'step': '派发工单', 'detail': '将负责人、优先级、SLA、证据和来源路径写入通知任务。'},
            {'step': '回写审计', 'detail': '维护动作进入任务异常中心，后续处理会保留通知和审计链路。'},
        ],
        'runbook': [
            {'step': '先处理 P0', 'detail': '红色预警和关键备件低水位优先，避免备件缺失扩大为产线停机。'},
            {'step': '核对库位', 'detail': '从工单来源回到物料详情或仓配流向，确认库存、库位和最近出入库流水。'},
            {'step': '补齐资料', 'detail': '检查维护 SOP、点检表和图纸是否已归档到文件中心。'},
            {'step': '复盘可靠性', 'detail': '生成维护报表，复核重复预警、供应商覆盖和备件保障评分。'},
        ],
        'service_boundary': [
            {'service': '设备可靠性聚合 API', 'contract': 'Parts + Alerts + Documents + Audit -> MaintenanceReliability', 'owner': '设备主管', 'readiness': _boundary_status(queue)},
            {'service': 'MRO 备件服务', 'contract': 'Product + Stock -> SparePartCoverage', 'owner': '维修班长', 'readiness': _line_status(asset_lines, 'mro-spares')},
            {'service': '点检资料服务', 'contract': 'Attachment -> MaintenanceDocumentCoverage', 'owner': '资料管理员', 'readiness': _line_status(asset_lines, 'inspection-docs')},
            {'service': '停机风险服务', 'contract': 'StockAlert + InventoryLog -> DowntimeRiskQueue', 'owner': '设备主管', 'readiness': _line_status(asset_lines, 'critical-line')},
        ],
    }


def select_maintenance_workorder_context(queue_item_id=None, product_id=None, title=None):
    payload = maintenance_reliability_payload()
    queue = payload['workorder_queue']
    item = None
    if queue_item_id:
        item = next((entry for entry in queue if entry['id'] == queue_item_id), None)
    if not item and product_id:
        item = next((entry for entry in queue if str(entry.get('product_id') or '') == str(product_id)), None)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and product_id:
        part = _part_by_id(product_id)
        if part:
            item = _queue_from_part(part)
    if not item and queue:
        item = queue[0]
    if not item:
        item = _fallback_workorder()
    return payload, item


def _spare_parts(limit=40):
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
    return [_part_record(product, total_stock, warehouse_count, location) for product, total_stock, warehouse_count, location in rows]


def _part_by_id(product_id):
    product = db.session.get(Product, int(product_id)) if product_id else None
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
    return _part_record(product, total_stock, warehouse_count, location)


def _part_record(product, total_stock, warehouse_count, location):
    total_stock = int(total_stock or 0)
    min_stock = int(product.min_stock or 0)
    max_stock = int(product.max_stock or 0)
    shortage = max(0, min_stock - total_stock)
    coverage = _percent(total_stock, max(min_stock, 1))
    if total_stock <= max(1, round(min_stock * 0.35)):
        priority = 'P0'
    elif total_stock <= min_stock:
        priority = 'P1'
    else:
        priority = 'P2'
    status = _status_from_priority(priority)
    return {
        'id': product.id,
        'product_id': product.id,
        'name': product.name,
        'sku': product.sku,
        'supplier': product.supplier.name if product.supplier else '供应商未维护',
        'category': product.category.name if product.category else '未分类',
        'total_stock': total_stock,
        'min_stock': min_stock,
        'max_stock': max_stock,
        'shortage': shortage,
        'coverage': coverage,
        'warehouse_count': int(warehouse_count or 0),
        'location': location or '待维护库位',
        'priority': priority,
        'status': status,
        'path': f'/app/inventory/products/{product.id}',
        'evidence': f'当前库存 {total_stock}，安全线 {min_stock}，缺口 {shortage} 件。',
        'action': '核对库位、供应商和最近出入库流水，必要时转补货或调拨。',
    }


def _active_alerts(limit=12):
    rows = StockAlert.query.filter(
        StockAlert.is_deleted == False,
        StockAlert.status == StockAlert.STATUS_ACTIVE,
    ).order_by(StockAlert.alert_level.desc(), StockAlert.current_qty.asc(), StockAlert.created_at.desc()).limit(limit)
    return [
        {
            'id': item.id,
            'product_id': item.product_id,
            'title': item.product.name if item.product else f'库存预警 #{item.id}',
            'sku': item.product.sku if item.product else str(item.id),
            'warehouse': item.warehouse.name if item.warehouse else '仓库',
            'level': item.alert_level,
            'current_qty': int(item.current_qty or 0),
            'min_qty': int(item.min_qty or 0),
            'suggested_qty': int(item.suggested_qty or 0),
            'priority': 'P0' if item.alert_level == StockAlert.LEVEL_RED else 'P1',
            'path': f'/app/inventory/products/{item.product_id}' if item.product_id else '/app/maintenance',
        }
        for item in rows
    ]


def _documents(limit=6):
    return [
        {
            'id': item.id,
            'title': item.filename or f'维护资料 #{item.id}',
            'size': int(item.size or 0),
            'mimetype': item.mimetype or 'application/octet-stream',
            'path': f'/app/files/{item.id}',
        }
        for item in Attachment.query.filter(Attachment.is_deleted == False).order_by(Attachment.created_at.desc()).limit(limit)
    ]


def _maintenance_metrics(spare_parts, alerts):
    low_spares = [item for item in spare_parts if item['priority'] in {'P0', 'P1'}]
    red_alerts = [item for item in alerts if item['priority'] == 'P0']
    document_count = Attachment.query.filter(Attachment.is_deleted == False).count()
    audit_events = InventoryLog.query.filter(InventoryLog.is_deleted == False).count()
    open_workorders = Notification.query.filter(
        Notification.is_deleted == False,
        Notification.is_read == False,
        Notification.related_type == 'maintenance',
    ).count()
    health_score = _bounded(92 - len(red_alerts) * 10 - len(low_spares) * 2 - open_workorders * 1.5 + min(8, document_count))
    return {
        'spare_parts': len(spare_parts),
        'low_spares': len(low_spares),
        'active_alerts': len(alerts),
        'red_alerts': len(red_alerts),
        'documents': int(document_count or 0),
        'audit_events': int(audit_events or 0),
        'open_workorders': int(open_workorders or 0),
        'health_score': health_score,
    }


def _asset_lines(m):
    return [
        _line('critical-line', '关键产线', '设备主管', 100 - m['red_alerts'] * 18 - m['open_workorders'] * 4, '/app/dispatch', f"{m['red_alerts']} 条红色预警、{m['open_workorders']} 个维护工单待闭环。", '先锁定 P0 停机风险，安排当班维修窗口。'),
        _line('mro-spares', 'MRO 备件', '维修班长', 100 - m['low_spares'] * 6, '/app/inventory/replenishment', f"{m['low_spares']} 项备件低于保障线。", '核对供应商、库位和补货建议，释放关键备件。'),
        _line('inspection-docs', '点检资料', '资料管理员', 42 + min(58, m['documents'] * 6), '/app/files', f"{m['documents']} 份维护资料已归档。", '补齐 SOP、点检表和图纸，避免现场维修无依据。'),
        _line('warehouse-maintenance', '库位维护', '仓库主管', 100 - m['active_alerts'] * 4, '/app/inventory/stock', f"{m['active_alerts']} 条库存预警需要库位复核。", '复核库位热区和最近出入库流水，确认库存准确性。'),
    ]


def _line(line_id, label, owner, health, path, evidence, action):
    health = _bounded(health)
    priority = 'P0' if health < 45 else 'P1' if health < 72 else 'P2'
    return {
        'id': line_id,
        'label': label,
        'owner': owner,
        'health': health,
        'risk_hours': round(max(0, (100 - health) / 8), 1),
        'priority': priority,
        'status': _status_from_priority(priority),
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'path': path,
        'evidence': evidence,
        'action': action,
    }


def _workorder_queue(spare_parts, alerts, asset_lines):
    items = []
    for alert in alerts[:6]:
        items.append(_queue_from_alert(alert))
    for part in spare_parts:
        if part['priority'] in {'P0', 'P1'}:
            items.append(_queue_from_part(part))
        if len(items) >= 10:
            break
    if not items and spare_parts:
        items.append(_queue_from_part(spare_parts[0]))
    if not items and asset_lines:
        items.append(_queue_from_line(min(asset_lines, key=lambda item: item['health'])))
    if not items:
        items.append(_fallback_workorder())
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    deduped = {}
    for item in items:
        deduped.setdefault(item['id'], item)
    result = list(deduped.values())
    result.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -float(item['risk_score'] or 0), item['id']))
    return result[:10]


def _queue_from_alert(alert):
    priority = alert['priority']
    return {
        'id': f"alert-{alert['id']}-workorder",
        'source': 'stock_alert',
        'source_id': alert['id'],
        'product_id': alert['product_id'],
        'title': f"{alert['title']}停机风险复核",
        'asset': '关键产线',
        'line': alert['warehouse'],
        'part_name': alert['title'],
        'owner': '设备主管' if priority == 'P0' else '维修班长',
        'priority': priority,
        'status': _status_from_priority(priority),
        'sla': '2h' if priority == 'P0' else '4h',
        'risk_score': 96 if priority == 'P0' else 76,
        'path': alert['path'],
        'evidence': f"{alert['warehouse']} {alert['title']} 当前 {alert['current_qty']}，安全线 {alert['min_qty']}，建议补货 {alert['suggested_qty']}。",
        'action': '先确认现场真实库存和替代件，再决定补货、调拨或停机窗口。',
        'checklist': ['确认库位和实物库存', '检查替代件和供应商交期', '记录维修窗口和停机影响', '创建工单并回写审计'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_part(part):
    priority = part['priority'] if part['priority'] in {'P0', 'P1', 'P2'} else 'P2'
    return {
        'id': f"part-{part['product_id']}-workorder",
        'source': 'spare_part',
        'source_id': part['product_id'],
        'product_id': part['product_id'],
        'title': f"{part['name']}备件保障复核",
        'asset': 'MRO 备件',
        'line': part['category'],
        'part_name': part['name'],
        'owner': '设备主管' if priority == 'P0' else '维修班长',
        'priority': priority,
        'status': _status_from_priority(priority),
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'risk_score': _bounded(100 - part['coverage'] + part['shortage'] * 3),
        'path': part['path'],
        'evidence': f"{part['sku']} {part['evidence']} 供应商：{part['supplier']}。",
        'action': part['action'],
        'checklist': ['核对库存和库位', '确认供应商与采购周期', '检查维护资料和替代件', '创建工单并回写审计'],
        'created_at': utcnow().isoformat(),
    }


def _queue_from_line(line):
    return {
        'id': f"{line['id']}-workorder",
        'source': 'asset_line',
        'source_id': line['id'],
        'product_id': None,
        'title': f"{line['label']}可靠性复核",
        'asset': line['label'],
        'line': line['label'],
        'part_name': line['label'],
        'owner': line['owner'],
        'priority': line['priority'],
        'status': line['status'],
        'sla': line['sla'],
        'risk_score': _bounded(100 - line['health']),
        'path': line['path'],
        'evidence': line['evidence'],
        'action': line['action'],
        'checklist': ['确认风险来源', '安排责任人和维修窗口', '回到来源模块处理', '创建工单并回写审计'],
        'created_at': utcnow().isoformat(),
    }


def _fallback_workorder():
    return {
        'id': 'maintenance-daily-inspection',
        'source': 'daily_inspection',
        'source_id': None,
        'product_id': None,
        'title': '设备日点检可靠性复核',
        'asset': '产线设备',
        'line': '当班点检',
        'part_name': '日点检',
        'owner': '设备主管',
        'priority': 'P2',
        'status': 'ready',
        'sla': '3d',
        'risk_score': 24,
        'path': '/app/maintenance',
        'evidence': '当前没有高优先级维护风险，建议保持日点检节奏。',
        'action': '复核维护资料、库位和备件保障评分。',
        'checklist': ['确认点检计划', '抽查备件库存', '归档维护资料', '记录审计证据'],
        'created_at': utcnow().isoformat(),
    }


def _technician_roster(queue, m):
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')
    return [
        _technician('tech-lead', '周启明', '设备主管', p0 + p1, 72 + p0 * 8, '关键停机风险和跨班资源协调。'),
        _technician('spare-lead', '林若辰', '维修班长', m['low_spares'], 58 + min(32, m['low_spares'] * 4), 'MRO 备件、替代件和供应商交期。'),
        _technician('warehouse-tech', '贺知远', '库位维修', m['active_alerts'], 48 + min(34, m['active_alerts'] * 3), '库位、货架和最近出入库流水复核。'),
        _technician('doc-admin', '陈苒', '资料管理员', max(0, 8 - m['documents']), max(18, 52 - m['documents'] * 2), 'SOP、图纸、点检表和维护报表归档。'),
    ]


def _technician(tech_id, name, role, task_count, load, focus):
    load = _bounded(load)
    return {
        'id': tech_id,
        'name': name,
        'role': role,
        'task_count': int(task_count or 0),
        'load': load,
        'status': 'blocked' if load >= 88 else 'attention' if load >= 70 else 'ready',
        'focus': focus,
    }


def _downtime_windows(asset_lines, m):
    return [
        {
            'id': f"window-{item['id']}",
            'label': item['label'],
            'window': window,
            'owner': item['owner'],
            'risk_hours': item['risk_hours'],
            'status': item['status'],
            'evidence': item['evidence'],
        }
        for item, window in zip(asset_lines, ['08:00-10:00', '10:30-12:00', '14:00-16:00', '20:00-22:00'])
    ]


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    if any(item['priority'] == 'P1' for item in queue):
        return 'attention'
    return 'ready'


def _line_status(asset_lines, line_id):
    line = next((item for item in asset_lines if item['id'] == line_id), None)
    return line['status'] if line else 'attention'


def _status_from_priority(priority):
    return 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'


def _percent(value, base):
    return _bounded((float(value or 0) / max(float(base or 1), 1)) * 100)


def _bounded(value):
    return round(max(0, min(100, float(value or 0))), 1)
