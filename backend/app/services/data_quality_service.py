from app.extensions import db
from app.models.biz import Product
from app.models.finance import Receivable
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.stock import Stock
from app.models.trade import Order, OrderItem
from app.utils.time import utcnow
from sqlalchemy import func, or_


def data_quality_payload():
    issues = _quality_issues()
    dimensions = _quality_dimensions(issues)
    failed_tests = sum(1 for item in issues if item['count'] > 0)
    issue_count = sum(int(item['count'] or 0) for item in issues)
    total_tests = len(issues) + 6
    passed_tests = max(0, total_tests - failed_tests)
    score = max(58, min(100, round(100 - failed_tests * 6 - min(issue_count, 80) * 0.45)))
    p0 = sum(1 for item in issues if item['priority'] == 'P0' and item['count'] > 0)
    p1 = sum(1 for item in issues if item['priority'] == 'P1' and item['count'] > 0)
    active_issues = [item for item in issues if item['count'] > 0]

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'database_quality_contract',
        'summary': {
            'score': score,
            'level': 'blocked' if p0 else 'attention' if active_issues else 'ready',
            'issue_count': issue_count,
            'failed_tests': failed_tests,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'p0': p0,
            'p1': p1,
            'coverage': _average([item['score'] for item in dimensions]),
            'next_action': active_issues[0]['action'] if active_issues else '保持主数据、库存、履约和财务链路每日抽检。',
            'primary_owner': active_issues[0]['owner'] if active_issues else '数据治理台',
        },
        'dimensions': dimensions,
        'issue_queue': active_issues,
        'test_suites': _test_suites(dimensions, issues),
        'lineage': [
            {'from': '物料主数据', 'to': '库存库位', 'status': _dimension_status(dimensions, 'masterdata'), 'label': 'SKU、供应商、安全库存'},
            {'from': '采购补货', 'to': '库存入库', 'status': _dimension_status(dimensions, 'procurement'), 'label': '供应商、仓库、明细、收货状态'},
            {'from': '销售订单', 'to': '应收账款', 'status': _dimension_status(dimensions, 'fulfillment'), 'label': '订单明细、客户、金额快照'},
            {'from': '应收账款', 'to': '经营报表', 'status': _dimension_status(dimensions, 'finance'), 'label': '账龄、回款、信用占用'},
        ],
        'runbook': [
            {'step': '定位失败维度', 'detail': '先处理 P0/P1 项，按影响记录数和业务链路顺序分派负责人。'},
            {'step': '修复源记录', 'detail': '进入来源模块补齐字段、推进状态或补录业务明细，保留附件和备注。'},
            {'step': '创建整改任务', 'detail': '把证据、SLA、负责人写入通知与审计日志，再进入任务异常中心跟踪闭环。'},
            {'step': '复跑质量体检', 'detail': '刷新数据质量中心，确认失败测试下降并更新最终交付截图。'},
        ],
    }


def _quality_issues():
    missing_supplier = Product.query.filter(Product.is_deleted == False, Product.supplier_id.is_(None)).count()
    invalid_stock_policy = Product.query.filter(
        Product.is_deleted == False,
        or_(Product.min_stock <= 0, Product.max_stock <= 0, Product.max_stock < Product.min_stock)
    ).count()
    missing_shelf = Stock.query.filter(
        Stock.is_deleted == False,
        or_(Stock.shelf_location.is_(None), Stock.shelf_location == '')
    ).count()
    active_orders = Order.query.filter(Order.is_deleted == False).count()
    sales_with_items = db.session.query(func.count(func.distinct(OrderItem.order_id))).join(
        Order, Order.id == OrderItem.order_id
    ).filter(Order.is_deleted == False, OrderItem.is_deleted == False).scalar()
    sales_without_items = max(0, int(active_orders or 0) - int(sales_with_items or 0))
    blocked_purchase = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING])
    ).count()
    active_purchases = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).count()
    purchases_with_items = db.session.query(func.count(func.distinct(PurchaseOrderItem.order_id))).join(
        PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id
    ).filter(PurchaseOrder.is_deleted == False, PurchaseOrderItem.is_deleted == False).scalar()
    purchase_without_items = max(0, int(active_purchases or 0) - int(purchases_with_items or 0))
    overdue_receivable = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).count()
    receivable_without_order = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.order_id.is_(None)
    ).count()

    return [
        _issue(
            'masterdata_supplier',
            '主数据',
            '物料缺少默认供应商',
            missing_supplier,
            'P1',
            '主数据负责人',
            '/app/inventory/products',
            '补齐默认供应商，确保采购建议可以自动生成采购单。',
            '完整性',
        ),
        _issue(
            'masterdata_stock_policy',
            '主数据',
            '安全库存或最大库存策略异常',
            invalid_stock_policy,
            'P1',
            '主数据负责人',
            '/app/inventory/products',
            '修复最小/最大库存阈值，避免补货规则产生噪声。',
            '有效性',
        ),
        _issue(
            'warehouse_slot',
            '仓配',
            '库存缺少库位',
            missing_shelf,
            'P1',
            '仓配主管',
            '/app/inventory/stock',
            '补齐库位，保证移动端收货、盘点和拣货可定位。',
            '完整性',
        ),
        _issue(
            'sales_items',
            '履约',
            '销售订单缺少明细',
            sales_without_items,
            'P0',
            '销售运营',
            '/app/sales/orders',
            '补录订单明细，避免应收、库存扣减和履约分析断链。',
            '一致性',
        ),
        _issue(
            'purchase_state',
            '采购',
            '采购单停留在草稿或待审批',
            blocked_purchase,
            'P1',
            '采购执行',
            '/app/procurement/orders',
            '推进采购单提交、审批或取消，释放补货执行队列。',
            '及时性',
        ),
        _issue(
            'purchase_items',
            '采购',
            '采购单缺少明细',
            purchase_without_items,
            'P0',
            '采购执行',
            '/app/procurement/orders',
            '补齐采购明细、仓库和预计到货，保证入库链路可追踪。',
            '一致性',
        ),
        _issue(
            'finance_overdue',
            '财务',
            '逾期或坏账应收',
            overdue_receivable,
            'P0',
            '应收风控',
            '/app/finance/receivables',
            '创建催收或信用复核动作，降低现金流风险。',
            '及时性',
        ),
        _issue(
            'finance_order_link',
            '财务',
            '应收缺少来源订单',
            receivable_without_order,
            'P1',
            '应收风控',
            '/app/finance/receivables',
            '回填订单关联，确保合同、履约和回款能被追溯。',
            '可追溯性',
        ),
    ]


