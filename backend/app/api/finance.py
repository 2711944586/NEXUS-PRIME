from sqlalchemy import func

from app.extensions import db
from app.models.finance import Receivable
from app.services.finance_service import FinanceService

from . import api_bp
from .auth import jwt_required
from .responses import api_success


@api_bp.get('/finance/receivables/aging')
@jwt_required
def receivables_aging():
    FinanceService.update_overdue_status()
    db.session.commit()
    aging = FinanceService.get_aging_analysis()
    total_amount = (
        db.session.query(func.coalesce(func.sum(Receivable.total_amount), 0))
        .filter(Receivable.is_deleted == False)
        .scalar()
    )
    unpaid_amount = sum(bucket['amount'] for bucket in aging.values())
    overdue_amount = sum(aging[key]['amount'] for key in ['0-30', '31-60', '61-90', '90+'])
    labels = {
        'current': '未逾期',
        '0-30': '0-30天',
        '31-60': '31-60天',
        '61-90': '61-90天',
        '90+': '90天以上',
    }
    return api_success({
        'total_amount': float(total_amount or 0),
        'unpaid_amount': float(unpaid_amount or 0),
        'overdue_amount': float(overdue_amount or 0),
        'buckets': [
            {'name': labels[key], 'value': float(value['amount'] or 0), 'count': value['count']}
            for key, value in aging.items()
        ],
    }, '应收账龄')
