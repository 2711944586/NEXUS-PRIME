from app.models.auth import Department, Role, User
from app.models.sys import AuditLog


identity_resources = {
    "users": {
        "model": User,
        "serializer_extra": "user",
        "search": ["username", "email", "full_name"],
        "filterable": ["role_id", "is_admin", "is_active_user", "department_id"],
        "create": ["username", "email", "phone", "full_name", "role_id", "department_id", "is_admin", "is_active_user", "password"],
        "update": ["username", "email", "phone", "full_name", "department_name", "position", "bio", "role_id", "department_id", "is_admin", "is_active_user"],
        "admin_only": True,
    },
    "roles": {
        "model": Role,
        "search": ["name"],
        "filterable": [],
        "create": ["name", "is_admin"],
        "update": ["name", "is_admin"],
        "admin_only": True,
    },
    "departments": {
        "model": Department,
        "search": ["name", "code"],
        "filterable": ["parent_id"],
        "create": ["name", "code", "parent_id"],
        "update": ["name", "code", "parent_id"],
        "admin_only": True,
    },
    "audit-logs": {
        "model": AuditLog,
        "serializer_extra": "audit",
        "search": ["module", "action", "details"],
        "filterable": ["module", "action", "user_id"],
        "create": [],
        "update": [],
        "admin_only": True,
    },
}
