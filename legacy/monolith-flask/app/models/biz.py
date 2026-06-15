from app.extensions import db
from .base import BaseModel

# 多对多：产品 <-> 标签
product_tags = db.Table('biz_product_tags',
    db.Column('product_id', db.Integer, db.ForeignKey('biz_products.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('biz_tags.id'))
)

class Tag(BaseModel):
    """通用标签"""
    __tablename__ = 'biz_tags'
    name = db.Column(db.String(32), unique=True)
    color = db.Column(db.String(16), default='blue') # 标签颜色(Bootstrap类名或Hex)

class Category(BaseModel):
    """产品分类"""
    __tablename__ = 'biz_categories'
    name = db.Column(db.String(64))
    icon = db.Column(db.String(64), default='box') # FontAwesome 图标名
    
    products = db.relationship('Product', backref='category', lazy='dynamic')

class Partner(BaseModel):
    """业务伙伴 (客户/供应商)"""
    __tablename__ = 'biz_partners'
    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'

    name = db.Column(db.String(128), index=True)
    type = db.Column(db.String(20), index=True) # customer/supplier
    contact_person = db.Column(db.String(64))
    phone = db.Column(db.String(32))
    email = db.Column(db.String(128))
    address = db.Column(db.String(256))
    credit_score = db.Column(db.Integer, default=100) # 信用分

class Product(BaseModel):
    """产品主表"""
    __tablename__ = 'biz_products'
    
    sku = db.Column(db.String(64), unique=True, index=True) # 唯一货号
    name = db.Column(db.String(128), index=True)
    price = db.Column(db.Float, default=0.0) # 建议零售价
    cost = db.Column(db.Float, default=0.0)  # 成本价
    
    description = db.Column(db.Text) # 富文本描述
    ai_summary = db.Column(db.Text) # DeepSeek 生成的智能摘要
    
    specs = db.Column(db.JSON) # JSON 字段：存储规格参数 {"weight": "1kg", "color": "red"}
    
    # 库存设置
    min_stock = db.Column(db.Integer, default=10)  # 最小库存（低于预警）
    max_stock = db.Column(db.Integer, default=1000)  # 最大库存
    
    category_id = db.Column(db.Integer, db.ForeignKey('biz_categories.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id')) # 默认供应商
    
    # 关系
    tags = db.relationship('Tag', secondary=product_tags, backref='products')
    supplier = db.relationship('Partner', foreign_keys=[supplier_id])
    
    # 动态属性：计算当前总库存 (需结合 stock 模块)
    @property
    def total_stock(self):
        return sum([s.quantity for s in self.stocks])