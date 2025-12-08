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