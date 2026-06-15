from flask import render_template, jsonify
from flask_login import login_required
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from . import reports_bp
from app.extensions import db
from app.models.trade import Order, OrderItem
from app.models.biz import Product, Partner
from app.models.stock import Stock

@reports_bp.route('/')
@login_required
def index():
    """报表中心首页"""
    # 获取快速统计数据
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    
    # 本月销售数据
    monthly_sales = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        and_(
            Order.created_at >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).scalar() or 0
    
    monthly_orders = db.session.query(
        func.count(Order.id)
    ).filter(Order.created_at >= month_start).scalar() or 0
    
    monthly_customers = db.session.query(
        func.count(Partner.id)
    ).filter(
        and_(
            Partner.created_at >= month_start,
            Partner.type == 'customer'
        )
    ).scalar() or 0
    
    # 库存统计（从Stock表计算）
    inventory_data = db.session.query(
        func.sum(Stock.quantity * Product.price).label('total_value'),
        func.sum(Stock.quantity).label('total_quantity')
    ).join(Product, Stock.product_id == Product.id).first()
    
    inventory_value = inventory_data.total_value or 0
    
    total_products = db.session.query(
        func.count(Product.id)
    ).scalar() or 0
    
    # 低库存产品统计（库存小于10）
    low_stock_count = db.session.query(
        func.count(func.distinct(Stock.product_id))
    ).filter(Stock.quantity < 10).scalar() or 0
    
    return render_template('reports/index.html',
                         monthly_sales=monthly_sales,
                         monthly_orders=monthly_orders,
                         monthly_customers=monthly_customers,
                         inventory_value=inventory_value,
                         total_products=total_products,
                         low_stock_count=low_stock_count)

