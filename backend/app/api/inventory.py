from app.domains.inventory.application.queries import InventoryHealthQuery

from . import api_bp
from .auth import jwt_required
from .responses import api_success


@api_bp.get('/inventory/health')
@jwt_required
def inventory_health():
    return api_success(InventoryHealthQuery().execute().to_dict(), '库存健康度')
