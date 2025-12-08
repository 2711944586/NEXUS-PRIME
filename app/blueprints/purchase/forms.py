"""采购管理表单"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField, TextAreaField, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional


class PurchaseItemForm(FlaskForm):
    """采购明细表单"""
    class Meta:
        csrf = False
    
    product_id = HiddenField('商品ID', validators=[DataRequired()])
    quantity = IntegerField('数量', validators=[DataRequired(), NumberRange(min=1)])
    unit_price = DecimalField('单价', places=2, validators=[DataRequired(), NumberRange(min=0)])


class PurchaseOrderForm(FlaskForm):
    """采购订单表单"""
    supplier_id = SelectField('供应商', coerce=int, validators=[DataRequired()])
    warehouse_id = SelectField('入库仓库', coerce=int, validators=[DataRequired()])
    remark = TextAreaField('备注', validators=[Optional()])


class ReceiveItemForm(FlaskForm):
    """收货表单"""
    item_id = HiddenField('明细ID', validators=[DataRequired()])
    received_qty = IntegerField('收货数量', validators=[DataRequired(), NumberRange(min=0)])
    is_quality_pass = SelectField('质检', coerce=int, choices=[(1, '合格'), (0, '不合格')], default=1)
