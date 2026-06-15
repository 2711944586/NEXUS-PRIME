from datetime import timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.models.finance import Receivable
from app.models.notification import GeneratedReport, ReportSubscription, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock
from app.models.sys import AuditLog
from app.utils.time import utcnow


def rules_governance_payload():
    metrics = _rule_metrics()
    rules = _rules(metrics)
    decision_queue = _decision_queue(rules)
    hits = sum(int(item['hit_count'] or 0) for item in rules)
    risks = sum(int(item['risk_count'] or 0) for item in rules)
    p0 = sum(1 for item in decision_queue if item['priority'] == 'P0')
    p1 = sum(1 for item in decision_queue if item['priority'] == 'P1')

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'rules_governance_contract',
        'summary': {
            'total': len(rules),
            'enabled': sum(1 for item in rules if item['enabled']),
            'hits': hits,
            'risks': risks,
            'p0': p0,
            'p1': p1,
            'queue_count': len(decision_queue),
            'automation_rate': _automation_rate(hits, risks),
            'coverage': _average([item['coverage'] for item in rules]),
            'primary_owner': decision_queue[0]['owner'] if decision_queue else '规则治理台',
            'next_action': decision_queue[0]['action'] if decision_queue else '保持每日规则命中抽样、阈值复核和审计回放。',
        },
        'items': rules,
        'decision_queue': decision_queue,
        'domains': _domains(rules),
        'decision_map': [
            {'from': '规则事实源', 'to': 'DMN 决策表', 'label': '库存、采购、应收、报表、审计事件', 'status': _status(risks, p0)},
            {'from': 'DMN 决策表', 'to': '风险队列', 'label': f'{len(decision_queue)} 个治理动作', 'status': 'attention' if decision_queue else 'ready'},
            {'from': '风险队列', 'to': '任务异常中心', 'label': '复核任务、负责人、SLA、证据写入通知', 'status': 'attention' if decision_queue else 'ready'},
            {'from': '任务异常中心', 'to': '审计日志', 'label': '规则复核、处理完成、来源模块闭环', 'status': 'ready'},
        ],
        'runbook': [
            {'step': '锁定命中事实', 'detail': '从规则卡进入来源模块，按规则输入字段核对命中对象和业务上下文。'},
            {'step': '复核决策表', 'detail': '检查 hit policy、条件列、输出列和优先级，确认是否存在阈值噪声或遗漏。'},
            {'step': '派发治理任务', 'detail': '把 rule_id、负责人、SLA、证据和下一步动作写入通知与当班任务队列。'},
            {'step': '回放审计证据', 'detail': '在审计日志中验证规则复核、业务处理和数据修复均有可追踪记录。'},
        ],
    }


def select_rule_review_context(rule_id=None, rule_name=None):
    payload = rules_governance_payload()
    rules = payload['items']
    rule = None
    if rule_id:
        rule = next((item for item in rules if item['id'] == rule_id), None)
    if not rule and rule_name:
        rule = next((item for item in rules if item['name'] == rule_name), None)
    if not rule:
        rule = sorted(rules, key=lambda item: (item['risk_count'], item['hit_count']), reverse=True)[0] if rules else None
    queue_item = next((item for item in payload['decision_queue'] if rule and item['rule_id'] == rule['id']), None)
    return payload, rule, queue_item


