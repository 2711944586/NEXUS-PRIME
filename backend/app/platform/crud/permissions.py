from app.platform.policy import policy


PERMISSION_LABELS = {
    "inventory.adjust": "库存调整",
    "purchase.write": "采购创建",
    "purchase.approve": "采购审批",
    "purchase.receive": "采购收货",
    "finance.payment": "收款处理",
    "finance.credit.write": "信用管理",
    "reports.generate": "报表生成",
    "files.manage": "文件管理",
    "content.write": "内容管理",
    "stocktake.write": "盘点管理",
    "masterdata.write": "主数据维护",
    "sales.write": "销售履约",
    "admin": "系统管理",
}


def is_admin_user(user):
    return policy.is_admin(user)


def can_user(user, permission):
    return policy.can(user, f"permission:{permission}").allowed


def permission_summary(user):
    if not user:
        return []
    if is_admin_user(user):
        names = sorted(PERMISSION_LABELS)
    else:
        names = sorted({perm.name for perm in user.role.permissions}) if user.role else []
    return [{"name": name, "label": PERMISSION_LABELS.get(name, name)} for name in names]


def resource_access_error(config, action, user, item=None):
    permission = config.get("permission")
    if action in {"list", "get"} and config.get("read_permissions"):
        permission = tuple(config["read_permissions"])
    decision = policy.can(
        user,
        action,
        resource=item,
        context={
            "admin_only": config.get("admin_only"),
            "permission": permission,
            "resource_model": config["model"],
        },
    )
    if not decision.allowed:
        return decision.reason or "权限不足", decision.error or "forbidden"
    return None
