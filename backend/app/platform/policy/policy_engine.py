from app.platform.policy.data_scope import DataScopePolicy
from app.platform.policy.field_policy import FieldPolicy
from app.platform.policy.object_authorization import ObjectAuthorizationPolicy, PolicyDecision


class PolicyEngine:
    def __init__(self):
        self.data_scope = DataScopePolicy(is_admin=self.is_admin, has_any_permission=self.has_any_permission)
        self.field_policy = FieldPolicy(is_admin=self.is_admin, has_any_permission=self.has_any_permission)
        self.object_authorization = ObjectAuthorizationPolicy(has_any_permission=self.has_any_permission)

    def is_admin(self, user):
        return bool(user and (user.is_admin or (user.role and user.role.is_admin)))

    def has_any_permission(self, user, permissions):
        return bool(user and any(user.can(permission) for permission in permissions))

    def can(self, user, action, *, resource=None, context=None):
        context = context or {}
        if not user:
            return PolicyDecision(False, "需要登录", "unauthorized")
        if action.startswith("ai.tool."):
            return self._ai_tool_decision(user, action, resource=resource, context=context)
        if self.is_admin(user):
            return PolicyDecision(True)

        if context.get("admin_only"):
            return PolicyDecision(False, "需要管理员权限", "admin_required")

        object_decision = self.object_authorization.decide(user, action, resource)
        if object_decision is not None:
            return object_decision

        required_permission = context.get("permission")
        if required_permission and not isinstance(required_permission, str):
            required_permissions = set(required_permission)
            if action in {"list", "get", "create", "update", "delete"} and not self.has_any_permission(user, required_permissions):
                return PolicyDecision(False, "权限不足", "permission_denied")
            if action in {"list", "get"} and self.has_any_permission(user, required_permissions):
                return PolicyDecision(True)
        elif required_permission and action in {"create", "update", "delete"} and not user.can(required_permission):
            return PolicyDecision(False, "权限不足", "permission_denied")
        elif required_permission and required_permission in {"finance.payment", "finance.credit.write"} and user.can(required_permission):
            return PolicyDecision(True)

        if action.startswith("permission:"):
            permission_name = action.split(":", 1)[1]
            return PolicyDecision(bool(user.can(permission_name)), "权限不足", "permission_denied")

        return PolicyDecision(True)

    def filter_query(self, query, model, user):
        return self.data_scope.filter_query(query, model, user)

    def filter_fields(self, user, model, data):
        return self.field_policy.filter_fields(user, model, data)

    def _ai_tool_decision(self, user, action, *, resource=None, context=None):
        tool_name = action.rsplit(".", 1)[-1]
        object_decision = self.object_authorization.decide(user, "get", resource)
        if object_decision is not None:
            return object_decision

        if tool_name == "search_documents":
            if resource is not None:
                return PolicyDecision(True)
            if self.has_any_permission(user, {"ai.use", "files.manage"}):
                return PolicyDecision(True)
            return PolicyDecision(False, "权限不足", "permission_denied")

        permission_sets = {
            "query_inventory_balance": {"inventory.adjust", "stocktake.write", "reports.generate"},
            "query_sales_orders": {"sales.write", "reports.generate"},
            "query_receivables": {"finance.payment", "reports.generate"},
            "query_purchase_orders": {"purchase.write", "purchase.approve", "purchase.receive", "reports.generate"},
            "generate_replenishment_draft": {"inventory.adjust", "purchase.write"},
            "create_report_job": {"reports.generate"},
        }
        permissions = permission_sets.get(tool_name)
        if permissions is None:
            return PolicyDecision(False, "未知 AI 工具", "unknown_ai_tool")
        if self.has_any_permission(user, permissions):
            return PolicyDecision(True)
        return PolicyDecision(False, "权限不足", "permission_denied")


policy = PolicyEngine()


def can(user, action, *, resource=None, context=None):
    return policy.can(user, action, resource=resource, context=context)


def filter_query(query, model, user):
    return policy.filter_query(query, model, user)


def filter_fields(user, model, data):
    return policy.filter_fields(user, model, data)
