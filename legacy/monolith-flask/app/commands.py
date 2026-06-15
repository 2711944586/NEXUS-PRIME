import click
import random
from datetime import datetime, timedelta
from flask.cli import with_appcontext
from app.extensions import db
# 导入 Part 2 定义的所有模型
from app.models.auth import User, Role, Department
from app.models.biz import Category, Product, Partner, Tag
from app.models.stock import Warehouse, Stock, InventoryLog
from app.models.trade import Order, OrderItem
from app.models.content import Article
from app.utils.fake_gen import fake

@click.command('status')
@with_appcontext
def status():
    """
    [验证指令] 查看当前数据库中的数据统计。
    解决 '看不到数据' 的问题。
    """
    click.echo(click.style('📊 NEXUS 数据库状态监控:', fg='cyan', bold=True))
    
    try:
        u_count = User.query.count()
        p_count = Product.query.count()
        o_count = Order.query.count()
        w_count = Warehouse.query.count()
        l_count = InventoryLog.query.count()
        
        click.echo(f" - 用户 (Users): \t{u_count}")
        click.echo(f" - 产品 (Products): \t{p_count}")
        click.echo(f" - 订单 (Orders): \t{o_count}")
        click.echo(f" - 仓库 (Warehouses): \t{w_count}")
        click.echo(f" - 库存流水 (Logs): \t{l_count}")
        
        if u_count > 0:
             click.echo(click.style('✔ 数据库连接正常，数据已存在。', fg='green'))
        else:
             click.echo(click.style('⚠ 数据库为空，请运行 flask forge 生成数据。', fg='yellow'))
             
    except Exception as e:
        click.echo(click.style(f'✘ 数据库读取失败: {str(e)}', fg='red'))
        click.echo("请检查是否执行了 'flask db upgrade'")


@click.command('forge')
@click.option('--scale', default=10, help='数据规模倍数 (默认10倍)')
@with_appcontext
def forge(scale):
    """
    [造物主指令] 初始化并填充 NEXUS 生态系统的所有数据。
    使用 --scale 参数调整数据规模 (默认10倍)
    警告：这将清除数据库中的现有数据！
    """
    click.echo(click.style(f'⚡ 初始化 NEXUS 创世程序 (规模: {scale}x)...', fg='cyan', bold=True))
    
    # 1. 清除旧数据
    db.drop_all()
    db.create_all()
    
    # 2. 初始化权限与部门 (Auth)
    click.echo('正在构建组织架构...')
    init_auth(scale)
    
    # 3. 初始化商业基础 (Biz)
    click.echo('正在注册商业实体...')
    products = init_biz(scale)
    
    # 4. 初始化仓储 (Stock)
    click.echo('正在建设量子仓库并初始化库存...')
    init_stock(products, scale)
    
    # 5. 模拟历史交易 (Trade)
    click.echo('正在回溯历史交易流水 (这可能需要一些时间)...')
    init_trade(products, scale)
    
    # 6. 初始化内容 (CMS)
    click.echo('正在发布系统公告...')
    init_cms(scale)
    
    click.echo(click.style('✔ NEXUS 系统数据构建完成！', fg='green', bold=True))
    click.echo(f"管理员账号: admin@nexus.com / 密码: admin")
    click.echo(f"数据统计: {50*scale}用户, {100*scale}产品, {200*scale}订单")


