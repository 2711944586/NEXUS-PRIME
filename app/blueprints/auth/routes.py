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
    """生成完整测试数据（包含用户、产品、订单等）- 仅首次使用"""
    import random
    from datetime import datetime, timedelta
    from app.models.biz import Category, Product, Partner
    from app.models.stock import Warehouse, Stock, InventoryLog
    from app.models.trade import Order, OrderItem
    
    try:
        # 检查是否已有数据
        if Product.query.count() > 0:
            return jsonify({
                'status': 'exists',
                'message': '数据已存在，无需重复生成',
                'stats': {
                    'users': User.query.count(),
                    'products': Product.query.count(),
                    'orders': Order.query.count()
                }
            })
        
        # 1. 确保有角色和部门
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            admin_role = Role(name='Admin', is_admin=True)
            manager_role = Role(name='Manager', is_admin=False)
            user_role = Role(name='User', is_admin=False)
            db.session.add_all([admin_role, manager_role, user_role])
        else:
            manager_role = Role.query.filter_by(name='Manager').first()
            user_role = Role.query.filter_by(name='User').first()
        
        # 部门
        dept_names = ['指挥部', '研发部', '市场部', '后勤部', '量子计算中心']
        depts = []
        for i, name in enumerate(dept_names):
            d = Department.query.filter_by(name=name).first()
            if not d:
                d = Department(name=name, code=f'D{i+1:02d}')
                db.session.add(d)
            depts.append(d)
        db.session.commit()
        
        # 2. 创建管理员（如果不存在）
        if not User.query.filter_by(email='admin@nexus.com').first():
            admin = User(
                username='Commander',
                email='admin@nexus.com',
                password='admin',
                role=admin_role,
                department=depts[0]
            )
            db.session.add(admin)
        
        # 3. 创建测试用户 (20个)
        for i in range(20):
            u = User(
                username=f'user_{i+1}',
                email=f'user{i+1}@nexus.com',
                password='password',
                role=random.choice([manager_role, user_role]),
                department=random.choice(depts)
            )
            db.session.add(u)
        db.session.commit()
        
        # 4. 创建分类
        cat_names = ['能源核心', '生物组件', '防御系统', '计算终端', '原材料']
        cats = []
        for name in cat_names:
            c = Category(name=name, icon='box')
            db.session.add(c)
            cats.append(c)
        db.session.commit()
        
        # 5. 创建供应商/客户
        partners = []
        for i in range(10):
            p = Partner(
                name=f'合作伙伴-{i+1}',
                type=random.choice(['supplier', 'customer', 'both']),
                contact=f'联系人{i+1}',
                phone=f'1380000{i:04d}',
                email=f'partner{i+1}@example.com'
            )
            db.session.add(p)
            partners.append(p)
        db.session.commit()
        
        # 6. 创建产品 (50个)
        products = []
        product_names = ['量子芯片', '纳米材料', '等离子电池', '生物传感器', '引力模块',
                        '超导线圈', '反物质容器', '神经接口', '全息投影仪', '时空稳定器']
        for i in range(50):
            p = Product(
                name=f'{random.choice(product_names)}-{i+1:03d}',
                sku=f'SKU{i+1:05d}',
                category=random.choice(cats),
                price=round(random.uniform(100, 10000), 2),
                cost=round(random.uniform(50, 5000), 2),
                unit='件',
                min_stock=random.randint(10, 50),
                max_stock=random.randint(100, 500)
            )
            db.session.add(p)
            products.append(p)
        db.session.commit()
        
        # 7. 创建仓库
        warehouses = []
        wh_names = ['主仓库 (Alpha)', '备用仓库 (Beta)', '冷链仓库 (Gamma)']
        for name in wh_names:
            w = Warehouse(name=name, code=name.split()[0], address='深空站点')
            db.session.add(w)
            warehouses.append(w)
        db.session.commit()
        
        # 8. 创建库存
        for p in products:
            for w in warehouses:
                s = Stock(
                    product_id=p.id,
                    warehouse_id=w.id,
                    quantity=random.randint(50, 500)
                )
                db.session.add(s)
        db.session.commit()
        
        # 9. 创建订单 (30个)
        customers = [p for p in partners if p.type in ('customer', 'both')]
        users = User.query.all()
        for i in range(30):
            order = Order(
                order_no=f'ORD{datetime.now().strftime("%Y%m%d")}{i+1:04d}',
                type=random.choice(['sale', 'purchase']),
                status=random.choice(['pending', 'confirmed', 'shipped', 'completed']),
                partner_id=random.choice(customers).id if customers else None,
                user_id=random.choice(users).id,
                total_amount=0,
                created_at=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            db.session.add(order)
            db.session.flush()
            
            # 订单明细
            total = 0
            for j in range(random.randint(1, 5)):
                prod = random.choice(products)
                qty = random.randint(1, 10)
                item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    quantity=qty,
                    price=prod.price
                )
                db.session.add(item)
                total += qty * float(prod.price)
            order.total_amount = total
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '✅ 完整测试数据生成成功！',
            'stats': {
                'users': User.query.count(),
                'products': Product.query.count(),
                'orders': Order.query.count(),
                'warehouses': Warehouse.query.count()
            },
            'admin': {
                'email': 'admin@nexus.com',
                'password': 'admin'
            }
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'trace': traceback.format_exc()
        })