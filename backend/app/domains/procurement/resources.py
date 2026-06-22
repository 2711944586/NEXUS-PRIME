from app.models.purchase import PurchaseOrder, PurchaseOrderItem, SupplierPerformance


procurement_resources = {
    "purchase-orders": {
        "model": PurchaseOrder,
        "serializer_extra": "purchase",
        "search": ["po_no", "status", "remark"],
        "filterable": ["status", "supplier_id", "warehouse_id"],
        "create": [],
        "update": ["expected_date", "remark"],
        "blocked_write_fields": ["status", "total_amount", "supplier_id", "warehouse_id"],
        "permission": "purchase.write",
        "read_permissions": ["purchase.write", "purchase.approve", "purchase.receive", "reports.generate"],
    },
    "purchase-order-items": {
        "model": PurchaseOrderItem,
        "serializer_extra": "purchase_item",
        "search": [],
        "filterable": ["order_id", "product_id"],
        "create": [],
        "update": [],
        "blocked_write_fields": ["received_qty", "quantity", "unit_price", "product_id", "order_id"],
        "permission": "purchase.write",
        "read_permissions": ["purchase.write", "purchase.approve", "purchase.receive", "reports.generate"],
    },
    "supplier-performance": {
        "model": SupplierPerformance,
        "serializer_extra": "supplier_performance",
        "search": [],
        "filterable": ["supplier_id"],
        "create": [],
        "update": [],
        "read_permissions": ["purchase.write", "purchase.approve", "purchase.receive", "reports.generate"],
    },
}
