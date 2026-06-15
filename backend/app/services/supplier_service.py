"""供应商协同与资质风险聚合服务。"""
from datetime import timedelta

from app.extensions import db
from app.models.biz import Partner, Product
from app.models.notification import Notification, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder, SupplierPerformance
from app.utils.time import utcnow


def supplier_collaboration_payload():
    """供应商协同工作台聚合合同。"""
    cards = _supplier_cards(limit=18)
    delivery_windows = _delivery_windows(limit=14)
    qualification_queue = _qualification_queue(cards)
    risk_queue = _risk_queue(cards, delivery_windows, qualification_queue)
    metrics = _summary_metrics(cards, delivery_windows, qualification_queue, risk_queue)
    lanes = _collaboration_lanes(metrics)

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'supplier_collaboration_contract',
        'summary': {
            'network_score': _network_score(metrics, risk_queue),
            'active_suppliers': metrics['active_suppliers'],
            'preferred_suppliers': metrics['preferred_suppliers'],
            'risk_suppliers': metrics['risk_suppliers'],
            'qualification_due': metrics['qualification_due'],
            'pending_orders': metrics['pending_orders'],
            'delivery_due': metrics['delivery_due'],
            'quality_watch': metrics['quality_watch'],
            'open_tasks': metrics['open_tasks'],
            'spend_amount': metrics['spend_amount'],
            'p0': sum(1 for item in risk_queue if item['priority'] == 'P0'),
            'p1': sum(1 for item in risk_queue if item['priority'] == 'P1'),
            'queue_count': len(risk_queue),
            'primary_owner': risk_queue[0]['owner'] if risk_queue else '供应商经理',
            'next_action': risk_queue[0]['action'] if risk_queue else '保持供应商资质、交付、质量和商务集中度周复核。',
        },
        'collaboration_lanes': lanes,
        'supplier_cards': cards,
        'risk_queue': risk_queue,
        'qualification_queue': qualification_queue,
        'delivery_windows': delivery_windows,
        'supplier_matrix': _supplier_matrix(cards),
        'collaboration_flow': [
            {'step': '准入与资质', 'detail': '供应商主数据、联系人、邮箱、信用分和资质状态进入准入复核。'},
            {'step': '采购承诺', 'detail': '未完采购、预计到货、金额集中度和交期 SLA 形成协同任务。'},
            {'step': '质量 CAPA', 'detail': '质检通过率、红色库存预警和来料异常推动供应商整改。'},
            {'step': '备选供应', 'detail': '高风险或高集中度供应商触发备选供应、价格和产能复核。'},
            {'step': '绩效回写', 'detail': '收货和质量结果回写供应商评分、报表和采购选择策略。'},
        ],
        'service_boundaries': [
            {'service': '供应商协同聚合 API', 'contract': 'Supplier + Purchase + Quality -> SupplierCollaborationPayload', 'owner': '供应商经理', 'deploy_unit': 'supplier-api', 'readiness': _boundary_status(risk_queue)},
            {'service': '供应商准入服务', 'contract': 'Partner.supplier -> QualificationStatus + ContactCompleteness', 'owner': '采购主数据', 'deploy_unit': 'supplier-master-service', 'readiness': _lane_status(lanes, 'qualification')},
            {'service': '供应商交付 SLA 服务', 'contract': 'PurchaseOrder.expected_date -> DeliveryWindow + SLA', 'owner': '采购跟单', 'deploy_unit': 'supplier-delivery-service', 'readiness': _lane_status(lanes, 'delivery')},
            {'service': '供应商质量 CAPA 服务', 'contract': 'SupplierPerformance.quality_rate + StockAlert -> CAPAQueue', 'owner': 'SQE', 'deploy_unit': 'supplier-quality-service', 'readiness': _lane_status(lanes, 'quality')},
            {'service': '供应商商务风险服务', 'contract': 'SpendShare + PendingOrders -> ConcentrationRisk', 'owner': '经营财务', 'deploy_unit': 'supplier-risk-service', 'readiness': _lane_status(lanes, 'commercial')},
        ],
        'deployment_checks': [
            {'key': 'api-contract', 'label': '供应商 API 合同', 'status': 'ready', 'owner': '平台后端', 'evidence': 'GET /api/v1/operations/supplier-collaboration 返回供应商协同合同。'},
            {'key': 'task-writeback', 'label': '任务写回', 'status': 'ready', 'owner': '协同工作台', 'evidence': 'POST /api/v1/operations/supplier-collaboration/task 写入通知和审计。'},
            {'key': 'quality-capa', 'label': '质量 CAPA', 'status': 'attention' if metrics['quality_watch'] else 'ready', 'owner': 'SQE', 'evidence': f"{metrics['quality_watch']} 家供应商进入质量观察。"},
            {'key': 'concentration-risk', 'label': '集中度风险', 'status': 'attention' if metrics['risk_suppliers'] else 'ready', 'owner': '经营财务', 'evidence': f"{metrics['risk_suppliers']} 家供应商需要备选或降集中度复核。"},
        ],
        'runbook': [
            {'step': '先处理 P0 供应商', 'detail': '资质缺失、交期超期、质量率低或高集中度供应商优先进入协同任务。'},
            {'step': '回到采购来源', 'detail': '交付窗口保留采购单路径，实际审批和收货仍回到采购领域动作。'},
            {'step': '补齐主数据', 'detail': '联系人、邮箱、电话、信用分和资质状态缺失时先做准入复核。'},
            {'step': '触发 CAPA', 'detail': '质量率低、红色预警或来料异常进入 SQE 整改闭环。'},
            {'step': '同步服务边界', 'detail': '供应商主数据、交付 SLA、质量 CAPA 和商务风险按服务边界拆分部署。'},
        ],
    }


