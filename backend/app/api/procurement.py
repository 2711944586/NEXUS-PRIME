from sqlalchemy import func

from app.extensions import db
from app.models.purchase import PurchaseOrder

from . import api_bp
from .auth import jwt_required
from .responses import api_success


@api_bp.get('/procurement/summary')
@jwt_required
def procurement_summary():
    rows = (
        db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.is_deleted == False)
        .group_by(PurchaseOrder.status)
        .all()
    )
    counts = {status: count for status, count in rows}
    total_amount = (
        db.session.query(func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
        .filter(PurchaseOrder.is_deleted == False)
        .scalar()
    )
    return api_success({
        'draft': counts.get(PurchaseOrder.STATUS_DRAFT, 0),
        'pending': counts.get(PurchaseOrder.STATUS_PENDING, 0),
        'approved': counts.get(PurchaseOrder.STATUS_APPROVED, 0),
        'partial': counts.get(PurchaseOrder.STATUS_PARTIAL, 0),
        'received': counts.get(PurchaseOrder.STATUS_RECEIVED, 0),
        'total_amount': float(total_amount or 0),
    }, '采购汇总')
