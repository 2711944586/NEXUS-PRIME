import logging
import colorlog
from flask import Flask, render_template
from config import config
from app.extensions import db, migrate, login_manager, cache, assets, csrf

# 新增：导入 commands 模块，用于注册 CLI 命令
from app import commands


def create_app(config_name='default'):
    """NEXUS PRIME 应用工厂函数"""
    app = Flask(__name__)
    
    # 1. 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 2. 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    assets.init_app(app)
    csrf.init_app(app)

    # 3. 配置日志
    configure_logging(app)

    # 4. 注册蓝图 (Blueprints)
    register_blueprints(app)

    # 5. 注册全局错误处理
    register_error_handlers(app)

    # 6. 注册 CLI 命令
    register_commands(app)

    # 7. 生产环境自动初始化数据库
    auto_init_database(app)

    return app


def auto_init_database(app):
    """生产环境自动初始化数据库 - 生成完整测试数据"""
    import os
    import random
    from datetime import datetime, timedelta
    
    flask_env = os.environ.get('FLASK_ENV', '')
    # 生产环境或检测到 DATABASE_URL 时自动初始化
    if flask_env == 'production' or os.environ.get('DATABASE_URL'):
        with app.app_context():
            try:
                from sqlalchemy import inspect
                from app.models.auth import User, Role, Department
                from app.models.biz import Category, Product, Partner, Tag
                from app.models.stock import Warehouse, Stock, InventoryLog
                from app.models.trade import Order, OrderItem
                from app.models.content import Article
                
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                
                # 如果表不存在，创建所有表
                if 'auth_users' not in tables:
                    app.logger.info('🚀 首次启动，正在创建数据库表...')
                    db.create_all()
                    tables = []  # 标记需要生成数据
                
                # 检查是否已有数据
                user_count = 0
                try:
                    user_count = User.query.count()
                except:
                    pass
                
                if user_count == 0:
                    app.logger.info('📦 正在生成完整测试数据...')
                    _generate_full_data(app, db)
                    app.logger.info('✅ 数据初始化完成！管理员: admin@nexus.com / admin')
                    
            except Exception as e:
                app.logger.error(f'❌ 数据库初始化错误: {e}')
                import traceback
                app.logger.error(traceback.format_exc())


