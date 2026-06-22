from app.extensions import db
from app.models.biz import Partner
from app.models.notification import ReplenishmentSuggestion
from app.models.stock import Warehouse
from app.models.stocktake import StockTake, StockTakeItem
from app.platform.policy import policy
from app.services.audit_service import AuditService
from app.services.finance_service import FinanceService
from app.services.inventory_service import InventoryService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.stock_alert_service import StockAlertService
from app.services.stocktake_service import StockTakeService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .resource_support import (
    current_payload,
    order_extra,
    parse_bool,
    parse_date,
    purchase_extra,
    require_permission,
    serialize_model,
    stocktake_extra,
)


def require_policy_decision(decision):
    if not decision.allowed:
        return api_error(decision.reason or '权限不足', status=403, error=decision.error or 'forbidden')
    return None


def require_stocktake_access(stocktake, action):
    return require_policy_decision(policy.can(current_api_user(), action, resource=stocktake))


@api_bp.post('/inventory/adjust')
@jwt_required
def adjust_inventory():
    denied = require_permission('inventory.adjust', '需要库存调整权限')
    if denied:
        return denied
    payload = current_payload()
    ok, message = InventoryService.adjust_stock(
        int(payload.get('product_id')),
        int(payload.get('warehouse_id')),
        int(payload.get('quantity')),
        payload.get('move_type', 'inbound'),
        current_api_user(),
        payload.get('remark', '')
    )
    if not ok:
        return api_error(message, status=400)
    AuditService.record('inventory', 'adjust', current_api_user(), payload)
    db.session.commit()
    return api_success(None, message)


@api_bp.post('/sales/orders')
@jwt_required
def create_sales_order():
    denied = require_permission('sales.write', '需要销售订单权限')
    if denied:
        return denied
    payload = current_payload()
    customer_id = payload.get('customer_id')
    if not customer_id:
        name = (payload.get('customer_name') or '').strip()
        if not name:
            return api_error('请选择或输入客户', status=400)
        partner = Partner.query.filter_by(name=name).first()
        if not partner:
            partner = Partner(name=name, type='customer')
            db.session.add(partner)
            db.session.flush()
        customer_id = partner.id
    try:
        order = SalesService.create_order(int(customer_id), current_api_user(), payload.get('items', []), payload.get('status', 'pending'))
        AuditService.record('sales', 'create_order', current_api_user(), {'id': order.id, 'order_no': order.order_no})
        db.session.commit()
        return api_success(serialize_model(order, order_extra), '订单创建成功', status=201)
    except Exception as exc:
        return api_error(str(exc) if isinstance(exc, ValueError) else '订单创建失败', status=400, error='order_create_failed')


