"""数据导入服务 - Excel/CSV导入"""
import os
import csv
import uuid
from datetime import datetime
from io import BytesIO, StringIO
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.biz import Product, Category
from app.models.biz import Partner
from app.models.stock import Stock, Warehouse, InventoryLog


class ImportService:
    """数据导入服务"""
    
    # 支持的文件类型
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    
    # 导入模板定义
    TEMPLATES = {
        'product': {
            'name': '商品导入',
            'required_fields': ['name', 'sku', 'unit', 'category'],
            'optional_fields': ['spec', 'cost', 'price', 'min_stock', 'description'],
            'sample_data': [
                {'name': '示例商品', 'sku': 'SKU001', 'unit': '个', 'category': '默认分类', 'cost': '10.00', 'price': '15.00'}
            ]
        },
        'partner': {
            'name': '往来单位导入',
            'required_fields': ['name', 'type'],
            'optional_fields': ['contact', 'phone', 'address', 'credit_limit'],
            'sample_data': [
                {'name': '示例客户', 'type': 'customer', 'contact': '张三', 'phone': '13800138000'}
            ]
        },
        'stock': {
            'name': '库存导入',
            'required_fields': ['sku', 'warehouse', 'quantity'],
            'optional_fields': [],
            'sample_data': [
                {'sku': 'SKU001', 'warehouse': '主仓库', 'quantity': '100'}
            ]
        }
    }
    
    @staticmethod
    def allowed_file(filename):
        """检查文件类型"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ImportService.ALLOWED_EXTENSIONS
    
    @staticmethod
    def parse_csv(file_content, encoding='utf-8'):
        """解析CSV文件"""
        try:
            content = file_content.decode(encoding)
            reader = csv.DictReader(StringIO(content))
            return list(reader), list(reader.fieldnames) if reader.fieldnames else []
        except UnicodeDecodeError:
            # 尝试GBK编码
            content = file_content.decode('gbk')
            reader = csv.DictReader(StringIO(content))
            return list(reader), list(reader.fieldnames) if reader.fieldnames else []
    
    @staticmethod
    def parse_excel(file_content):
        """解析Excel文件"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
            ws = wb.active
            
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return [], []
            
            headers = [str(h).strip() if h else '' for h in rows[0]]
            data = []
            
            for row in rows[1:]:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers) and headers[i]:
                        row_dict[headers[i]] = str(value).strip() if value else ''
                if any(row_dict.values()):  # 跳过空行
                    data.append(row_dict)
            
            return data, headers
        except ImportError:
            raise Exception("请安装openpyxl: pip install openpyxl")
    
    @staticmethod
    def validate_data(data, template_type):
        """
        验证数据
        返回: (valid_rows, errors)
        """
        template = ImportService.TEMPLATES.get(template_type)
        if not template:
            return [], [{'row': 0, 'error': f'未知的导入类型: {template_type}'}]
        
        required = template['required_fields']
        valid_rows = []
        errors = []
        
        for i, row in enumerate(data, start=2):  # Excel行号从2开始（跳过表头）
            row_errors = []
            
            # 检查必填字段
            for field in required:
                if not row.get(field) or not str(row.get(field)).strip():
                    row_errors.append(f'缺少必填字段: {field}')
            
            if row_errors:
                errors.append({'row': i, 'error': '; '.join(row_errors), 'data': row})
            else:
                valid_rows.append({'row': i, 'data': row})
        
        return valid_rows, errors
    
    @staticmethod
    def import_products(data, user, update_existing=False):
        """
        导入商品
        
        Args:
            data: 验证后的数据列表
            user: 操作用户
            update_existing: 是否更新已存在的商品
        
        Returns:
            (success_count, skip_count, errors)
        """
        success_count = 0
        skip_count = 0
        errors = []
        
        # 缓存分类
        categories = {c.name: c for c in Category.query.all()}
        
        for item in data:
            row = item['row']
            d = item['data']
            
            try:
                # 检查SKU是否存在
                existing = Product.query.filter_by(sku=d['sku'], is_deleted=False).first()
                
                if existing:
                    if update_existing:
                        existing.name = d['name']
                        existing.unit = d['unit']
                        existing.spec = d.get('spec', '')
                        existing.cost = float(d.get('cost', 0)) if d.get('cost') else None
                        existing.price = float(d.get('price', 0)) if d.get('price') else None
                        existing.min_stock = int(d.get('min_stock', 0)) if d.get('min_stock') else 0
                        existing.description = d.get('description', '')
                        success_count += 1
                    else:
                        skip_count += 1
                    continue
                
                # 获取或创建分类
                category_name = d.get('category', '默认分类')
                category = categories.get(category_name)
                if not category:
                    category = Category(
                        name=category_name,
                        created_by=user.id
                    )
                    db.session.add(category)
                    db.session.flush()
                    categories[category_name] = category
                
                product = Product(
                    name=d['name'],
                    sku=d['sku'],
                    unit=d['unit'],
                    spec=d.get('spec', ''),
                    category_id=category.id,
                    cost=float(d.get('cost', 0)) if d.get('cost') else None,
                    price=float(d.get('price', 0)) if d.get('price') else None,
                    min_stock=int(d.get('min_stock', 0)) if d.get('min_stock') else 0,
                    description=d.get('description', ''),
                    created_by=user.id
                )
                db.session.add(product)
                success_count += 1
                
            except Exception as e:
                errors.append({'row': row, 'error': str(e), 'data': d})
        
        db.session.commit()
        return success_count, skip_count, errors
    
    @staticmethod
    def import_partners(data, user, update_existing=False):
        """导入往来单位"""
        success_count = 0
        skip_count = 0
        errors = []
        
        for item in data:
            row = item['row']
            d = item['data']
            
            try:
                partner_type = d['type'].lower()
                if partner_type not in ['customer', 'supplier', 'both']:
                    errors.append({'row': row, 'error': f"无效的类型: {d['type']}", 'data': d})
                    continue
                
                # 检查是否存在（按名称）
                existing = Partner.query.filter_by(name=d['name'], is_deleted=False).first()
                
                if existing:
                    if update_existing:
                        existing.type = partner_type
                        existing.contact = d.get('contact', '')
                        existing.phone = d.get('phone', '')
                        existing.address = d.get('address', '')
                        success_count += 1
                    else:
                        skip_count += 1
                    continue
                
                partner = Partner(
                    name=d['name'],
                    type=partner_type,
                    contact=d.get('contact', ''),
                    phone=d.get('phone', ''),
                    address=d.get('address', ''),
                    created_by=user.id
                )
                db.session.add(partner)
                success_count += 1
                
            except Exception as e:
                errors.append({'row': row, 'error': str(e), 'data': d})
        
        db.session.commit()
        return success_count, skip_count, errors
    
    @staticmethod
    def import_stock(data, user):
        """导入库存初始化"""
        success_count = 0
        skip_count = 0
        errors = []
        
        # 缓存
        products = {p.sku: p for p in Product.query.filter_by(is_deleted=False).all()}
        warehouses = {w.name: w for w in Warehouse.query.filter_by(is_deleted=False).all()}
        
        for item in data:
            row = item['row']
            d = item['data']
            
            try:
                product = products.get(d['sku'])
                if not product:
                    errors.append({'row': row, 'error': f"商品不存在: {d['sku']}", 'data': d})
                    continue
                
                warehouse = warehouses.get(d['warehouse'])
                if not warehouse:
                    errors.append({'row': row, 'error': f"仓库不存在: {d['warehouse']}", 'data': d})
                    continue
                
                quantity = int(d['quantity'])
                
                # 检查是否已有库存
                stock = Stock.query.filter_by(
                    product_id=product.id,
                    warehouse_id=warehouse.id
                ).first()
                
                if stock:
                    old_qty = stock.quantity
                    stock.quantity = quantity
                else:
                    old_qty = 0
                    stock = Stock(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        quantity=quantity
                    )
                    db.session.add(stock)
                
                # 库存日志
                log = InventoryLog(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    type='import',
                    quantity=quantity,
                    before_qty=old_qty,
                    after_qty=quantity,
                    reference_type='import',
                    remark='数据导入',
                    operator_id=user.id
                )
                db.session.add(log)
                success_count += 1
                
            except ValueError:
                errors.append({'row': row, 'error': '数量必须是整数', 'data': d})
            except Exception as e:
                errors.append({'row': row, 'error': str(e), 'data': d})
        
        db.session.commit()
        return success_count, skip_count, errors
    
    @staticmethod
    def generate_template_csv(template_type):
        """生成CSV模板"""
        template = ImportService.TEMPLATES.get(template_type)
        if not template:
            return None
        
        all_fields = template['required_fields'] + template['optional_fields']
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=all_fields)
        writer.writeheader()
        
        for sample in template['sample_data']:
            writer.writerow(sample)
        
        return output.getvalue()
    
    @staticmethod
    def process_import(file, template_type, user, update_existing=False):
        """
        处理导入文件
        
        Returns:
            {
                'success': True/False,
                'message': str,
                'success_count': int,
                'skip_count': int,
                'error_count': int,
                'errors': list
            }
        """
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if ext not in ImportService.ALLOWED_EXTENSIONS:
            return {
                'success': False,
                'message': f'不支持的文件类型: {ext}'
            }
        
        try:
            content = file.read()
            
            # 解析文件
            if ext == 'csv':
                data, headers = ImportService.parse_csv(content)
            else:
                data, headers = ImportService.parse_excel(content)
            
            if not data:
                return {
                    'success': False,
                    'message': '文件为空或格式错误'
                }
            
            # 验证数据
            valid_rows, validation_errors = ImportService.validate_data(data, template_type)
            
            if not valid_rows and validation_errors:
                return {
                    'success': False,
                    'message': '数据验证失败',
                    'error_count': len(validation_errors),
                    'errors': validation_errors[:20]  # 只返回前20条错误
                }
            
            # 执行导入
            if template_type == 'product':
                success, skip, errors = ImportService.import_products(valid_rows, user, update_existing)
            elif template_type == 'partner':
                success, skip, errors = ImportService.import_partners(valid_rows, user, update_existing)
            elif template_type == 'stock':
                success, skip, errors = ImportService.import_stock(valid_rows, user)
            else:
                return {'success': False, 'message': f'未知的导入类型: {template_type}'}
            
            all_errors = validation_errors + errors
            
            return {
                'success': True,
                'message': f'导入完成，成功: {success}，跳过: {skip}，失败: {len(errors)}',
                'success_count': success,
                'skip_count': skip,
                'error_count': len(all_errors),
                'errors': all_errors[:20]
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'导入失败: {str(e)}'
            }
