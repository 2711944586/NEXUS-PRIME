"""Password policy helpers shared by API and domain code."""

import re


def check_password_strength(password):
    """Returns (ok: bool, error: str)."""
    if len(password) < 8:
        return False, '密码长度至少8位'
    if not re.search(r'[a-z]', password):
        return False, '密码必须包含小写字母'
    if not re.search(r'[A-Z]', password):
        return False, '密码必须包含大写字母'
    if not re.search(r'\d', password):
        return False, '密码必须包含数字'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, '密码必须包含特殊字符'
    return True, ''
