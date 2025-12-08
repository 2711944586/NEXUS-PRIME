from flask import render_template, request, flash, redirect, url_for, current_app, send_file, Response, stream_with_context
from flask_login import login_required, current_user
from datetime import datetime
import csv
import io
from app.extensions import db
from app.blueprints.inventory import inventory_bp
from app.models.biz import Product, Category, Tag, Partner
from app.models.stock import Warehouse, Stock, InventoryLog
from app.blueprints.inventory.forms import StockAdjustmentForm, ProductSearchForm
from app.services.inventory_service import InventoryService
from app.services.export_service import export_service
from app.utils.audit import audit_log

@inventory_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    库存商品列表页
    包含：分页、搜索、调整库存模态框处理
    """
    search_form = ProductSearchForm()
    adjust_form = StockAdjustmentForm()
    
    # 动态填充仓库下拉列表
    warehouses = Warehouse.query.all()
    adjust_form.warehouse_id.choices = [(w.id, w.name) for w in warehouses]

    # 处理库存调整提交
    if adjust_form.validate_on_submit():
        success, msg = InventoryService.adjust_stock(
            product_id=adjust_form.product_id.data,
            warehouse_id=adjust_form.warehouse_id.data,
            quantity=adjust_form.quantity.data,
            move_type=adjust_form.move_type.data,
            user=current_user,
            remark=adjust_form.remark.data
        )
        if success:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('inventory.index'))

    # 处理搜索查询 - 从 URL 参数获取
    query = Product.query
    search_keyword = request.args.get('q', '').strip()
    if search_keyword:
        keyword = f"%{search_keyword}%"
        query = query.filter(Product.name.ilike(keyword) | Product.sku.ilike(keyword))
        # 将搜索词回填到表单
        search_form.q.data = search_keyword

    # 分页
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Product.id.asc()).paginate(page=page, per_page=12, error_out=False)
    products = pagination.items

    return render_template(
        'inventory/index.html', 
        products=products, 
        pagination=pagination,
        search_form=search_form,
        search_keyword=search_keyword,
        adjust_form=adjust_form,
        warehouses=warehouses
    )


@inventory_bp.route('/export/<format>')
@login_required
@audit_log(module='inventory', action='export')
def export_inventory(format):
    """导出库存数据到 Excel 或 CSV - 优化版本使用流式响应"""
    filename_base = f'inventory_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    if format == 'csv':
        # CSV 使用流式响应，速度更快
        def generate_csv():
            # 输出 BOM 以支持 Excel 打开中文
            yield '\ufeff'
            # 表头
            yield 'SKU编码,产品名称,分类,当前库存,最小库存,最大库存,成本价,售价,供应商,状态,创建时间\n'
            # 分批查询数据
            batch_size = 100
            offset = 0
            while True:
                products = Product.query.order_by(Product.sku.asc()).offset(offset).limit(batch_size).all()
                if not products:
                    break
                for p in products:
                    status = '正常' if p.total_stock >= (p.min_stock or 10) else '低库存'
                    created = p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else ''
                    line = f'{p.sku},{p.name},{p.category.name if p.category else ""},{p.total_stock},{p.min_stock or 10},{p.max_stock or 1000},{p.cost or 0},{p.price or 0},{p.supplier.name if p.supplier else ""},{status},{created}\n'
                    yield line
                offset += batch_size
        
        return Response(
            stream_with_context(generate_csv()),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename_base}.csv'}
        )
    else:
        # Excel 格式保持原有逻辑但优化查询
        try:
            products = Product.query.options(
                db.joinedload(Product.category),
                db.joinedload(Product.supplier)
            ).order_by(Product.sku.asc()).all()
            
            data = [{
                'sku': p.sku,
                'name': p.name,
                'category': p.category.name if p.category else '',
                'stock': p.total_stock,
                'min_stock': p.min_stock or 10,
                'max_stock': p.max_stock or 1000,
                'cost': float(p.cost or 0),
                'price': float(p.price or 0),
                'supplier': p.supplier.name if p.supplier else '',
                'status': '正常' if p.total_stock >= (p.min_stock or 10) else '低库存',
                'created_at': p.created_at
            } for p in products]
            
            columns = [
                {'field': 'sku', 'header': 'SKU编码', 'width': 15},
                {'field': 'name', 'header': '产品名称', 'width': 25},
                {'field': 'category', 'header': '分类', 'width': 12},
                {'field': 'stock', 'header': '当前库存', 'width': 12},
                {'field': 'min_stock', 'header': '最小库存', 'width': 12},
                {'field': 'max_stock', 'header': '最大库存', 'width': 12},
                {'field': 'cost', 'header': '成本价', 'width': 12},
                {'field': 'price', 'header': '售价', 'width': 12},
                {'field': 'supplier', 'header': '供应商', 'width': 20},
                {'field': 'status', 'header': '状态', 'width': 10},
                {'field': 'created_at', 'header': '创建时间', 'width': 18}
            ]
            
            output = export_service.export_to_excel(
                data=data, columns=columns,
                sheet_name='库存数据',
                title='NEXUS PRIME - 库存数据报表'
            )
            return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                           as_attachment=True, download_name=f'{filename_base}.xlsx')
        except Exception as e:
            flash(f'导出失败: {str(e)}', 'danger')
            return redirect(url_for('inventory.index'))


@inventory_bp.route('/barcode/<sku>')
@login_required
def get_barcode(sku):
    """
    (可选) 这是一个占位接口
    实际项目中可以使用 python-barcode 生成 SVG 并返回
    这里我们只在前端用 CSS 模拟条码效果，所以此接口暂时留空
    """
    return "Barcode Generation API"


@inventory_bp.route('/view/<int:product_id>', methods=['GET', 'POST'])
@login_required
def view(product_id):
    """商品详情页"""
    product = Product.query.get_or_404(product_id)
    
    # 库存调整表单
    adjust_form = StockAdjustmentForm()
    warehouses = Warehouse.query.all()
    adjust_form.warehouse_id.choices = [(w.id, w.name) for w in warehouses]
    
    # 处理库存调整提交
    if adjust_form.validate_on_submit():
        success, msg = InventoryService.adjust_stock(
            product_id=product_id,
            warehouse_id=adjust_form.warehouse_id.data,
            quantity=adjust_form.quantity.data,
            move_type=adjust_form.move_type.data,
            operator_id=current_user.id,
            remark=adjust_form.remark.data
        )
        if success:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('inventory.view', product_id=product_id))
    
    # 获取库存变动记录
    stock_movements = InventoryLog.query.filter_by(product_id=product_id)\
        .order_by(InventoryLog.created_at.desc())\
        .limit(20).all()
    
    return render_template(
        'inventory/view.html',
        product=product,
        stock_movements=stock_movements,
        adjust_form=adjust_form
    )


@inventory_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@audit_log(module='inventory', action='edit')
def edit(product_id):
    """编辑商品页"""
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            # 更新基本信息
            product.sku = request.form.get('sku', product.sku)
            product.name = request.form.get('name', product.name)
            product.description = request.form.get('description', '')
            
            # 处理分类 - 支持选择已有或创建新分类
            category_id = request.form.get('category_id')
            category_name = request.form.get('category_name', '').strip()
            
            if category_id:
                # 用户选择了已有分类
                product.category_id = int(category_id)
            elif category_name:
                # 用户输入了新分类名称，需要创建
                existing_cat = Category.query.filter_by(name=category_name).first()
                if existing_cat:
                    product.category_id = existing_cat.id
                else:
                    # 创建新分类
                    new_category = Category(
                        name=category_name,
                        icon='cube',  # 默认图标
                        description=f'自动创建的分类: {category_name}'
                    )
                    db.session.add(new_category)
                    db.session.flush()  # 获取新 ID
                    product.category_id = new_category.id
            
            # 处理供应商 - 支持选择已有或创建新供应商
            supplier_id = request.form.get('supplier_id')
            supplier_name = request.form.get('supplier_name', '').strip()
            
            if supplier_id:
                product.supplier_id = int(supplier_id)
            elif supplier_name:
                # 用户输入了新供应商名称
                existing_sup = Partner.query.filter_by(name=supplier_name, type='supplier').first()
                if existing_sup:
                    product.supplier_id = existing_sup.id
                else:
                    # 创建新供应商
                    new_supplier = Partner(
                        name=supplier_name,
                        type='supplier',
                        contact='',
                        phone='',
                        address=''
                    )
                    db.session.add(new_supplier)
                    db.session.flush()
                    product.supplier_id = new_supplier.id
            else:
                product.supplier_id = None
            
            # 更新价格
            product.cost = float(request.form.get('cost', product.cost))
            product.price = float(request.form.get('price', product.price))
            
            # 更新库存设置
            product.min_stock = int(request.form.get('min_stock', 10))
            product.max_stock = int(request.form.get('max_stock', 1000))
            
            # 更新标签
            tag_ids = request.form.getlist('tags')
            product.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
            
            db.session.commit()
            flash('商品信息更新成功！', 'success')
            return redirect(url_for('inventory.view', product_id=product.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')
    
    # GET 请求 - 获取表单数据（只查询必要字段提升性能）
    categories = db.session.query(Category.id, Category.name).order_by(Category.name).all()
    suppliers = db.session.query(Partner.id, Partner.name).filter_by(
        type='supplier', is_deleted=False
    ).order_by(Partner.name).all()
    all_tags = db.session.query(Tag.id, Tag.name, Tag.color).order_by(Tag.name).all()
    
    # 获取商品已选标签的ID集合，用于模板判断
    product_tag_ids = {t.id for t in product.tags}
    
    return render_template(
        'inventory/edit.html',
        product=product,
        categories=categories,
        suppliers=suppliers,
        all_tags=all_tags,
        product_tag_ids=product_tag_ids
    )