def _generate_full_data(app, db):
    """生成完整的测试数据 - 与本地 flask forge 相同"""
    import random
    from datetime import datetime, timedelta
    from app.models.auth import User, Role, Department
    from app.models.biz import Category, Product, Partner, Tag
    from app.models.stock import Warehouse, Stock, InventoryLog
    from app.models.trade import Order, OrderItem
    from app.models.content import Article
    
    # ========== 1. 角色 ==========
    roles = {}
    for r in ['Admin', 'Manager', 'User']:
        role = Role(name=r, is_admin=(r == 'Admin'))
        db.session.add(role)
        roles[r] = role
    
    # ========== 2. 部门 ==========
    depts = []
    dept_names = ['指挥部', '研发部', '市场部', '后勤部', '深空探索部', 
                  '量子计算中心', '生物工程实验室', '防御系统部', '能源管理部', '星际贸易部']
    for i, d_name in enumerate(dept_names):
        d = Department(name=d_name, code=f'D{i+1:02d}')
        db.session.add(d)
        depts.append(d)
    db.session.commit()
    
    # ========== 3. 管理员 ==========
    admin = User(
        username='Commander',
        email='admin@nexus.com',
        password='admin',
        role=roles['Admin'],
        department=depts[0],
        avatar='https://ui-avatars.com/api/?name=Commander&background=6366f1&color=fff'
    )
    db.session.add(admin)
    
    # ========== 4. 普通用户 (50个) ==========
    for i in range(50):
        u = User(
            username=f'crew_{i+1:03d}',
            email=f'user{i+1}@nexus.com',
            password='password',
            role=random.choice([roles['Manager'], roles['User']]),
            department=random.choice(depts),
            avatar=f'https://ui-avatars.com/api/?name=U{i+1}&background=random'
        )
        db.session.add(u)
    db.session.commit()
    
    # ========== 5. 产品分类 ==========
    cats = []
    category_names = ['能源核心', '生物组件', '防御系统', '计算终端', '原材料',
                     '量子芯片', '纳米材料', '星际引擎', '通讯设备', '医疗器械']
    for c_name in category_names:
        c = Category(name=c_name, icon='box')
        db.session.add(c)
        cats.append(c)
    db.session.commit()
    
    # ========== 6. 合作伙伴 ==========
    partners = []
    partner_names = ['星际贸易联盟', '量子科技集团', '深空矿业公司', '生物基因实验室', 
                    '银河运输队', '能源开发署', '防御系统承包商', '医疗供应链', '通讯网络公司', '原材料供应商']
    for i, p_name in enumerate(partner_names):
        p = Partner(
            name=p_name,
            type=random.choice(['supplier', 'customer', 'both']),
            contact=f'联系人{i+1}',
            phone=f'138{random.randint(10000000, 99999999)}',
            email=f'partner{i+1}@galaxy.com',
            address=f'银河系第{i+1}象限'
        )
        db.session.add(p)
        partners.append(p)
    db.session.commit()
    
    # ========== 7. 产品 (100个) ==========
    products = []
    product_prefixes = ['量子', '纳米', '等离子', '生物', '超导', '反物质', '暗能量', '引力', '时空', '全息']
    product_suffixes = ['芯片', '电池', '传感器', '模块', '容器', '线圈', '接口', '投影仪', '稳定器', '引擎']
    for i in range(100):
        p = Product(
            name=f'{random.choice(product_prefixes)}{random.choice(product_suffixes)}-{i+1:03d}',
            sku=f'NX{i+1:05d}',
            category=random.choice(cats),
            price=round(random.uniform(100, 50000), 2),
            cost=round(random.uniform(50, 25000), 2),
            unit=random.choice(['件', '个', '套', '组', '台']),
            min_stock=random.randint(10, 50),
            max_stock=random.randint(200, 1000),
            description=f'高科技产品-{i+1}'
        )
        db.session.add(p)
        products.append(p)
    db.session.commit()
    
    # ========== 8. 仓库 ==========
    warehouses = []
    wh_data = [
        ('主板舱仓 (Alpha)', 'ALPHA', '空间站A区'),
        ('备用舱仓 (Beta)', 'BETA', '空间站B区'),
        ('冷链舱仓 (Gamma)', 'GAMMA', '空间站C区'),
        ('危险品舱 (Delta)', 'DELTA', '隔离区域'),
        ('原料舱仓 (Epsilon)', 'EPSILON', '采矿平台')
    ]
    for name, code, addr in wh_data:
        w = Warehouse(name=name, code=code, address=addr, is_active=True)
        db.session.add(w)
        warehouses.append(w)
    db.session.commit()
    
    # ========== 9. 库存数据 ==========
    for p in products:
        for w in warehouses:
            qty = random.randint(0, 500)
            if qty > 0:
                s = Stock(product_id=p.id, warehouse_id=w.id, quantity=qty)
                db.session.add(s)
    db.session.commit()
    
    # ========== 10. 库存流水日志 (200条) ==========
    users = User.query.all()
    log_types = ['in', 'out', 'adjust', 'transfer']
    for i in range(200):
        log = InventoryLog(
            product_id=random.choice(products).id,
            warehouse_id=random.choice(warehouses).id,
            type=random.choice(log_types),
            quantity=random.randint(-50, 100),
            user_id=random.choice(users).id,
            remark=f'操作记录-{i+1}',
            created_at=datetime.now() - timedelta(days=random.randint(0, 60))
        )
        db.session.add(log)
    db.session.commit()
    
    # ========== 11. 订单 (200个) ==========
    order_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'completed', 'cancelled']
    for i in range(200):
        order_type = random.choice(['sale', 'purchase'])
        order = Order(
            order_no=f'{"SO" if order_type == "sale" else "PO"}{datetime.now().strftime("%Y%m")}{i+1:05d}',
            type=order_type,
            status=random.choice(order_statuses),
            partner_id=random.choice(partners).id,
            user_id=random.choice(users).id,
            total_amount=0,
            remark=f'订单备注-{i+1}',
            created_at=datetime.now() - timedelta(days=random.randint(0, 90))
        )
        db.session.add(order)
        db.session.flush()
        
        # 订单明细 (1-5个产品)
        total = 0
        for j in range(random.randint(1, 5)):
            prod = random.choice(products)
            qty = random.randint(1, 20)
            price = float(prod.price) * (0.9 + random.random() * 0.2)  # 价格波动
            item = OrderItem(
                order_id=order.id,
                product_id=prod.id,
                quantity=qty,
                price=round(price, 2)
            )
            db.session.add(item)
            total += qty * price
        order.total_amount = round(total, 2)
    db.session.commit()
    
    # ========== 12. 文章/公告 ==========
    articles = [
        ('NEXUS 系统上线公告', '欢迎使用 NEXUS PRIME 量子仓储管理系统！', 'notice'),
        ('安全操作指南', '请遵守空间站安全协议，正确操作仓储设备。', 'guide'),
        ('本月库存盘点通知', '请各部门配合完成本月库存盘点工作。', 'notice'),
        ('新员工培训材料', 'NEXUS 系统操作培训文档，请新员工认真学习。', 'guide'),
        ('系统维护通知', '系统将于本周末进行例行维护，届时部分功能暂停。', 'notice')
    ]
    for title, content, cat in articles:
        a = Article(
            title=title,
            content=content * 10,  # 扩展内容
            category=cat,
            author_id=admin.id,
            status='published',
            created_at=datetime.now() - timedelta(days=random.randint(0, 30))
        )
        db.session.add(a)
    db.session.commit()
    
    app.logger.info(f'📊 数据统计: {User.query.count()}用户, {Product.query.count()}产品, {Order.query.count()}订单')