def init_auth(scale=10):
    """初始化用户、角色、部门"""
    # 角色
    roles = {}
    for r in ['Admin', 'Manager', 'User']:
        role = Role(name=r, is_admin=(r == 'Admin'))
        db.session.add(role)
        roles[r] = role
    
    # 部门 (扩展)
    depts = []
    dept_names = ['指挥部', '研发部', '市场部', '后勤部', '深空探索部', 
                  '量子计算中心', '生物工程实验室', '防御系统部', '能源管理部', '星际贸易部']
    for d_name in dept_names:
        d = Department(name=d_name, code=fake.word().upper())
        db.session.add(d)
        depts.append(d)
    db.session.commit()

    # 超级管理员
    admin = User(
        username='Commander',
        email='admin@nexus.com',
        password='admin',
        role=roles['Admin'],
        department=depts[0],
        avatar=f"https://ui-avatars.com/api/?name=Commander&background=6366f1&color=fff"
    )
    db.session.add(admin)

    # 生成员工 (50 * scale)
    user_count = 50 * scale
    batch_size = 100
    click.echo(f'  → 创建 {user_count} 个用户...')
    
    for i in range(user_count):
        u = User(
            username=fake.user_name() + str(i),
            email=f"user{i}@nexus.com",
            password='password',
            role=random.choice([roles['Manager'], roles['User']]),
            department=random.choice(depts),
            avatar=f"https://ui-avatars.com/api/?name=U{i}&background=random"
        )
        db.session.add(u)
        
        # 批量提交
        if (i + 1) % batch_size == 0:
            db.session.commit()
    
    db.session.commit()
    click.echo(f'  ✓ 已创建 {user_count} 个用户')