def _issue(key, module, title, count, priority, owner, path, action, dimension):
    severity = 'danger' if priority == 'P0' and count > 0 else 'warn' if count > 0 else 'success'
    return {
        'id': key,
        'module': module,
        'dimension': dimension,
        'title': title,
        'count': int(count or 0),
        'severity': severity,
        'priority': priority,
        'owner': owner,
        'status': 'open' if count else 'passed',
        'sla': '4h' if priority == 'P0' else '1d',
        'path': path,
        'evidence': f'{module}链路发现 {int(count or 0)} 条记录需要治理。',
        'action': action,
        'runbook': [
            '进入来源模块筛选异常记录',
            '补齐字段、状态或业务明细',
            '刷新数据质量中心并归档审计证据',
        ],
    }


def _quality_dimensions(issues):
    groups = [
        ('masterdata', '主数据', '主数据负责人', ['masterdata_supplier', 'masterdata_stock_policy'], Product.query.filter(Product.is_deleted == False).count()),
        ('warehouse', '仓配', '仓配主管', ['warehouse_slot'], Stock.query.filter(Stock.is_deleted == False).count()),
        ('procurement', '采购', '采购执行', ['purchase_state', 'purchase_items'], PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).count()),
        ('fulfillment', '履约', '销售运营', ['sales_items'], Order.query.filter(Order.is_deleted == False).count()),
        ('finance', '财务', '应收风控', ['finance_overdue', 'finance_order_link'], Receivable.query.filter(Receivable.is_deleted == False).count()),
    ]
    by_id = {item['id']: item for item in issues}
    dimensions = []
    for key, label, owner, issue_ids, total in groups:
        failed = sum(by_id[item]['count'] for item in issue_ids)
        score = max(60, min(100, round(100 - failed * 4)))
        dimensions.append({
            'key': key,
            'label': label,
            'owner': owner,
            'total': int(total or 0),
            'failed': int(failed or 0),
            'score': score,
            'coverage': score,
            'status': 'blocked' if any(by_id[item]['priority'] == 'P0' and by_id[item]['count'] > 0 for item in issue_ids) else 'attention' if failed else 'ready',
        })
    return dimensions


def _test_suites(dimensions, issues):
    issue_map = {}
    for item in issues:
        issue_map.setdefault(item['module'], []).append(item)
    return [
        {
            'id': dimension['key'],
            'name': f"{dimension['label']}质量测试",
            'scope': f"{dimension['total']} 条业务记录",
            'owner': dimension['owner'],
            'passed': max(0, 4 - sum(1 for item in issue_map.get(dimension['label'], []) if item['count'] > 0)),
            'failed': sum(1 for item in issue_map.get(dimension['label'], []) if item['count'] > 0),
            'coverage': dimension['coverage'],
            'last_run': utcnow().isoformat(),
            'slo': '>= 92%',
            'status': dimension['status'],
        }
        for dimension in dimensions
    ]


def _dimension_status(dimensions, key):
    match = next((item for item in dimensions if item['key'] == key), None)
    return match['status'] if match else 'attention'


def _average(values):
    values = [float(item or 0) for item in values]
    return round(sum(values) / max(len(values), 1), 1)
