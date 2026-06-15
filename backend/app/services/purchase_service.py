"""采购管理服务"""
import uuid
from datetime import datetime, timedelta
from app.extensions import db
from app.models.notification import Notification, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchasePriceHistory, SupplierPerformance
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product, Partner
from app.utils.time import utcnow


def query_with_lock(query):
    dialect_name = db.session.get_bind().dialect.name
    if not dialect_name.startswith('sqlite'):
        return query.with_for_update()
    return query


class PurchaseService:
    """采购服务"""
    
    @staticmethod
    def generate_po_no():
        """生成采购单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"PO-{date_str}-{random_str}"
    
    @staticmethod
    def create_purchase_order(supplier_id, warehouse_id, items_data, user, expected_date=None, remark=None):
        """
        创建采购订单
        :param items_data: [{'product_id': 1, 'quantity': 10, 'unit_price': 50.0}, ...]
        """
        try:
            supplier = db.session.get(Partner, supplier_id)
            warehouse = db.session.get(Warehouse, warehouse_id)
            if not supplier or supplier.type != Partner.TYPE_SUPPLIER:
                return False, "供应商不存在"
            if not warehouse:
                return False, "仓库不存在"
            if not items_data:
                return False, "采购单至少需要一条商品明细"
            po = PurchaseOrder(
                po_no=PurchaseService.generate_po_no(),
                supplier_id=supplier_id,
                warehouse_id=warehouse_id,
                expected_date=expected_date,
                remark=remark,
                status=PurchaseOrder.STATUS_DRAFT
            )
            db.session.add(po)
            db.session.flush()
            
            total = 0.0
            for item_data in items_data:
                quantity = int(item_data.get('quantity') or 0)
                unit_price = float(item_data.get('unit_price') or 0)
                product_id = int(item_data.get('product_id') or 0)
                product = db.session.get(Product, product_id)
                if not product or product.is_deleted:
                    return False, f"商品不存在: {product_id}"
                if quantity <= 0 or unit_price < 0:
                    return False, "采购数量必须大于0，单价不能为负"
                item = PurchaseOrderItem(
                    order_id=po.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price
                )
                db.session.add(item)
                total += item.quantity * item.unit_price
                
                # 记录采购价格历史
                PurchaseService.record_price_history(
                    product_id,
                    supplier_id,
                    unit_price
                )
            
            po.total_amount = total
            return True, po
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def submit_for_approval(po_id, user):
        """提交审批"""
        po = db.session.get(PurchaseOrder, po_id)
        if not po:
            return False, "采购单不存在"
        if po.status != PurchaseOrder.STATUS_DRAFT:
            return False, "只有草稿状态可以提交审批"
        
        po.status = PurchaseOrder.STATUS_PENDING
        po.submitted_at = utcnow()
        po.submitted_by = user.id
        return True, "提交成功"
    
    @staticmethod
    def approve(po_id, user, approved=True, remark=None):
        """审批"""
        po = db.session.get(PurchaseOrder, po_id)
        if not po:
            return False, "采购单不存在"
        if po.status != PurchaseOrder.STATUS_PENDING:
            return False, "只有待审批状态可以审批"
        
        if approved:
            po.status = PurchaseOrder.STATUS_APPROVED
        else:
            po.status = PurchaseOrder.STATUS_DRAFT
            po.remark = (po.remark or '') + f"\n[审批驳回] {remark}"
        
        po.approved_at = utcnow()
        po.approved_by = user.id
        return True, "审批完成"
    
    @staticmethod
    def receive_items(po_id, receive_data, user):
        """
        收货
        :param receive_data: [{'item_id': 1, 'receive_qty': 5}, ...]
        """
        po = db.session.get(PurchaseOrder, po_id)
        if not po:
            return False, "采购单不存在"
        if po.status not in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL]:
            return False, "当前状态不允许收货"
        if not receive_data:
            return False, "请提供收货明细"
        
        try:
            all_received = True
            for data in receive_data:
                receive_qty_raw = data.get('receive_qty')
                if receive_qty_raw is None:
                    return False, "收货数量不能为空"
                item = query_with_lock(PurchaseOrderItem.query.filter_by(id=data['item_id'])).first()
                if not item or item.order_id != po_id:
                    return False, "收货明细不存在或不属于该采购单"
                
                receive_qty = int(receive_qty_raw)
                if receive_qty <= 0:
                    return False, "收货数量必须大于0"
                if receive_qty > item.pending_qty:
                    return False, f"收货数量超过待收数量，当前待收 {item.pending_qty}"
                
                item.received_qty += receive_qty
                
                # 更新库存
                stock = query_with_lock(Stock.query.filter_by(
                    product_id=item.product_id,
                    warehouse_id=po.warehouse_id
                )).first()
                
                if not stock:
                    stock = Stock(
                        product_id=item.product_id,
                        warehouse_id=po.warehouse_id,
                        quantity=0
                    )
                    db.session.add(stock)
                
                stock.quantity += receive_qty
                
                # 记录库存流水
                log = InventoryLog(
                    transaction_code=po.po_no,
                    move_type=InventoryLog.TYPE_IN,
                    product_id=item.product_id,
                    warehouse_id=po.warehouse_id,
                    qty_change=receive_qty,
                    balance_after=stock.quantity,
                    operator_id=user.id,
                    remark=f"采购入库 - {po.po_no}"
                )
                db.session.add(log)
                
                if item.pending_qty > 0:
                    all_received = False
            
            # 更新订单状态
            all_received = all(item.pending_qty <= 0 for item in po.items)
            if all_received:
                po.status = PurchaseOrder.STATUS_RECEIVED
                po.actual_receive_date = utcnow()
                # 更新供应商绩效
                PurchaseService.update_supplier_performance(po)
            else:
                po.status = PurchaseOrder.STATUS_PARTIAL
            
            return True, "收货成功"
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def record_price_history(product_id, supplier_id, price):
        """记录采购价格历史"""
        history = PurchasePriceHistory(
            product_id=product_id,
            supplier_id=supplier_id,
            price=price
        )
        db.session.add(history)
    
    @staticmethod
    def update_supplier_performance(po):
        """更新供应商绩效"""
        perf = SupplierPerformance.query.filter_by(supplier_id=po.supplier_id).first()
        if not perf:
            perf = SupplierPerformance(supplier_id=po.supplier_id)
            db.session.add(perf)
        
        perf.total_orders += 1
        perf.total_amount += po.total_amount
        perf.last_order_date = utcnow()
        
        # 判断是否准时
        if po.expected_date and po.actual_receive_date:
            if po.actual_receive_date.date() <= po.expected_date:
                perf.on_time_orders += 1
        else:
            perf.on_time_orders += 1  # 无预期日期默认准时
        
        # 默认质量合格
        perf.quality_pass_orders += 1
    
    @staticmethod
    def get_supplier_price(product_id, supplier_id):
        """获取最近采购价格"""
        history = PurchasePriceHistory.query.filter_by(
            product_id=product_id,
            supplier_id=supplier_id
        ).order_by(PurchasePriceHistory.effective_date.desc()).first()
        
        if history:
            return history.price
        
        # 如果没有历史，返回产品成本价
        product = db.session.get(Product, product_id)
        return product.cost if product else 0


def procurement_control_payload():
    """采购协同控制台聚合合同。"""
    orders = _purchase_orders(limit=64)
    suggestions = _replenishment_suggestions(limit=18)
    suppliers = _supplier_risk_cards(limit=16)
    metrics = _procurement_metrics(orders, suggestions, suppliers)
    lanes = _procurement_lanes(metrics)
    approval_queue = _approval_queue(orders, suppliers)
    receiving_windows = _receiving_windows(orders)
    supplier_risks = _supplier_risk_queue(suppliers, orders)
    control_queue = _control_queue(approval_queue, receiving_windows, supplier_risks, suggestions)

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'procurement_control_contract',
        'summary': {
            'control_score': _control_score(metrics, control_queue),
            'pending_approvals': metrics['pending_approvals'],
            'receiving_due': metrics['receiving_due'],
            'supplier_risk': metrics['supplier_risk'],
            'quality_hold': metrics['quality_hold'],
            'budget_exposure': metrics['budget_exposure'],
            'replenishment_pending': metrics['replenishment_pending'],
            'open_tasks': metrics['open_tasks'],
            'queue_count': len(control_queue),
            'p0': sum(1 for item in control_queue if item['priority'] == 'P0'),
            'p1': sum(1 for item in control_queue if item['priority'] == 'P1'),
            'primary_owner': control_queue[0]['owner'] if control_queue else '采购负责人',
            'next_action': control_queue[0]['action'] if control_queue else '保持补货、审批、到货、质检和预算每日复核。',
            'next_path': control_queue[0]['path'] if control_queue else '/app/procurement/orders',
        },
        'procurement_lanes': lanes,
        'approval_queue': approval_queue,
        'receiving_windows': receiving_windows,
        'supplier_risk_cards': suppliers,
        'supplier_risk_queue': supplier_risks,
        'replenishment_candidates': suggestions,
        'control_queue': control_queue,
        'purchase_flow': [
            {'step': '需求来源', 'detail': '低库存、补货建议和销售履约压力进入采购需求池。'},
            {'step': '审批承诺', 'detail': '采购负责人按金额、供应商风险、预算暴露和到货窗口推进审批。'},
            {'step': '供应商确认', 'detail': '供应商确认交期、数量和价格偏差，异常进入协同任务。'},
            {'step': '到货与质检', 'detail': '收货入库前核对采购明细、来料检验、库位和批次证据。'},
            {'step': '预算与绩效回写', 'detail': '采购承诺、收货结果和供应商表现回写成本、质量和报表。'},
        ],
        'service_boundaries': [
            {'service': '采购控制台聚合 API', 'contract': 'Purchase + Supplier + Stock + Quality -> ProcurementControlPayload', 'owner': '采购负责人', 'deploy_unit': 'procurement-api', 'readiness': _boundary_status(control_queue)},
            {'service': '补货转采购服务', 'contract': 'ReplenishmentSuggestion -> PurchaseOrderDraft', 'owner': '仓配与采购', 'deploy_unit': 'replenishment-service', 'readiness': _lane_status(lanes, 'demand')},
            {'service': '采购审批服务', 'contract': 'PurchaseOrder.pending -> approved/rejected', 'owner': '采购审批', 'deploy_unit': 'approval-service', 'readiness': _lane_status(lanes, 'approval')},
            {'service': '收货质检交接服务', 'contract': 'PurchaseOrderItem.received_qty -> Stock + IQC', 'owner': '仓库主管', 'deploy_unit': 'receiving-quality-service', 'readiness': _lane_status(lanes, 'receiving')},
            {'service': '供应商绩效服务', 'contract': 'SupplierPerformance -> RiskScore + SupplierSelection', 'owner': '供应商经理', 'deploy_unit': 'supplier-service', 'readiness': _lane_status(lanes, 'supplier')},
        ],
        'deployment_checks': [
            {'key': 'api-contract', 'label': '采购 API 合同', 'status': 'ready', 'owner': '平台后端', 'evidence': 'GET /api/v1/operations/procurement-control 返回聚合控制台合同。'},
            {'key': 'domain-actions', 'label': '领域动作隔离', 'status': 'ready', 'owner': '采购服务', 'evidence': '创建、提交、审批、收货仍走采购领域动作接口，通用资源写入被限制。'},
            {'key': 'quality-handoff', 'label': '质检交接', 'status': 'attention' if metrics['quality_hold'] else 'ready', 'owner': '质量工程师', 'evidence': f"{metrics['quality_hold']} 个采购/库存对象需要质检或证据复核。"},
            {'key': 'budget-exposure', 'label': '预算暴露', 'status': 'attention' if metrics['budget_exposure'] else 'ready', 'owner': '经营财务', 'evidence': f"未完成采购承诺 {metrics['budget_exposure']:.2f} 元。"},
        ],
        'runbook': [
            {'step': '先看 P0/P1 队列', 'detail': '优先处理超 SLA 审批、临近到货、供应商风险和质检阻塞。'},
            {'step': '回到来源单据', 'detail': '每个任务保留采购单、补货建议、供应商或库存路径，避免口头协同。'},
            {'step': '执行领域动作', 'detail': '审批、收货和补货转采购必须通过后端领域动作，确保库存和审计一致。'},
            {'step': '同步服务边界', 'detail': '把 API 合同、部署单元、负责人和 readiness 作为上线前检查项。'},
            {'step': '复盘供应商', 'detail': '收货和质检结果回写准点率、质量率和采购金额集中度。'},
        ],
    }


def select_procurement_control_context(item_id=None, title=None, purchase_id=None, supplier_id=None):
    payload = procurement_control_payload()
    queue = payload['control_queue']
    item = None
    if item_id:
        item = next((entry for entry in queue if entry['id'] == item_id), None)
    if not item and purchase_id:
        item = next((entry for entry in queue if str(entry.get('purchase_id') or '') == str(purchase_id)), None)
    if not item and supplier_id:
        item = next((entry for entry in queue if str(entry.get('supplier_id') or '') == str(supplier_id)), None)
    if not item and title:
        item = next((entry for entry in queue if entry['title'] == title), None)
    if not item and queue:
        item = queue[0]
    return payload, item


def _purchase_orders(limit=64):
    return (
        PurchaseOrder.query
        .filter(PurchaseOrder.is_deleted == False)
        .order_by(PurchaseOrder.status.asc(), PurchaseOrder.expected_date.asc().nullslast(), PurchaseOrder.created_at.desc())
        .limit(limit)
        .all()
    )


def _replenishment_suggestions(limit=18):
    suggestions = (
        ReplenishmentSuggestion.query
        .filter(ReplenishmentSuggestion.is_deleted == False)
        .order_by(ReplenishmentSuggestion.status.asc(), ReplenishmentSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_suggestion_record(item) for item in suggestions]


def _suggestion_record(item):
    amount = float((item.suggested_qty or 0) * ((item.product.cost if item.product else 0) or 0))
    priority = 'P0' if (item.current_qty or 0) <= max(1, int((item.safety_stock or item.product.min_stock if item.product else 0) * 0.35)) else 'P1'
    return {
        'id': f'replenishment-{item.id}',
        'suggestion_id': item.id,
        'product_id': item.product_id,
        'supplier_id': item.supplier_id,
        'sku': item.product.sku if item.product else str(item.product_id),
        'title': item.product.name if item.product else f'补货建议 #{item.id}',
        'supplier': item.supplier.name if item.supplier else '供应商未维护',
        'warehouse': item.warehouse.name if item.warehouse else '待入库仓',
        'status': item.status,
        'current_qty': int(item.current_qty or 0),
        'suggested_qty': int(item.suggested_qty or 0),
        'lead_time_days': int(item.lead_time_days or 0),
        'amount': round(amount, 2),
        'priority': priority if item.status == ReplenishmentSuggestion.STATUS_PENDING else 'P2',
        'path': f'/app/inventory/replenishment/{item.id}',
        'evidence': f"{item.product.name if item.product else '物料'} 当前 {item.current_qty or 0}，建议补货 {item.suggested_qty or 0}。",
        'action': '确认供应商、采购周期和预算后转采购草稿。',
    }


def _supplier_risk_cards(limit=16):
    rows = (
        SupplierPerformance.query
        .join(SupplierPerformance.supplier)
        .filter(SupplierPerformance.is_deleted == False)
        .order_by(SupplierPerformance.on_time_orders.asc(), SupplierPerformance.quality_pass_orders.asc(), SupplierPerformance.total_amount.desc())
        .limit(limit)
        .all()
    )
    cards = [_supplier_card(row) for row in rows]
    if cards:
        return cards
    suppliers = Partner.query.filter_by(type=Partner.TYPE_SUPPLIER, is_deleted=False).limit(limit).all()
    return [_supplier_fallback_card(item) for item in suppliers]


def _supplier_card(item):
    supplier = item.supplier
    pending = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.supplier_id == item.supplier_id,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING, PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL]),
    ).count()
    on_time_rate = float(item.on_time_rate or 0)
    quality_rate = float(item.quality_rate or 0)
    concentration = float(item.total_amount or 0)
    score = _bounded(on_time_rate * 0.42 + quality_rate * 0.42 + max(0, 16 - pending * 3))
    priority = 'P0' if score < 72 or quality_rate < 82 else 'P1' if score < 88 or pending >= 3 else 'P2'
    name = supplier.name if supplier else f'供应商 {item.supplier_id}'
    return {
        'id': f'supplier-{item.supplier_id}',
        'supplier_id': item.supplier_id,
        'name': name,
        'contact': supplier.contact_person if supplier else None,
        'phone': supplier.phone if supplier else None,
        'on_time_rate': round(on_time_rate, 1),
        'quality_rate': round(quality_rate, 1),
        'pending_orders': int(pending or 0),
        'total_orders': int(item.total_orders or 0),
        'total_amount': round(concentration, 2),
        'score': score,
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': '/app/suppliers/performance',
        'evidence': f'{name} 准点率 {on_time_rate:.1f}%，质量率 {quality_rate:.1f}%，未完采购 {pending} 单。',
        'action': '复核交期承诺、来料质量和采购集中度，必要时切换备选供应商。',
    }


def _supplier_fallback_card(item):
    pending = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.supplier_id == item.id,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING, PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL]),
    ).count()
    score = _bounded((item.credit_score or 90) - pending * 4)
    priority = 'P1' if pending >= 3 or score < 82 else 'P2'
    return {
        'id': f'supplier-{item.id}',
        'supplier_id': item.id,
        'name': item.name,
        'contact': item.contact_person,
        'phone': item.phone,
        'on_time_rate': score,
        'quality_rate': score,
        'pending_orders': int(pending or 0),
        'total_orders': pending,
        'total_amount': 0,
        'score': score,
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': '/app/suppliers/performance',
        'evidence': f'{item.name} 暂无完整绩效样本，当前未完采购 {pending} 单。',
        'action': '补齐供应商绩效样本，确认准点率、质量率和联系方式。',
    }


def _procurement_metrics(orders, suggestions, suppliers):
    active_statuses = {
        PurchaseOrder.STATUS_DRAFT,
        PurchaseOrder.STATUS_PENDING,
        PurchaseOrder.STATUS_APPROVED,
        PurchaseOrder.STATUS_ORDERED,
        PurchaseOrder.STATUS_PARTIAL,
    }
    receiving_due = 0
    today = utcnow().date()
    for order in orders:
        if order.status in {PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL}:
            if not order.expected_date or order.expected_date <= today + timedelta(days=3):
                receiving_due += 1
    quality_hold = StockAlert.query.filter(
        StockAlert.is_deleted == False,
        StockAlert.status == StockAlert.STATUS_ACTIVE,
        StockAlert.alert_level == StockAlert.LEVEL_RED,
    ).count()
    open_tasks = Notification.query.filter(
        Notification.is_deleted == False,
        Notification.is_read == False,
        Notification.related_type == 'procurement_control',
    ).count()
    budget_exposure = sum(float(order.total_amount or 0) for order in orders if order.status in active_statuses)
    return {
        'total_orders': len(orders),
        'pending_approvals': sum(1 for order in orders if order.status in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING}),
        'approved_orders': sum(1 for order in orders if order.status == PurchaseOrder.STATUS_APPROVED),
        'partial_orders': sum(1 for order in orders if order.status == PurchaseOrder.STATUS_PARTIAL),
        'received_orders': sum(1 for order in orders if order.status == PurchaseOrder.STATUS_RECEIVED),
        'receiving_due': receiving_due,
        'supplier_risk': sum(1 for supplier in suppliers if supplier['priority'] in {'P0', 'P1'}),
        'quality_hold': int(quality_hold or 0),
        'budget_exposure': round(budget_exposure, 2),
        'replenishment_pending': sum(1 for item in suggestions if item['status'] == ReplenishmentSuggestion.STATUS_PENDING),
        'open_tasks': int(open_tasks or 0),
    }


def _procurement_lanes(m):
    return [
        _lane('demand', '需求与补货', '仓配与采购', m['replenishment_pending'], 1 if m['replenishment_pending'] >= 8 else 0, m['replenishment_pending'], 100 - m['replenishment_pending'] * 5, '/app/inventory/replenishment', f"{m['replenishment_pending']} 条补货建议等待确认。", '确认供应商、建议量和预算后转采购草稿。'),
        _lane('approval', '采购审批', '采购负责人', m['pending_approvals'], 1 if m['pending_approvals'] >= 8 else 0, m['pending_approvals'], 100 - m['pending_approvals'] * 7, '/app/procurement/orders', f"{m['pending_approvals']} 张采购单处于草稿或待审批。", '按金额、供应商风险和到货窗口推进审批。'),
        _lane('receiving', '到货收货', '仓库主管', m['receiving_due'], 1 if m['receiving_due'] >= 6 else 0, m['receiving_due'], 100 - m['receiving_due'] * 8, '/app/procurement/orders', f"{m['receiving_due']} 张采购单需要收货或到货确认。", '安排月台、核对数量并交接质检。'),
        _lane('quality', '质检放行', '质量工程师', m['quality_hold'], m['quality_hold'], max(0, m['quality_hold'] - 1), 100 - m['quality_hold'] * 11, '/app/quality', f"{m['quality_hold']} 个库存/采购对象需要质量复核。", '确认来料检验、隔离和使用决策。'),
        _lane('supplier', '供应商协同', '供应商经理', m['supplier_risk'], 1 if m['supplier_risk'] >= 4 else 0, m['supplier_risk'], 100 - m['supplier_risk'] * 9, '/app/suppliers/performance', f"{m['supplier_risk']} 家供应商进入观察或整改。", '复核交期、质量、联系人和备选供应商。'),
        _lane('finance', '预算承诺', '经营财务', 1 if m['budget_exposure'] else 0, 0, 1 if m['budget_exposure'] > 500000 else 0, 100 - min(38, m['budget_exposure'] / 50000), '/app/budget', f"未完成采购承诺 {m['budget_exposure']:.2f} 元。", '核对采购承诺、预算余量和付款计划。'),
    ]


def _lane(lane_id, label, owner, count, p0, p1, score, path, evidence, action):
    priority = 'P0' if p0 else 'P1' if p1 or score < 88 else 'P2'
    return {
        'id': lane_id,
        'label': label,
        'owner': owner,
        'active_count': int(count or 0),
        'p0': int(p0 or 0),
        'p1': int(p1 or 0),
        'score': _bounded(score),
        'priority': priority,
        'status': _status_from_priority(priority),
        'path': path,
        'evidence': evidence,
        'action': action,
        'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
    }


def _approval_queue(orders, suppliers):
    supplier_map = {item['supplier_id']: item for item in suppliers}
    queue = []
    for order in orders:
        if order.status not in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_PENDING}:
            continue
        supplier = supplier_map.get(order.supplier_id)
        age_hours = max(1, round((utcnow() - (order.submitted_at or order.created_at or utcnow())).total_seconds() / 3600, 1))
        risk = (supplier or {}).get('priority') or 'P2'
        priority = 'P0' if age_hours >= 48 or risk == 'P0' else 'P1' if age_hours >= 12 or risk == 'P1' or (order.total_amount or 0) >= 100000 else 'P2'
        queue.append({
            'id': f'approval-{order.id}',
            'source': 'purchase_order',
            'purchase_id': order.id,
            'supplier_id': order.supplier_id,
            'po_no': order.po_no,
            'title': f'{order.po_no}采购审批',
            'supplier': order.supplier.name if order.supplier else '供应商未维护',
            'warehouse': order.warehouse.name if order.warehouse else '待入库仓',
            'amount': round(float(order.total_amount or 0), 2),
            'status': order.status,
            'owner': '采购负责人',
            'priority': priority,
            'sla': '4h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
            'age_hours': age_hours,
            'risk': risk,
            'path': f'/app/procurement/orders/{order.id}',
            'evidence': f'{order.po_no} 金额 {order.total_amount:.2f}，供应商风险 {risk}，等待 {age_hours} 小时。',
            'action': '复核补货来源、预算暴露、供应商风险和到货窗口后审批或驳回。',
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    queue.sort(key=lambda item: (priority_rank.get(item['priority'], 9), -item['amount'], -item['age_hours']))
    return queue[:12]


def _receiving_windows(orders):
    today = utcnow().date()
    windows = []
    for order in orders:
        if order.status not in {PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL}:
            continue
        expected = order.expected_date
        days_to_due = (expected - today).days if expected else 0
        progress = _bounded(order.receive_progress)
        priority = 'P0' if days_to_due < 0 or (progress < 30 and days_to_due <= 1) else 'P1' if days_to_due <= 3 or progress < 80 else 'P2'
        windows.append({
            'id': f'receiving-{order.id}',
            'source': 'purchase_receiving',
            'purchase_id': order.id,
            'supplier_id': order.supplier_id,
            'po_no': order.po_no,
            'title': f'{order.po_no}到货窗口',
            'supplier': order.supplier.name if order.supplier else '供应商未维护',
            'warehouse': order.warehouse.name if order.warehouse else '待入库仓',
            'expected_date': expected.isoformat() if expected else None,
            'days_to_due': days_to_due,
            'progress': progress,
            'amount': round(float(order.total_amount or 0), 2),
            'owner': '仓库主管',
            'priority': priority,
            'status': _status_from_priority(priority),
            'sla': '2h' if priority == 'P0' else '1d' if priority == 'P1' else '3d',
            'path': f'/app/procurement/orders/{order.id}',
            'evidence': f'{order.po_no} 收货进度 {progress}%，预计到货 {expected.isoformat() if expected else "未维护"}。',
            'action': '确认月台、质检资源、待收数量和入库库位，推进收货或供应商改期确认。',
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    windows.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item['days_to_due'], item['progress']))
    return windows[:12]


def _supplier_risk_queue(suppliers, orders):
    active_supplier_ids = {order.supplier_id for order in orders if order.status in {
        PurchaseOrder.STATUS_DRAFT,
        PurchaseOrder.STATUS_PENDING,
        PurchaseOrder.STATUS_APPROVED,
        PurchaseOrder.STATUS_PARTIAL,
    }}
    queue = []
    for supplier in suppliers:
        if supplier['priority'] not in {'P0', 'P1'} and supplier['supplier_id'] not in active_supplier_ids:
            continue
        queue.append({
            'id': f"{supplier['id']}-risk",
            'source': 'supplier_risk',
            'supplier_id': supplier['supplier_id'],
            'purchase_id': None,
            'title': f"{supplier['name']}供应商协同复核",
            'owner': '供应商经理',
            'priority': supplier['priority'],
            'status': supplier['status'],
            'sla': '4h' if supplier['priority'] == 'P0' else '1d',
            'path': supplier['path'],
            'metric': f"{supplier['score']}分 / {supplier['pending_orders']}单",
            'evidence': supplier['evidence'],
            'action': supplier['action'],
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    queue.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item['title']))
    return queue[:10]


def _control_queue(approval, receiving, supplier_risks, suggestions):
    items = []
    for item in approval:
        items.append({**item, 'metric': f"{item['amount']:.0f}元", 'kind': '审批'})
    for item in receiving:
        items.append({**item, 'metric': f"{item['progress']}%", 'kind': '收货'})
    for item in supplier_risks:
        items.append({**item, 'kind': '供应商'})
    for item in suggestions:
        if item['priority'] in {'P0', 'P1'}:
            items.append({
                'id': f"{item['id']}-task",
                'source': 'replenishment',
                'suggestion_id': item['suggestion_id'],
                'product_id': item['product_id'],
                'supplier_id': item['supplier_id'],
                'purchase_id': None,
                'title': f"{item['title']}补货转采购",
                'owner': '仓配与采购',
                'priority': item['priority'],
                'status': _status_from_priority(item['priority']),
                'sla': '4h' if item['priority'] == 'P0' else '1d',
                'path': item['path'],
                'metric': f"{item['suggested_qty']}件",
                'kind': '补货',
                'evidence': item['evidence'],
                'action': item['action'],
            })
    if not items:
        items.append({
            'id': 'procurement-daily-control',
            'source': 'daily_control',
            'purchase_id': None,
            'supplier_id': None,
            'title': '采购日常协同复核',
            'owner': '采购负责人',
            'priority': 'P2',
            'status': 'ready',
            'sla': '3d',
            'path': '/app/procurement/orders',
            'metric': '例行',
            'kind': '日常',
            'evidence': '当前采购链路没有高优先级风险。',
            'action': '复核补货建议、供应商评分和预算承诺。',
        })
    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    deduped = {}
    for item in items:
        deduped.setdefault(item['id'], item)
    result = list(deduped.values())
    result.sort(key=lambda item: (priority_rank.get(item['priority'], 9), item.get('kind', ''), item['id']))
    return result[:18]


def _control_score(metrics, queue):
    p0 = sum(1 for item in queue if item['priority'] == 'P0')
    p1 = sum(1 for item in queue if item['priority'] == 'P1')
    exposure_penalty = min(16, metrics['budget_exposure'] / 80000)
    return _bounded(100 - p0 * 14 - p1 * 6 - metrics['supplier_risk'] * 2 - metrics['quality_hold'] * 4 - exposure_penalty)


def _lane_status(lanes, lane_id):
    lane = next((item for item in lanes if item['id'] == lane_id), None)
    return lane['status'] if lane else 'attention'


def _boundary_status(queue):
    if any(item['priority'] == 'P0' for item in queue):
        return 'blocked'
    if any(item['priority'] == 'P1' for item in queue):
        return 'attention'
    return 'ready'


def _status_from_priority(priority):
    return 'blocked' if priority == 'P0' else 'attention' if priority == 'P1' else 'ready'


def _bounded(value):
    return round(max(0, min(100, float(value or 0))), 1)