@api_bp.post('/purchase-orders/<int:po_id>/submit')
@jwt_required
def submit_purchase_order(po_id):
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    ok, message = PurchaseService.submit_for_approval(
        po_id,
        current_api_user(),
        assignee_id=current_payload().get('assignee_id'),
    )
    if ok:
        AuditService.record('procurement', 'submit', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/approve')
@jwt_required
def approve_purchase_order(po_id):
    denied = require_permission('purchase.approve', '需要采购审批权限')
    if denied:
        return denied
    ok, message = PurchaseService.approve(po_id, current_api_user(), True, current_payload().get('remark'))
    if ok:
        AuditService.record('procurement', 'approve', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/reject')
@jwt_required
def reject_purchase_order(po_id):
    denied = require_permission('purchase.approve', '需要采购审批权限')
    if denied:
        return denied
    ok, message = PurchaseService.approve(po_id, current_api_user(), False, current_payload().get('remark'))
    if ok:
        AuditService.record('procurement', 'reject', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/receive')
@jwt_required
def receive_purchase_order(po_id):
    denied = require_permission('purchase.receive', '需要采购收货权限')
    if denied:
        return denied
    ok, message = PurchaseService.receive_items(po_id, current_payload().get('items', []), current_api_user())
    if ok:
        AuditService.record('procurement', 'receive', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/receivables/<int:receivable_id>/payment')
@jwt_required
def api_record_payment(receivable_id):
    denied = require_permission('finance.payment', '需要收款权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = FinanceService.record_payment(
        receivable_id,
        float(payload.get('amount', 0)),
        payload.get('payment_method', 'bank'),
        current_api_user(),
        payload.get('reference_no'),
        payload.get('remark')
    )
    if ok:
        AuditService.record('finance', 'record_payment', current_api_user(), {'receivable_id': receivable_id, 'amount': payload.get('amount')})
        db.session.commit()
    return api_success(serialize_model(result), '收款成功') if ok else api_error(result, status=400)


@api_bp.post('/statements/generate')
@jwt_required
def api_generate_statement():
    denied = require_permission('reports.generate', '需要报表生成权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = FinanceService.generate_statement(
        int(payload.get('customer_id')),
        parse_date(payload.get('period_start')),
        parse_date(payload.get('period_end')),
        current_api_user()
    )
    if ok:
        AuditService.record('reports', 'generate_statement', current_api_user(), {'id': result.id, 'customer_id': payload.get('customer_id')})
        db.session.commit()
    return api_success(serialize_model(result), '对账单生成成功', status=201) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/create')
@jwt_required
def api_create_stocktake():
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = StockTakeService.create_stocktake(
        int(payload.get('warehouse_id')),
        payload.get('take_type', StockTake.TYPE_FULL),
        payload.get('product_ids') or [],
        current_api_user(),
        payload.get('remark'),
        payload.get('planned_date')
    )
    if ok:
        AuditService.record('stocktake', 'create', current_api_user(), {'id': result.id})
        db.session.commit()
    return api_success(serialize_model(result, stocktake_extra), '盘点单创建成功', status=201) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/<int:take_id>/start')
@jwt_required
def api_start_stocktake(take_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    stocktake = db.session.get(StockTake, take_id)
    if not stocktake or stocktake.is_deleted:
        return api_error('盘点单不存在', status=404, error='not_found')
    denied = require_stocktake_access(stocktake, 'update')
    if denied:
        return denied
    ok, result = StockTakeService.start_stocktake(take_id, current_api_user())
    if ok:
        AuditService.record('stocktake', 'start', current_api_user(), {'id': take_id})
        db.session.commit()
    return api_success(None, result) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/<int:take_id>/complete')
@jwt_required
def api_complete_stocktake(take_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    stocktake = db.session.get(StockTake, take_id)
    if not stocktake or stocktake.is_deleted:
        return api_error('盘点单不存在', status=404, error='not_found')
    denied = require_stocktake_access(stocktake, 'update')
    if denied:
        return denied
    ok, result = StockTakeService.complete_stocktake(take_id, current_api_user(), parse_bool(current_payload().get('auto_adjust'), True))
    if ok:
        AuditService.record('stocktake', 'complete', current_api_user(), {'id': take_id})
        db.session.commit()
    return api_success(None, result) if ok else api_error(result, status=400)


@api_bp.post('/stocktake-items/<int:item_id>/count')
@jwt_required
def api_count_stocktake_item(item_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    payload = current_payload()
    item = db.session.get(StockTakeItem, item_id)
    if not item:
        return api_error('盘点明细不存在', status=404)
    denied = require_policy_decision(policy.can(current_api_user(), 'update', resource=item))
    if denied:
        return denied
    ok, result = StockTakeService.input_count(item.take_id, item_id, int(payload.get('actual_qty')), current_api_user(), payload.get('remark'))
    if ok:
        db.session.commit()
    return api_success(serialize_model(result), '录入成功') if ok else api_error(result, status=400)


@api_bp.post('/stock-alerts/check')
@jwt_required
def api_check_alerts():
    denied = require_permission('inventory.adjust', '需要库存预警权限')
    if denied:
        return denied
    count = StockAlertService.check_all_stock_alerts()
    AuditService.record('inventory', 'check_alerts', current_api_user(), {'created': count})
    db.session.commit()
    return api_success({'created': count}, '库存预警检查完成')


@api_bp.post('/replenishment-suggestions/generate')
@jwt_required
def api_generate_replenishment():
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    StockAlertService.check_all_stock_alerts()
    count = StockAlertService.generate_replenishment_suggestions()
    AuditService.record('inventory', 'generate_replenishment', current_api_user(), {'created': count})
    db.session.commit()
    return api_success({'created': count}, '补货建议生成完成')


@api_bp.post('/replenishment-suggestions/<int:suggestion_id>/accept')
@jwt_required
def api_accept_replenishment(suggestion_id):
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    suggestion = db.session.get(ReplenishmentSuggestion, suggestion_id)
    if not suggestion:
        return api_error('补货建议不存在', status=404)
    items = [{
        'product_id': suggestion.product_id,
        'quantity': suggestion.suggested_qty or 1,
        'unit_price': suggestion.product.cost or 0,
    }]
    ok, result = PurchaseService.create_purchase_order(
        suggestion.supplier_id,
        suggestion.warehouse_id or Warehouse.query.first().id,
        items,
        current_api_user(),
        remark=f'由补货建议 #{suggestion.id} 自动创建'
    )
    if not ok:
        return api_error(result, status=400)
    suggestion.status = ReplenishmentSuggestion.STATUS_ORDERED
    suggestion.processed_at = utcnow()
    suggestion.processed_by = current_api_user().id
    suggestion.purchase_order_id = result.id
    AuditService.record('inventory', 'accept_replenishment', current_api_user(), {'suggestion_id': suggestion_id, 'purchase_order_id': result.id})
    db.session.commit()
    return api_success({'purchase_order': serialize_model(result, purchase_extra)}, '已接受建议并创建采购单')
