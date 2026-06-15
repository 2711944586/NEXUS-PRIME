from flask import render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
import random

from app.extensions import db
from . import main_bp
from app.models.auth import User
from app.models.biz import Product, Partner
from app.models.trade import Order
from app.models.stock import InventoryLog


def get_chart_data():
    """生成图表数据的辅助函数"""
    chart_dates = []
    chart_values = []
    today = datetime.now()
    for i in range(6, -1, -1):
        date = (today - timedelta(days=i)).strftime('%m-%d')
        # 模拟查询每天的订单数 (这里用随机数代替复杂SQL，保证有图表显示)
        # 真实写法: Order.query.filter(...).count()
        value = random.randint(10, 50) 
        chart_dates.append(date)
        chart_values.append(value)
    return chart_dates, chart_values


def get_category_data():
    """生成分类数据"""
    # 模拟分类数据，真实项目中应从数据库查询
    categories = [
        {'name': '电子产品', 'value': random.randint(25, 40), 'color': '#6366f1'},
        {'name': '服装配饰', 'value': random.randint(20, 35), 'color': '#10b981'},
        {'name': '家居用品', 'value': random.randint(15, 25), 'color': '#fbbf24'},
        {'name': '食品饮料', 'value': random.randint(10, 20), 'color': '#f43f5e'},
        {'name': '其他', 'value': random.randint(8, 18), 'color': '#8b5cf6'}
    ]
    return categories


def get_order_status_data():
    """获取订单状态分布"""
    # 真实项目应从Order表group by status查询
    return [
        {'name': '待确认', 'value': random.randint(5, 15), 'color': '#f59e0b'},
        {'name': '处理中', 'value': random.randint(10, 25), 'color': '#3b82f6'},
        {'name': '已发货', 'value': random.randint(15, 30), 'color': '#8b5cf6'},
        {'name': '已完成', 'value': random.randint(30, 60), 'color': '#10b981'},
        {'name': '已取消', 'value': random.randint(2, 8), 'color': '#ef4444'}
    ]


def get_inventory_trend():
    """获取库存趋势数据"""
    dates = []
    inbound = []
    outbound = []
    today = datetime.now()
    for i in range(6, -1, -1):
        date = (today - timedelta(days=i)).strftime('%m-%d')
        dates.append(date)
        inbound.append(random.randint(20, 80))
        outbound.append(random.randint(15, 60))
    return {'dates': dates, 'inbound': inbound, 'outbound': outbound}


@main_bp.route('/')
@login_required
def index():
    # 1. 核心 KPI 卡片数据
    kpi_data = {
        'total_users': User.query.count(),
        'total_products': Product.query.count(),
        'total_orders': Order.query.count(),
        'total_revenue': db.session.query(func.sum(Order.total_amount)).scalar() or 0.0
    }

    # 2. 获取最近 5 条系统动态 (审计日志或库存流水)
    recent_logs = InventoryLog.query.order_by(InventoryLog.created_at.desc()).limit(5).all()

    # 3. 计算 ECharts 图表数据
    chart_dates, chart_values = get_chart_data()
    
    # 4. 分类数据
    category_data = get_category_data()
    
    # 5. 订单状态数据
    order_status_data = get_order_status_data()
    
    # 6. 库存趋势数据
    inventory_trend = get_inventory_trend()

    return render_template('main/dashboard.html', 
                           kpi=kpi_data, 
                           logs=recent_logs,
                           chart_dates=chart_dates,
                           chart_values=chart_values,
                           category_data=category_data,
                           order_status_data=order_status_data,
                           inventory_trend=inventory_trend)


@main_bp.route('/api/chart/refresh')
@login_required
def refresh_chart():
    """刷新图表数据的 API"""
    chart_dates, chart_values = get_chart_data()
    return jsonify({
        'success': True,
        'dates': chart_dates,
        'values': chart_values
    })


@main_bp.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """获取完整仪表盘统计数据"""
    chart_dates, chart_values = get_chart_data()
    return jsonify({
        'success': True,
        'sales': {
            'dates': chart_dates,
            'values': chart_values
        },
        'categories': get_category_data(),
        'orderStatus': get_order_status_data(),
        'inventoryTrend': get_inventory_trend()
    })