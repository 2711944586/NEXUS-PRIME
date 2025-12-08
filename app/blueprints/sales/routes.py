from flask import render_template, request, flash, redirect, url_for, abort, send_file
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy.orm import subqueryload
from app.blueprints.sales import sales_bp
from app.blueprints.sales.forms import OrderCreateForm
from app.services.sales_service import SalesService
from app.models.trade import Order
from app.models.biz import Partner, Product
from app.extensions import db
from app.services.export_service import export_service
from app.utils.audit import audit_log

@sales_bp.route('/kanban')
@login_required
def kanban():
    """看板视图"""
    # 使用 subqueryload 预加载关联数据（比 joinedload 更快）
    all_orders = Order.query.options(
        subqueryload(Order.customer),
        subqueryload(Order.items)
    ).filter(
        Order.status.in_(['pending', 'paid', 'shipped', 'done'])
    ).order_by(Order.created_at.desc()).limit(40).all()
    
    # 在内存中按状态分组
    orders_by_status = {
        'pending': [],
        'paid': [],
        'shipped': [],
        'done': []
    }
    
    for order in all_orders:
        if order.status in orders_by_status and len(orders_by_status[order.status]) < 10:
            orders_by_status[order.status].append(order)
    
    return render_template('sales/kanban.html', 
                           pending=orders_by_status['pending'],
                           paid=orders_by_status['paid'],
                           shipped=orders_by_status['shipped'],
                           done=orders_by_status['done'])

@sales_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建订单页面"""
    form = OrderCreateForm()
    # 填充客户下拉框（只查询必要字段）
    customers = db.session.query(Partner.id, Partner.name).filter_by(
        type='customer', is_deleted=False
    ).order_by(Partner.name).all()
    form.customer_id.choices = [(c.id, c.name) for c in customers]
    
    if request.method == 'POST':
        # 由于是动态表单，我们需要手动解析 product_id_list 和 quantity_list
        # 简单起见，假设前端传来了 parallel arrays
        p_ids = request.form.getlist('product_ids[]')
        qtys = request.form.getlist('quantities[]')
        
        # 获取客户ID（支持可搜索下拉框的新格式）
        customer_id = request.form.get('customer_id')
        customer_name = request.form.get('customer_name', '').strip()
        
        # 如果没有选择现有客户但输入了客户名称，可以创建新客户
        if not customer_id and customer_name:
            # 尝试查找现有客户
            existing_customer = Partner.query.filter_by(name=customer_name, type='customer').first()
            if existing_customer:
                customer_id = existing_customer.id
            else:
                # 创建新客户
                new_customer = Partner(name=customer_name, type='customer')
                db.session.add(new_customer)
                db.session.flush()
                customer_id = new_customer.id
        
        if not customer_id:
            flash('请选择或输入客户名称', 'danger')
        elif not p_ids or not any(p_ids):
            flash('请至少添加一个商品', 'danger')
        else:
            # 组装数据，过滤掉空的商品ID
            items_data = []
            for i in range(len(p_ids)):
                if p_ids[i]:  # 只处理有效的商品ID
                    items_data.append({'product_id': p_ids[i], 'quantity': qtys[i] if i < len(qtys) else 1})
            
            if not items_data:
                flash('请至少添加一个有效商品', 'danger')
            else:
                try:
                    order = SalesService.create_order(
                        customer_id=int(customer_id),
                        user=current_user,
                        items_data=items_data,
                        status=form.status.data
                    )
                    flash(f'订单 {order.order_no} 创建成功！', 'success')
                    return redirect(url_for('sales.kanban'))
                except Exception as e:
                    flash(f'创建失败: {str(e)}', 'danger')

    # 获取所有商品供前端 JS 选择（只查询必要字段提升性能）
    all_products = db.session.query(
        Product.id, Product.name, Product.price
    ).order_by(Product.name).all()
    return render_template('sales/create.html', form=form, products=all_products)

@sales_bp.route('/invoice/<int:order_id>')
@login_required
def invoice(order_id):
    """打印发票视图"""
    order = Order.query.get_or_404(order_id)
    return render_template('sales/invoice.html', order=order)

@sales_bp.route('/')
@login_required
def index():
    return redirect(url_for('sales.kanban'))


@sales_bp.route('/export/<format>')
@login_required
@audit_log(module='sales', action='export')
def export_orders(format):
    """导出订单数据到 Excel 或 CSV"""
    try:
        # 优化查询：预加载关联数据避免 N+1 问题
        orders = Order.query.options(
            subqueryload(Order.customer),
            subqueryload(Order.seller),
            subqueryload(Order.items)
        ).order_by(Order.created_at.desc()).limit(500).all()
        
        status_map = {'pending': '待处理', 'paid': '已支付', 'shipped': '已发货', 'done': '已完成', 'cancelled': '已取消'}
        
        data = [{
            'order_no': o.order_no,
            'customer': o.customer.name if o.customer else '',
            'total_amount': float(o.total_amount) if o.total_amount else 0,
            'status': status_map.get(o.status, o.status),
            'items_count': len(o.items) if o.items else 0,
            'seller': o.seller.username if o.seller else '',
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else ''
        } for o in orders]
        
        columns = [
            {'field': 'order_no', 'header': '订单编号', 'width': 18},
            {'field': 'customer', 'header': '客户名称', 'width': 20},
            {'field': 'total_amount', 'header': '订单金额', 'width': 12},
            {'field': 'status', 'header': '订单状态', 'width': 10},
            {'field': 'items_count', 'header': '商品数量', 'width': 10},
            {'field': 'seller', 'header': '销售员', 'width': 12},
            {'field': 'created_at', 'header': '创建时间', 'width': 18}
        ]
        
        if format == 'excel':
            output = export_service.export_to_excel(
                data=data, columns=columns,
                sheet_name='订单数据',
                title='NEXUS PRIME - 销售订单报表'
            )
            filename = f'orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            output = export_service.export_to_csv(data=data, columns=columns)
            filename = f'orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            mimetype = 'text/csv'
        
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
        
    except Exception as e:
        flash(f'导出失败: {str(e)}', 'danger')
        return redirect(url_for('sales.kanban'))