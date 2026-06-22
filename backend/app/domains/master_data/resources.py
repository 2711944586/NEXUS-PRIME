from app.models.biz import Category, Partner, Product


MASTER_DATA_READ_PERMISSIONS = [
    "masterdata.write",
    "inventory.adjust",
    "stocktake.write",
    "purchase.write",
    "purchase.approve",
    "purchase.receive",
    "sales.write",
    "finance.payment",
    "finance.credit.write",
    "reports.generate",
]


master_data_resources = {
    "categories": {
        "model": Category,
        "search": ["name"],
        "filterable": [],
        "create": ["name", "icon"],
        "update": ["name", "icon"],
        "permission": "masterdata.write",
        "read_permissions": MASTER_DATA_READ_PERMISSIONS,
    },
    "partners": {
        "model": Partner,
        "search": ["name", "contact_person", "phone", "email"],
        "filterable": ["type"],
        "create": ["name", "type", "contact_person", "phone", "email", "address", "credit_score"],
        "update": ["name", "contact_person", "phone", "email", "address", "credit_score"],
        "permission": "masterdata.write",
        "read_permissions": MASTER_DATA_READ_PERMISSIONS,
    },
    "products": {
        "model": Product,
        "serializer_extra": "product",
        "search": ["name", "sku", "description"],
        "filterable": ["category_id", "supplier_id"],
        "create": ["sku", "name", "price", "cost", "description", "ai_summary", "specs", "min_stock", "max_stock", "category_id", "supplier_id"],
        "update": ["name", "price", "cost", "description", "ai_summary", "specs", "min_stock", "max_stock", "category_id", "supplier_id"],
        "permission": "masterdata.write",
        "read_permissions": MASTER_DATA_READ_PERMISSIONS,
    },
}
