from app.extensions import db
from app.models.biz import Category, Product
from app.models.finance import PaymentRecord, Receivable
from app.models.notification import ReplenishmentSuggestion
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock
from app.models.trade import Order
from app.utils.time import utcnow
from sqlalchemy import func


def cost_governance_payload():
    metrics = _cost_metrics()
    centers = _cost_centers(metrics)
    variance_queue = _variance_queue(centers)
    p0 = sum(1 for item in variance_queue if item['priority'] == 'P0')
    p1 = sum(1 for item in variance_queue if item['priority'] == 'P1')
    total_budget = sum(item['budget'] for item in centers)
    total_actual = sum(item['actual'] for item in centers)
    total_commitment = sum(item['commitment'] for item in centers)
    available_budget = total_budget - total_actual - total_commitment

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'cost_governance_contract',
        'summary': {
            'inventory_value': metrics['inventory_value'],
            'sales_amount': metrics['sales_amount'],
            'procurement_amount': metrics['procurement_amount'],
            'unpaid_amount': metrics['unpaid_amount'],
            'paid_amount': metrics['paid_amount'],
            'cash_gap': metrics['unpaid_amount'] - metrics['paid_amount'],
            'budget_total': round(total_budget, 2),
            'actual_total': round(total_actual, 2),
            'commitment_total': round(total_commitment, 2),
            'available_budget': round(available_budget, 2),
            'variance_amount': round(total_actual + total_commitment - total_budget, 2),
            'burn_rate': _percent(total_actual + total_commitment, total_budget),
            'score': _score(centers, variance_queue),
            'p0': p0,
            'p1': p1,
            'queue_count': len(variance_queue),
            'primary_owner': variance_queue[0]['owner'] if variance_queue else '经营财务',
            'next_action': variance_queue[0]['action'] if variance_queue else '保持预算、实际、采购承诺和现金回款每日复盘。',
        },
        'cost_centers': centers,
        'variance_queue': variance_queue,
        'categories': _inventory_categories(),
        'timeline': [
            {'name': '销售收入', 'value': metrics['sales_amount']},
            {'name': '采购投入', 'value': metrics['procurement_amount']},
            {'name': '库存占用', 'value': metrics['inventory_value']},
            {'name': '已收款', 'value': metrics['paid_amount']},
            {'name': '未收款', 'value': metrics['unpaid_amount']},
            {'name': '采购承诺', 'value': metrics['pending_procurement_amount']},
        ],
        'waterfall': [
            {'name': '预算池', 'value': round(total_budget, 2), 'type': 'budget'},
            {'name': '实际消耗', 'value': -round(total_actual, 2), 'type': 'actual'},
            {'name': '采购承诺', 'value': -round(total_commitment, 2), 'type': 'commitment'},
            {'name': '可用预算', 'value': round(available_budget, 2), 'type': 'available'},
        ],
        'runbook': [
            {'step': '锁定差异来源', 'detail': '先看 P0/P1 成本中心，核对预算、实际消耗、采购承诺和可用预算。'},
            {'step': '回到业务模块', 'detail': '进入采购、库存或应收模块处理单据、库存资金占用或回款缺口。'},
            {'step': '创建复核任务', 'detail': '把差异金额、负责人、SLA、证据和处理动作写入通知与审计日志。'},
            {'step': '归档经营复盘', 'detail': '完成后生成经营报表，保留预算调整和成本复核证据。'},
        ],
        'service_boundary': [
            {'service': '成本治理聚合 API', 'contract': 'BudgetActualCommitment -> CostGovernance', 'owner': '经营财务', 'readiness': _boundary_status(variance_queue)},
            {'service': '采购承诺服务边界', 'contract': 'PurchaseOrder -> CommitmentExposure', 'owner': '采购执行', 'readiness': _center_status(centers, 'procurement-commitment')},
            {'service': '库存资金服务边界', 'contract': 'Stock + Product.cost -> InventoryCapital', 'owner': '仓配主管', 'readiness': _center_status(centers, 'inventory-capital')},
            {'service': '应收现金服务边界', 'contract': 'Receivable + PaymentRecord -> CashGap', 'owner': '应收风控', 'readiness': _center_status(centers, 'cash-collection')},
        ],
    }