def _rule_metrics():
    active_alerts = StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE, is_deleted=False)
    red_alerts = active_alerts.filter(StockAlert.alert_level == StockAlert.LEVEL_RED).count()
    yellow_alerts = active_alerts.filter(StockAlert.alert_level == StockAlert.LEVEL_YELLOW).count()
    low_stock_hits = ReplenishmentSuggestion.query.filter_by(is_deleted=False).count()
    stock_without_slot = Stock.query.filter(
        Stock.is_deleted == False,
        or_(Stock.shelf_location.is_(None), Stock.shelf_location == '')
    ).count()

    pending_purchase = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False)
    draft_purchase = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_DRAFT, is_deleted=False)
    high_value_purchase = pending_purchase.filter(PurchaseOrder.total_amount >= 100000).count()
    pending_purchase_count = pending_purchase.count()
    draft_purchase_count = draft_purchase.count()

    overdue_receivable = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status == Receivable.STATUS_OVERDUE
    ).count()
    bad_debt_receivable = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status == Receivable.STATUS_BAD_DEBT
    ).count()
    receivable_without_order = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.order_id.is_(None)
    ).count()
    overdue_amount = db.session.query(
        func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)
    ).filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).scalar()

    report_hits = GeneratedReport.query.filter_by(is_deleted=False).count()
    inactive_subscriptions = ReportSubscription.query.filter_by(is_active=False, is_deleted=False).count()
    reports_without_file = GeneratedReport.query.filter(
        GeneratedReport.is_deleted == False,
        or_(GeneratedReport.file_path.is_(None), GeneratedReport.file_path == '')
    ).count()

    audit_hits = AuditLog.query.filter_by(is_deleted=False).count()
    delete_actions = AuditLog.query.filter(
        AuditLog.is_deleted == False,
        AuditLog.action.ilike('%delete%')
    ).count()
    orphan_audit = AuditLog.query.filter(
        AuditLog.is_deleted == False,
        AuditLog.user_id.is_(None)
    ).count()

    return {
        'red_alerts': red_alerts,
        'yellow_alerts': yellow_alerts,
        'low_stock_hits': low_stock_hits,
        'stock_without_slot': stock_without_slot,
        'pending_purchase': pending_purchase_count,
        'draft_purchase': draft_purchase_count,
        'high_value_purchase': high_value_purchase,
        'overdue_receivable': overdue_receivable,
        'bad_debt_receivable': bad_debt_receivable,
        'receivable_without_order': receivable_without_order,
        'overdue_amount': float(overdue_amount or 0),
        'report_hits': report_hits,
        'inactive_subscriptions': inactive_subscriptions,
        'reports_without_file': reports_without_file,
        'audit_hits': audit_hits,
        'delete_actions': delete_actions,
        'orphan_audit': orphan_audit,
    }


