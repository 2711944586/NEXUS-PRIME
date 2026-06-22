import os
import random
import sqlite3
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import click
from flask import current_app
from sqlalchemy import text
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.auth import Department, Permission, Role, User
from app.models.biz import Category, Partner, Product, Tag, product_tags
from app.models.content import Article, ArticleComment, Attachment
from app.models.finance import CustomerCredit, PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion, StockAlert
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchasePriceHistory, SupplierPerformance
from app.models.stock import InventoryLog, Stock, Warehouse
from app.models.stocktake import StockTake, StockTakeHistory, StockTakeItem
from app.models.sys import AiChatMessage, AiChatSession, AuditLog
from app.models.trade import Order, OrderItem
from app.platform.events import event_dispatcher
from app.utils.time import utcnow


def pick(rng, values):
    return values[rng.randrange(len(values))]


DEFAULT_DEMO_ADMIN_PASSWORD = 'admin123'
DEFAULT_DEMO_USER_PASSWORD = 'password123'


def demo_passwords(admin_password=None, user_password=None, multiplier=1):
    admin = admin_password or os.environ.get('NEXUS_DEMO_ADMIN_PASSWORD') or DEFAULT_DEMO_ADMIN_PASSWORD
    user = user_password or os.environ.get('NEXUS_DEMO_USER_PASSWORD') or DEFAULT_DEMO_USER_PASSWORD
    if current_app.config.get('ENV') == 'production' or os.environ.get('FLASK_CONFIG') == 'production':
        uses_default = admin == DEFAULT_DEMO_ADMIN_PASSWORD or user == DEFAULT_DEMO_USER_PASSWORD
        if uses_default and int(multiplier or 1) >= 50:
            raise click.ClickException(
                '生产环境生成远程演示数据必须设置 NEXUS_DEMO_ADMIN_PASSWORD 和 NEXUS_DEMO_USER_PASSWORD，'
                '或传入 --admin-password/--user-password。'
            )
    return admin, user


def echo_demo_accounts(admin_password, user_password):
    admin_label = admin_password if admin_password == DEFAULT_DEMO_ADMIN_PASSWORD else '<已自定义>'
    user_label = user_password if user_password == DEFAULT_DEMO_USER_PASSWORD else '<已自定义>'
    click.echo(f'管理员账号: admin@nexus.com / {admin_label}')
    click.echo(f'普通账号: user00001@nexus.com / {user_label}')


def configured_library_folder():
    folder = current_app.config.get('UPLOAD_LIBRARY_FOLDER')
    if folder:
        return folder
    upload_root = current_app.config.get('UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'storage', 'uploads')
    return os.path.join(upload_root, 'library')


def write_seed_pdf(path, title, lines):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    def safe_pdf_text(value):
        return str(value).encode('latin-1', errors='replace').decode('latin-1')

    pdf = canvas.Canvas(path, pagesize=A4)
    pdf.setTitle(safe_pdf_text(title))
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(42, 800, safe_pdf_text(title)[:54])
    pdf.setFont('Helvetica', 10)
    y = 770
    for line in lines:
        pdf.drawString(42, y, safe_pdf_text(line)[:92])
        y -= 20
        if y < 52:
            pdf.showPage()
            pdf.setFont('Helvetica', 10)
            y = 800
    pdf.save()


def write_seed_xlsx(path, title, rows):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    sheet.append(['指标', '当前值', '负责人', '处理建议'])
    for row in rows:
        sheet.append(row)
    for column in ('A', 'B', 'C', 'D'):
        sheet.column_dimensions[column].width = 22
    workbook.save(path)


def write_seed_docx(path, title, paragraphs):
    document_lines = ''.join(
        f'<w:p><w:r><w:t>{xml_escape(line)}</w:t></w:r></w:p>'
        for line in [title, *paragraphs]
    )
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ))
        archive.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        ))
        archive.writestr('word/document.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{document_lines}</w:body>'
            '</w:document>'
        ))


def write_seed_text(path, title, rows, mimetype):
    if mimetype == 'text/csv':
        content = '项目,状态,负责人,下一步\n' + '\n'.join(','.join(row) for row in rows)
    else:
        content = title + '\n\n' + '\n'.join(' - '.join(row) for row in rows)
    with open(path, 'w', encoding='utf-8-sig', newline='') as handle:
        handle.write(content)


def ensure_seed_library_files(file_templates, seed_label):
    library_dir = configured_library_folder()
    os.makedirs(library_dir, exist_ok=True)
    sizes = {}
    rows = [
        ['库存水位', '低库存对象已生成补货建议', '仓储主管', '复核库位并提交采购草稿'],
        ['采购到货', '审批与收货节点已串联', '采购经理', '同步供应商交期和质检窗口'],
        ['应收回款', '逾期客户进入跟进队列', '财务会计', '联动信用额度与催款记录'],
        ['审计归档', '文件、报表、评论已关联', '数据运营', '每日收班前完成资料库归档'],
    ]
    for filename, mimetype, filepath in file_templates:
        relative = str(filepath).replace('\\', '/').lstrip('/')
        if not relative.startswith('library/'):
            continue
        stored_name = relative.split('/', 1)[1]
        target = os.path.join(library_dir, stored_name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target):
            title = f'NEXUS {seed_label} {filename}'
            try:
                if mimetype == 'application/pdf':
                    write_seed_pdf(target, title, [f'{item[0]}: {item[1]}，负责人 {item[2]}，下一步 {item[3]}' for item in rows])
                elif mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    write_seed_xlsx(target, '资料库', rows)
                elif mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    write_seed_docx(target, title, [f'{item[0]}：{item[1]}；{item[3]}。' for item in rows])
                else:
                    write_seed_text(target, title, rows, mimetype)
            except Exception:
                write_seed_text(target, title, rows, 'text/plain')
        sizes[filepath] = os.path.getsize(target)
    return sizes


SEED_PERMISSIONS = [
    ('inventory.adjust', '库存调整'),
    ('purchase.write', '采购创建'),
    ('purchase.approve', '采购审批'),
    ('purchase.receive', '采购收货'),
    ('finance.payment', '收款处理'),
    ('finance.credit.write', '信用管理'),
    ('reports.generate', '报表生成'),
    ('files.manage', '文件管理'),
    ('content.write', '内容管理'),
    ('stocktake.write', '盘点管理'),
    ('masterdata.write', '主数据维护'),
    ('sales.write', '销售履约'),
    ('admin', '系统管理'),
]


MANUFACTURING_CATEGORIES = ['原材料', '半成品', '成品组件', 'MRO 备件', '包装与周转', '质量检测', '工装夹具', '安全防护']
MANUFACTURING_TAGS = [('关键物料', 'red'), ('低库存', 'orange'), ('战略供应', 'green'), ('长交期', 'blue'), ('高价值', 'purple')]
MANUFACTURING_CUSTOMERS = [
    '长三角装配中心', '华东新能源总装厂', '苏南精密制造', '甬江自动化产线', '珠三角机器人事业部',
    '川渝机电集成', '武汉智能装备基地', '合肥驱动控制工厂', '厦门工控集成', '青岛海工装备',
    '郑州轨交装备基地', '天津动力总成工厂', '常熟柔性装配中心', '佛山电驱事业部', '重庆机器人集成',
    '南昌工控整机厂', '湖州精密传动基地', '太仓工业自动化', '长沙工程机械电控', '南通新能源装备'
]
MANUFACTURING_SUPPLIERS = [
    '昆山伺服部件', '宁波铝合金压铸', '苏州精密轴承', '无锡工业线束', '嘉兴包装周转', '东莞传感器科技',
    '常州 MRO 备件', '深圳控制模组', '湖州高强紧固件', '台州气动元件', '厦门工业连接器', '天津散热模组',
    '青岛海工密封件', '合肥钣金工艺', '南通工业胶黏', '广州检测治具'
]
MANUFACTURING_PRODUCTS = [
    '伺服电机组件', '铝合金外壳', '精密导轨滑块', '工业控制板', '编码器线束', '变频器模块', '气动执行器', '机器人关节包',
    'MRO 备件包', '耐高温密封圈', '高强度紧固件', '电柜散热风扇', '包装周转箱', '防静电托盘', '质量检测治具', '装配工装夹具',
    '扭矩传感器', '工业相机模组', '减速机齿轮组', '安全继电器', '铜排连接件', '冷却水泵组件', 'AGV 充电触点', '线性模组滑台',
    '工控屏面板', '视觉光源控制器', '液压快速接头', '机器人拖链线缆', '精密定位销', '真空吸盘组件', '电机刹车片', '工装定位底板',
]
MANUFACTURING_WAREHOUSES = [
    ('华东工厂仓', '上海市嘉定区智能制造园', 62000),
    ('长三角区域仓', '苏州市昆山开发区', 36000),
    ('华南区域仓', '深圳市龙岗区坪地物流园', 42000),
    ('西南备件仓', '成都市龙泉驿区装备产业港', 28000),
]


