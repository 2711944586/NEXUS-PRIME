"""财务管理表单"""
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, TextAreaField, DateField, StringField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional


class CreditSettingForm(FlaskForm):
    """信用额度设置表单"""
    customer_id = HiddenField('客户ID', validators=[DataRequired()])
    credit_limit = DecimalField('信用额度', places=2, validators=[DataRequired(), NumberRange(min=0)])
    warning_threshold = DecimalField('预警阈值(%)', places=0, validators=[Optional(), NumberRange(min=0, max=100)], default=80)


class PaymentForm(FlaskForm):
    """收款表单"""
    receivable_id = HiddenField('应收ID', validators=[DataRequired()])
    amount = DecimalField('收款金额', places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    payment_method = SelectField('收款方式', choices=[
        ('cash', '现金'),
        ('bank', '银行转账'),
        ('alipay', '支付宝'),
        ('wechat', '微信'),
        ('other', '其他')
    ], validators=[DataRequired()])
    reference_no = StringField('参考单号', validators=[Optional()])
    remark = TextAreaField('备注', validators=[Optional()])


class StatementForm(FlaskForm):
    """对账单表单"""
    customer_id = SelectField('客户', coerce=int, validators=[DataRequired()])
    period_start = DateField('开始日期', validators=[DataRequired()])
    period_end = DateField('结束日期', validators=[DataRequired()])
