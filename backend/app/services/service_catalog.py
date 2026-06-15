from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.auth import User
from app.models.biz import Product
from app.models.content import Attachment
from app.models.finance import PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder
from app.models.stock import InventoryLog, Stock
from app.models.stocktake import StockTake
from app.models.sys import AiChatSession, AuditLog
from app.models.trade import Order
from app.utils.time import utcnow


SERVICE_CATALOG = [
    {
        'id': 'identity',
        'name': '身份与权限服务',
        'domain': 'platform',
        'owner': '平台安全',
        'path': '/app/system/users',
        'dependencies': ['audit'],
        'contracts': ['JWT Cookie', 'CSRF', 'RBAC'],
        'api_surface': ['/auth/*', '/me/*', '/system/users'],
        'runtime': {'unit': 'backend-api', 'probe': '/api/v1/health/ready', 'store': 'PostgreSQL'},
        'runbook': ['确认 Cookie/CSRF 配置', '复核角色权限矩阵', '查看审计登录事件'],
        'slo_ms': 120,
        'data_objects': ['users', 'roles', 'permissions'],
        'status_metric': 'users',
    },
    {
        'id': 'inventory',
        'name': '库存与库位服务',
        'domain': 'supply',
        'owner': '仓配运营',
        'path': '/app/inventory/stock',
        'dependencies': ['procurement', 'fulfillment', 'audit'],
        'contracts': ['StockSnapshot.v1', 'InventoryMovement.v1'],
        'api_surface': ['/inventory/stock', '/inventory/health', '/inventory/adjust'],
        'runtime': {'unit': 'inventory-domain', 'probe': '/api/v1/inventory/health', 'store': 'PostgreSQL'},
        'runbook': ['查看低库存物料', '重新生成补货建议', '复核库存流水和盘点差异'],
        'slo_ms': 160,
        'data_objects': ['products', 'stock', 'inventory_logs'],
        'status_metric': 'stock_logs',
    },
    {
        'id': 'procurement',
        'name': '采购协同服务',
        'domain': 'supply',
        'owner': '采购中心',
        'path': '/app/procurement/orders',
        'dependencies': ['inventory', 'finance', 'audit'],
        'contracts': ['PurchaseOrder.v1', 'SupplierScore.v1'],
        'api_surface': ['/procurement/orders', '/purchase-orders/*', '/suppliers/performance'],
        'runtime': {'unit': 'procurement-domain', 'probe': '/api/v1/procurement/summary', 'store': 'PostgreSQL'},
        'runbook': ['处理待提交采购单', '审批或驳回采购单', '复核供应商绩效'],
        'slo_ms': 180,
        'data_objects': ['purchase_orders', 'suppliers', 'replenishment'],
        'status_metric': 'purchase_orders',
    },
    {
        'id': 'fulfillment',
        'name': '销售履约服务',
        'domain': 'revenue',
        'owner': '销售运营',
        'path': '/app/sales/orders',
        'dependencies': ['inventory', 'finance', 'notifications', 'audit'],
        'contracts': ['SalesOrder.v1', 'FulfillmentTransition.v1'],
        'api_surface': ['/sales/orders', '/sales/orders/*/transition'],
        'runtime': {'unit': 'fulfillment-domain', 'probe': '/api/v1/manufacturing/command-center', 'store': 'PostgreSQL'},
        'runbook': ['推进待履约订单', '复核库存占用', '检查应收生成状态'],
        'slo_ms': 180,
        'data_objects': ['orders', 'customers', 'stock'],
        'status_metric': 'orders',
    },
    {
        'id': 'finance',
        'name': '应收与信用服务',
        'domain': 'revenue',
        'owner': '财务共享',
        'path': '/app/finance/receivables',
        'dependencies': ['fulfillment', 'notifications', 'audit'],
        'contracts': ['Receivable.v1', 'PaymentRecord.v1'],
        'api_surface': ['/finance/receivables', '/receivables/*/payment', '/finance/credits'],
        'runtime': {'unit': 'finance-domain', 'probe': '/api/v1/analytics/executive', 'store': 'PostgreSQL'},
        'runbook': ['处理逾期应收', '记录银行回款', '冻结或解冻高风险客户'],
        'slo_ms': 150,
        'data_objects': ['receivables', 'payments', 'credits'],
        'status_metric': 'finance_records',
    },
    {
        'id': 'stocktake',
        'name': '盘点闭环服务',
        'domain': 'supply',
        'owner': '仓储稽核',
        'path': '/app/stocktakes',
        'dependencies': ['inventory', 'audit'],
        'contracts': ['StockTakePlan.v1', 'VarianceAdjustment.v1'],
        'api_surface': ['/stocktakes', '/stocktakes/*/count', '/stocktakes/*/complete'],
        'runtime': {'unit': 'stocktake-domain', 'probe': '/api/v1/stocktakes', 'store': 'PostgreSQL'},
        'runbook': ['开始计划盘点', '补录未盘物料', '完成盘点并自动调整'],
        'slo_ms': 190,
        'data_objects': ['stocktakes', 'stocktake_items'],
        'status_metric': 'stocktakes',
    },
    {
        'id': 'reporting',
        'name': '报表归档服务',
        'domain': 'insight',
        'owner': '经营分析',
        'path': '/app/reports',
        'dependencies': ['inventory', 'procurement', 'fulfillment', 'finance', 'files'],
        'contracts': ['GeneratedReport.v1', 'Subscription.v1'],
        'api_surface': ['/reports', '/reports/generate/*', '/reports/types'],
        'runtime': {'unit': 'reporting-domain', 'probe': '/api/v1/reports/types', 'store': 'PostgreSQL + file storage'},
        'runbook': ['检查报表类型', '重新生成失败报表', '确认导出件进入文件中心'],
        'slo_ms': 220,
        'data_objects': ['generated_reports', 'subscriptions'],
        'status_metric': 'reports',
    },
    {
        'id': 'files',
        'name': '文件资料服务',
        'domain': 'platform',
        'owner': '知识运营',
        'path': '/app/files',
        'dependencies': ['identity', 'audit'],
        'contracts': ['Attachment.v1', 'SignedDownload.v1'],
        'api_surface': ['/files', '/files/upload', '/files/*/download'],
        'runtime': {'unit': 'file-domain', 'probe': '/api/v1/health', 'store': 'Cloudinary or persistent volume'},
        'runbook': ['确认持久化存储', '复核上传类型策略', '检查下载权限和审计'],
        'slo_ms': 210,
        'data_objects': ['attachments', 'library'],
        'status_metric': 'attachments',
    },
    {
        'id': 'ai',
        'name': '经营分析服务',
        'domain': 'insight',
        'owner': '数据运营',
        'path': '/app/ai',
        'dependencies': ['inventory', 'finance', 'reporting', 'audit'],
        'contracts': ['OperationsBrief.v1', 'AnalysisSettings.v1'],
        'api_surface': ['/ai/*', '/analytics/executive'],
        'runtime': {'unit': 'analysis-domain', 'probe': '/api/v1/ai/diagnostics', 'store': 'PostgreSQL + AI provider'},
        'runbook': ['运行 AI 诊断', '切换本地/混合/外部模式', '复核经营分析上下文'],
        'slo_ms': 260,
        'data_objects': ['ai_sessions', 'ai_messages'],
        'status_metric': 'ai_sessions',
    },
    {
        'id': 'notifications',
        'name': '通知任务服务',
        'domain': 'platform',
        'owner': '运营协同',
        'path': '/app/notifications',
        'dependencies': ['identity', 'audit'],
        'contracts': ['Notification.v1', 'TaskSignal.v1'],
        'api_surface': ['/notifications', '/notifications/mark-read', '/operations/*'],
        'runtime': {'unit': 'notification-domain', 'probe': '/api/v1/operations/todo', 'store': 'PostgreSQL'},
        'runbook': ['查看未读任务', '标记处理完成', '回到相关业务源闭环'],
        'slo_ms': 130,
        'data_objects': ['notifications', 'alerts'],
        'status_metric': 'notifications',
    },
    {
        'id': 'audit',
        'name': '审计追踪服务',
        'domain': 'platform',
        'owner': '内控合规',
        'path': '/app/system/audit',
        'dependencies': [],
        'contracts': ['AuditEvent.v1'],
        'api_surface': ['/system/audit', '/audit-logs'],
        'runtime': {'unit': 'audit-domain', 'probe': '/api/v1/system/audit', 'store': 'PostgreSQL'},
        'runbook': ['筛选失败事件', '回看操作者和模块', '抽查高风险写入动作'],
        'slo_ms': 110,
        'data_objects': ['audit_logs'],
        'status_metric': 'audit_logs',
    },
]