@click.command('status')
@with_appcontext
def status():
    counts = {
        '用户': User.query.count(),
        '商品': Product.query.count(),
        '销售订单': Order.query.count(),
        '仓库': Warehouse.query.count(),
        '库存流水': InventoryLog.query.count(),
        '采购单': PurchaseOrder.query.count(),
        '应收账款': Receivable.query.count(),
        '收款记录': PaymentRecord.query.count(),
        '盘点单': StockTake.query.count(),
        '通知': Notification.query.count(),
        '报表': GeneratedReport.query.count(),
        '文章': Article.query.count(),
        '评论': ArticleComment.query.count(),
        '文件': Attachment.query.count(),
        '审计日志': AuditLog.query.count(),
    }
    click.echo('NEXUS 数据库状态')
    for label, value in counts.items():
        click.echo(f' - {label}: {value}')
    click.echo('演示账号: admin@nexus.com 与 user00001@nexus.com；生产种子请使用自定义密码。')
    if counts['用户'] == 0:
        click.echo('数据库为空，请运行: flask seed-enterprise --scale 3 --multiplier 100 --reset --seed 20241334')


@click.command('seed-enterprise')
@click.option('--scale', default=3, show_default=True, help='企业数据规模倍数')
@click.option('--multiplier', default=100, show_default=True, help='在 scale 基础上继续放大的倍数；1 适合开发，100 适合提交数据库')
@click.option('--reset', is_flag=True, help='清空并重建数据库')
@click.option('--seed', default=20241334, show_default=True, help='固定随机种子')
@click.option('--admin-password', default=None, help='演示管理员密码；生产远程种子必须显式设置或使用 NEXUS_DEMO_ADMIN_PASSWORD')
@click.option('--user-password', default=None, help='演示普通用户密码；生产远程种子必须显式设置或使用 NEXUS_DEMO_USER_PASSWORD')
@with_appcontext
def seed_enterprise(scale, multiplier, reset, seed, admin_password, user_password):
    passwords = demo_passwords(admin_password=admin_password, user_password=user_password, multiplier=multiplier)
    run_enterprise_data_seed(scale=scale, multiplier=multiplier, reset=reset, seed=seed, passwords=passwords)


@click.command('audit-enterprise-data')
@click.option('--strict', is_flag=True, help='数据不足时返回失败')
@with_appcontext
def audit_enterprise_data(strict):
    """Audit whether every visible product module is backed by database records."""
    checks = [
        ('运营首页', Product.query.count() and Order.query.count() and PurchaseOrder.query.count() and Receivable.query.count()),
        ('物料与成品', Product.query.count()),
        ('仓配流向', Stock.query.count() and InventoryLog.query.count() and Warehouse.query.count()),
        ('补货采购', ReplenishmentSuggestion.query.count() and PurchaseOrder.query.count()),
        ('销售履约', Order.query.count() and OrderItem.query.count()),
        ('库存盘点', StockTake.query.count() and StockTakeItem.query.count()),
        ('应收风控', Receivable.query.count() and PaymentRecord.query.count()),
        ('信用管理', CustomerCredit.query.count()),
        ('报表工作室', GeneratedReport.query.count()),
        ('文件资料库', Attachment.query.count()),
        ('公告知识库', Article.query.count() and ArticleComment.query.count()),
        ('通知中心', Notification.query.count()),
        ('经营分析台', AiChatSession.query.count() and AiChatMessage.query.count()),
        ('系统安全', User.query.count() and Role.query.count() and Permission.query.count() and AuditLog.query.count()),
        ('供应商绩效', SupplierPerformance.query.count()),
    ]
    failed = []
    click.echo('NEXUS 企业功能数据覆盖')
    for label, value in checks:
        count = int(value or 0)
        mark = 'OK' if count > 0 else 'MISSING'
        click.echo(f' - {label}: {mark} ({count})')
        if count <= 0:
            failed.append(label)

    chain_checks = {
        '低库存到补货': ReplenishmentSuggestion.query.join(Product).filter(Product.is_deleted == False).count(),
        '采购审批到收货': PurchaseOrder.query.filter(PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_PARTIAL,
            PurchaseOrder.STATUS_RECEIVED,
        ])).count(),
        '销售到应收': Receivable.query.join(Order, Receivable.order_id == Order.id).count(),
        '收款到应收': PaymentRecord.query.join(Receivable, PaymentRecord.receivable_id == Receivable.id).count(),
        '公告到讨论': ArticleComment.query.count(),
        '报表到归档': GeneratedReport.query.count() and Attachment.query.count(),
    }
    click.echo('NEXUS 业务闭环数据')
    for label, count in chain_checks.items():
        mark = 'OK' if int(count or 0) > 0 else 'MISSING'
        click.echo(f' - {label}: {mark} ({int(count or 0)})')
        if int(count or 0) <= 0:
            failed.append(label)

    if strict and failed:
        raise click.ClickException('数据覆盖不足：' + '、'.join(failed))


@click.command('events-dispatch')
@click.option('--limit', default=100, show_default=True, help='本次最多消费的 pending domain events 数量')
@with_appcontext
def events_dispatch(limit):
    """Dispatch pending domain events from the database outbox."""
    summary = event_dispatcher.dispatch_pending(limit=max(int(limit or 1), 1))
    click.echo(
        'domain events dispatched: '
        f"processed={summary['processed']} "
        f"published={summary['published']} "
        f"failed={summary['failed']}"
    )


@click.command('events-retry-failed')
@click.option('--limit', default=100, show_default=True, help='本次最多重新入队的 failed domain events 数量')
@click.option('--event-type', default=None, help='仅重新入队指定事件类型')
@with_appcontext
def events_retry_failed(limit, event_type):
    """Move failed domain events back to pending for a later dispatch."""
    summary = event_dispatcher.retry_failed(limit=max(int(limit or 1), 1), event_type=event_type)
    click.echo(
        'domain events retried: '
        f"retried={summary['retried']}"
    )


@click.command('events-worker')
@click.option('--loglevel', default='info', show_default=True, help='Celery worker 日志级别')
@click.option('--queues', default='events,reports,ai,celery', show_default=True, help='Celery worker 消费队列')
def events_worker(loglevel, queues):
    """Start a Celery worker for domain event and background jobs."""
    from app.platform.jobs.worker import main

    return main(['worker', f'--loglevel={loglevel}', '-Q', queues])


@click.command('openapi-export')
@click.option('--output', default=None, help='OpenAPI JSON 输出路径；默认写入 backend/openapi.json')
@with_appcontext
def openapi_export(output):
    """Export the runtime OpenAPI contract."""
    from app.platform.openapi import write_openapi_schema

    target = Path(output) if output else Path(current_app.root_path).parent / 'openapi.json'
    target = write_openapi_schema(current_app, target)
    click.echo(f'OpenAPI schema exported to {target}')


@click.command('forge')
@click.option('--scale', default=3, show_default=True, help='兼容旧命令，等同于 seed-enterprise --multiplier 1')
@with_appcontext
def forge(scale):
    run_enterprise_data_seed(scale=scale, multiplier=1, reset=True, seed=20241334, passwords=demo_passwords(multiplier=1))


