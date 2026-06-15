from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Length

class StockAdjustmentForm(FlaskForm):
    """库存调整表单"""
    # 隐藏字段：产品ID和仓库ID
    product_id = HiddenField('Product ID', validators=[DataRequired()])
    warehouse_id = SelectField('选择仓库', coerce=int, validators=[DataRequired()])
    
    # 变动类型
    move_type = SelectField('操作类型', choices=[
        ('inbound', '采购入库 (+IN)'),
        ('outbound', '销售出库 (-OUT)'),
        ('check', '盘点修正 (FIX)'),
        ('return', '退货入库 (+RET)')
    ], validators=[DataRequired()])
    
    # 数量
    quantity = IntegerField('变动数量', validators=[
        DataRequired(),
        NumberRange(min=1, message="数量必须大于 0")
    ])
    
    # 备注
    remark = StringField('业务备注', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    submit = SubmitField('提交执行指令')

class ProductSearchForm(FlaskForm):
    """商品搜索表单"""
    q = StringField('Search', validators=[Length(max=50)], render_kw={"placeholder": "输入 SKU 或名称搜索..."})
    submit = SubmitField('Search')