def select_cost_review_context(item_id=None, title=None):
    payload = cost_governance_payload()
    queue = payload['variance_queue']
    centers = payload['cost_centers']
    item = None
    if item_id:
        item = next((entry for entry in queue if entry['id'] == item_id or entry['cost_center_id'] == item_id), None)
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


def _cost_metrics():
    inventory_value = db.session.query(
        func.coalesce(func.sum(Stock.quantity * Product.cost), 0)
    ).join(Product, Product.id == Stock.product_id).filter(
        Stock.is_deleted == False,
        Product.is_deleted == False,
    ).scalar()
    sales_amount = db.session.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(Order.is_deleted == False).scalar()
    procurement_amount = db.session.query(
        func.coalesce(func.sum(PurchaseOrder.total_amount), 0)
    ).filter(PurchaseOrder.is_deleted == False).scalar()
    pending_procurement_amount = db.session.query(
        func.coalesce(func.sum(PurchaseOrder.total_amount), 0)
    ).filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_ORDERED,
            PurchaseOrder.STATUS_PARTIAL,
        ])
    ).scalar()
    unpaid_amount = db.session.query(
        func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)
    ).filter(Receivable.is_deleted == False).scalar()
    overdue_unpaid_amount = db.session.query(
        func.coalesce(func.sum(Receivable.total_amount - Receivable.paid_amount), 0)
    ).filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).scalar()
    paid_amount = db.session.query(
        func.coalesce(func.sum(PaymentRecord.amount), 0)
    ).filter(PaymentRecord.is_deleted == False).scalar()
    replenishment_commitment = db.session.query(
        func.coalesce(func.sum(ReplenishmentSuggestion.suggested_qty * Product.cost), 0)
    ).join(Product, Product.id == ReplenishmentSuggestion.product_id).filter(
        ReplenishmentSuggestion.is_deleted == False,
        ReplenishmentSuggestion.status == ReplenishmentSuggestion.STATUS_PENDING,
        Product.is_deleted == False,
    ).scalar()
    return {
        'inventory_value': float(inventory_value or 0),
        'sales_amount': float(sales_amount or 0),
        'procurement_amount': float(procurement_amount or 0),
        'pending_procurement_amount': float(pending_procurement_amount or 0),
        'unpaid_amount': float(unpaid_amount or 0),
        'overdue_unpaid_amount': float(overdue_unpaid_amount or 0),
        'paid_amount': float(paid_amount or 0),
        'replenishment_commitment': float(replenishment_commitment or 0),
    }


def _cost_centers(m):
    return [
        _center(
            center_id='cash-collection',
            label='应收现金缺口',
            owner='应收风控',
            budget=max(m['sales_amount'] * 0.16, 1),
            actual=m['unpaid_amount'],
            commitment=m['overdue_unpaid_amount'],
            path='/app/finance/receivables',
            action='推进逾期回款、催收提醒和信用复核，释放经营现金流。',
            evidence=f"未收款 {m['unpaid_amount']:.2f}，其中逾期或坏账 {m['overdue_unpaid_amount']:.2f}。",
            priority_owner='财务负责人',
        ),
        _center(
            center_id='procurement-commitment',
            label='采购承诺暴露',
            owner='采购执行',
            budget=max(m['sales_amount'] * 0.38, m['procurement_amount'] * 0.88, 1),
            actual=m['procurement_amount'],
            commitment=m['pending_procurement_amount'],
            path='/app/procurement/orders',
            action='复核待审批、已审批和部分到货采购单，压降未释放承诺。',
            evidence=f"采购投入 {m['procurement_amount']:.2f}，未完成采购承诺 {m['pending_procurement_amount']:.2f}。",
            priority_owner='采购负责人',
        ),
        _center(
            center_id='inventory-capital',
            label='库存资金占用',
            owner='仓配主管',
            budget=max(m['sales_amount'] * 0.22, m['inventory_value'] * 0.9, 1),
            actual=m['inventory_value'],
            commitment=m['replenishment_commitment'],
            path='/app/inventory/stock',
            action='复核慢动销和安全库存阈值，冻结非必要补货建议。',
            evidence=f"库存资金占用 {m['inventory_value']:.2f}，待执行补货承诺 {m['replenishment_commitment']:.2f}。",
            priority_owner='仓配负责人',
        ),
        _center(
            center_id='gross-margin-guardrail',
            label='经营毛利护栏',
            owner='经营财务',
            budget=max(m['sales_amount'] * 0.72, 1),
            actual=m['procurement_amount'] + m['inventory_value'],
            commitment=m['pending_procurement_amount'],
            path='/app/reports',
            action='生成经营复盘报表，解释采购、库存和销售收入的毛利偏差。',
            evidence=f"销售收入 {m['sales_amount']:.2f}，采购加库存成本暴露 {(m['procurement_amount'] + m['inventory_value']):.2f}。",
            priority_owner='经营负责人',
        ),
    ]