def run_enterprise_data_seed(scale=3, multiplier=1, reset=False, seed=20241334, passwords=None):
    rng = random.Random(int(seed or 20241334))
    scale = max(int(scale or 1), 1)
    multiplier = max(int(multiplier or 1), 1)
    if multiplier >= 50:
        return run_enterprise_seed(scale=scale, multiplier=multiplier, reset=reset, seed=seed, passwords=passwords)

    admin_password, user_password = passwords or demo_passwords(multiplier=multiplier)
    effective_scale = scale * multiplier
    click.echo(f'初始化 NEXUS 企业经营数据: scale={scale}, multiplier={multiplier}, seed={seed}')

    if reset:
        db.session.remove()
        db.drop_all()
        db.create_all()

    permission_rows = {}
    for name, description in SEED_PERMISSIONS:
        perm = Permission(name=name, description=description)
        db.session.add(perm)
        permission_rows[name] = perm

    roles = {}
    for name, is_admin in [('Admin', True), ('Manager', False), ('User', False)]:
        role = Role(name=name, is_admin=is_admin)
        db.session.add(role)
        roles[name] = role
    db.session.flush()
    roles['Admin'].permissions = list(permission_rows.values())
    roles['Manager'].permissions = [
        permission_rows[name] for name in [
            'inventory.adjust', 'purchase.write', 'purchase.approve', 'purchase.receive',
            'finance.payment', 'finance.credit.write', 'reports.generate', 'files.manage',
            'content.write', 'stocktake.write', 'masterdata.write', 'sales.write'
        ]
    ]
    roles['User'].permissions = [
        permission_rows[name] for name in ['purchase.write', 'sales.write', 'files.manage', 'reports.generate']
    ]
    departments = []
    for index, name in enumerate(['总经办', '销售部', '采购部', '仓储部', '财务部', '客服部', '数据运营部']):
        dept = Department(name=name, code=f'D{index + 1:02d}')
        db.session.add(dept)
        departments.append(dept)
    db.session.flush()

    admin = User(
        username='admin',
        email='admin@nexus.com',
        full_name='庄颂',
        avatar='/api/v1/avatars/initials/admin-庄颂',
        role=roles['Admin'],
        department=departments[0],
        position='系统管理员',
        is_admin=True,
        preferences={
            'density': 'compact',
            'default_workspace': '运营',
            'recent': [{'label': '运营首页', 'path': '/app/overview', 'at': utcnow().isoformat()}],
            'theme': 'dark-cockpit',
        },
    )
    admin.password = admin_password
    db.session.add(admin)

    employees = []
    surnames = ['赵', '钱', '孙', '李', '周', '吴', '郑', '王', '陈', '林', '黄', '何']
    given_names = ['明轩', '思远', '雨桐', '嘉宁', '子涵', '亦辰', '若曦', '景行', '沐阳', '书瑶', '清扬', '安然']
    positions = ['运营专员', '销售经理', '采购专员', '仓储主管', '财务会计', '客服主管']
    for i in range(12 * effective_scale):
        user = User(
            username=f'user{i + 1:03d}',
            email=f'user{i + 1:03d}@nexus.com',
            full_name=f'{pick(rng, surnames)}{pick(rng, given_names)}',
            role=pick(rng, [roles['Manager'], roles['User']]),
            department=pick(rng, departments[1:]),
            position=pick(rng, positions),
        )
        user.password = user_password
        db.session.add(user)
        employees.append(user)
    db.session.flush()

    categories = []
    for name in MANUFACTURING_CATEGORIES:
        category = Category(name=name, icon='box')
        db.session.add(category)
        categories.append(category)

    tags = []
    for name, color in MANUFACTURING_TAGS:
        tag = Tag(name=name, color=color)
        db.session.add(tag)
        tags.append(tag)
    db.session.flush()

    cities = ['上海', '杭州', '苏州', '南京', '宁波', '合肥', '深圳', '广州', '成都', '武汉']
    customer_names = MANUFACTURING_CUSTOMERS
    supplier_names = MANUFACTURING_SUPPLIERS
    customers = []
    suppliers = []
    for i in range(10 * effective_scale):
        customer = Partner(
            name=f'{customer_names[i % len(customer_names)]}{i // len(customer_names) + 1 if i >= len(customer_names) else ""}',
            type='customer',
            contact_person=f'{pick(rng, surnames)}{pick(rng, given_names)}',
            phone=f'13{rng.randrange(100000000, 999999999)}',
            email=f'customer{i + 1:03d}@example.com',
            address=f'{pick(rng, cities)}市先进制造园 {rng.randrange(10, 399)} 号',
            credit_score=rng.randrange(68, 99),
        )
        db.session.add(customer)
        customers.append(customer)
    for i in range(8 * effective_scale):
        supplier = Partner(
            name=f'{supplier_names[i % len(supplier_names)]}{i // len(supplier_names) + 1 if i >= len(supplier_names) else ""}',
            type='supplier',
            contact_person=f'{pick(rng, surnames)}{pick(rng, given_names)}',
            phone=f'18{rng.randrange(100000000, 999999999)}',
            email=f'supplier{i + 1:03d}@example.com',
            address=f'{pick(rng, cities)}市工业配套园 {rng.randrange(1, 88)} 栋',
            credit_score=rng.randrange(72, 100),
        )
        db.session.add(supplier)
        suppliers.append(supplier)
    db.session.flush()

    product_bases = MANUFACTURING_PRODUCTS
    products = []
    for i in range(36 * effective_scale):
        cost = rng.randrange(18, 1800)
        product = Product(
            sku=f'MFG-{seed}-{i + 1:04d}',
            name=f'{product_bases[i % len(product_bases)]} {chr(65 + (i % 6))}型',
            price=round(cost * rng.uniform(1.18, 1.85), 2),
            cost=round(cost, 2),
            description='适用于制造业仓配、装配线领料和区域仓补货，支持批次追踪与质量复核。',
            min_stock=rng.randrange(20, 120),
            max_stock=rng.randrange(450, 1600),
            category=pick(rng, categories),
            supplier=pick(rng, suppliers),
            specs={'单位': pick(rng, ['件', '箱', '套', '托']), '批次': f'LOT-{seed}-{i + 1:04d}', '质检': pick(rng, ['全检', '抽检', '免检'])},
        )
        product.tags = rng.sample(tags, k=rng.randrange(0, min(3, len(tags)) + 1))
        db.session.add(product)
        products.append(product)
    db.session.flush()

    warehouses = []
    for name, location, capacity in MANUFACTURING_WAREHOUSES:
        warehouse = Warehouse(name=name, location=location, capacity=capacity)
        db.session.add(warehouse)
        warehouses.append(warehouse)
    db.session.flush()

    for product in products:
        selected_warehouses = rng.sample(warehouses, k=rng.randrange(1, min(3, len(warehouses)) + 1))
        for warehouse in selected_warehouses:
            if 'MRO' in product.name:
                quantity = max(0, int(product.min_stock / (len(selected_warehouses) * 3)))
            else:
                quantity = rng.randrange(0, max(product.max_stock // 2, product.min_stock + 1))
            stock = Stock(
                product=product,
                warehouse=warehouse,
                quantity=quantity,
                shelf_location=f'{warehouse.name} {chr(65 + rng.randrange(0, 6))}区-{rng.randrange(1, 18):02d}-{rng.randrange(1, 8):02d}',
            )
            db.session.add(stock)
            db.session.add(InventoryLog(
                transaction_code=f'INIT-{product.id}-{warehouse.id}',
                move_type=InventoryLog.TYPE_IN,
                product=product,
                warehouse=warehouse,
                qty_change=quantity,
                balance_after=quantity,
                operator=admin,
                remark='制造仓配期初入库',
            ))
    db.session.flush()

    orders = []
    for i in range(60 * effective_scale):
        created_at = utcnow() - timedelta(days=rng.randrange(0, 90), hours=rng.randrange(0, 24))
        order = Order(
            order_no=f'SO-{created_at.strftime("%Y%m%d")}-{i + 1:04d}',
            customer=pick(rng, customers),
            seller=pick(rng, [admin, *employees]),
            status=pick(rng, [Order.STATUS_PENDING, Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE, Order.STATUS_DONE]),
            created_at=created_at,
        )
        db.session.add(order)
        total = 0
        for product in rng.sample(products, k=rng.randrange(1, 5)):
            qty = rng.randrange(1, 16)
            db.session.add(OrderItem(order=order, product=product, quantity=qty, price_snapshot=product.price))
            total += qty * product.price
        order.total_amount = round(total, 2)
        orders.append(order)
    db.session.flush()

    for order in orders:
        if order.status not in [Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE]:
            continue
        due_date = order.created_at.date() + timedelta(days=pick(rng, [15, 30, 45, 60]))
        paid_rate = pick(rng, [0, 0.35, 0.7, 1.0]) if order.status != Order.STATUS_DONE else pick(rng, [0.7, 1.0])
        receivable = Receivable(
            receivable_no=f'AR-{order.created_at.strftime("%Y%m%d")}-{order.id:04d}',
            order=order,
            customer=order.customer,
            total_amount=order.total_amount,
            paid_amount=round(order.total_amount * paid_rate, 2),
            due_date=due_date,
            status=Receivable.STATUS_PAID if paid_rate >= 1 else Receivable.STATUS_PARTIAL if paid_rate > 0 else Receivable.STATUS_PENDING,
            remark='由销售订单自动生成',
        )
        if due_date < utcnow().date() and receivable.status != Receivable.STATUS_PAID:
            receivable.status = Receivable.STATUS_OVERDUE
        db.session.add(receivable)
        db.session.flush()
        if paid_rate > 0:
            db.session.add(PaymentRecord(
                payment_no=f'PAY-{order.created_at.strftime("%Y%m%d")}-{order.id:04d}',
                receivable=receivable,
                customer=order.customer,
                amount=receivable.paid_amount,
                payment_method=pick(rng, ['bank', 'wechat', 'alipay', 'check']),
                payment_date=min(utcnow().date(), due_date),
                operator=admin,
                reference_no=f'BANK{seed}{order.id:06d}',
                remark='装配中心回款记录',
            ))

    for customer in customers:
        used = sum(item.unpaid_amount for item in Receivable.query.filter_by(customer_id=customer.id).all())
        db.session.add(CustomerCredit(
            customer=customer,
            credit_limit=float(rng.randrange(80000, 300000)),
            used_credit=round(float(used), 2),
            warning_threshold=80.0,
            is_frozen=customer.credit_score < 72,
            frozen_reason='信用评分低于阈值' if customer.credit_score < 72 else None,
            frozen_by=admin.id if customer.credit_score < 72 else None,
        ))

    purchase_orders = []
    for i in range(24 * effective_scale):
        created_at = utcnow() - timedelta(days=rng.randrange(0, 75))
        status_value = pick(rng, [
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_PARTIAL,
            PurchaseOrder.STATUS_RECEIVED,
        ])
        po = PurchaseOrder(
            po_no=f'PO-{created_at.strftime("%Y%m%d")}-{i + 1:04d}',
            supplier=pick(rng, suppliers),
            warehouse=pick(rng, warehouses),
            status=status_value,
            submitted_at=created_at + timedelta(hours=2) if status_value != PurchaseOrder.STATUS_DRAFT else None,
            submitted_by=admin.id if status_value != PurchaseOrder.STATUS_DRAFT else None,
            approved_at=created_at + timedelta(days=1) if status_value in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL, PurchaseOrder.STATUS_RECEIVED] else None,
            approved_by=admin.id if status_value in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL, PurchaseOrder.STATUS_RECEIVED] else None,
            expected_date=(created_at + timedelta(days=rng.randrange(3, 18))).date(),
            actual_receive_date=created_at + timedelta(days=rng.randrange(4, 20)) if status_value == PurchaseOrder.STATUS_RECEIVED else None,
            remark='产线补货采购',
            created_at=created_at,
        )
        db.session.add(po)
        total = 0
        for product in rng.sample(products, k=rng.randrange(1, 5)):
            qty = rng.randrange(20, 180)
            received = qty if status_value == PurchaseOrder.STATUS_RECEIVED else rng.randrange(0, qty) if status_value == PurchaseOrder.STATUS_PARTIAL else 0
            db.session.add(PurchaseOrderItem(order=po, product=product, quantity=qty, unit_price=product.cost, received_qty=received))
            db.session.add(PurchasePriceHistory(product=product, supplier=po.supplier, price=product.cost))
            total += qty * product.cost
        po.total_amount = round(total, 2)
        purchase_orders.append(po)
    db.session.flush()

    for supplier in suppliers:
        related = [po for po in purchase_orders if po.supplier_id == supplier.id]
        db.session.add(SupplierPerformance(
            supplier=supplier,
            total_orders=len(related),
            on_time_orders=max(0, len(related) - rng.randrange(0, 3)),
            quality_pass_orders=max(0, len(related) - rng.randrange(0, 2)),
            total_amount=round(sum(po.total_amount for po in related), 2),
            last_order_date=max([po.created_at for po in related], default=None),
        ))

    low_stock_products = []
    for product in products:
        total_stock = sum(stock.quantity for stock in product.stocks)
        if total_stock > product.min_stock:
            continue
        low_stock_products.append(product)
        warehouse = pick(rng, warehouses)
        suggested_qty = max(product.min_stock * 3 - total_stock, product.min_stock)
        db.session.add(StockAlert(
            product=product,
            warehouse=warehouse,
            alert_level=StockAlert.LEVEL_RED if total_stock == 0 else StockAlert.LEVEL_YELLOW,
            status=StockAlert.STATUS_ACTIVE,
            current_qty=total_stock,
            min_qty=product.min_stock,
            suggested_qty=suggested_qty,
        ))
        db.session.add(ReplenishmentSuggestion(
            product=product,
            warehouse=warehouse,
            supplier=product.supplier,
            current_qty=total_stock,
            suggested_qty=suggested_qty,
            avg_daily_sales=round(rng.uniform(2, 18), 1),
            lead_time_days=rng.randrange(3, 12),
            safety_stock=product.min_stock,
            status=ReplenishmentSuggestion.STATUS_PENDING,
        ))

    for i, warehouse in enumerate(warehouses[: max(2, min(len(warehouses), effective_scale + 1))]):
        take = StockTake(
            take_no=f'ST-{utcnow().strftime("%Y%m%d")}-{i + 1:04d}',
            warehouse=warehouse,
            take_type=pick(rng, [StockTake.TYPE_FULL, StockTake.TYPE_CYCLE]),
            status=pick(rng, [StockTake.STATUS_DRAFT, StockTake.STATUS_IN_PROGRESS, StockTake.STATUS_COMPLETED]),
            planned_date=(utcnow() + timedelta(days=i + 1)).date(),
            created_by=admin.id,
            remark='工厂仓月度循环盘点',
        )
        db.session.add(take)
        db.session.flush()
        stocks = Stock.query.filter_by(warehouse_id=warehouse.id).limit(8 * effective_scale).all()
        variance_items = 0
        for stock in stocks:
            variance = rng.randrange(-3, 4)
            actual_qty = stock.quantity + variance if take.status != StockTake.STATUS_DRAFT else None
            if actual_qty is not None and actual_qty != stock.quantity:
                variance_items += 1
            db.session.add(StockTakeItem(
                stock_take=take,
                product=stock.product,
                system_qty=stock.quantity,
                actual_qty=actual_qty,
                unit_cost=stock.product.cost,
                shelf_location=stock.shelf_location,
                counted_at=utcnow() if actual_qty is not None else None,
                counted_by=admin.id if actual_qty is not None else None,
            ))
        take.total_items = len(stocks)
        take.counted_items = 0 if take.status == StockTake.STATUS_DRAFT else len(stocks)
        take.variance_items = variance_items
        db.session.add(StockTakeHistory(take_id=take.id, action='create', operator_id=admin.id, details={'message': '初始化盘点单'}))

    notice_templates = [
        ('库存水位预警', '部分关键物料低于安全库存，请检查补货建议和供应商交期。', Notification.CATEGORY_STOCK, Notification.TYPE_WARNING),
        ('采购审批', '产线补货采购单已进入审批队列，请在采购补货中心处理。', Notification.CATEGORY_APPROVAL, Notification.TYPE_INFO),
        ('应收风控提醒', '部分装配中心应收账款已进入逾期区间。', Notification.CATEGORY_ORDER, Notification.TYPE_ALERT),
        ('制造仓配报表', '仓配运营日报已生成，可在报表工作室查看。', Notification.CATEGORY_REPORT, Notification.TYPE_SUCCESS),
    ]
    for i in range(18 * effective_scale):
        title, content, category, notice_type = pick(rng, notice_templates)
        db.session.add(Notification(
            user=admin if i % 3 == 0 else pick(rng, employees),
            title=title,
            content=content,
            type=notice_type,
            category=category,
            related_type=pick(rng, ['product', 'order', 'purchase_order', 'receivable']),
            related_id=rng.randrange(1, max(2, len(products))),
            is_read=i % 4 == 0,
        ))

    report_names = [('sales_daily', '销售履约日报'), ('inventory_summary', '库存水位汇总'), ('receivable_aging', '应收账龄'), ('product_ranking', '关键物料排行')]
    for i in range(8 * effective_scale):
        report_type, report_name = pick(rng, report_names)
        db.session.add(GeneratedReport(
            report_type=report_type,
            report_name=report_name,
            period_start=(utcnow() - timedelta(days=30)).date(),
            period_end=utcnow().date(),
            report_data={
                'summary': f'{report_name}经营数据',
                'period_label': f'{(utcnow() - timedelta(days=i % 90)).strftime("%Y-%m-%d")} 班次',
                'source': 'operations-ledger',
                'quality_score': 88 + (i % 10),
            },
            generated_by=admin.id,
            sent_count=rng.randrange(0, 4),
        ))

    article_objects = []
    for i, title in enumerate(['制造仓配月度复盘', '采购补货流程规范', '库存盘点作业说明', '客户信用风控规则', '质量文件归档要求'] * effective_scale):
        article = Article(
            title=f'{title} {i + 1}',
            content=f'<p>{title}。请相关岗位在业务流转时按节点更新状态、附件和异常说明。</p>',
            content_raw=f'{title}。请相关岗位在业务流转时按节点更新状态、附件和异常说明。',
            category=pick(rng, ['运营公告', '流程制度', '盘点公告', '风控规则', '供应商协同']),
            author=admin,
            view_count=rng.randrange(20, 600),
        )
        db.session.add(Article(
            title=article.title,
            content=article.content,
            content_raw=article.content_raw,
            category=article.category,
            author=admin,
            view_count=article.view_count,
        ))
        article_objects.append(article)
    db.session.flush()
    persisted_articles = Article.query.order_by(Article.id.desc()).limit(max(5, len(article_objects))).all()
    comment_templates = [
        '已同步仓库班组，现场会在交接班前回填库位状态。',
        '采购已联系供应商确认到货窗口，异常会进入通知中心。',
        '财务已复核客户信用占用，逾期项目会按优先级跟进。',
        '销售履约会把发货节点与应收单据保持一致。',
        '报表生成后请归档到文件中心并同步负责人。',
    ]
    for i, article in enumerate(persisted_articles):
        db.session.add(ArticleComment(
            article=article,
            author=pick(rng, employees) if employees else admin,
            content=comment_templates[i % len(comment_templates)],
            status='published',
        ))
    file_templates = [
        ('华东工厂仓库位图.pdf', 'application/pdf', 'library/warehouse-map-east.pdf'),
        ('供应商绩效月报.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'library/supplier-score.xlsx'),
        ('MRO 备件安全库存策略.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'library/mro-safety-stock.docx'),
        ('长三角区域仓调拨SOP.pdf', 'application/pdf', 'library/regional-transfer-sop.pdf'),
    ]
    library_sizes = ensure_seed_library_files(file_templates, 'light-seed')
    for i in range(max(6, 4 * effective_scale)):
        filename, mimetype, filepath = file_templates[i % len(file_templates)]
        db.session.add(Attachment(
            filename=f'{i + 1:04d}-{filename}',
            filepath=filepath,
            mimetype=mimetype,
            size=library_sizes.get(filepath, 64000 + i * 2048),
            uploader_id=admin.id,
        ))

    session = AiChatSession(user=admin, title='经营风险晨会摘要')
    db.session.add(session)
    db.session.flush()
    db.session.add(AiChatMessage(session=session, role='user', content='请总结今天最需要关注的经营风险。', tokens=26))
    db.session.add(AiChatMessage(session=session, role='assistant', content='当前优先处理关键物料低库存、待审批补货采购单和逾期应收。', tokens=48))

    for module, action, details in [
        ('auth', 'login', '管理员登录系统'),
        ('inventory', 'stock_opening', '制造仓配库存与流水完成期初入账'),
        ('sales', 'create_order', '批量生成装配中心销售订单'),
        ('procurement', 'approve_order', '生成补货采购审批记录'),
        ('finance', 'record_payment', '生成收款记录'),
        ('system', 'enterprise_init', '企业经营数据完成初始化'),
    ]:
        db.session.add(AuditLog(user=admin, module=module, action=action, ip_address='127.0.0.1', details=details))
    db.session.add(AuditLog(
        user=admin,
        module='system',
        action='seed_enterprise',
        ip_address='127.0.0.1',
        details=json.dumps({
            'scale': scale,
            'multiplier': multiplier,
            'effective_scale': effective_scale,
            'seed': seed,
            'reset': reset,
        }, ensure_ascii=False),
    ))

    db.session.commit()
    validate_seed_quality(expected_scale=effective_scale)
    vacuum_sqlite_database()
    click.echo('企业经营数据初始化完成。')
    echo_demo_accounts(admin_password, user_password)
    click.echo(f'商品: {len(products)}，销售订单: {len(orders)}，采购单: {len(purchase_orders)}，低库存商品: {len(low_stock_products)}')


def base_row(now):
    return {'created_at': now, 'updated_at': now, 'is_deleted': False}


def insert_many(model, rows, chunk_size=5000):
    if not rows:
        return
    for start in range(0, len(rows), chunk_size):
        db.session.bulk_insert_mappings(model, rows[start:start + chunk_size])
        db.session.flush()


def insert_table(table, rows, chunk_size=5000):
    if not rows:
        return
    for start in range(0, len(rows), chunk_size):
        db.session.execute(table.insert(), rows[start:start + chunk_size])
        db.session.flush()


def validate_seed_quality(expected_scale=1):
    """Fail fast when the seed database no longer tells a manufacturing logistics story."""
    minimums = {
        '用户': (User.query.count(), 12 * expected_scale),
        '物料': (Product.query.count(), 36 * expected_scale),
        '客户': (Partner.query.filter_by(type='customer').count(), 10 * expected_scale),
        '供应商': (Partner.query.filter_by(type='supplier').count(), 8 * expected_scale),
        '销售订单': (Order.query.count(), 60 * expected_scale),
        '采购单': (PurchaseOrder.query.count(), 24 * expected_scale),
        '应收账款': (Receivable.query.count(), 1),
        '补货建议': (ReplenishmentSuggestion.query.count(), 1),
        '库存预警': (StockAlert.query.count(), 1),
        '盘点单': (StockTake.query.count(), 1),
        '报表': (GeneratedReport.query.count(), 1),
        '文章': (Article.query.count(), max(5, expected_scale)),
        '评论': (ArticleComment.query.count(), max(5, expected_scale)),
        '文件': (Attachment.query.count(), max(6, expected_scale)),
        '审计日志': (AuditLog.query.count(), 1),
    }
    failed = [f'{label} {actual} < {minimum}' for label, (actual, minimum) in minimums.items() if actual < minimum]
    if failed:
        raise click.ClickException('Seed 数据规模不足：' + '；'.join(failed))

    required_terms = ['伺服', '铝合金', 'MRO', '编码器', '工装']
    missing_terms = [
        term for term in required_terms
        if not Product.query.filter(Product.name.ilike(f'%{term}%')).first()
    ]
    if missing_terms:
        raise click.ClickException('Seed 缺少制造业物料命名：' + '、'.join(missing_terms))

    if not Warehouse.query.filter(Warehouse.name.ilike('%工厂仓%')).first():
        raise click.ClickException('Seed 缺少工厂仓')
    if not Warehouse.query.filter(Warehouse.name.ilike('%区域仓%')).first():
        raise click.ClickException('Seed 缺少区域仓')
    if Product.query.filter(Product.name.ilike('%人体工学椅%')).first():
        raise click.ClickException('Seed 仍包含旧办公用品数据')
    if not ReplenishmentSuggestion.query.join(Product).filter(Product.name.ilike('%MRO%')).first():
        raise click.ClickException('Seed 缺少 MRO 补货链路')
    if not Receivable.query.filter(Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_PARTIAL, Receivable.STATUS_PENDING])).first():
        raise click.ClickException('Seed 缺少应收风险链路')