def _count(query):
    return int(query.scalar() or 0)


def service_metrics():
    overdue = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).count()
    low_stock = (
        db.session.query(Product.id)
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .having(func.coalesce(func.sum(Stock.quantity), 0) <= func.coalesce(Product.min_stock, 0))
        .count()
    )
    audit_errors = AuditLog.query.filter(
        AuditLog.is_deleted == False,
        AuditLog.details.ilike('%失败%')
    ).count()
    pending_purchase = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING])
    ).count()
    open_stocktakes = StockTake.query.filter(
        StockTake.is_deleted == False,
        StockTake.status != StockTake.STATUS_COMPLETED,
    ).count()

    return {
        'users': User.query.filter_by(is_deleted=False).count(),
        'stock_logs': InventoryLog.query.filter_by(is_deleted=False).count(),
        'purchase_orders': PurchaseOrder.query.filter_by(is_deleted=False).count(),
        'orders': Order.query.filter_by(is_deleted=False).count(),
        'finance_records': Receivable.query.filter_by(is_deleted=False).count() + PaymentRecord.query.filter_by(is_deleted=False).count(),
        'stocktakes': StockTake.query.filter_by(is_deleted=False).count(),
        'reports': GeneratedReport.query.filter_by(is_deleted=False).count(),
        'attachments': Attachment.query.filter_by(is_deleted=False).count(),
        'ai_sessions': AiChatSession.query.count(),
        'notifications': Notification.query.filter_by(is_deleted=False).count() + StockAlert.query.filter_by(is_deleted=False).count() + ReplenishmentSuggestion.query.filter_by(is_deleted=False).count(),
        'audit_logs': AuditLog.query.filter_by(is_deleted=False).count(),
        'risk': {
            'overdue_receivables': overdue,
            'low_stock_products': low_stock,
            'audit_errors': audit_errors,
            'pending_purchase': pending_purchase,
            'open_stocktakes': open_stocktakes,
        }
    }