def _rules(m):
    now = utcnow()
    return [
        _rule(
            rule_id='replenishment-low-stock',
            name='低库存自动补货规则',
            domain='库存',
            owner='仓配主管',
            priority='P0' if m['red_alerts'] else 'P1',
            sla='4h' if m['red_alerts'] else '1d',
            trigger='库存量 <= 安全库存，且补货建议未处理',
            action='生成补货建议，红色预警推送采购与仓配主管',
            hit_count=m['low_stock_hits'],
            risk_count=m['red_alerts'] + m['yellow_alerts'],
            path='/app/inventory/replenishment',
            hit_policy='RULE ORDER',
            status=_status(m['red_alerts'] + m['yellow_alerts'], 1 if m['red_alerts'] else 0),
            coverage=94,
            confidence=91,
            risk_note=f"{m['red_alerts']} 个红色预警、{m['yellow_alerts']} 个黄色预警、{m['stock_without_slot']} 条库存缺少库位。",
            inputs=[
                _io('stock_qty', '当前库存', 'stock_quantities.quantity', '<= safety_stock'),
                _io('alert_level', '预警等级', 'stock_alerts.alert_level', 'red/yellow'),
                _io('suggestion_status', '建议状态', 'stock_replenishment_suggestions.status', 'pending'),
            ],
            outputs=[
                _io('task_priority', '治理优先级', 'task_queue.priority', 'P0/P1'),
                _io('purchase_signal', '采购信号', 'purchase_orders', 'create_or_review'),
            ],
            rows=[
                _row('R1', 'P0', ['alert_level == red', 'suggestion_status == pending'], ['priority = P0', 'owner = 仓配主管'], '立即确认补货和安全库存阈值', m['red_alerts'], m['red_alerts'], 'blocked' if m['red_alerts'] else 'ready'),
                _row('R2', 'P1', ['stock_qty <= safety_stock', 'alert_level == yellow'], ['priority = P1', 'owner = 仓配计划'], '复核日均销量和采购提前期', m['yellow_alerts'], m['yellow_alerts'], 'attention' if m['yellow_alerts'] else 'ready'),
            ],
            service='库存与补货规则服务',
            contract='StockAlert + ReplenishmentSuggestion -> RuleDecision',
            event='inventory.low_stock.detected',
        ),
        _rule(
            rule_id='purchase-approval',
            name='采购审批优先级规则',
            domain='采购',
            owner='采购执行',
            priority='P0' if m['high_value_purchase'] else 'P1',
            sla='4h' if m['high_value_purchase'] else '1d',
            trigger='草稿或待审批采购单进入审批排序',
            action='按金额、供应商和补货影响排序，通知审批负责人',
            hit_count=m['pending_purchase'],
            risk_count=m['draft_purchase'] + m['pending_purchase'],
            path='/app/procurement/orders',
            hit_policy='FIRST',
            status=_status(m['draft_purchase'] + m['pending_purchase'], 1 if m['high_value_purchase'] else 0),
            coverage=92,
            confidence=89,
            risk_note=f"{m['draft_purchase']} 张草稿、{m['pending_purchase']} 张待审批、{m['high_value_purchase']} 张高金额采购单。",
            inputs=[
                _io('status', '采购状态', 'purchase_orders.status', 'draft/pending'),
                _io('amount', '采购金额', 'purchase_orders.total_amount', '>= 100000'),
                _io('supplier_score', '供应商评分', 'supplier_performance', 'on_time + quality'),
            ],
            outputs=[
                _io('approval_lane', '审批泳道', 'task_queue.category', 'approval'),
                _io('priority', '优先级', 'task_queue.priority', 'P0/P1'),
            ],
            rows=[
                _row('R1', 'P0', ['status == pending', 'total_amount >= 100000'], ['priority = P0', 'sla = 4h'], '高金额采购进入主管审批', m['high_value_purchase'], m['high_value_purchase'], 'blocked' if m['high_value_purchase'] else 'ready'),
                _row('R2', 'P1', ['status in draft,pending'], ['priority = P1', 'sla = 1d'], '推进提交、审批或取消', m['draft_purchase'] + m['pending_purchase'], m['draft_purchase'] + m['pending_purchase'], 'attention' if m['draft_purchase'] + m['pending_purchase'] else 'ready'),
            ],
            service='采购审批规则服务',
            contract='PurchaseOrder -> ApprovalDecision',
            event='procurement.approval.queued',
        ),
        _rule(
            rule_id='receivable-credit',
            name='应收信用联动规则',
            domain='财务',
            owner='应收风控',
            priority='P0' if m['bad_debt_receivable'] or m['overdue_receivable'] else 'P1',
            sla='4h' if m['bad_debt_receivable'] or m['overdue_receivable'] else '1d',
            trigger='逾期、坏账或信用占用异常',
            action='发送催收提醒，必要时冻结信用并创建回款任务',
            hit_count=m['overdue_receivable'] + m['bad_debt_receivable'],
            risk_count=m['overdue_receivable'] + m['bad_debt_receivable'],
            path='/app/finance/receivables',
            hit_policy='RULE ORDER',
            status=_status(m['overdue_receivable'] + m['bad_debt_receivable'], 1 if m['bad_debt_receivable'] or m['overdue_receivable'] else 0),
            coverage=90,
            confidence=88,
            risk_note=f"{m['overdue_receivable']} 笔逾期、{m['bad_debt_receivable']} 笔坏账风险，未收金额 {round(m['overdue_amount'], 2)}。",
            inputs=[
                _io('status', '应收状态', 'finance_receivables.status', 'overdue/bad_debt'),
                _io('unpaid', '未收金额', 'finance_receivables.total-paid', '> 0'),
                _io('order_link', '来源订单', 'finance_receivables.order_id', 'required'),
            ],
            outputs=[
                _io('collection_task', '催收任务', 'task_queue.category', 'finance'),
                _io('credit_action', '信用动作', 'finance_customer_credit', 'review/freeze'),
            ],
            rows=[
                _row('R1', 'P0', ['status == bad_debt'], ['priority = P0', 'credit_action = freeze_review'], '冻结前复核并升级财务负责人', m['bad_debt_receivable'], m['bad_debt_receivable'], 'blocked' if m['bad_debt_receivable'] else 'ready'),
                _row('R2', 'P0', ['status == overdue', 'unpaid > 0'], ['priority = P0', 'collection_task = create'], '创建催收与信用复核任务', m['overdue_receivable'], m['overdue_receivable'], 'blocked' if m['overdue_receivable'] else 'ready'),
            ],
            service='应收信用规则服务',
            contract='Receivable + CustomerCredit -> CreditDecision',
            event='finance.receivable.risk_detected',
        ),
        _rule(
            rule_id='report-archive',
            name='经营报表归档规则',
            domain='报表',
            owner='经营分析',
            priority='P1',
            sla='1d',
            trigger='报表生成完成但订阅、文件或发送状态异常',
            action='补齐归档文件、恢复订阅并通知经营分析负责人',
            hit_count=m['report_hits'],
            risk_count=m['inactive_subscriptions'] + m['reports_without_file'],
            path='/app/reports',
            hit_policy='COLLECT',
            status=_status(m['inactive_subscriptions'] + m['reports_without_file'], 0),
            coverage=93,
            confidence=90,
            risk_note=f"{m['inactive_subscriptions']} 个订阅停用、{m['reports_without_file']} 份报表缺少文件归档。",
            inputs=[
                _io('report_generated', '生成状态', 'generated_reports.generated_at', 'exists'),
                _io('subscription', '订阅状态', 'report_subscriptions.is_active', 'true'),
                _io('file_path', '归档文件', 'generated_reports.file_path', 'required'),
            ],
            outputs=[
                _io('archive_state', '归档状态', 'files', 'linked'),
                _io('notification', '通知', 'sys_notifications', 'report_ready'),
            ],
            rows=[
                _row('R1', 'P1', ['file_path is empty'], ['archive_state = missing'], '重新生成或补录归档文件', m['reports_without_file'], m['reports_without_file'], 'attention' if m['reports_without_file'] else 'ready'),
                _row('R2', 'P1', ['subscription == inactive'], ['notification = review'], '复核报表订阅和发送对象', m['inactive_subscriptions'], m['inactive_subscriptions'], 'attention' if m['inactive_subscriptions'] else 'ready'),
            ],
            service='报表归档规则服务',
            contract='GeneratedReport + ReportSubscription -> ArchiveDecision',
            event='report.archive.required',
        ),
        _rule(
            rule_id='audit-write',
            name='关键写入审计规则',
            domain='安全',
            owner='平台安全',
            priority='P0' if m['delete_actions'] else 'P1',
            sla='4h' if m['delete_actions'] else '1d',
            trigger='创建、审批、收货、发货、收款、上传和删除动作',
            action='记录操作人、模块、动作和业务对象，异常写入安全复核',
            hit_count=m['audit_hits'],
            risk_count=m['delete_actions'] + m['orphan_audit'],
            path='/app/system/audit',
            hit_policy='COLLECT',
            status=_status(m['delete_actions'] + m['orphan_audit'], 1 if m['delete_actions'] else 0),
            coverage=96,
            confidence=94,
            risk_note=f"{m['delete_actions']} 条删除类动作、{m['orphan_audit']} 条缺少操作者的审计记录。",
            inputs=[
                _io('module', '模块', 'sys_audit_logs.module', 'required'),
                _io('action', '动作', 'sys_audit_logs.action', 'write/delete/approve'),
                _io('operator', '操作者', 'sys_audit_logs.user_id', 'required'),
            ],
            outputs=[
                _io('audit_state', '审计状态', 'sys_audit_logs', 'recorded/review'),
                _io('security_review', '安全复核', 'task_queue.category', 'security'),
            ],
            rows=[
                _row('R1', 'P0', ['action contains delete'], ['security_review = required'], '复核删除动作和业务对象', m['delete_actions'], m['delete_actions'], 'blocked' if m['delete_actions'] else 'ready'),
                _row('R2', 'P1', ['operator is empty'], ['audit_state = incomplete'], '回填操作者或系统来源', m['orphan_audit'], m['orphan_audit'], 'attention' if m['orphan_audit'] else 'ready'),
            ],
            service='审计规则服务',
            contract='AuditLog -> AuditDecision',
            event='audit.write.captured',
        ),
    ]