def register_blueprints(app):
    """注册所有业务模块蓝图"""
    # 主页蓝图
    from app.blueprints.main import main_bp
    app.register_blueprint(main_bp)
    
    # 认证蓝图
    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # 库存管理蓝图
    from app.blueprints.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    
    # 销售管理蓝图
    from app.blueprints.sales import sales_bp
    app.register_blueprint(sales_bp, url_prefix='/sales')
    
    # 内容管理蓝图
    from app.blueprints.cms import cms_bp
    app.register_blueprint(cms_bp, url_prefix='/cms')
    
    # AI 助手蓝图
    from app.blueprints.ai import ai_bp
    app.register_blueprint(ai_bp, url_prefix='/ai')
    
    # 个人信息蓝图
    from app.blueprints.profile import profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')
    
    # 报表分析蓝图
    from app.blueprints.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    # 系统管理蓝图
    from app.blueprints.system import bp as system_bp
    app.register_blueprint(system_bp)
    
    # 采购管理蓝图
    from app.blueprints.purchase import purchase_bp
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    
    # 财务管理蓝图
    from app.blueprints.finance import finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')
    
    # 盘点管理蓝图
    from app.blueprints.stocktake import stocktake_bp
    app.register_blueprint(stocktake_bp, url_prefix='/stocktake')
    
    # 通知与预警蓝图
    from app.blueprints.notification import notification_bp
    app.register_blueprint(notification_bp, url_prefix='/notification')


def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500


def register_commands(app):
    """注册 Flask CLI 命令"""
    app.cli.add_command(commands.forge)
    app.cli.add_command(commands.status)
    app.cli.add_command(commands.forge_finance)


def configure_logging(app):
    """配置彩色控制台日志，提升开发体验"""
    if app.debug:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(blue)s%(message)s",
            datefmt="%H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)