def select_supplier_collaboration_context(item_id=None, supplier_id=None, title=None):
    payload = supplier_collaboration_payload()
    queue = payload['risk_queue']
    item = None
    if item_id:
        item = next((entry for entry in queue if entry['id'] == item_id), None)
    if not item and supplier_id:
        item = next((entry for entry in queue if str(entry.get('supplier_id') or '') == str(supplier_id)), None)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and queue:
        item = queue[0]
    return payload, item


def _supplier_cards(limit=18):
    suppliers = (
        Partner.query
        .filter(Partner.is_deleted == False, Partner.type == Partner.TYPE_SUPPLIER)
        .order_by(Partner.credit_score.asc(), Partner.created_at.desc())
        .limit(limit)
        .all()
    )
    total_spend = db.session.query(db.func.coalesce(db.func.sum(PurchaseOrder.total_amount), 0)).filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.supplier_id.isnot(None),
    ).scalar() or 0
    return [_supplier_card(item, float(total_spend or 0)) for item in suppliers]


def _supplier_card(supplier, total_spend):
    perf = SupplierPerformance.query.filter_by(supplier_id=supplier.id, is_deleted=False).first()
    pending_orders = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.supplier_id == supplier.id,
        PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_ORDERED,
            PurchaseOrder.STATUS_PARTIAL,
        ]),
    ).count()
    active_amount = db.session.query(db.func.coalesce(db.func.sum(PurchaseOrder.total_amount), 0)).filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.supplier_id == supplier.id,
        PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_ORDERED,
            PurchaseOrder.STATUS_PARTIAL,
        ]),
    ).scalar() or 0
    products = Product.query.filter_by(supplier_id=supplier.id, is_deleted=False).count()
    suggestions = ReplenishmentSuggestion.query.filter(
        ReplenishmentSuggestion.is_deleted == False,
        ReplenishmentSuggestion.supplier_id == supplier.id,
        ReplenishmentSuggestion.status == ReplenishmentSuggestion.STATUS_PENDING,
    ).count()
    on_time_rate = float(perf.on_time_rate if perf else supplier.credit_score or 88)
    quality_rate = float(perf.quality_rate if perf else supplier.credit_score or 88)
    credit_score = int(supplier.credit_score or 0)
    contact_ready = bool(supplier.contact_person and supplier.phone and supplier.email)
    spend_share = round((float(active_amount or 0) / total_spend * 100), 1) if total_spend else 0
    score = _bounded(on_time_rate * .28 + quality_rate * .3 + credit_score * .22 + (100 if contact_ready else 68) * .1 + max(0, 100 - pending_orders * 6) * .1)
    priority = _supplier_priority(score, quality_rate, credit_score, contact_ready, spend_share, pending_orders)
    status = _status_from_priority(priority)
    last_order = perf.last_order_date if perf else None
    return {
        'id': f'supplier-{supplier.id}',
        'supplier_id': supplier.id,
        'name': supplier.name,
        'contact': supplier.contact_person,
        'phone': supplier.phone,
        'email': supplier.email,
        'credit_score': credit_score,
        'on_time_rate': round(on_time_rate, 1),
        'quality_rate': round(quality_rate, 1),
        'score': score,
        'priority': priority,
        'status': status,
        'qualification_status': 'ready' if contact_ready and credit_score >= 80 else 'attention' if contact_ready else 'blocked',
        'capa_status': 'blocked' if quality_rate < 75 else 'attention' if quality_rate < 88 else 'ready',
        'pending_orders': int(pending_orders or 0),
        'active_amount': round(float(active_amount or 0), 2),
        'spend_share': spend_share,
        'product_count': int(products or 0),
        'suggestion_count': int(suggestions or 0),
        'last_order_date': last_order.isoformat() if last_order else None,
        'owner': '供应商经理' if priority != 'P0' else '采购总监',
        'path': '/app/suppliers/performance',
        'evidence': f"{supplier.name} 评分 {score}%，准点 {on_time_rate:.1f}%，质量 {quality_rate:.1f}%，未完采购 {pending_orders} 单，采购占比 {spend_share}%。",
        'action': _supplier_action(priority, contact_ready, quality_rate, spend_share, pending_orders),
    }


