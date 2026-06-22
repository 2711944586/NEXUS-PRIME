from app.models.finance import AccountStatement, CustomerCredit, PaymentRecord, Receivable


finance_resources = {
    "receivables": {
        "model": Receivable,
        "serializer_extra": "receivable",
        "search": ["receivable_no", "status", "remark"],
        "filterable": ["status", "customer_id"],
        "create": [],
        "update": ["due_date", "remark"],
        "blocked_write_fields": ["total_amount", "paid_amount", "status", "customer_id"],
        "permission": "finance.payment",
        "read_permissions": ["finance.payment", "sales.write", "reports.generate"],
    },
    "payments": {
        "model": PaymentRecord,
        "search": ["payment_no", "payment_method", "reference_no"],
        "filterable": ["customer_id", "receivable_id"],
        "create": [],
        "update": [],
        "blocked_write_fields": ["amount", "customer_id", "receivable_id"],
        "permission": "finance.payment",
        "read_permissions": ["finance.payment", "sales.write", "reports.generate"],
    },
    "statements": {
        "model": AccountStatement,
        "search": ["statement_no"],
        "filterable": ["confirmed"],
        "create": [],
        "update": ["confirmed"],
        "permission": "reports.generate",
        "read_permissions": ["reports.generate"],
    },
    "credits": {
        "model": CustomerCredit,
        "serializer_extra": "credit",
        "search": [],
        "filterable": ["customer_id", "is_frozen"],
        "create": [],
        "update": ["credit_limit", "warning_threshold"],
        "blocked_write_fields": ["used_credit", "is_frozen", "frozen_reason"],
        "permission": "finance.credit.write",
        "read_permissions": ["finance.credit.write"],
    },
}
