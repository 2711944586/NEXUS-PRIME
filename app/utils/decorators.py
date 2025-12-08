from functools import wraps
from flask import abort
from flask_login import current_user
from app.models.auth import Permission

def permission_required(permission):
    """
    检查用户是否具有特定权限
    (需配合 Role 模型中的 permissions 关联使用)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """
    检查用户是否是管理员
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 假设 Role 模型有一个 is_admin 字段，或者检查 role.name == 'Admin'
        # 这里使用我们在 Part 2 中定义的 role.name
        if not current_user.is_authenticated or \
           (current_user.role and current_user.role.name != 'Admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function