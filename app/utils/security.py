"""
安全工具函数
"""
import re
from flask import request, abort
from functools import wraps
from datetime import datetime, timedelta

# 速率限制存储（生产环境应使用 Redis）
_rate_limit_storage = {}

def rate_limit(max_requests=60, window=60):
    """
    API速率限制装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window: 时间窗口（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取客户端标识（IP地址）
            client_id = request.remote_addr
            key = f"{func.__name__}:{client_id}"
            
            now = datetime.now()
            
            # 清理过期记录
            if key in _rate_limit_storage:
                _rate_limit_storage[key] = [
                    timestamp for timestamp in _rate_limit_storage[key]
                    if now - timestamp < timedelta(seconds=window)
                ]
            else:
                _rate_limit_storage[key] = []
            
            # 检查是否超限
            if len(_rate_limit_storage[key]) >= max_requests:
                abort(429, description='请求过于频繁，请稍后再试')
            
            # 记录本次请求
            _rate_limit_storage[key].append(now)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def sanitize_input(text, allow_html=False):
    """
    清理用户输入，防止XSS攻击
    
    Args:
        text: 输入文本
        allow_html: 是否允许HTML（富文本编辑器）
    """
    if not text:
        return text
    
    if not allow_html:
        # 移除所有HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 转义特殊字符
        text = (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    
    # 移除潜在的SQL注入字符
    dangerous_patterns = [
        r'(\bOR\b.*?=.*?)',
        r'(\bAND\b.*?=.*?)',
        r'(;.*?DROP\b)',
        r'(;.*?DELETE\b)',
        r'(;.*?UPDATE\b)',
        r'(UNION.*?SELECT)',
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text.strip()


def validate_file_upload(filename, allowed_extensions=None):
    """
    验证上传文件
    
    Args:
        filename: 文件名
        allowed_extensions: 允许的扩展名集合
    """
    if not allowed_extensions:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    
    if '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def check_password_strength(password):
    """
    检查密码强度
    
    Returns:
        (bool, str): (是否通过, 错误信息)
    """
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