def init_biz(scale=10):
    """初始化分类、伙伴、产品"""
    # 分类 (扩展)
    cats = []
    category_names = [
        '能源核心', '生物组件', '防御系统', '计算终端', '原材料',
        '量子芯片', '纳米材料', '星际引擎', '通讯设备', '医疗器械',
        '环境控制', '人工智能', '武器系统', '探测设备', '维生系统'
    ]
    for c_name in category_names:
        c = Category(name=c_name, icon='box')
        db.session.add(c)
        cats.append(c)
    
    # 标签 (扩展)
    tags = []
    tag_data = [
        ('热销', 'red'), ('新品', 'green'), ('军用级', 'purple'), ('民用', 'blue'),
        ('限量版', 'orange'), ('预售', 'cyan'), ('折扣', 'yellow'), ('VIP专属', 'pink'),
        ('环保', 'teal'), ('高能效', 'indigo')
    ]
    for t_name, color in tag_data:
        t = Tag(name=t_name, color=color)
        db.session.add(t)
        tags.append(t)

    # 合作伙伴 (30 * scale / 5)
    partner_count = max(30, 30 * scale // 5)
    click.echo(f'  → 创建 {partner_count} 个合作伙伴...')
    for i in range(partner_count):
        p = Partner(
            name=fake.sci_fi_company(),
            type=random.choice(['customer', 'supplier']),
            contact_person=fake.name(),
            phone=fake.phone_number(),
            email=f"partner{i}@company.com",
            address=fake.address(),
            credit_score=random.randint(60, 100)
        )
        db.session.add(p)
    db.session.commit()

    # 产品 (100 * scale)
    product_count = 100 * scale
    products = []
    suppliers = Partner.query.filter_by(type='supplier').all()
    
    if not suppliers:
        click.echo("  ⚠ 警告: 没有供应商，跳过产品创建")
        return []

    click.echo(f'  → 创建 {product_count} 个产品...')
    batch_size = 100
    
    for i in range(product_count):
        p = Product(
            sku=f"SKU-{fake.hex_color()}-{i:05d}",
            name=fake.tech_product_name(),
            price=round(random.uniform(100, 50000), 2),
            cost=round(random.uniform(50, 25000), 2),
            description=fake.sentence(nb_words=12),
            category=random.choice(cats),
            supplier=random.choice(suppliers)
        )
        # 随机打标签
        if tags:
            p.tags = random.sample(tags, k=random.randint(0, 3))
        db.session.add(p)
        products.append(p)
        
        # 批量提交
        if (i + 1) % batch_size == 0:
            db.session.commit()
    
    db.session.commit()
    click.echo(f'  ✓ 已创建 {product_count} 个产品')
    return products

def init_stock(products, scale=10):
    """初始化仓库和库存"""
    # 扩展仓库
    warehouse_data = [
        ('主枢纽仓 (Alpha)', 'Sector 1 - 地球轨道'),
        ('保税仓 (Beta)', 'Sector 7 - 拉格朗日点'),
        ('深空冷库 (Zero)', 'Moon Base - 月球背面'),
        ('火星中转站 (Mars-1)', 'Mars Colony - 奥林帕斯'),
        ('木星采矿站 (Jupiter-X)', 'Jupiter Moon - 欧罗巴'),
        ('土星环仓库 (Saturn-R)', 'Saturn Ring - A环区域'),
    ]
    warehouses = []
    for name, loc in warehouse_data:
        wh = Warehouse(name=name, location=loc)
        db.session.add(wh)
        warehouses.append(wh)
    db.session.commit()
    
    # 为每个产品在随机仓库生成初始库存
    admin = User.query.first()
    click.echo(f'  → 初始化 {len(products)} 个产品的库存...')
    batch_size = 100
    
    for i, prod in enumerate(products):
        # 每个产品可能在多个仓库有库存
        num_warehouses = random.randint(1, 3)
        selected_warehouses = random.sample(warehouses, k=num_warehouses)
        
        for wh in selected_warehouses:
            qty = random.randint(50, 2000)
            
            # 1. 创建库存记录
            stock = Stock(product=prod, warehouse=wh, quantity=qty)
            db.session.add(stock)
            
            # 2. 创建入库审计流水
            log = InventoryLog(
                transaction_code=f"INIT-{fake.hex_color()}-{i}",
                move_type='inbound',
                product=prod,
                warehouse=wh,
                qty_change=qty,
                balance_after=qty,
                operator=admin,
                remark="系统初始化入库"
            )
            db.session.add(log)
        
        # 批量提交
        if (i + 1) % batch_size == 0:
            db.session.commit()
    
    db.session.commit()
    click.echo(f'  ✓ 库存初始化完成')

def init_trade(products, scale=10):
    """模拟生成过去 60 天的订单流水"""
    customers = Partner.query.filter_by(type='customer').all()
    sellers = User.query.all()
    
    if not customers or not sellers:
        return

    # 订单数量 (200 * scale)
    order_count = 200 * scale
    click.echo(f'  → 创建 {order_count} 个订单...')
    batch_size = 50
    
    for i in range(order_count):
        # 随机日期 (过去60天内)
        delta_days = random.randint(0, 60)
        order_date = datetime.utcnow() - timedelta(days=delta_days)
        
        order = Order(
            order_no=f"ORD-{20250000+i}",
            customer=random.choice(customers),
            seller=random.choice(sellers),
            status=random.choice(['pending', 'paid', 'shipped', 'done', 'done', 'done']),  # 更多完成订单
            created_at=order_date
        )
        
        # 随机添加 1-8 个商品
        total = 0
        items_count = random.randint(1, 8)
        selected_products = random.sample(products, k=min(items_count, len(products)))
        
        for prod in selected_products:
            qty = random.randint(1, 20)
            item = OrderItem(
                order=order,
                product=prod,
                quantity=qty,
                price_snapshot=prod.price
            )
            total += item.subtotal
            db.session.add(item)
        
        order.total_amount = total
        db.session.add(order)
        
        # 批量提交
        if (i + 1) % batch_size == 0:
            db.session.commit()
            if (i + 1) % 500 == 0:
                click.echo(f'    进度: {i+1}/{order_count}')
    
    db.session.commit()
    click.echo(f'  ✓ 已创建 {order_count} 个订单')

def init_cms(scale=10):
    """发布系统公告和文章"""
    admin = User.query.first()
    
    # 扩展文章内容
    articles_data = [
        ("关于系统升级至 NEXUS V3.0 的通知", "重大更新：全新科幻界面，10倍数据规模，更强AI助手。"),
        ("2025年度 Q1 销售冠军表彰", "恭喜深空探索部创造历史最高销售记录！"),
        ("安全警报：请所有员工更新神经连接协议", "安全部门检测到潜在威胁，请立即更新。"),
        ("新产品线【泰坦机甲】即将上线", "最新军用级装备，预计下月投入量产。"),
        ("量子计算中心扩容完成", "算力提升100倍，支持更复杂的星际导航计算。"),
        ("火星殖民地第三期工程启动", "招募深空建设工程师，高薪福利。"),
        ("AI智脑系统全面升级", "集成DeepSeek最新模型，对话能力大幅提升。"),
        ("星际贸易协定签署成功", "与木卫三联盟达成50年战略合作。"),
        ("员工健康计划2025", "免费基因优化、意识备份服务启动。"),
        ("技术白皮书：超光速通讯协议", "研发部最新成果，详细技术规格公布。"),
    ]
    
    # 根据 scale 生成文章
    article_count = len(articles_data) * max(1, scale // 2)
    click.echo(f'  → 发布 {article_count} 篇文章...')
    
    for i in range(article_count):
        idx = i % len(articles_data)
        title, summary = articles_data[idx]
        
        article = Article(
            title=f"{title}" if i < len(articles_data) else f"{title} [Vol.{i//len(articles_data)+1}]",
            content=f"<p>{summary}</p><p>{fake.paragraph(nb_sentences=5)}</p><p>{fake.paragraph(nb_sentences=3)}</p>",
            author=admin,
            view_count=random.randint(100, 10000)
        )
        db.session.add(article)
    
    db.session.commit()
    click.echo(f'  ✓ 已发布 {article_count} 篇文章')


@click.command('forge-finance')
@with_appcontext
def forge_finance():
    """
    生成财务模块示例数据（对账表等）
    """
    from app.models.finance import AccountStatement
    from app.models.biz import Partner
    from app.models.auth import User
    
    click.echo(click.style('📊 生成财务示例数据...', fg='cyan', bold=True))
    
    # 获取客户
    customers = Partner.query.filter(
        Partner.type.in_(['customer', 'both']),
        Partner.is_deleted == False
    ).limit(20).all()
    
    if not customers:
        click.echo(click.style('⚠ 没有客户数据，请先运行 flask forge', fg='yellow'))
        return
    
    admin = User.query.filter_by(email='admin@nexus.com').first()
    if not admin:
        admin = User.query.first()
    
    # 清除旧的对账表数据
    AccountStatement.query.delete()
    
    # 生成过去6个月的对账表
    today = datetime.now().date()
    statements_count = 0
    
    for customer in customers:
        # 每个客户生成3-6个月的对账表
        months_count = random.randint(3, 6)
        opening = random.uniform(5000, 50000)  # 初始期初余额
        
        for i in range(months_count):
            # 计算账期
            month_offset = months_count - i
            period_end = today.replace(day=1) - timedelta(days=1)
            for _ in range(month_offset - 1):
                period_end = period_end.replace(day=1) - timedelta(days=1)
            period_start = period_end.replace(day=1)
            
            # 生成数据
            sales = random.uniform(10000, 100000)
            payment = random.uniform(sales * 0.6, sales * 1.1)  # 收款金额
            closing = opening + sales - payment
            
            statement = AccountStatement(
                statement_no=f"STM{period_end.strftime('%Y%m')}{customer.id:04d}",
                customer_id=customer.id,
                period_start=period_start,
                period_end=period_end,
                opening_balance=round(opening, 2),
                sales_amount=round(sales, 2),
                payment_amount=round(payment, 2),
                closing_balance=round(closing, 2),
                generated_at=datetime.combine(period_end, datetime.min.time()) + timedelta(days=random.randint(1, 5)),
                generated_by=admin.id if admin else None,
                confirmed=random.choice([True, False, False]),  # 30%确认
                confirmed_at=datetime.now() if random.random() > 0.7 else None
            )
            db.session.add(statement)
            statements_count += 1
            
            # 下期期初 = 本期期末
            opening = closing
    
    db.session.commit()
    click.echo(click.style(f'✓ 已生成 {statements_count} 条对账表记录', fg='green'))