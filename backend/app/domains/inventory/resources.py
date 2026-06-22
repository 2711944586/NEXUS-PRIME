from app.models.notification import ReplenishmentSuggestion, StockAlert
from app.models.stock import InventoryLog, Stock, StockBalance, StockMovement, Warehouse


INVENTORY_READ_PERMISSIONS = [
    "inventory.adjust",
    "stocktake.write",
    "purchase.write",
    "purchase.approve",
    "purchase.receive",
    "sales.write",
    "reports.generate",
]


inventory_resources = {
    "warehouses": {
        "model": Warehouse,
        "search": ["name", "location"],
        "filterable": [],
        "create": ["name", "location", "capacity"],
        "update": ["name", "location", "capacity"],
        "permission": "inventory.adjust",
        "read_permissions": INVENTORY_READ_PERMISSIONS,
    },
    "stock": {
        "model": Stock,
        "serializer_extra": "stock",
        "search": [],
        "filterable": ["product_id", "warehouse_id"],
        "create": [],
        "update": ["shelf_location"],
        "blocked_write_fields": ["quantity", "product_id", "warehouse_id"],
        "permission": "inventory.adjust",
        "read_permissions": INVENTORY_READ_PERMISSIONS,
    },
    "inventory-logs": {
        "model": InventoryLog,
        "search": ["transaction_code", "move_type", "remark"],
        "filterable": ["product_id", "warehouse_id", "move_type"],
        "create": [],
        "update": [],
    },
    "stock-balances": {
        "model": StockBalance,
        "search": ["tenant_id"],
        "filterable": ["tenant_id", "product_id", "warehouse_id"],
        "create": [],
        "update": [],
        "read_permissions": ["inventory.adjust", "stocktake.write", "reports.generate"],
    },
    "stock-movements": {
        "model": StockMovement,
        "search": ["source_type", "source_id", "idempotency_key", "reason"],
        "filterable": ["tenant_id", "product_id", "warehouse_id", "direction", "source_type"],
        "create": [],
        "update": [],
    },
    "stock-alerts": {
        "model": StockAlert,
        "search": ["alert_level", "status"],
        "filterable": ["status", "product_id"],
        "create": [],
        "update": ["resolution_note"],
        "blocked_write_fields": ["current_qty", "min_qty", "suggested_qty", "status"],
        "permission": "inventory.adjust",
        "read_permissions": ["inventory.adjust", "stocktake.write", "reports.generate"],
    },
    "replenishment-suggestions": {
        "model": ReplenishmentSuggestion,
        "serializer_extra": "replenishment",
        "search": ["status"],
        "filterable": ["status", "product_id"],
        "create": [],
        "update": [],
        "blocked_write_fields": ["status", "processed_at", "processed_by", "purchase_order_id"],
        "permission": "purchase.write",
        "read_permissions": ["purchase.write", "inventory.adjust", "reports.generate"],
    },
}