@reports_bp.route('/sales-analysis')
@login_required
def sales_analysis():
    """销售分析报表"""
    # 获取本月销售数据
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    
    # 本月总销售额
    monthly_sales = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        and_(
            Order.created_at >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).scalar() or 0
    
    # 本月订单数
    monthly_orders = db.session.query(
        func.count(Order.id)
    ).filter(
        Order.created_at >= month_start
    ).scalar() or 0
    
    # 本月新客户数
    monthly_customers = db.session.query(
        func.count(Partner.id)
    ).filter(
        and_(
            Partner.created_at >= month_start,
            Partner.type == 'customer'
        )
    ).scalar() or 0
    
    # 最近30天每日销售额
    thirty_days_ago = now - timedelta(days=30)
    daily_sales = db.session.query(
        func.date(Order.created_at).label('date'),
        func.sum(Order.total_amount).label('amount')
    ).filter(
        and_(
            Order.created_at >= thirty_days_ago,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).group_by(func.date(Order.created_at)).all()
    
    # 产品销售排行 TOP 10
    top_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('total_qty'),
        func.sum(OrderItem.quantity * OrderItem.price_snapshot).label('total_amount')
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        and_(
            Order.created_at >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).group_by(Product.id).order_by(
        func.sum(OrderItem.quantity * OrderItem.price_snapshot).desc()
    ).limit(10).all()
    
    # 客户消费排行 TOP 10
    top_customers = db.session.query(
        Partner.name,
        func.count(Order.id).label('order_count'),
        func.sum(Order.total_amount).label('total_amount')
    ).join(
        Order, Partner.id == Order.customer_id
    ).filter(
        and_(
            Order.created_at >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).group_by(Partner.id).order_by(
        func.sum(Order.total_amount).desc()
    ).limit(10).all()
    
    return render_template('reports/sales_analysis.html',
                         monthly_sales=monthly_sales,
                         monthly_orders=monthly_orders,
                         monthly_customers=monthly_customers,
                         daily_sales=daily_sales,
                         top_products=top_products,
                         top_customers=top_customers)

@reports_bp.route('/inventory-report')
@login_required
def inventory_report():
    """库存分析报表"""
    # 库存统计（从Stock表聚合）
    inventory_data = db.session.query(
        func.sum(Stock.quantity * Product.price).label('total_value'),
        func.sum(Stock.quantity).label('total_stock')
    ).join(Product, Stock.product_id == Product.id).first()
    
    inventory_value = inventory_data.total_value or 0
    total_stock = int(inventory_data.total_stock or 0)
    
    # 产品总数
    total_products = db.session.query(
        func.count(Product.id)
    ).scalar() or 0
    
    # 低库存产品（按product_id分组，总库存 < 10）
    low_stock_subquery = db.session.query(
        Stock.product_id,
        func.sum(Stock.quantity).label('total_qty')
    ).group_by(Stock.product_id).having(
        func.sum(Stock.quantity) < 10
    ).subquery()
    
    low_stock_products = db.session.query(
        Product, low_stock_subquery.c.total_qty
    ).join(
        low_stock_subquery, Product.id == low_stock_subquery.c.product_id
    ).order_by(low_stock_subquery.c.total_qty).limit(20).all()
    
    # 高库存产品（总库存 > 100）
    high_stock_subquery = db.session.query(
        Stock.product_id,
        func.sum(Stock.quantity).label('total_qty')
    ).group_by(Stock.product_id).having(
        func.sum(Stock.quantity) > 100
    ).subquery()
    
    high_stock_products = db.session.query(
        Product, high_stock_subquery.c.total_qty
    ).join(
        high_stock_subquery, Product.id == high_stock_subquery.c.product_id
    ).order_by(high_stock_subquery.c.total_qty.desc()).limit(20).all()
    
    # 零库存产品（没有Stock记录或quantity=0）
    zero_stock_count = db.session.query(
        func.count(Product.id)
    ).outerjoin(Stock, Product.id == Stock.product_id).filter(
        Stock.id == None
    ).scalar() or 0
    
    # 按类别统计库存（需要join Category表）
    from app.models.biz import Category
    category_stock = db.session.query(
        Category.name.label('category'),
        func.count(func.distinct(Product.id)).label('product_count'),
        func.sum(Stock.quantity).label('total_stock'),
        func.sum(Stock.quantity * Product.price).label('total_value')
    ).join(Product, Category.id == Product.category_id
    ).outerjoin(Stock, Product.id == Stock.product_id
    ).group_by(Category.id).all()
    
    return render_template('reports/inventory_report.html',
                         inventory_value=inventory_value,
                         total_stock=total_stock,
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         high_stock_products=high_stock_products,
                         zero_stock_count=zero_stock_count,
                         category_stock=category_stock)

@reports_bp.route('/api/sales-trend')
@login_required
def api_sales_trend():
    """销售趋势 API（最近7天）"""
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    daily_data = db.session.query(
        func.date(Order.created_at).label('date'),
        func.count(Order.id).label('orders'),
        func.sum(Order.total_amount).label('revenue')
    ).filter(
        and_(
            Order.created_at >= seven_days_ago,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).group_by(func.date(Order.created_at)).all()
    
    return jsonify({
        'dates': [str(item.date) for item in daily_data],
        'orders': [item.orders for item in daily_data],
        'revenue': [float(item.revenue or 0) for item in daily_data]
    })

@reports_bp.route('/api/product-category-distribution')
@login_required
def api_product_category():
    """产品类别分布 API"""
    from app.models.biz import Category
    
    category_data = db.session.query(
        Category.name,
        func.count(Product.id).label('count')
    ).outerjoin(Product, Category.id == Product.category_id
    ).group_by(Category.id).all()
    
    return jsonify({
        'categories': [item.name or '未分类' for item in category_data],
        'counts': [item.count for item in category_data]
    })


@reports_bp.route('/customer-analysis')
@login_required
def customer_analysis():
    """客户分析报表"""
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    thirty_days_ago = now - timedelta(days=30)
    
    # 客户总数
    total_customers = db.session.query(
        func.count(Partner.id)
    ).filter(Partner.type == 'customer').scalar() or 0
    
    # 本月新增客户
    new_customers = db.session.query(
        func.count(Partner.id)
    ).filter(
        and_(
            Partner.type == 'customer',
            Partner.created_at >= month_start
        )
    ).scalar() or 0
    
    # 活跃客户（30天内有订单）
    active_customers = db.session.query(
        func.count(func.distinct(Order.customer_id))
    ).filter(Order.created_at >= thirty_days_ago).scalar() or 0
    
    # 客户消费排行 TOP 20
    top_customers = db.session.query(
        Partner.id,
        Partner.name,
        Partner.phone,
        Partner.created_at,
        func.count(Order.id).label('order_count'),
        func.sum(Order.total_amount).label('total_amount')
    ).join(
        Order, Partner.id == Order.customer_id
    ).filter(
        Partner.type == 'customer'
    ).group_by(Partner.id).order_by(
        func.sum(Order.total_amount).desc()
    ).limit(20).all()
    
    # 客户消费分布 - 优化：一次查询获取所有客户消费总额，然后在内存中分组
    customer_totals = db.session.query(
        Order.customer_id,
        func.sum(Order.total_amount).label('total')
    ).group_by(Order.customer_id).all()
    
    # 在内存中按消费区间分组
    consumption_counts = {
        '0-1000': 0,
        '1000-5000': 0,
        '5000-10000': 0,
        '10000-50000': 0,
        '50000+': 0
    }
    
    for _, total in customer_totals:
        if total is None:
            continue
        total = float(total)
        if total < 1000:
            consumption_counts['0-1000'] += 1
        elif total < 5000:
            consumption_counts['1000-5000'] += 1
        elif total < 10000:
            consumption_counts['5000-10000'] += 1
        elif total < 50000:
            consumption_counts['10000-50000'] += 1
        else:
            consumption_counts['50000+'] += 1
    
    consumption_distribution = [
        {'range': k, 'count': v} for k, v in consumption_counts.items()
    ]
    
    # 最近新增客户
    recent_customers = Partner.query.filter_by(
        type='customer'
    ).order_by(Partner.created_at.desc()).limit(10).all()
    
    return render_template('reports/customer_analysis.html',
                         total_customers=total_customers,
                         new_customers=new_customers,
                         active_customers=active_customers,
                         top_customers=top_customers,
                         consumption_distribution=consumption_distribution,
                         recent_customers=recent_customers)


@reports_bp.route('/financial-report')
@login_required
def financial_report():
    """财务数据报表"""
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    year_start = datetime(now.year, 1, 1)
    
    # 本月营收
    monthly_revenue = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        and_(
            Order.created_at >= month_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).scalar() or 0
    
    # 本年营收
    yearly_revenue = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        and_(
            Order.created_at >= year_start,
            Order.status.in_(['paid', 'shipped', 'done'])
        )
    ).scalar() or 0
    
    # 本月订单数
    monthly_orders = db.session.query(
        func.count(Order.id)
    ).filter(Order.created_at >= month_start).scalar() or 0
    
    # 平均订单金额
    avg_order_value = db.session.query(
        func.avg(Order.total_amount)
    ).filter(
        Order.status.in_(['paid', 'shipped', 'done'])
    ).scalar() or 0
    
    # 月度营收趋势（最近12个月）
    monthly_trend = []
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i*30)
        m_start = datetime(month_date.year, month_date.month, 1)
        if month_date.month == 12:
            m_end = datetime(month_date.year + 1, 1, 1)
        else:
            m_end = datetime(month_date.year, month_date.month + 1, 1)
        
        revenue = db.session.query(
            func.sum(Order.total_amount)
        ).filter(
            and_(
                Order.created_at >= m_start,
                Order.created_at < m_end,
                Order.status.in_(['paid', 'shipped', 'done'])
            )
        ).scalar() or 0
        
        monthly_trend.append({
            'month': m_start.strftime('%Y-%m'),
            'revenue': float(revenue)
        })
    
    # 订单状态分布
    status_distribution = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()
    
    # 库存价值
    from app.models.stock import Stock
    inventory_value = db.session.query(
        func.sum(Stock.quantity * Product.price)
    ).join(Product, Stock.product_id == Product.id).scalar() or 0
    
    return render_template('reports/financial_report.html',
                         monthly_revenue=monthly_revenue,
                         yearly_revenue=yearly_revenue,
                         monthly_orders=monthly_orders,
                         avg_order_value=avg_order_value,
                         monthly_trend=monthly_trend,
                         status_distribution=status_distribution,
                         inventory_value=inventory_value)
