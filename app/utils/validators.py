"""
表单验证器
"""
from wtforms.validators import ValidationError
import re

def validate_phone(form, field):
    """验证手机号格式"""
    if field.data:
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, field.data):
            raise ValidationError('请输入有效的手机号码')

def validate_username(form, field):
    """验证用户名格式"""
    if field.data:
        # 只允许字母、数字、下划线、中文
        if not re.match(r'^[\w\u4e00-\u9fa5]+$', field.data):
            raise ValidationError('用户名只能包含字母、数字、下划线和中文')

def validate_sku(form, field):
    """验证SKU格式"""
    if field.data:
        # SKU应为字母数字组合
        if not re.match(r'^[A-Z0-9-]+$', field.data):
            raise ValidationError('SKU只能包含大写字母、数字和连字符')

def validate_positive_number(form, field):
    """验证正数"""
    if field.data is not None and field.data <= 0:
        raise ValidationError('数值必须大于0')

def validate_non_negative(form, field):
    """验证非负数"""
    if field.data is not None and field.data < 0:
        raise ValidationError('数值不能为负')
