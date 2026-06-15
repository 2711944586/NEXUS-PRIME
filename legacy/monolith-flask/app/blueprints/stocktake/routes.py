"""盘点管理路由"""
from flask import render_template, request, flash, redirect, url_for, jsonify, Response
from flask_login import login_required, current_user
from datetime import datetime
import io
from app.extensions import db
from app.blueprints.stocktake import stocktake_bp
from app.blueprints.stocktake.forms import StockTakeCreateForm, StockTakeItemForm, StockTakeConfirmForm
from app.models.stocktake import StockTake, StockTakeItem, StockTakeHistory
from app.models.stock import Warehouse
from app.models.biz import Product
from app.services.stocktake_service import StockTakeService
from app.utils.decorators import permission_required


@stocktake_bp.route('/')
@login_required
def index():
    """盘点单列表"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    
    query = StockTake.query
    
    if status:
        query = query.filter_by(status=status)
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    
    pagination = query.order_by(StockTake.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    
    warehouses = Warehouse.query.filter_by(is_deleted=False).all()
    
    return render_template('stocktake/index.html',
                         stocktakes=pagination.items,
                         pagination=pagination,
                         warehouses=warehouses,
                         current_status=status,
                         current_warehouse=warehouse_id)


@stocktake_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建盘点单"""
    form = StockTakeCreateForm()
    
    # 获取URL参数中的盘点类型
    preset_type = request.args.get('type', 'full')
    today = datetime.now().strftime('%Y-%m-%d')
    
    warehouses = Warehouse.query.filter_by(is_deleted=False).all()
    form.warehouse_id.choices = [(w.id, w.name) for w in warehouses]
    
    if form.validate_on_submit():
        take_type = form.take_type.data
        product_ids = []
        
        if take_type == 'partial':
            # 抽盘需要选择商品
            product_ids = request.form.getlist('product_ids[]')
            product_ids = [int(pid) for pid in product_ids if pid]
            
            if not product_ids:
                flash('抽盘请选择要盘点的商品', 'danger')
                products = Product.query.filter_by(is_deleted=False).all()
                return render_template('stocktake/create.html', form=form, products=products, preset_type=preset_type, today=today)
        
        # 获取计划日期
        planned_date = request.form.get('planned_date')
        
        success, result = StockTakeService.create_stocktake(
            warehouse_id=form.warehouse_id.data,
            take_type=take_type,
            product_ids=product_ids,
            user=current_user,
            remark=form.remark.data,
            planned_date=planned_date
        )
        
        if success:
            flash(f'盘点单 {result.take_no} 创建成功', 'success')
            return redirect(url_for('stocktake.detail', take_id=result.id))
        else:
            flash(result, 'danger')
    
    # 使用 joinedload 预加载关联数据避免 N+1 查询，并限制数量提高性能
    from sqlalchemy.orm import joinedload
    products = Product.query.options(
        joinedload(Product.category),
        joinedload(Product.stocks)
    ).filter_by(is_deleted=False).limit(200).all()
    return render_template('stocktake/create.html', form=form, products=products, preset_type=preset_type, today=today)


@stocktake_bp.route('/<int:take_id>')
@login_required
def detail(take_id):
    """盘点单详情"""
    stocktake = StockTake.query.get_or_404(take_id)
    items = StockTakeItem.query.filter_by(take_id=take_id).all()
    history = StockTakeHistory.query.filter_by(take_id=take_id).order_by(StockTakeHistory.created_at.desc()).all()
    
    variance_summary = StockTakeService.get_variance_summary(take_id)
    
    return render_template('stocktake/detail.html',
                         stocktake=stocktake,
                         items=items,
                         history=history,
                         variance_summary=variance_summary)


@stocktake_bp.route('/<int:take_id>/start', methods=['POST'])
@login_required
def start(take_id):
    """开始盘点"""
    success, msg = StockTakeService.start_stocktake(take_id, current_user)
    if success:
        flash('盘点已开始', 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('stocktake.detail', take_id=take_id))


@stocktake_bp.route('/<int:take_id>/input', methods=['GET', 'POST'])
@login_required
def input_count(take_id):
    """录入盘点数量"""
    stocktake = StockTake.query.get_or_404(take_id)
    
    if stocktake.status != StockTake.STATUS_IN_PROGRESS:
        flash('盘点单不在进行中状态', 'danger')
        return redirect(url_for('stocktake.detail', take_id=take_id))
    
    if request.method == 'POST':
        # 批量录入
        item_ids = request.form.getlist('item_id[]')
        actual_qtys = request.form.getlist('actual_qty[]')
        remarks = request.form.getlist('remark[]')
        
        counts = []
        for i, item_id in enumerate(item_ids):
            if item_id and actual_qtys[i] != '':
                counts.append({
                    'item_id': int(item_id),
                    'actual_qty': int(actual_qtys[i]),
                    'remark': remarks[i] if i < len(remarks) else ''
                })
        
        if counts:
            success_count = StockTakeService.batch_input_count(take_id, counts, current_user)
            flash(f'成功录入 {success_count} 条', 'success')
        
        return redirect(url_for('stocktake.detail', take_id=take_id))
    
    # 获取未盘点的项目（actual_qty 为 None）
    items = StockTakeItem.query.filter_by(take_id=take_id).filter(StockTakeItem.actual_qty.is_(None)).all()
    
    return render_template('stocktake/input.html', stocktake=stocktake, items=items)


