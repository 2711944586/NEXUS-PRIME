from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired

class OrderCreateForm(FlaskForm):
    """创建订单表单 (商品明细由 JS 动态处理)"""
    customer_id = SelectField('客户', coerce=int, validators=[DataRequired()])
    status = SelectField('初始状态', choices=[
        ('pending', '待付款 (Pending)'),
        ('paid', '已付款 (Paid)'),
        ('shipped', '已发货 (Shipped)')
    ], default='pending')
    remark = StringField('订单备注')
    submit = SubmitField('创建订单')

class OrderStatusForm(FlaskForm):
    """快速更新状态表单"""
    status = SelectField('更新状态', choices=[
        ('pending', '待付款'),
        ('paid', '已付款'),
        ('shipped', '已发货'),
        ('done', '已完成'),
        ('cancelled', '已取消')
    ])
    submit = SubmitField('更新')