def _delivery_windows(limit=14):
    today = utcnow().date()
    orders = (
        PurchaseOrder.query
        .filter(
            PurchaseOrder.is_deleted == False,
            PurchaseOrder.supplier_id.isnot(None),
            PurchaseOrder.status.in_([
                PurchaseOrder.STATUS_PENDING,
                PurchaseOrder.STATUS_APPROVED,
                PurchaseOrder.STATUS_ORDERED,
                PurchaseOrder.STATUS_PARTIAL,
            ]),
        )
        .order_by(PurchaseOrder.expected_date.asc().nullslast(), PurchaseOrder.total_amount.desc())
        .limit(limit)
        .all()
    )
    windows = []
    for order in orders:
        expected = order.expected_date
        days_to_due = (expected - today).days if expected else 0
        progress = _bounded(order.receive_progress)
        priority = 'P0' if days_to_due < 0 or (order.status == PurchaseOrder.STATUS_PENDING and (order.total_amount or 0) > 100000) else 'P1' if days_to_due <= 3 or progress < 70 else 'P2'
        windows.append({
            'id': f'delivery-{order.id}',
            'purchase_id': order.id,
            'supplier_id': order.supplier_id,
            'po_no': order.po_no,
            'supplier': order.supplier.name if order.supplier else '供应商未维护',
            'warehouse': order.warehouse.name if order.warehouse else '待入库仓',
            'status': _status_from_priority(priority),
            'order_status': order.status,
            'priority': priority,
            'expected_date': expected.isoformat() if expected else None,
            'days_to_due': days_to_due,
            'progress': progress,
            'amount': round(float(order.total_amount or 0), 2),
            'owner': '采购跟单',
            'path': f'/app/procurement/orders/{order.id}',
            'evidence': f"{order.po_no} 预计到货 {expected.isoformat() if expected else '未维护'}，收货进度 {progress}%。",
            'action': '确认供应商交期、月台资源和质检窗口，必要时触发改期或替代供应。',
        })
    return windows


def _qualification_queue(cards):
    queue = []
    for card in cards:
        if card['qualification_status'] == 'ready' and card['credit_score'] >= 88:
            continue
        priority = 'P0' if card['qualification_status'] == 'blocked' or card['credit_score'] < 70 else 'P1'
        queue.append({
            'id': f"qualification-{card['supplier_id']}",
            'supplier_id': card['supplier_id'],
            'title': f"{card['name']}资质准入复核",
            'owner': '采购主数据',
            'priority': priority,
            'status': _status_from_priority(priority),
            'sla': '4h' if priority == 'P0' else '1d',
            'metric': f"{card['credit_score']}分",
            'path': card['path'],
            'evidence': f"{card['name']} 联系人/邮箱/电话或信用分未达到准入标准。",
            'action': '补齐联系人、邮箱、电话、资质材料和信用分，必要时冻结新采购。',
            'kind': '资质',
        })
    return queue[:10]


def _risk_queue(cards, delivery_windows, qualification_queue):
    queue = list(qualification_queue)
    for card in cards:
        if card['priority'] == 'P2':
            continue
        queue.append({
            'id': f"supplier-risk-{card['supplier_id']}",
            'supplier_id': card['supplier_id'],
            'title': f"{card['name']}供应商 360 复核",
            'owner': card['owner'],
            'priority': card['priority'],
            'status': card['status'],
            'sla': '4h' if card['priority'] == 'P0' else '1d',
            'metric': f"{card['score']}%",
            'path': card['path'],
            'evidence': card['evidence'],
            'action': card['action'],
            'kind': '风险',
        })
    for window in delivery_windows:
        if window['priority'] == 'P2':
            continue
        queue.append({
            'id': f"supplier-delivery-{window['purchase_id']}",
            'supplier_id': window['supplier_id'],
            'purchase_id': window['purchase_id'],
            'title': f"{window['po_no']}供应商交付 SLA",
            'owner': window['owner'],
            'priority': window['priority'],
            'status': window['status'],
            'sla': '4h' if window['priority'] == 'P0' else '1d',
            'metric': f"{window['progress']}%",
            'path': window['path'],
            'evidence': window['evidence'],
            'action': window['action'],
            'kind': '交付',
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    deduped = {}
    for item in queue:
        deduped.setdefault(item['id'], item)
    result = list(deduped.values())
    result.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item['kind'], item['title']))
    return result[:18]


