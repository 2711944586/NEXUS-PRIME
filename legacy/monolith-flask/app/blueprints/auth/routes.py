from flask import render_template, redirect, request, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlsplit

from app.extensions import db
from app.models.auth import User, Role, Department
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, RegisterForm
from app.utils.audit import log_action
from app.utils.captcha import create_captcha

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 如果已登录，直接跳到首页
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        # 1. 验证用户存在
        if user is None:
            flash('访问被拒绝：无效的凭证。', 'danger')
            return redirect(url_for('auth.login'))
        
        # 2. 检查账号是否被锁定
        if user.is_locked():
            flash('🔒 安全警报：该账户已被临时锁定（连续登录失败5次）。请30分钟后重试。', 'danger')
            log_action('auth', 'login_attempt_locked', {'email': form.email.data})
            return redirect(url_for('auth.login'))
        
        # 3. 验证密码
        if not user.verify_password(form.password.data):
            user.record_failed_login()
            remaining_attempts = 5 - user.failed_login_attempts
            if remaining_attempts > 0:
                flash(f'访问被拒绝：密码错误。剩余尝试次数: {remaining_attempts}', 'danger')
            log_action('auth', 'login_failed', {'email': form.email.data})
            return redirect(url_for('auth.login'))
            
        # 4. 验证用户是否被软删除
        if user.is_deleted:
            flash('账户不存在或已被注销。', 'danger')
            return redirect(url_for('auth.login'))

        # 5. 验证用户是否被封禁 (is_active_user)
        if not user.is_active_user:
            flash('安全警报：该账户已被系统锁定，请联系管理员。', 'danger')
            return redirect(url_for('auth.login'))

        # 6. 执行登录
        login_user(user, remember=form.remember_me.data)
        user.reset_failed_attempts()
        
        # 7. 记录审计日志
        log_action('auth', 'login_success', {'username': user.username})
        
        # 8. 处理 Next 跳转 (防止开放重定向攻击)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
            
        flash(f'✨ 欢迎回来，指挥官 {user.username}。', 'success')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    log_action('auth', 'logout', {'username': current_user.username})
    logout_user()
    flash('您已安全断开连接。', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    注册逻辑 (默认注册为普通用户)
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegisterForm()
    
    # 生成验证码
    captcha_code, captcha_image = create_captcha()
    
    if form.validate_on_submit():
        # 验证码校验
        stored_captcha = session.get('captcha_code', '')
        user_captcha = form.captcha.data.upper()
        
        if stored_captcha != user_captcha:
            flash('验证码错误，请重新输入。', 'danger')
            # 生成新验证码
            captcha_code, captcha_image = create_captcha()
            session['captcha_code'] = captcha_code
            return render_template('auth/register.html', form=form, captcha_image=captcha_image)
        
        # 检查邮箱是否已存在
        if User.query.filter_by(email=form.email.data).first():
            flash('该电子邮箱已被注册。', 'warning')
            # 生成新验证码
            captcha_code, captcha_image = create_captcha()
            session['captcha_code'] = captcha_code
            return render_template('auth/register.html', form=form, captcha_image=captcha_image)

        # 获取默认角色和部门 (防止报错)
        default_role = Role.query.filter_by(name='User').first()
        default_dept = Department.query.first() # 随机分一个部门

        user = User(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data, # Setter 会自动 Hash
            role=default_role,
            department=default_dept,
            avatar=f"https://ui-avatars.com/api/?name={form.username.data}&background=random"
        )
        
        db.session.add(user)
        db.session.commit()
        
        # 清除验证码session
        session.pop('captcha_code', None)
        
        flash('身份注册成功，请登录。', 'success')
        return redirect(url_for('auth.login'))
    
    # GET请求或表单验证失败时，生成新验证码
    session['captcha_code'] = captcha_code
    return render_template('auth/register.html', form=form, captcha_image=captcha_image)


@auth_bp.route('/refresh-captcha')
def refresh_captcha():
    """AJAX刷新验证码"""
    captcha_code, captcha_image = create_captcha()
    session['captcha_code'] = captcha_code
    return jsonify({'image': captcha_image})


@auth_bp.route('/terms')
def terms():
    """用户协议页面"""
    return render_template('auth/terms.html')


@auth_bp.route('/privacy')
def privacy():
    """隐私政策页面"""
    return render_template('auth/privacy.html')


@auth_bp.route('/init-admin')
def init_admin():
    """初始化管理员账户（仅首次使用）"""
    try:
        # 检查是否已有管理员
        admin = User.query.filter_by(email='admin@nexus.com').first()
        if admin:
            return jsonify({
                'status': 'exists',
                'message': '管理员已存在，请使用 admin@nexus.com / admin 登录'
            })
        
        # 创建角色
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            admin_role = Role(name='Admin', is_admin=True)
            db.session.add(admin_role)
        
        user_role = Role.query.filter_by(name='User').first()
        if not user_role:
            user_role = Role(name='User', is_admin=False)
            db.session.add(user_role)
        
        # 创建部门
        dept = Department.query.first()
        if not dept:
            dept = Department(name='总部', code='HQ')
            db.session.add(dept)
        
        db.session.commit()
        
        # 创建管理员
        admin = User(
            username='Commander',
            email='admin@nexus.com',
            password='admin',
            role=admin_role,
            department=dept
        )
        db.session.add(admin)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '✅ 管理员创建成功！请使用 admin@nexus.com / admin 登录',
            'email': 'admin@nexus.com',
            'password': 'admin'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'创建失败: {str(e)}'
        })


