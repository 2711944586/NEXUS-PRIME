from flask import request
from sqlalchemy import or_

from app.models.biz import Partner, Product
from app.models.stock import Stock, Warehouse

from . import api_bp
from .auth import jwt_required
from .responses import api_success


def lookup_payload(item, label, description=None, extra=None):
    data = {'id': item.id, 'label': label, 'value': item.id}
    if description:
        data['description'] = description
    if extra:
        data.update(extra)
    return data


@api_bp.get('/lookups/products')
@jwt_required
def lookup_products():
    term = (request.args.get('q') or '').strip()
    query = Product.query.filter(Product.is_deleted == False)
    if term:
        like = f'%{term}%'
        query = query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like)))
    rows = query.order_by(Product.name.asc()).limit(30).all()
    return api_success({'items': [
        lookup_payload(item, item.name, item.sku, {'sku': item.sku, 'price': item.price, 'cost': item.cost, 'total_stock': item.total_stock})
        for item in rows
    ]}, '商品选择')


@api_bp.get('/lookups/partners')
@jwt_required
def lookup_partners():
    term = (request.args.get('q') or '').strip()
    partner_type = request.args.get('type')
    query = Partner.query.filter(Partner.is_deleted == False)
    if partner_type in (Partner.TYPE_CUSTOMER, Partner.TYPE_SUPPLIER):
        query = query.filter(Partner.type == partner_type)
    if term:
        like = f'%{term}%'
        query = query.filter(or_(Partner.name.ilike(like), Partner.contact_person.ilike(like), Partner.phone.ilike(like)))
    rows = query.order_by(Partner.name.asc()).limit(30).all()
    return api_success({'items': [
        lookup_payload(item, item.name, item.contact_person, {'type': item.type, 'credit_score': item.credit_score})
        for item in rows
    ]}, '伙伴选择')


@api_bp.get('/lookups/warehouses')
@jwt_required
def lookup_warehouses():
    term = (request.args.get('q') or '').strip()
    query = Warehouse.query.filter(Warehouse.is_deleted == False)
    if term:
        like = f'%{term}%'
        query = query.filter(or_(Warehouse.name.ilike(like), Warehouse.location.ilike(like)))
    rows = query.order_by(Warehouse.name.asc()).limit(30).all()
    return api_success({'items': [
        lookup_payload(item, item.name, item.location, {'capacity': item.capacity})
        for item in rows
    ]}, '仓库选择')


@api_bp.get('/lookups/stock-locations')
@jwt_required
def lookup_stock_locations():
    product_id = request.args.get('product_id')
    warehouse_id = request.args.get('warehouse_id')
    query = Stock.query.filter(Stock.is_deleted == False)
    if product_id:
        query = query.filter(Stock.product_id == int(product_id))
    if warehouse_id:
        query = query.filter(Stock.warehouse_id == int(warehouse_id))
    rows = query.limit(50).all()
    return api_success({'items': [
        lookup_payload(item, item.shelf_location or f'库位 #{item.id}', item.warehouse.name if item.warehouse else None, {
            'product_id': item.product_id,
            'warehouse_id': item.warehouse_id,
            'quantity': item.quantity,
        })
        for item in rows
    ]}, '库位选择')