def _rule(rule_id, name, domain, owner, priority, sla, trigger, action, hit_count, risk_count, path, hit_policy,
          status, coverage, confidence, risk_note, inputs, outputs, rows, service, contract, event):
    return {
        'id': rule_id,
        'name': name,
        'domain': domain,
        'trigger': trigger,
        'action': action,
        'enabled': True,
        'status': status,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'hit_policy': hit_policy,
        'hit_count': int(hit_count or 0),
        'risk_count': int(risk_count or 0),
        'automation_rate': _automation_rate(hit_count, risk_count),
        'coverage': coverage,
        'confidence': confidence,
        'path': path,
        'risk_note': risk_note,
        'evidence': f'{domain}规则命中 {int(hit_count or 0)} 个对象，风险队列 {int(risk_count or 0)} 个对象。',
        'runbook': [
            '确认事实源记录与规则输入字段一致',
            '复核命中行、输出动作和负责人',
            '必要时创建规则复核任务并在任务中心闭环',
        ],
        'decision_table': {
            'hit_policy': hit_policy,
            'inputs': inputs,
            'outputs': outputs,
            'rows': rows,
        },
        'governance': {
            'version': 'DMN-2026.06',
            'last_reviewed': (utcnow() - timedelta(days=7)).date().isoformat(),
            'next_review_due': (utcnow() + timedelta(days=7)).date().isoformat(),
            'approval_group': owner,
            'change_window': '每日 18:00-19:00',
            'monitoring_metric': f'nexus_rule_{rule_id.replace("-", "_")}_hits',
        },
        'service_boundary': {
            'service': service,
            'contract': contract,
            'event': event,
            'fallback': '规则复核失败时保留来源模块人工处理入口',
        },
    }


def _decision_queue(rules):
    items = []
    for rule in rules:
        if int(rule['risk_count'] or 0) <= 0:
            continue
        items.append({
            'id': f"{rule['id']}-review",
            'rule_id': rule['id'],
            'title': f"{rule['name']}复核",
            'domain': rule['domain'],
            'owner': rule['owner'],
            'priority': rule['priority'],
            'sla': rule['sla'],
            'status': rule['status'],
            'path': rule['path'],
            'hit_count': rule['hit_count'],
            'risk_count': rule['risk_count'],
            'evidence': rule['risk_note'],
            'action': rule['action'],
            'runbook': rule['runbook'],
            'escalation': f"{rule['owner']} -> 运营负责人 -> 平台安全" if rule['priority'] == 'P0' else f"{rule['owner']} -> 运营负责人",
            'created_at': utcnow().isoformat(),
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    items.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -int(item['risk_count'] or 0), item['rule_id']))
    return items


def _domains(rules):
    return [
        {
            'key': item['id'],
            'label': item['domain'],
            'owner': item['owner'],
            'hits': item['hit_count'],
            'risks': item['risk_count'],
            'coverage': item['coverage'],
            'status': item['status'],
            'metric': item['governance']['monitoring_metric'],
        }
        for item in rules
    ]


def _io(item_id, label, source, value):
    return {'id': item_id, 'label': label, 'source': source, 'value': value}


def _row(row_id, priority, conditions, outputs, action, hit_count, risk_count, status):
    return {
        'id': row_id,
        'priority': priority,
        'conditions': conditions,
        'outputs': outputs,
        'action': action,
        'hit_count': int(hit_count or 0),
        'risk_count': int(risk_count or 0),
        'status': status,
    }


def _status(risk_count, p0_count):
    if p0_count:
        return 'blocked'
    return 'attention' if int(risk_count or 0) > 0 else 'ready'


def _automation_rate(hits, risks):
    hits = float(hits or 0)
    risks = float(risks or 0)
    if hits + risks <= 0:
        return 100
    return max(0, min(100, round((hits / (hits + risks)) * 100)))


def _average(values):
    values = [float(item or 0) for item in values]
    return round(sum(values) / max(len(values), 1), 1)