def _summary_metrics(cards, delivery_windows, qualification_queue, risk_queue):
    open_tasks = Notification.query.filter(
        Notification.is_deleted == False,
        Notification.is_read == False,
        Notification.related_type == 'supplier_collaboration',
    ).count()
    quality_watch = sum(1 for card in cards if card['capa_status'] != 'ready')
    return {
        'active_suppliers': len(cards),
        'preferred_suppliers': sum(1 for card in cards if card['score'] >= 90 and card['priority'] == 'P2'),
        'risk_suppliers': sum(1 for card in cards if card['priority'] in {'P0', 'P1'}),
        'qualification_due': len(qualification_queue),
        'pending_orders': sum(card['pending_orders'] for card in cards),
        'delivery_due': sum(1 for item in delivery_windows if item['priority'] in {'P0', 'P1'}),
        'quality_watch': quality_watch,
        'open_tasks': int(open_tasks or 0),
        'spend_amount': round(sum(card['active_amount'] for card in cards), 2),
        'risk_queue': len(risk_queue),
    }


def _collaboration_lanes(m):
    return [
        _lane('qualification', '资质准入', '采购主数据', m['qualification_due'], m['qualification_due'], 100 - m['qualification_due'] * 12, '/app/suppliers/performance', f"{m['qualification_due']} 家供应商资质或联系人需要补齐。", '补齐资质材料、联系人、邮箱和信用分。'),
        _lane('delivery', '交付 SLA', '采购跟单', m['delivery_due'], 1 if m['delivery_due'] >= 4 else 0, 100 - m['delivery_due'] * 10, '/app/procurement/orders', f"{m['delivery_due']} 个供应商交付窗口需要跟进。", '确认交期、月台和异常改期。'),
        _lane('quality', '质量 CAPA', 'SQE', m['quality_watch'], 1 if m['quality_watch'] >= 4 else 0, 100 - m['quality_watch'] * 11, '/app/quality', f"{m['quality_watch']} 家供应商进入质量观察。", '发起 CAPA、隔离和使用决策复核。'),
        _lane('commercial', '商务集中度', '经营财务', m['risk_suppliers'], 1 if m['risk_suppliers'] >= 5 else 0, 100 - m['risk_suppliers'] * 7, '/app/budget', f"{m['risk_suppliers']} 家供应商存在风险或集中度复核。", '核对采购占比、备选供应和价格波动。'),
        _lane('collaboration', '协同任务', '供应商经理', m['open_tasks'], m['open_tasks'], 100 - m['open_tasks'] * 9, '/app/tasks', f"{m['open_tasks']} 个供应商协同任务未闭环。", '进入任务异常中心跟踪处理。'),
    ]


def _lane(lane_id, label, owner, count, p1, score, path, evidence, action):
    priority = 'P0' if score < 62 or p1 >= 8 else 'P1' if p1 or score < 88 else 'P2'
    return {
        'id': lane_id,
        'label': label,
        'owner': owner,
        'active_count': int(count or 0),
        'p0': 1 if priority == 'P0' else 0,
        'p1': int(p1 or 0),
        'score': _bounded(score),
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': path,
        'evidence': evidence,
        'action': action,
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
    }


def _supplier_matrix(cards):
    return [
        {
            'name': card['name'],
            'score': card['score'],
            'on_time_rate': card['on_time_rate'],
            'quality_rate': card['quality_rate'],
            'credit_score': card['credit_score'],
            'spend_share': card['spend_share'],
            'pending_orders': card['pending_orders'],
            'status': card['status'],
        }
        for card in cards[:12]
    ]


def _network_score(metrics, queue):
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')
    return _bounded(100 - p0 * 13 - p1 * 5 - metrics['qualification_due'] * 3 - metrics['quality_watch'] * 2)


def _supplier_priority(score, quality_rate, credit_score, contact_ready, spend_share, pending_orders):
    if score < 70 or quality_rate < 72 or credit_score < 68 or not contact_ready:
        return 'P0'
    if score < 86 or quality_rate < 88 or spend_share >= 35 or pending_orders >= 4:
        return 'P1'
    return 'P2'


def _supplier_action(priority, contact_ready, quality_rate, spend_share, pending_orders):
    if not contact_ready:
        return '补齐联系人、邮箱、电话和资质材料后再释放新增采购。'
    if quality_rate < 88:
        return '发起 SQE 质量 CAPA，复核来料批次、检验记录和使用决策。'
    if spend_share >= 35:
        return '复核采购集中度、备选供应商和价格波动，避免单点供应风险。'
    if pending_orders >= 4:
        return '确认供应商交付承诺、到货窗口和采购跟单负责人。'
    return '保持准点、质量和商务条款周复盘。'


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


def _bounded(value):
    return round(max(0, min(100, float(value or 0))), 1)
