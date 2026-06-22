from app.models.trade import Order, OrderItem


sales_resources = {
    "orders": {
        "model": Order,
        "serializer_extra": "order",
        "search": ["order_no", "status"],
        "filterable": ["status", "customer_id"],
        "create": [],
        "update": [],
        "blocked_write_fields": ["total_amount", "status", "seller_id"],
        "permission": "sales.write",
        "read_permissions": ["sales.write", "reports.generate"],
    },
    "order-items": {
        "model": OrderItem,
        "serializer_extra": "order_item",
        "search": [],
        "filterable": ["order_id", "product_id"],
        "create": [],
        "update": [],
        "blocked_write_fields": ["quantity", "price_snapshot", "product_id", "order_id"],
        "permission": "sales.write",
        "read_permissions": ["sales.write", "reports.generate"],
    },
}