def _center(center_id, label, owner, budget, actual, commitment, path, action, evidence, priority_owner):
    budget = float(budget or 0)
    actual = float(actual or 0)
    commitment = float(commitment or 0)
    variance = actual + commitment - budget
    variance_rate = _percent(variance, budget)
    used_rate = _percent(actual + commitment, budget)
    priority = 'P0' if used_rate >= 125 or variance > max(budget * 0.25, 100000) else 'P1' if used_rate >= 96 or variance > 0 else 'P2'
    status = 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'
    return {
        'id': center_id,
        'label': label,
        'owner': owner,
        'priority_owner': priority_owner,
        'budget': round(budget, 2),
        'actual': round(actual, 2),
        'commitment': round(commitment, 2),
        'available': round(budget - actual - commitment, 2),
        'variance': round(variance, 2),
        'variance_rate': variance_rate,
        'used_rate': used_rate,
        'status': status,
        'priority': priority,
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
        'path': path,
        'evidence': evidence,
        'action': action,
        'runbook': [
            '核对预算、实际和采购承诺三栏金额',
            '进入来源模块处理单据、库存或回款',
            '创建复核任务并在经营复盘报表中归档',
        ],
    }


def _variance_queue(centers):
    items = [_queue_item(center) for center in centers if center['priority'] in {'P0', 'P1'}]
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    items.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -float(item['variance'] or 0)))
    return items


def _queue_item(center):
    return {
        'id': f"{center['id']}-variance",
        'cost_center_id': center['id'],
        'title': f"{center['label']}预算差异复核",
        'owner': center['owner'],
        'priority': center['priority'],
        'sla': center['sla'],
        'status': center['status'],
        'budget': center['budget'],
        'actual': center['actual'],
        'commitment': center['commitment'],
        'available': center['available'],
        'variance': center['variance'],
        'variance_rate': center['variance_rate'],
        'path': center['path'],
        'evidence': center['evidence'],
        'action': center['action'],
        'runbook': center['runbook'],
        'created_at': utcnow().isoformat(),
    }


def _inventory_categories():
    categories = (
        db.session.query(Category.name, func.coalesce(func.sum(Stock.quantity * Product.cost), 0))
        .join(Product, Product.category_id == Category.id)
        .join(Stock, Stock.product_id == Product.id)
        .filter(Category.is_deleted == False, Product.is_deleted == False, Stock.is_deleted == False)
        .group_by(Category.name)
        .order_by(func.coalesce(func.sum(Stock.quantity * Product.cost), 0).desc())
        .limit(8)
        .all()
    )
    return [{'name': name or '未分类', 'value': float(value or 0)} for name, value in categories]


def _score(centers, queue):
    max_used = max([center['used_rate'] for center in centers] or [0])
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')
    return max(42, min(100, round(100 - p0 * 16 - p1 * 7 - max(0, max_used - 100) * 0.35)))


def _center_status(centers, center_id):
    match = next((item for item in centers if item['id'] == center_id), None)
    return match['status'] if match else 'attention'


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    return 'attention' if queue else 'ready'


def _percent(value, total):
    total = float(total or 0)
    if total <= 0:
        return 0
    return round((float(value or 0) / total) * 100, 1)
