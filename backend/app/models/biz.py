from sqlalchemy import select, func
from sqlalchemy.ext.hybrid import hybrid_property
from app.extensions import db
from .base import BaseModel

# 多对多：产品 <-> 标签
product_tags = db.Table('biz_product_tags',
    db.Column('product_id', db.Integer, db.ForeignKey('biz_products.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('biz_tags.id'))
)

class Tag(BaseModel):
    __tablename__ = 'biz_tags'
    name = db.Column(db.String(32), unique=True)
    color = db.Column(db.String(16), default='blue')

class Category(BaseModel):
    __tablename__ = 'biz_categories'
    name = db.Column(db.String(64))
    icon = db.Column(db.String(64), default='box')
    products = db.relationship('Product', backref='category', lazy='dynamic')

class Partner(BaseModel):
    __tablename__ = 'biz_partners'
    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'
    name = db.Column(db.String(128), index=True)
    type = db.Column(db.String(20), index=True)
    contact_person = db.Column(db.String(64))
    phone = db.Column(db.String(32))
    email = db.Column(db.String(128))
    address = db.Column(db.String(256))
    credit_score = db.Column(db.Integer, default=100)

class Product(BaseModel):
    __tablename__ = 'biz_products'
    sku = db.Column(db.String(64), unique=True, index=True)
    name = db.Column(db.String(128), index=True)
    price = db.Column(db.Numeric(18, 4), default=0)
    cost = db.Column(db.Numeric(18, 4), default=0)
    description = db.Column(db.Text)
    ai_summary = db.Column(db.Text)
    specs = db.Column(db.JSON)
    min_stock = db.Column(db.Integer, default=10)
    max_stock = db.Column(db.Integer, default=1000)
    category_id = db.Column(db.Integer, db.ForeignKey('biz_categories.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('biz_partners.id'))
    tags = db.relationship('Tag', secondary=product_tags, backref='products')
    supplier = db.relationship('Partner', foreign_keys=[supplier_id])

    @hybrid_property
    def total_stock(self):
        return sum(s.quantity for s in self.stocks)

    @total_stock.expression
    def total_stock(cls):
        from app.models.stock import Stock  # local import avoids potential init-order issues
        return (
            select(func.coalesce(func.sum(Stock.quantity), 0))
            .where(Stock.product_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )
