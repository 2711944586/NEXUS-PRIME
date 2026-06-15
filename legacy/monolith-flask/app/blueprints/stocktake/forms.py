"""盘点管理表单"""
from flask_wtf import FlaskForm
from wtforms import SelectField, SelectMultipleField, TextAreaField, IntegerField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange


class StockTakeCreateForm(FlaskForm):
    """创建盘点表单"""
    warehouse_id = SelectField('仓库', coerce=int, validators=[DataRequired()])
    take_type = SelectField('盘点类型', choices=[
        ('full', '全盘'),
        ('partial', '抽盘'),
        ('cycle', '循环盘点')
    ], validators=[DataRequired()])
    remark = TextAreaField('备注', validators=[Optional()])


class StockTakeItemForm(FlaskForm):
    """盘点录入表单"""
    item_id = HiddenField('明细ID', validators=[DataRequired()])
    actual_qty = IntegerField('实盘数量', validators=[DataRequired(), NumberRange(min=0)])
    remark = TextAreaField('备注', validators=[Optional()])


class StockTakeConfirmForm(FlaskForm):
    """差异确认表单"""
    item_id = HiddenField('明细ID', validators=[DataRequired()])
    adjustment_reason = TextAreaField('调整原因', validators=[DataRequired()])