@stocktake_bp.route('/<int:take_id>/confirm/<int:item_id>', methods=['POST'])
@login_required
def confirm_item(take_id, item_id):
    """确认差异项"""
    adjustment_reason = request.form.get('adjustment_reason', '')
    
    success, msg = StockTakeService.confirm_item(take_id, item_id, current_user, adjustment_reason)
    if success:
        flash('已确认', 'success')
    else:
        flash(msg, 'danger')
    
    return redirect(url_for('stocktake.detail', take_id=take_id))


@stocktake_bp.route('/<int:take_id>/complete', methods=['POST'])
@login_required
@permission_required('stocktake.complete')
def complete(take_id):
    """完成盘点"""
    auto_adjust = request.form.get('auto_adjust', '1') == '1'
    
    success, msg = StockTakeService.complete_stocktake(take_id, current_user, auto_adjust)
    if success:
        flash('盘点已完成', 'success')
    else:
        flash(msg, 'danger')
    
    return redirect(url_for('stocktake.detail', take_id=take_id))


@stocktake_bp.route('/<int:take_id>/cancel', methods=['POST'])
@login_required
def cancel(take_id):
    """取消盘点"""
    reason = request.form.get('reason', '手动取消')
    
    success, msg = StockTakeService.cancel_stocktake(take_id, current_user, reason)
    if success:
        flash('盘点已取消', 'success')
    else:
        flash(msg, 'danger')
    
    return redirect(url_for('stocktake.detail', take_id=take_id))


# ============== API 接口 ==============

@stocktake_bp.route('/api/item/<int:item_id>/count', methods=['POST'])
@login_required
def api_input_count(item_id):
    """API: 录入单个商品"""
    data = request.get_json()
    
    item = StockTakeItem.query.get_or_404(item_id)
    
    success, result = StockTakeService.input_count(
        item.stocktake_id,
        item_id,
        data.get('actual_qty', 0),
        current_user,
        data.get('remark', '')
    )
    
    if success:
        return jsonify({
            'success': True,
            'variance_qty': result.variance_qty,
            'variance_type': result.variance_type
        })
    else:
        return jsonify({'success': False, 'message': result}), 400


@stocktake_bp.route('/api/variance-summary/<int:take_id>')
@login_required
def api_variance_summary(take_id):
    """API: 获取差异汇总"""
    summary = StockTakeService.get_variance_summary(take_id)
    return jsonify(summary)


@stocktake_bp.route('/export/excel')
@login_required
def export_excel():
    """导出盘点数据为 Excel"""
    import csv
    
    status = request.args.get('status', '')
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    
    query = StockTake.query
    if status:
        query = query.filter_by(status=status)
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    
    stocktakes = query.order_by(StockTake.created_at.desc()).all()
    
    # 创建 CSV 内容
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['盘点单号', '仓库', '盘点类型', '状态', '进度', '创建时间', '创建人', '完成时间'])
    
    # 写入数据
    for st in stocktakes:
        status_map = {'draft': '草稿', 'in_progress': '进行中', 'completed': '已完成', 'cancelled': '已取消'}
        type_map = {'full': '全盘', 'partial': '抽盘', 'cycle': '循环盘点'}
        writer.writerow([
            st.take_no,
            st.warehouse.name if st.warehouse else '-',
            type_map.get(st.take_type, st.take_type),
            status_map.get(st.status, st.status),
            f"{st.progress}%" if st.progress else '0%',
            st.created_at.strftime('%Y-%m-%d %H:%M') if st.created_at else '-',
            st.creator.username if st.creator else '-',
            st.completed_at.strftime('%Y-%m-%d %H:%M') if st.completed_at else '-'
        ])
    
    # 返回 CSV 文件
    output.seek(0)
    filename = f"stocktake_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@stocktake_bp.route('/export/pdf')
@login_required
def export_pdf():
    """导出盘点数据为 PDF (通过打印页面)"""
    status = request.args.get('status', '')
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    
    query = StockTake.query
    if status:
        query = query.filter_by(status=status)
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    
    stocktakes = query.order_by(StockTake.created_at.desc()).all()
    warehouses = Warehouse.query.filter_by(is_deleted=False).all()
    
    return render_template('stocktake/print_report.html',
                         stocktakes=stocktakes,
                         warehouses=warehouses,
                         export_time=datetime.now())