@auth_bp.route('/init-full-data')
def init_full_data():
    """
    生成完整测试数据（和本地 flask forge 一样的规模）
    包含：用户、产品、订单、库存、图表数据等
    """
    import random
    from datetime import datetime, timedelta
    from app.models.biz import Category, Product, Partner, Tag
    from app.models.stock import Warehouse, Stock, InventoryLog
    from app.models.trade import Order, OrderItem
    from app.models.content import Article
    
    scale = 3  # 数据规模倍数（Railway用小一点，避免超时）
    
    try:
        # 检查是否已有数据
        if Product.query.count() > 10:
            return jsonify({
                'status': 'exists',
                'message': '数据已存在，无需重复生成',
                'stats': {
                    'users': User.query.count(),
                    'products': Product.query.count(),
                    'orders': Order.query.count(),
                    'warehouses': Warehouse.query.count()
                }
            })
        
        # ========== 1. 角色和部门 ==========
        roles = {}
        for r in ['Admin', 'Manager', 'User']:
            role = Role.query.filter_by(name=r).first()
            if not role:
                role = Role(name=r, is_admin=(r == 'Admin'))
                db.session.add(role)
            roles[r] = role
        
        dept_names = ['指挥部', '研发部', '市场部', '后勤部', '深空探索部', 
                      '量子计算中心', '生物工程实验室', '防御系统部', '能源管理部', '星际贸易部']
        depts = []
        for i, d_name in enumerate(dept_names):
            d = Department.query.filter_by(name=d_name).first()
            if not d:
                d = Department(name=d_name, code=f'DEPT{i:02d}')
                db.session.add(d)
            depts.append(d)
        db.session.commit()
        
        # ========== 2. 管理员和用户 ==========
        if not User.query.filter_by(email='admin@nexus.com').first():
            admin = User(
                username='Commander',
                email='admin@nexus.com',
                password='admin',
                role=roles['Admin'],
                department=depts[0],
                avatar='https://ui-avatars.com/api/?name=Commander&background=6366f1&color=fff'
            )
            db.session.add(admin)
        
        # 生成员工 (50 * scale)
        user_count = 50 * scale
        for i in range(user_count):
            if not User.query.filter_by(email=f'user{i}@nexus.com').first():
                u = User(
                    username=f'employee_{i+1}',
                    email=f'user{i}@nexus.com',
                    password='password',
                    role=random.choice([roles['Manager'], roles['User']]),
                    department=random.choice(depts),
                    avatar=f'https://ui-avatars.com/api/?name=U{i}&background=random'
                )
                db.session.add(u)
        db.session.commit()
        
        # ========== 3. 分类和标签 ==========
        cats = []
        category_names = ['能源核心', '生物组件', '防御系统', '计算终端', '原材料',
                         '量子芯片', '纳米材料', '星际引擎', '通讯设备', '医疗器械']
        for c_name in category_names:
            c = Category.query.filter_by(name=c_name).first()
            if not c:
                c = Category(name=c_name, icon='box')
                db.session.add(c)
            cats.append(c)
        
        tags = []
        tag_data = [('热销', 'red'), ('新品', 'green'), ('军用级', 'purple'), ('民用', 'blue'),
                   ('限量版', 'orange'), ('预售', 'cyan'), ('折扣', 'yellow'), ('VIP专属', 'pink')]
        for t_name, color in tag_data:
            t = Tag.query.filter_by(name=t_name).first()
            if not t:
                t = Tag(name=t_name, color=color)
                db.session.add(t)
            tags.append(t)
        db.session.commit()
        
        # ========== 4. 合作伙伴 ==========
        partners = []
        partner_count = 30 * scale // 5
        for i in range(partner_count):
            p = Partner(
                name=f'星际企业-{i+1:03d}',
                type=random.choice(['customer', 'supplier']),
                contact_person=f'联系人{i+1}',
                phone=f'1380000{i:04d}',
                email=f'partner{i}@galaxy.com',
                address=f'深空站点-{random.randint(1,100)}区'
            )
            db.session.add(p)
            partners.append(p)
        db.session.commit()
        
        # ========== 5. 产品 ==========
        products = []
        product_names = ['量子处理器', '反物质电池', '曲率引擎', '神经接口', '全息投影仪',
                        '等离子护盾', '引力发生器', '时空稳定器', '生物芯片', '纳米修复液']
        product_count = 100 * scale
        suppliers = [p for p in partners if p.type == 'supplier']
        
        for i in range(product_count):
            p = Product(
                sku=f'SKU-{i+1:05d}',
                name=f'{random.choice(product_names)}-MK{random.randint(1,99):02d}',
                price=round(random.uniform(100, 50000), 2),
                cost=round(random.uniform(50, 25000), 2),
                category=random.choice(cats),
                min_stock=random.randint(10, 50),
                max_stock=random.randint(200, 1000),
                description=f'高科技产品，适用于深空探索和星际贸易。'
            )
            if tags:
                p.tags = random.sample(tags, k=random.randint(0, 3))
            db.session.add(p)
            products.append(p)
            if (i + 1) % 100 == 0:
                db.session.commit()
        db.session.commit()
        
        # ========== 6. 仓库和库存 ==========
        warehouse_data = [
            ('主枢纽仓 (Alpha)', 'Sector 1 - 地球轨道'),
            ('保税仓 (Beta)', 'Sector 7 - 拉格朗日点'),
            ('深空冷库 (Zero)', 'Moon Base - 月球背面'),
            ('火星中转站 (Mars-1)', 'Mars Colony - 奥林帕斯'),
        ]
        warehouses = []
        for name, loc in warehouse_data:
            wh = Warehouse.query.filter_by(name=name).first()
            if not wh:
                wh = Warehouse(name=name, location=loc)
                db.session.add(wh)
            warehouses.append(wh)
        db.session.commit()
        
        # 库存和流水
        admin_user = User.query.filter_by(email='admin@nexus.com').first()
        for i, prod in enumerate(products):
            for wh in random.sample(warehouses, k=random.randint(1, 3)):
                qty = random.randint(50, 2000)
                stock = Stock.query.filter_by(product_id=prod.id, warehouse_id=wh.id).first()
                if not stock:
                    stock = Stock(product_id=prod.id, warehouse_id=wh.id, quantity=qty)
                    db.session.add(stock)
                    
                    # 库存流水
                    log = InventoryLog(
                        transaction_code=f'INIT-{i:05d}-{wh.id}',
                        move_type='inbound',
                        product_id=prod.id,
                        warehouse_id=wh.id,
                        qty_change=qty,
                        balance_after=qty,
                        operator_id=admin_user.id if admin_user else 1,
                        remark='系统初始化入库'
                    )
                    db.session.add(log)
            if (i + 1) % 100 == 0:
                db.session.commit()
        db.session.commit()
        
        # ========== 7. 订单 ==========
        customers = [p for p in partners if p.type == 'customer']
        users = User.query.all()
        order_count = 200 * scale
        
        for i in range(order_count):
            delta_days = random.randint(0, 60)
            order_date = datetime.utcnow() - timedelta(days=delta_days)
            
            order = Order(
                order_no=f'ORD-{20250000+i}',
                status=random.choice(['pending', 'paid', 'shipped', 'done', 'done', 'done']),
                customer_id=random.choice(customers).id if customers else None,
                seller_id=random.choice(users).id,
                total_amount=0,
                created_at=order_date
            )
            db.session.add(order)
            db.session.flush()
            
            total = 0
            for j in range(random.randint(1, 8)):
                prod = random.choice(products)
                qty = random.randint(1, 20)
                item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    quantity=qty,
                    price_snapshot=prod.price
                )
                db.session.add(item)
                total += qty * float(prod.price)
            order.total_amount = total
            
            if (i + 1) % 50 == 0:
                db.session.commit()
        db.session.commit()
        
        # ========== 8. 文章/公告 ==========
        articles_data = [
            ("关于系统升级至 NEXUS V3.0 的通知", "重大更新：全新科幻界面，强大AI助手。"),
            ("2025年度 Q1 销售冠军表彰", "恭喜深空探索部创造历史最高销售记录！"),
            ("新产品线【泰坦机甲】即将上线", "最新军用级装备，预计下月投入量产。"),
            ("量子计算中心扩容完成", "算力提升100倍，支持更复杂的星际导航计算。"),
            ("AI智脑系统全面升级", "集成DeepSeek最新模型，对话能力大幅提升。"),
        ]
        for title, content in articles_data:
            if not Article.query.filter_by(title=title).first():
                article = Article(
                    title=title,
                    content=content,
                    author_id=admin_user.id if admin_user else 1,
                    status='published'
                )
                db.session.add(article)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '✅ 完整测试数据生成成功！和本地 flask forge 效果一致',
            'stats': {
                'users': User.query.count(),
                'departments': Department.query.count(),
                'products': Product.query.count(),
                'categories': Category.query.count(),
                'partners': Partner.query.count(),
                'warehouses': Warehouse.query.count(),
                'orders': Order.query.count(),
                'inventory_logs': InventoryLog.query.count()
            },
            'admin': {
                'email': 'admin@nexus.com',
                'password': 'admin'
            },
            'scale': f'{scale}x (用户:{50*scale}, 产品:{100*scale}, 订单:{200*scale})'
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'trace': traceback.format_exc()
        })