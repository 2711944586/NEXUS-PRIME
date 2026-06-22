from app.models.biz import Partner, Product
from app.models.finance import CustomerCredit, PaymentRecord, Receivable
from app.models.trade import Order, OrderItem


class FieldPolicy:
    """Remove sensitive fields from serialized payloads."""

    def __init__(self, *, is_admin, has_any_permission):
        self._is_admin = is_admin
        self._has_any_permission = has_any_permission

    def filter_fields(self, user, model, data):
        if not data or not user or self._is_admin(user):
            return data
        hidden = self.hidden_fields(user, model)
        if not hidden:
            return data
        return {key: value for key, value in data.items() if key not in hidden}

    def hidden_fields(self, user, model):
        if model is Product and not self._has_any_permission(user, {"masterdata.write", "finance.credit.write", "finance.payment"}):
            return {"cost", "supplier_id"}
        if model is Partner and not self._has_any_permission(user, {"masterdata.write", "finance.credit.write", "finance.payment"}):
            return {"credit_score"}
        if model is Receivable and not self._has_any_permission(user, {"finance.payment"}):
            return {"total_amount", "paid_amount", "unpaid_amount"}
        if model is PaymentRecord and not self._has_any_permission(user, {"finance.payment"}):
            return {"amount", "reference_no"}
        if model is CustomerCredit and not self._has_any_permission(user, {"finance.credit.write"}):
            return {"credit_limit", "used_credit", "available_credit", "usage_rate", "is_warning", "warning_threshold", "is_frozen", "frozen_reason"}
        if model is Order and not self._has_any_permission(user, {"sales.write", "finance.payment"}):
            return {"total_amount"}
        if model is OrderItem and not self._has_any_permission(user, {"sales.write", "finance.payment"}):
            return {"price_snapshot", "subtotal"}
        return set()