def vacuum_sqlite_database():
    bind = db.session.get_bind()
    if not bind or bind.dialect.name != 'sqlite':
        return
    database_path = bind.url.database
    if not database_path:
        return
    db.session.remove()
    db.engine.dispose()
    connection = sqlite3.connect(database_path, timeout=30)
    try:
        try:
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            connection.execute('PRAGMA journal_mode=DELETE')
            connection.execute('VACUUM')
        except sqlite3.OperationalError as exc:
            click.echo(f'SQLite 收尾跳过：{exc}')
    finally:
        connection.close()


def run_enterprise_seed(scale=3, multiplier=100, reset=False, seed=20241334, passwords=None):
    rng = random.Random(int(seed or 20241334))
    scale = max(int(scale or 1), 1)
    multiplier = max(int(multiplier or 1), 1)
    admin_password, user_password = passwords or demo_passwords(multiplier=multiplier)
    effective_scale = scale * multiplier
    now = utcnow()
    click.echo(f'初始化 NEXUS 企业经营数据: scale={scale}, multiplier={multiplier}, seed={seed}')

    if reset:
        db.session.remove()
        db.drop_all()
        db.create_all()

    permission_rows = {}
    for name, description in SEED_PERMISSIONS:
        perm = Permission(name=name, description=description)
        db.session.add(perm)
        permission_rows[name] = perm

    roles = {}
    for name, is_admin in [('Admin', True), ('Manager', False), ('User', False)]:
        role = Role(name=name, is_admin=is_admin)
        db.session.add(role)
        roles[name] = role
    db.session.flush()
    roles['Admin'].permissions = list(permission_rows.values())
    roles['Manager'].permissions = [
        permission_rows[name] for name in [
            'inventory.adjust', 'purchase.write', 'purchase.approve', 'purchase.receive',
            'finance.payment', 'finance.credit.write', 'reports.generate', 'files.manage',
            'content.write', 'stocktake.write', 'masterdata.write', 'sales.write'
        ]
    ]
    roles['User'].permissions = [
        permission_rows[name] for name in ['purchase.write', 'sales.write', 'files.manage', 'reports.generate']
    ]

    departments = []
    for index, name in enumerate(['总经办', '销售部', '采购部', '仓储部', '财务部', '客服部', '数据运营部']):
        dept = Department(name=name, code=f'D{index + 1:02d}')
        db.session.add(dept)
        departments.append(dept)
    db.session.flush()

    admin = User(
        username='admin',
        email='admin@nexus.com',
        full_name='庄颂',
        role=roles['Admin'],
        department=departments[0],
        position='系统管理员',
        is_admin=True,
        preferences={
            'density': 'compact',
            'default_workspace': '运营',
            'recent': [{'label': '运营首页', 'path': '/app/overview', 'at': now.isoformat()}],
            'theme': 'dark-cockpit',
        },
    )
    admin.password = admin_password
    db.session.add(admin)
    db.session.flush()

    admin_id = admin.id
    role_ids = {name: role.id for name, role in roles.items()}
    dept_ids = [dept.id for dept in departments]
    db.session.commit()

    surnames = ['赵', '钱', '孙', '李', '周', '吴', '郑', '王', '陈', '林', '黄', '何', '郭', '沈', '韩', '杨']
    given_names = ['明轩', '思远', '雨桐', '嘉宁', '子涵', '亦辰', '若曦', '景行', '沐阳', '书瑶', '清扬', '安然', '知远', '嘉树']
    positions = ['运营专员', '销售经理', '采购专员', '仓储主管', '财务会计', '客服主管', '数据分析师']
    password_hash = generate_password_hash(user_password)
    employee_count = 16 * effective_scale + multiplier * 2
    user_rows = []
    for i in range(employee_count):
        user_rows.append({
            **base_row(now),
            'username': f'user{i + 1:05d}',
            'email': f'user{i + 1:05d}@nexus.com',
            'password_hash': password_hash,
            'full_name': f'{pick(rng, surnames)}{pick(rng, given_names)}',
            'avatar': f'/api/v1/avatars/initials/user{i + 1:05d}',
            'phone': f'15{rng.randrange(100000000, 999999999)}',
            'position': pick(rng, positions),
            'bio': pick(rng, ['负责仓配现场协同', '跟进采购与供应商交期', '处理销售履约和客户窗口', '维护经营数据质量']),
            'preferences': {'theme': 'dark-cockpit' if i % 2 == 0 else 'light-luxury', 'density': 'compact' if i % 3 else 'comfortable'},
            'is_active_user': True,
            'is_admin': False,
            'failed_login_attempts': 0,
            'role_id': role_ids['Manager'] if i % 7 == 0 else role_ids['User'],
            'department_id': pick(rng, dept_ids[1:]),
        })
    insert_many(User, user_rows)
    db.session.commit()
    employee_ids = [row[0] for row in User.query.with_entities(User.id).filter(User.email != 'admin@nexus.com').all()]

    category_names = MANUFACTURING_CATEGORIES
    category_rows = [{**base_row(now), 'name': name, 'icon': 'box'} for name in category_names]
    insert_many(Category, category_rows)
    tag_rows = [
        *[{**base_row(now), 'name': name, 'color': color} for name, color in MANUFACTURING_TAGS],
    ]
    insert_many(Tag, tag_rows)
    db.session.commit()
    category_ids = [row[0] for row in Category.query.with_entities(Category.id).all()]
    tag_ids = [row[0] for row in Tag.query.with_entities(Tag.id).all()]

    cities = ['上海', '杭州', '苏州', '南京', '宁波', '合肥', '深圳', '广州', '成都', '武汉', '厦门', '青岛']
    customer_names = MANUFACTURING_CUSTOMERS
    supplier_names = MANUFACTURING_SUPPLIERS
    customer_count = 16 * effective_scale
    supplier_count = 12 * effective_scale
    partner_rows = []
    for i in range(customer_count):
        partner_rows.append({
            **base_row(now),
            'name': f'{customer_names[i % len(customer_names)]}{i // len(customer_names) + 1:04d}',
            'type': 'customer',
            'contact_person': f'{pick(rng, surnames)}{pick(rng, given_names)}',
            'phone': f'13{rng.randrange(100000000, 999999999)}',
            'email': f'customer{i + 1:05d}@example.com',
            'address': f'{pick(rng, cities)}市先进制造园 {rng.randrange(10, 399)} 号',
            'credit_score': rng.randrange(68, 99),
        })
    for i in range(supplier_count):
        partner_rows.append({
            **base_row(now),
            'name': f'{supplier_names[i % len(supplier_names)]}{i // len(supplier_names) + 1:04d}',
            'type': 'supplier',
            'contact_person': f'{pick(rng, surnames)}{pick(rng, given_names)}',
            'phone': f'18{rng.randrange(100000000, 999999999)}',
            'email': f'supplier{i + 1:05d}@example.com',
            'address': f'{pick(rng, cities)}市工业配套园 {rng.randrange(1, 88)} 栋',
            'credit_score': rng.randrange(72, 100),
        })
    insert_many(Partner, partner_rows)
    db.session.commit()
    customer_ids = [row[0] for row in Partner.query.with_entities(Partner.id).filter_by(type='customer').all()]
    supplier_ids = [row[0] for row in Partner.query.with_entities(Partner.id).filter_by(type='supplier').all()]

    product_bases = MANUFACTURING_PRODUCTS
    product_count = 64 * effective_scale
    product_rows = []
    for i in range(product_count):
        cost = rng.randrange(18, 1800)
        product_rows.append({
            **base_row(now),
            'sku': f'MFG-{seed}-{i + 1:06d}',
            'name': f'{product_bases[i % len(product_bases)]} {chr(65 + (i % 6))}型-{i // len(product_bases) + 1:04d}',
            'price': round(cost * rng.uniform(1.18, 1.85), 2),
            'cost': round(cost, 2),
            'description': '适用于制造业仓配、装配线领料和区域仓补货，支持批次追踪与质量复核。',
            'min_stock': rng.randrange(20, 120),
            'max_stock': rng.randrange(450, 1600),
            'category_id': category_ids[i % len(category_ids)],
            'supplier_id': supplier_ids[i % len(supplier_ids)],
            'specs': {'单位': pick(rng, ['件', '箱', '套', '托']), '批次': f'LOT-{seed}-{i + 1:06d}', '质检': pick(rng, ['全检', '抽检', '免检'])},
        })
    insert_many(Product, product_rows)
    db.session.commit()
    products = Product.query.with_entities(Product.id, Product.price, Product.cost, Product.min_stock, Product.max_stock, Product.supplier_id).order_by(Product.id).all()
    tag_rows = [
        {'product_id': product_id, 'tag_id': tag_ids[index % len(tag_ids)]}
        for index, (product_id, *_rest) in enumerate(products)
        if index % 5 == 0
    ]
    insert_table(product_tags, tag_rows)
    db.session.commit()

    warehouse_rows = [
        {**base_row(now), 'name': name, 'location': location, 'capacity': capacity * multiplier}
        for name, location, capacity in MANUFACTURING_WAREHOUSES
    ]
    insert_many(Warehouse, warehouse_rows)
    db.session.commit()
    warehouse_ids = [row[0] for row in Warehouse.query.with_entities(Warehouse.id).all()]

    stock_rows = []
    log_rows = []
    low_products = []
    for index, product in enumerate(products):
        product_id, _price, _cost, min_stock, max_stock, _supplier_id = product
        if index % 15 == 0:
            target_warehouses = [warehouse_ids[index % len(warehouse_ids)]]
            quantities = [max(0, int((min_stock or 20) * 0.45))]
            low_products.append((product_id, min_stock, _supplier_id, target_warehouses[0], quantities[0], _cost))
        else:
            target_warehouses = [warehouse_ids[index % len(warehouse_ids)], warehouse_ids[(index + 1) % len(warehouse_ids)]]
            quantities = [
                rng.randrange(max(20, min_stock or 20), max((max_stock or 500) // 2, 80)),
                rng.randrange(10, max((max_stock or 500) // 3, 60)),
            ]
        for warehouse_id, quantity in zip(target_warehouses, quantities):
            stock_rows.append({
                **base_row(now),
                'product_id': product_id,
                'warehouse_id': warehouse_id,
                'quantity': quantity,
                'shelf_location': f'{chr(65 + (index % 6))}区-{index % 18 + 1:02d}-{index % 8 + 1:02d}',
            })
            log_rows.append({
                **base_row(now),
                'transaction_code': f'INIT-{product_id}-{warehouse_id}',
                'move_type': InventoryLog.TYPE_IN,
                'product_id': product_id,
                'warehouse_id': warehouse_id,
                'qty_change': quantity,
                'balance_after': quantity,
                'operator_id': admin_id,
                'remark': '制造仓配期初入库',
            })
    insert_many(Stock, stock_rows)
    insert_many(InventoryLog, log_rows)
    db.session.commit()

    order_count = 112 * effective_scale
    order_rows = []
    order_item_rows = []
    for i in range(order_count):
        created_at = now - timedelta(days=i % 180, hours=i % 24)
        status_value = [Order.STATUS_PENDING, Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE, Order.STATUS_DONE][i % 5]
        first = products[(i * 7) % len(products)]
        second = products[(i * 11 + 5) % len(products)]
        qty1 = i % 9 + 1
        qty2 = i % 7 + 2
        total = round(qty1 * first.price + qty2 * second.price, 2)
        order_rows.append({
            **base_row(created_at),
            'order_no': f'SO-{created_at.strftime("%Y%m%d")}-{i + 1:06d}',
            'customer_id': customer_ids[i % len(customer_ids)],
            'seller_id': employee_ids[i % len(employee_ids)] if employee_ids else admin_id,
            'total_amount': total,
            'status': status_value,
        })
    insert_many(Order, order_rows)
    db.session.commit()
    orders = Order.query.with_entities(Order.id, Order.order_no, Order.created_at, Order.status, Order.total_amount, Order.customer_id).order_by(Order.id).all()
    for i, order in enumerate(orders):
        first = products[(i * 7) % len(products)]
        second = products[(i * 11 + 5) % len(products)]
        order_item_rows.append({
            **base_row(order.created_at),
            'order_id': order.id,
            'product_id': first.id,
            'quantity': i % 9 + 1,
            'price_snapshot': first.price,
        })
        order_item_rows.append({
            **base_row(order.created_at),
            'order_id': order.id,
            'product_id': second.id,
            'quantity': i % 7 + 2,
            'price_snapshot': second.price,
        })
    insert_many(OrderItem, order_item_rows)
    db.session.commit()

    receivable_rows = []
    payment_rows = []
    credit_used = {}
    for i, order in enumerate(orders):
        if order.status not in [Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE]:
            continue
        due_date = order.created_at.date() + timedelta(days=[15, 30, 45, 60][i % 4])
        paid_rate = [0, 0.35, 0.7, 1.0][i % 4] if order.status != Order.STATUS_DONE else [0.7, 1.0][i % 2]
        paid_amount = round(order.total_amount * paid_rate, 2)
        receivable_status = Receivable.STATUS_PAID if paid_rate >= 1 else Receivable.STATUS_PARTIAL if paid_rate > 0 else Receivable.STATUS_PENDING
        if due_date < now.date() and receivable_status != Receivable.STATUS_PAID:
            receivable_status = Receivable.STATUS_OVERDUE
        unpaid = round(order.total_amount - paid_amount, 2)
        credit_used[order.customer_id] = credit_used.get(order.customer_id, 0) + unpaid
        receivable_rows.append({
            **base_row(order.created_at),
            'receivable_no': f'AR-{order.created_at.strftime("%Y%m%d")}-{order.id:06d}',
            'order_id': order.id,
            'customer_id': order.customer_id,
            'total_amount': order.total_amount,
            'paid_amount': paid_amount,
            'due_date': due_date,
            'status': receivable_status,
            'remark': '由销售订单自动生成',
        })
        if paid_rate > 0:
            payment_rows.append({
                **base_row(order.created_at),
                'payment_no': f'PAY-{order.created_at.strftime("%Y%m%d")}-{order.id:06d}',
                'receivable_id': None,
                'customer_id': order.customer_id,
                'amount': paid_amount,
                'payment_method': ['bank', 'wechat', 'alipay', 'check'][i % 4],
                'payment_date': min(now.date(), due_date),
                'operator_id': admin_id,
                'reference_no': f'BANK{seed}{order.id:08d}',
                'remark': '装配中心回款记录',
            })
    insert_many(Receivable, receivable_rows)
    db.session.commit()
    receivable_ids = [row[0] for row in Receivable.query.with_entities(Receivable.id).order_by(Receivable.id).all()]
    payment_index = 0
    for row in payment_rows:
        if payment_index < len(receivable_ids):
            row['receivable_id'] = receivable_ids[payment_index]
        payment_index += 1
    insert_many(PaymentRecord, payment_rows)
    credit_rows = []
    for i, customer_id in enumerate(customer_ids):
        used = round(float(credit_used.get(customer_id, 0)), 2)
        limit = float(80000 + (i % 220) * 1000)
        credit_rows.append({
            **base_row(now),
            'customer_id': customer_id,
            'credit_limit': limit,
            'used_credit': used,
            'warning_threshold': 80.0,
            'is_frozen': used > limit * 1.2,
            'frozen_reason': '信用额度超限' if used > limit * 1.2 else None,
            'frozen_by': admin_id if used > limit * 1.2 else None,
        })
    insert_many(CustomerCredit, credit_rows)
    db.session.commit()

    purchase_count = 52 * effective_scale
    purchase_rows = []
    for i in range(purchase_count):
        created_at = now - timedelta(days=i % 150, hours=i % 12)
        status_value = [
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_PENDING,
            PurchaseOrder.STATUS_APPROVED,
            PurchaseOrder.STATUS_PARTIAL,
            PurchaseOrder.STATUS_RECEIVED,
        ][i % 5]
        first = products[(i * 13) % len(products)]
        second = products[(i * 17 + 9) % len(products)]
        qty1 = 20 + i % 90
        qty2 = 30 + i % 120
        total = round(qty1 * first.cost + qty2 * second.cost, 2)
        purchase_rows.append({
            **base_row(created_at),
            'po_no': f'PO-{created_at.strftime("%Y%m%d")}-{i + 1:06d}',
            'supplier_id': supplier_ids[i % len(supplier_ids)],
            'warehouse_id': warehouse_ids[i % len(warehouse_ids)],
            'total_amount': total,
            'status': status_value,
            'submitted_at': created_at + timedelta(hours=2) if status_value != PurchaseOrder.STATUS_DRAFT else None,
            'submitted_by': admin_id if status_value != PurchaseOrder.STATUS_DRAFT else None,
            'approved_at': created_at + timedelta(days=1) if status_value in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL, PurchaseOrder.STATUS_RECEIVED] else None,
            'approved_by': admin_id if status_value in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL, PurchaseOrder.STATUS_RECEIVED] else None,
            'expected_date': (created_at + timedelta(days=3 + i % 15)).date(),
            'actual_receive_date': created_at + timedelta(days=5 + i % 18) if status_value == PurchaseOrder.STATUS_RECEIVED else None,
            'remark': '产线补货采购',
        })
    insert_many(PurchaseOrder, purchase_rows)
    db.session.commit()
    purchase_orders = PurchaseOrder.query.with_entities(PurchaseOrder.id, PurchaseOrder.status, PurchaseOrder.supplier_id, PurchaseOrder.total_amount, PurchaseOrder.created_at).order_by(PurchaseOrder.id).all()
    purchase_item_rows = []
    price_history_rows = []
    performance = {}
    for i, po in enumerate(purchase_orders):
        first = products[(i * 13) % len(products)]
        second = products[(i * 17 + 9) % len(products)]
        qty1 = 20 + i % 90
        qty2 = 30 + i % 120
        received1 = qty1 if po.status == PurchaseOrder.STATUS_RECEIVED else qty1 // 2 if po.status == PurchaseOrder.STATUS_PARTIAL else 0
        received2 = qty2 if po.status == PurchaseOrder.STATUS_RECEIVED else qty2 // 3 if po.status == PurchaseOrder.STATUS_PARTIAL else 0
        purchase_item_rows.extend([
            {**base_row(po.created_at), 'order_id': po.id, 'product_id': first.id, 'quantity': qty1, 'unit_price': first.cost, 'received_qty': received1},
            {**base_row(po.created_at), 'order_id': po.id, 'product_id': second.id, 'quantity': qty2, 'unit_price': second.cost, 'received_qty': received2},
        ])
        price_history_rows.extend([
            {**base_row(po.created_at), 'product_id': first.id, 'supplier_id': po.supplier_id, 'price': first.cost, 'effective_date': po.created_at.date()},
            {**base_row(po.created_at), 'product_id': second.id, 'supplier_id': po.supplier_id, 'price': second.cost, 'effective_date': po.created_at.date()},
        ])
        current = performance.setdefault(po.supplier_id, {'orders': 0, 'amount': 0.0, 'last': po.created_at})
        current['orders'] += 1
        current['amount'] += po.total_amount
        current['last'] = max(current['last'], po.created_at)
    insert_many(PurchaseOrderItem, purchase_item_rows)
    insert_many(PurchasePriceHistory, price_history_rows)
    performance_rows = []
    for supplier_id, values in performance.items():
        performance_rows.append({
            **base_row(now),
            'supplier_id': supplier_id,
            'total_orders': values['orders'],
            'on_time_orders': max(0, values['orders'] - values['orders'] // 12),
            'quality_pass_orders': max(0, values['orders'] - values['orders'] // 18),
            'total_amount': round(values['amount'], 2),
            'last_order_date': values['last'],
        })
    insert_many(SupplierPerformance, performance_rows)
    db.session.commit()

    alert_rows = []
    suggestion_rows = []
    for index, (product_id, min_stock, supplier_id, warehouse_id, quantity, cost) in enumerate(low_products):
        suggested_qty = max((min_stock or 20) * 3 - quantity, min_stock or 20)
        alert_rows.append({
            **base_row(now),
            'product_id': product_id,
            'warehouse_id': warehouse_id,
            'alert_level': StockAlert.LEVEL_RED if quantity == 0 else StockAlert.LEVEL_YELLOW,
            'status': StockAlert.STATUS_ACTIVE,
            'current_qty': quantity,
            'min_qty': min_stock or 20,
            'suggested_qty': suggested_qty,
        })
        suggestion_rows.append({
            **base_row(now),
            'product_id': product_id,
            'warehouse_id': warehouse_id,
            'supplier_id': supplier_id,
            'current_qty': quantity,
            'suggested_qty': suggested_qty,
            'avg_daily_sales': round(2 + (index % 160) / 10, 1),
            'lead_time_days': 3 + index % 9,
            'safety_stock': min_stock or 20,
            'status': ReplenishmentSuggestion.STATUS_PENDING,
        })
    insert_many(StockAlert, alert_rows)
    insert_many(ReplenishmentSuggestion, suggestion_rows)
    db.session.commit()

    stocktake_count = max(8 * multiplier, 6 * scale)
    stocktake_rows = []
    for i in range(stocktake_count):
        planned = now + timedelta(days=i % 30)
        stocktake_rows.append({
            **base_row(now),
            'take_no': f'ST-{now.strftime("%Y%m%d")}-{i + 1:06d}',
            'warehouse_id': warehouse_ids[i % len(warehouse_ids)],
            'take_type': [StockTake.TYPE_FULL, StockTake.TYPE_CYCLE][i % 2],
            'status': [StockTake.STATUS_DRAFT, StockTake.STATUS_IN_PROGRESS, StockTake.STATUS_COMPLETED][i % 3],
            'planned_date': planned.date(),
            'created_by': admin_id,
            'remark': '周期库存盘点',
            'total_items': 12,
            'counted_items': 0 if i % 3 == 0 else 12,
            'variance_items': 0 if i % 3 == 0 else i % 5,
        })
    insert_many(StockTake, stocktake_rows)
    db.session.commit()
    stocktakes = StockTake.query.with_entities(StockTake.id, StockTake.status, StockTake.warehouse_id).order_by(StockTake.id).all()
    stocktake_item_rows = []
    history_rows = []
    for i, take in enumerate(stocktakes):
        for offset in range(12):
            product = products[(i * 19 + offset) % len(products)]
            system_qty = 60 + (i + offset) % 220
            variance = (offset % 5) - 2
            actual_qty = None if take.status == StockTake.STATUS_DRAFT else system_qty + variance
            stocktake_item_rows.append({
                **base_row(now),
                'take_id': take.id,
                'product_id': product.id,
                'system_qty': system_qty,
                'actual_qty': actual_qty,
                'unit_cost': product.cost,
                'shelf_location': f'{chr(65 + offset % 6)}-{offset + 1:02d}-01',
                'counted_at': now if actual_qty is not None else None,
                'counted_by': admin_id if actual_qty is not None else None,
            })
        history_rows.append({**base_row(now), 'take_id': take.id, 'action': 'create', 'operator_id': admin_id, 'details': {'message': '初始化盘点单'}})
    insert_many(StockTakeItem, stocktake_item_rows)
    insert_many(StockTakeHistory, history_rows)
    db.session.commit()

    notice_templates = [
        ('库存水位预警', '部分关键物料低于安全库存，请检查补货建议和供应商交期。', Notification.CATEGORY_STOCK, Notification.TYPE_WARNING),
        ('采购审批', '产线补货采购单已进入审批队列，请在采购补货中心处理。', Notification.CATEGORY_APPROVAL, Notification.TYPE_INFO),
        ('应收风控提醒', '部分装配中心应收账款已进入逾期区间。', Notification.CATEGORY_ORDER, Notification.TYPE_ALERT),
        ('制造仓配报表', '仓配运营日报已生成，可在报表工作室查看。', Notification.CATEGORY_REPORT, Notification.TYPE_SUCCESS),
    ]
    notification_count = 36 * effective_scale
    notification_rows = []
    for i in range(notification_count):
        title, content, category, notice_type = notice_templates[i % len(notice_templates)]
        notification_rows.append({
            **base_row(now - timedelta(hours=i % 240)),
            'user_id': admin_id if i % 3 == 0 else employee_ids[i % len(employee_ids)],
            'title': title,
            'content': content,
            'type': notice_type,
            'category': category,
            'related_type': ['product', 'order', 'purchase_order', 'receivable'][i % 4],
            'related_id': i % max(2, product_count) + 1,
            'is_read': i % 4 == 0,
        })
    insert_many(Notification, notification_rows)

    report_names = [
        ('sales_daily', '销售履约日报'),
        ('inventory_summary', '库存水位汇总'),
        ('receivable_aging', '应收账龄'),
        ('product_ranking', '关键物料排行'),
        ('supplier_performance', '供应商绩效周报'),
        ('financial_overview', '财务风控总览'),
        ('customer_operations', '客户经营报表'),
        ('capacity_plan', '产能计划复核'),
        ('quality_inspection', '质量检验概览'),
        ('contract_collection', '合同回款跟进'),
        ('service_overview', '售后服务概览'),
    ]
    report_rows = []
    for i in range(18 * effective_scale):
        report_type, report_name = report_names[i % len(report_names)]
        report_rows.append({
            **base_row(now - timedelta(days=i % 90)),
            'report_type': report_type,
            'report_name': report_name,
            'period_start': (now - timedelta(days=30 + i % 30)).date(),
            'period_end': now.date(),
            'report_data': {
                'summary': f'{report_name}经营数据',
                'period_label': f'{(now - timedelta(days=i % 90)).strftime("%Y-%m-%d")} 班次',
                'source': 'operations-ledger',
                'quality_score': 88 + (i % 10),
            },
            'generated_by': admin_id,
            'generated_at': now - timedelta(days=i % 90),
            'sent_count': i % 4,
        })
    insert_many(GeneratedReport, report_rows)

    article_titles = [
        '制造仓配月度复盘', '采购补货流程规范', '库存盘点作业说明', '客户信用风控规则', '质量文件归档要求',
        '区域仓调拨协同', '供应商到货窗口', '质量检验放行规则', '设备维护备件策略', '客户回访闭环制度',
        '经营日报归档规范', '产能计划复核纪要'
    ]
    article_categories = ['运营公告', '流程制度', '盘点公告', '风控规则', '供应商协同', '质量管理', '设备维护', '客户服务']
    article_rows = []
    for i in range(18 * effective_scale):
        title = article_titles[i % len(article_titles)]
        article_rows.append({
            **base_row(now - timedelta(days=i % 120)),
            'title': f'{title} {i + 1}',
            'content': f'<p>{title}。请相关岗位在业务流转时按节点更新状态、附件和异常说明。</p>',
            'content_raw': f'{title}。请相关岗位在业务流转时按节点更新状态、附件和异常说明。',
            'category': article_categories[i % len(article_categories)],
            'author_id': admin_id if i % 4 == 0 else employee_ids[i % len(employee_ids)],
            'status': 'published',
            'view_count': 20 + i % 600,
        })
    insert_many(Article, article_rows)
    db.session.commit()

    article_ids = [row[0] for row in Article.query.with_entities(Article.id).order_by(Article.id).all()]
    comment_templates = [
        '已同步仓库班组，现场会在交接班前回填库位状态。',
        '采购已联系供应商确认到货窗口，异常会进入通知中心。',
        '财务已复核客户信用占用，逾期项目会按优先级跟进。',
        '销售履约会把发货节点与应收单据保持一致。',
        '报表生成后请归档到文件中心并同步负责人。',
    ]
    comment_rows = []
    for i in range(24 * effective_scale):
        comment_rows.append({
            **base_row(now - timedelta(hours=i % 360)),
            'article_id': article_ids[i % len(article_ids)],
            'author_id': employee_ids[i % len(employee_ids)] if employee_ids else admin_id,
            'parent_id': None,
            'content': comment_templates[i % len(comment_templates)],
            'status': 'published',
        })
    insert_many(ArticleComment, comment_rows)

    file_templates = [
        ('华东工厂仓库位图.pdf', 'application/pdf', 'library/warehouse-map-east.pdf'),
        ('供应商绩效月报.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'library/supplier-score.xlsx'),
        ('MRO 备件安全库存策略.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'library/mro-safety-stock.docx'),
        ('长三角区域仓调拨SOP.pdf', 'application/pdf', 'library/regional-transfer-sop.pdf'),
        ('应收账龄复核清单.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'library/receivable-aging.xlsx'),
        ('采购收货质检记录.csv', 'text/csv', 'library/purchase-receiving-quality.csv'),
        ('设备维护备件台账.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'library/maintenance-spares.xlsx'),
        ('接口同步巡检记录.csv', 'text/csv', 'library/integration-sync-check.csv'),
    ]
    library_sizes = ensure_seed_library_files(file_templates, 'enterprise-seed')
    file_rows = []
    for i in range(8 * effective_scale):
        filename, mimetype, filepath = file_templates[i % len(file_templates)]
        file_rows.append({
            **base_row(now - timedelta(days=i % 90)),
            'filename': f'{i + 1:04d}-{filename}',
            'filepath': filepath,
            'mimetype': mimetype,
            'size': library_sizes.get(filepath, 64000 + (i % 128) * 2048),
            'uploader_id': employee_ids[i % len(employee_ids)] if employee_ids else admin_id,
        })
    insert_many(Attachment, file_rows)
    db.session.commit()

    session_count = max(12, multiplier * 2)
    session_rows = []
    for i in range(session_count):
        session_rows.append({
            **base_row(now - timedelta(days=i % 30)),
            'user_id': admin_id,
            'title': f'经营风险晨会摘要 {i + 1}',
            'last_message_at': now - timedelta(days=i % 30),
            'is_archived': False,
        })
    insert_many(AiChatSession, session_rows)
    db.session.commit()
    sessions = [row[0] for row in AiChatSession.query.with_entities(AiChatSession.id).order_by(AiChatSession.id).all()]
    message_rows = []
    for i, session_id in enumerate(sessions[-session_count:]):
        message_rows.append({**base_row(now - timedelta(minutes=i * 6)), 'session_id': session_id, 'role': 'user', 'content': '汇总今天最需要关注的经营风险。', 'tokens': 24})
        message_rows.append({**base_row(now - timedelta(minutes=i * 6 - 1)), 'session_id': session_id, 'role': 'assistant', 'content': '当前优先级为关键物料低水位、待审批补货采购单和逾期应收。请先推进补货转采购，再复核客户信用占用。', 'tokens': 56})
    insert_many(AiChatMessage, message_rows)

    audit_actions = [
        ('auth', 'login', '管理员登录系统'),
        ('inventory', 'stock_opening', '制造仓配库存与流水完成期初入账'),
        ('sales', 'create_order', '装配中心销售订单完成批量导入'),
        ('procurement', 'approve_order', '补货采购审批记录完成归档'),
        ('finance', 'record_payment', '客户收款记录完成入账'),
        ('system', 'enterprise_init', '企业经营数据完成初始化'),
    ]
    audit_rows = []
    for i in range(12 * multiplier):
        module, action, details = audit_actions[i % len(audit_actions)]
        audit_rows.append({
            **base_row(now - timedelta(minutes=i)),
            'user_id': admin_id,
            'module': module,
            'action': action,
            'ip_address': '127.0.0.1',
            'details': details,
        })
    audit_rows.append({
        **base_row(now),
        'user_id': admin_id,
        'module': 'system',
        'action': 'seed_enterprise',
        'ip_address': '127.0.0.1',
        'details': json.dumps({
            'scale': scale,
            'multiplier': multiplier,
            'effective_scale': effective_scale,
            'seed': seed,
            'reset': reset,
        }, ensure_ascii=False),
    })
    insert_many(AuditLog, audit_rows)
    db.session.commit()
    validate_seed_quality(expected_scale=effective_scale)
    vacuum_sqlite_database()

    click.echo('企业经营数据初始化完成。')
    echo_demo_accounts(admin_password, user_password)
    click.echo(f'用户: {employee_count + 1}，商品: {product_count}，销售订单: {order_count}，采购单: {purchase_count}，库存流水: {len(log_rows)}')
    click.echo(f'应收账款: {len(receivable_rows)}，收款记录: {len(payment_rows)}，通知: {notification_count}，报表: {len(report_rows)}')


@click.command('forge-finance')
@with_appcontext
def forge_finance():
    click.echo('财务经营数据已纳入统一初始化命令，请运行: flask seed-enterprise --scale 3 --multiplier 100 --reset --seed 20241334')
