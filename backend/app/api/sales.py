from app.extensions import db
from app.models.trade import Order
from app.services.audit_service import AuditService

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import order_extra, require_permission, serialize_model


ALLOWED_TRANSITIONS = {
    Order.STATUS_PENDING: {Order.STATUS_PAID, Order.STATUS_CANCEL},
    Order.STATUS_PAID: {Order.STATUS_SHIPPED, Order.STATUS_DONE, Order.STATUS_CANCEL},
    Order.STATUS_SHIPPED: {Order.STATUS_DONE, Order.STATUS_CANCEL},
    Order.STATUS_DONE: set(),
    Order.STATUS_CANCEL: set(),
}


@api_bp.post('/sales/orders/<int:order_id>/transition')
@jwt_required
def sales_order_transition(order_id):
    from flask import request

    payload = request.get_json(silent=True) or {}
    status = payload.get('status')
    denied = require_permission('sales.write', '需要销售订单权限')
    if denied:
        return denied
    order = db.session.get(Order, order_id)
    if not order or order.is_deleted:
        return api_error('订单不存在', status=404, error='not_found')
    if status not in {Order.STATUS_PENDING, Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE, Order.STATUS_CANCEL}:
        return api_error('不支持的订单状态', status=400, error='invalid_status')
    if status != order.status and status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        return api_error('当前状态不允许该流转', status=400, error='invalid_transition')
    old_status = order.status
    try:
        from app.services.sales_service import SalesService
        SalesService.transition_order(order, status, current_api_user())
        AuditService.record('sales', 'transition', current_api_user(), {'id': order_id, 'from': old_status, 'to': status})
        db.session.commit()
        return api_success(serialize_model(order, order_extra), '订单状态已更新')
    except Exception as exc:
        db.session.rollback()
        return api_error(str(exc) if isinstance(exc, ValueError) else '订单流转失败', status=400, error='order_transition_failed')