def risk_for_service(service_id, metrics):
    risk = metrics['risk']
    if service_id == 'finance' and risk['overdue_receivables']:
        return 'attention', f"{risk['overdue_receivables']} 笔逾期/坏账应收需要回写"
    if service_id == 'inventory' and risk['low_stock_products']:
        return 'attention', f"{risk['low_stock_products']} 个物料触发低库存"
    if service_id == 'procurement' and risk['pending_purchase']:
        return 'attention', f"{risk['pending_purchase']} 张采购单等待审批或提交"
    if service_id == 'stocktake' and risk['open_stocktakes']:
        return 'attention', f"{risk['open_stocktakes']} 个盘点计划未闭环"
    if service_id == 'audit' and risk['audit_errors']:
        return 'attention', f"{risk['audit_errors']} 条失败事件需要复核"
    return 'healthy', '服务契约与业务对象同步正常'


def latency_for(service, records, status):
    load_factor = min(int(records or 0) // 1200, 90)
    dependency_factor = len(service['dependencies']) * 9
    status_factor = 34 if status != 'healthy' else 0
    return int(min(service['slo_ms'] + load_factor + dependency_factor + status_factor, 420))


def readiness_for(status, latency_ms, slo_ms, dependencies):
    score = 100
    if status != 'healthy':
        score -= 18
    if latency_ms > slo_ms:
        score -= min(22, int((latency_ms - slo_ms) / max(slo_ms, 1) * 40))
    score -= min(len(dependencies) * 2, 12)
    return max(score, 45)


def architecture_for(service, readiness, contract_coverage):
    dependencies = service.get('dependencies') or []
    api_surface = service.get('api_surface') or []
    data_objects = service.get('data_objects') or []
    readiness_level = 'ready' if readiness >= 86 and contract_coverage >= 92 else 'attention' if readiness >= 68 else 'blocked'
    split_score = max(45, min(100, round(readiness * .42 + contract_coverage * .34 + min(len(api_surface), 4) * 6 + min(len(data_objects), 4) * 3 - min(len(dependencies), 5) * 2)))
    return {
        'bounded_context': f"{service['domain']}.{service['id']}",
        'frontend_entry': service.get('path'),
        'api_gateway_prefix': f"/api/v1/{service['id']}",
        'database_owner': service['runtime']['store'],
        'deployment_unit': service['runtime']['unit'],
        'split_phase': split_phase_for(service['id']),
        'split_readiness': readiness_level,
        'split_score': split_score,
        'ownership': {
            'product_owner': service['owner'],
            'tech_owner': f"{service['id']}-domain",
            'support_channel': f"#nexus-{service['id']}",
        },
        'anti_corruption_layer': anti_corruption_layer_for(service),
    }


def split_phase_for(service_id):
    phases = {
        'identity': 'phase-0-platform',
        'audit': 'phase-0-platform',
        'inventory': 'phase-1-supply-core',
        'procurement': 'phase-1-supply-core',
        'finance': 'phase-2-revenue-risk',
        'fulfillment': 'phase-2-revenue-risk',
        'notifications': 'phase-3-collaboration',
        'reporting': 'phase-3-collaboration',
        'files': 'phase-3-collaboration',
        'ai': 'phase-4-intelligence',
        'stocktake': 'phase-1-supply-core',
    }
    return phases.get(service_id, 'phase-2-domain')


def anti_corruption_layer_for(service):
    dependencies = service.get('dependencies') or []
    if not dependencies:
        return 'none'
    return {
        'adapter': f"{service['id']}_adapter",
        'contracts': service.get('contracts') or [],
        'upstream_dependencies': dependencies,
    }


def domain_events_for(service):
    event_catalog = {
        'identity': ['UserLoggedIn.v1', 'RoleChanged.v1'],
        'inventory': ['StockSnapshotChanged.v1', 'LowStockDetected.v1'],
        'procurement': ['PurchaseOrderSubmitted.v1', 'GoodsReceived.v1'],
        'fulfillment': ['SalesOrderTransitioned.v1', 'ShipmentCompleted.v1'],
        'finance': ['ReceivableIssued.v1', 'PaymentRecorded.v1'],
        'stocktake': ['StockTakeStarted.v1', 'VarianceAdjusted.v1'],
        'reporting': ['ReportGenerated.v1', 'ReportArchived.v1'],
        'files': ['AttachmentUploaded.v1', 'FileDownloaded.v1'],
        'ai': ['AnalysisRequested.v1', 'OperationsBriefCreated.v1'],
        'notifications': ['NotificationCreated.v1', 'TaskCompleted.v1'],
        'audit': ['AuditEventRecorded.v1'],
    }
    return event_catalog.get(service['id'], [f"{service['id'].title()}Changed.v1"])


def gateway_routes_for(service):
    return [
        {
            'source': surface,
            'gateway': f"/api/v1/{service['id']}{('/' + surface.strip('/').split('/')[-1]) if surface.startswith('/') else ''}",
            'policy': 'cookie+jwt+csrf' if any(token in surface for token in ('*', 'orders', 'receivables', 'stocktakes', 'files', 'system')) else 'cookie+jwt',
        }
        for surface in service.get('api_surface') or []
    ]


def integration_payload():
    metrics = service_metrics()
    now = utcnow()
    items = []

    for index, service in enumerate(SERVICE_CATALOG):
        records = int(metrics.get(service['status_metric'], 0) or 0)
        status, risk_note = risk_for_service(service['id'], metrics)
        latency_ms = latency_for(service, records, status)
        readiness = readiness_for(status, latency_ms, service['slo_ms'], service['dependencies'])
        last_sync = now - timedelta(minutes=index * 3 + len(service['dependencies']))
        items.append({
            'id': service['id'],
            'name': service['name'],
            'domain': service['domain'],
            'owner': service['owner'],
            'runtime': service['runtime'],
            'status': status,
            'latency_ms': latency_ms,
            'slo_ms': service['slo_ms'],
            'records': records,
            'readiness': readiness,
            'contract_coverage': contract_coverage_for(service),
            'risk_note': risk_note,
            'last_sync': last_sync.isoformat(),
            'path': service['path'],
            'dependencies': service['dependencies'],
            'contracts': service['contracts'],
            'api_surface': service['api_surface'],
            'data_objects': service['data_objects'],
            'runbook': service['runbook'],
            'observability': observability_for(service),
            'architecture': architecture_for(service, readiness, contract_coverage_for(service)),
            'events': domain_events_for(service),
            'gateway_routes': gateway_routes_for(service),
        })

    dependencies = [
        {'from': service['id'], 'to': dependency}
        for service in SERVICE_CATALOG
        for dependency in service['dependencies']
    ]
    healthy = sum(1 for item in items if item['status'] == 'healthy')
    attention = len(items) - healthy
    return {
        'items': items,
        'summary': {
            'healthy': healthy,
            'attention': attention,
            'records': sum(int(item['records'] or 0) for item in items),
            'avg_latency_ms': round(sum(item['latency_ms'] for item in items) / max(len(items), 1)),
            'avg_readiness': round(sum(item['readiness'] for item in items) / max(len(items), 1)),
            'contracts': sum(len(item['contracts']) for item in items),
            'dependencies': len(dependencies),
            'api_surfaces': sum(len(item['api_surface']) for item in items),
            'runbook_steps': sum(len(item['runbook']) for item in items),
            'avg_contract_coverage': round(sum(item['contract_coverage'] for item in items) / max(len(items), 1)),
            'avg_split_score': round(sum(item['architecture']['split_score'] for item in items) / max(len(items), 1)),
        },
        'topology': topology_summary(items, dependencies),
        'split_plan': split_plan(items),
        'observability': observability_summary(items),
        'incident_queue': incident_queue(items),
        'readiness': {
            'level': 'attention' if attention else 'ready',
            'message': '存在需复核的业务域，优先处理风险服务。' if attention else '核心服务契约、依赖和业务数据均处于就绪状态。',
            'risk': metrics['risk'],
        },
        'dependencies': dependencies,
        'domains': domain_summary(items),
    }


def contract_coverage_for(service):
    required = {
        'contracts': len(service.get('contracts') or []),
        'api_surface': len(service.get('api_surface') or []),
        'data_objects': len(service.get('data_objects') or []),
        'runbook': len(service.get('runbook') or []),
        'probe': 1 if (service.get('runtime') or {}).get('probe') else 0,
    }
    score = 0
    score += 28 if required['contracts'] >= 1 else 0
    score += 24 if required['api_surface'] >= 1 else 0
    score += 20 if required['data_objects'] >= 1 else 0
    score += 16 if required['runbook'] >= 2 else 0
    score += 12 if required['probe'] else 0
    return score


def observability_for(service):
    dependencies = service.get('dependencies') or []
    contracts = service.get('contracts') or []
    api_surface = service.get('api_surface') or []
    data_objects = service.get('data_objects') or []
    signals = {
        'metrics': bool((service.get('runtime') or {}).get('probe')),
        'logs': 'audit' in dependencies or service.get('id') in {'identity', 'audit', 'notifications'},
        'traces': bool(dependencies and api_surface and contracts),
    }
    coverage = round(sum(1 for enabled in signals.values() if enabled) / max(len(signals), 1) * 100)
    missing = [label for label, enabled in signals.items() if not enabled]
    evidence = []
    if signals['metrics']:
        evidence.append('health probe')
    if signals['logs']:
        evidence.append('audit log')
    if signals['traces']:
        evidence.append('dependency trace')
    return {
        'signals': signals,
        'coverage': coverage,
        'missing': missing,
        'evidence': evidence,
        'span_name': f"{service['id']}.request",
        'metric_name': f"nexus_{service['id']}_latency_ms",
        'log_stream': f"nexus.{service['id']}.audit" if service.get('id') != 'audit' else 'nexus.audit',
        'data_objects': data_objects,
    }


def observability_summary(items):
    signals = {'metrics': 0, 'logs': 0, 'traces': 0}
    for item in items:
        for key, enabled in item['observability']['signals'].items():
            signals[key] += 1 if enabled else 0
    total = max(len(items), 1)
    signal_items = [
        {'key': key, 'label': {'metrics': 'Metrics', 'logs': 'Logs', 'traces': 'Traces'}[key], 'ready': value, 'total': len(items), 'coverage': round(value / total * 100)}
        for key, value in signals.items()
    ]
    avg_coverage = round(sum(item['observability']['coverage'] for item in items) / total)
    missing = sorted({
        f"{item['name']} 缺少 {signal}"
        for item in items
        for signal in item['observability']['missing']
    })
    return {
        'coverage': avg_coverage,
        'signals': signal_items,
        'missing': missing[:8],
        'policy': 'metrics + logs + traces',
    }


def incident_queue(items):
    queue = []
    for item in items:
        latency_gap = max(0, item['latency_ms'] - item['slo_ms'])
        latency_ratio = item['latency_ms'] / max(item['slo_ms'], 1)
        error_budget_remaining = max(0, min(100, item['readiness'] - (18 if item['status'] != 'healthy' else 0) - round(latency_gap / max(item['slo_ms'], 1) * 35)))
        needs_action = (
            item['status'] != 'healthy'
            or item['contract_coverage'] < 92
            or item['observability']['coverage'] < 100
            or item['latency_ms'] > item['slo_ms']
        )
        if not needs_action:
            continue
        if latency_ratio >= 1.35 or item['readiness'] < 64:
            priority = 'P0'
        elif item['status'] != 'healthy' or item['latency_ms'] > item['slo_ms']:
            priority = 'P1'
        else:
            priority = 'P2'
        missing = ', '.join(item['observability']['missing']) if item['observability']['missing'] else '观测信号完整'
        action = item['runbook'][0] if item['runbook'] else '复核服务契约与运行状态'
        queue.append({
            'id': f"integration-{item['id']}",
            'service_id': item['id'],
            'title': item['name'],
            'priority': priority,
            'owner': item['owner'],
            'status': item['status'],
            'path': item['path'],
            'action': action,
            'evidence': f"{item['risk_note']}；延迟 {item['latency_ms']}ms / SLO {item['slo_ms']}ms；观测缺口：{missing}",
            'due': 'T+30m' if priority == 'P0' else 'T+2h' if priority == 'P1' else 'T+1d',
            'error_budget_remaining': error_budget_remaining,
            'signal_coverage': item['observability']['coverage'],
            'contract_coverage': item['contract_coverage'],
            'runtime_unit': item['runtime']['unit'],
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    queue.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item['error_budget_remaining'], item['signal_coverage']))
    return queue[:8]


def topology_summary(items, dependencies):
    units = sorted({item['runtime']['unit'] for item in items})
    stores = sorted({item['runtime']['store'] for item in items})
    probes = [item['runtime']['probe'] for item in items]
    return {
        'deployment_units': units,
        'stores': stores,
        'probe_count': len(probes),
        'edge_count': len(dependencies),
        'max_dependencies': max((len(item['dependencies']) for item in items), default=0),
    }


def split_plan(items):
    phases = {}
    for item in items:
        phase = item['architecture']['split_phase']
        bucket = phases.setdefault(phase, {
            'phase': phase,
            'services': [],
            'ready': 0,
            'attention': 0,
            'avg_split_score': 0,
            'events': 0,
            'gateway_routes': 0,
        })
        bucket['services'].append(item['id'])
        bucket['ready'] += 1 if item['architecture']['split_readiness'] == 'ready' else 0
        bucket['attention'] += 1 if item['architecture']['split_readiness'] != 'ready' else 0
        bucket['avg_split_score'] += item['architecture']['split_score']
        bucket['events'] += len(item.get('events') or [])
        bucket['gateway_routes'] += len(item.get('gateway_routes') or [])
    for bucket in phases.values():
        bucket['avg_split_score'] = round(bucket['avg_split_score'] / max(len(bucket['services']), 1))
    return sorted(phases.values(), key=lambda item: item['phase'])


def domain_summary(items):
    domains = {}
    for item in items:
        bucket = domains.setdefault(item['domain'], {'domain': item['domain'], 'services': 0, 'attention': 0, 'records': 0, 'readiness': 0})
        bucket['services'] += 1
        bucket['attention'] += 1 if item['status'] != 'healthy' else 0
        bucket['records'] += int(item['records'] or 0)
        bucket['readiness'] += int(item['readiness'] or 0)
    for bucket in domains.values():
        bucket['avg_readiness'] = round(bucket['readiness'] / max(bucket['services'], 1))
        del bucket['readiness']
    return list(domains.values())
