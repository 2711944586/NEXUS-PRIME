import hashlib

from flask import current_app, make_response, request
from sqlalchemy import func

from app.extensions import cache, db
from app.models.auth import Role, User
from app.services.audit_service import AuditService

from . import api_bp
from .auth import (
    CSRF_COOKIE_NAME,
    create_access_token,
    current_api_user,
    generate_csrf_token,
    jwt_required,
    response_with_cleared_auth,
    with_auth_cookies,
)
from .responses import api_error, api_success
from .resource_support import (
    CAPTCHA_TERMS_VERSION,
    current_payload,
    new_captcha_challenge,
    normalize_register_payload,
    permission_summary,
    serialize_model,
    user_extra,
    validate_register_gate,
    validate_register_profile,
)


def login_rate_limit_identity(email):
    forwarded = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
    ip_address = forwarded.split(',')[0].strip().lower() or 'unknown'
    normalized_email = (email or '').strip().lower() or 'blank'
    digest = hashlib.sha256(f'{ip_address}:{normalized_email}'.encode('utf-8')).hexdigest()
    return f'auth-login-fail:{digest}'


def login_rate_limit_state(email):
    key = login_rate_limit_identity(email)
    attempts = int(cache.get(key) or 0)
    limit = int(current_app.config.get('LOGIN_RATE_LIMIT_ATTEMPTS', 8))
    return key, attempts, limit


def login_rate_limited(email):
    _key, attempts, limit = login_rate_limit_state(email)
    return attempts >= limit


def record_login_failure(email, user=None, reason='invalid_credentials'):
    key, attempts, limit = login_rate_limit_state(email)
    attempts += 1
    window = int(current_app.config.get('LOGIN_RATE_LIMIT_WINDOW_SECONDS', 10 * 60))
    cache.set(key, attempts, timeout=window)
    details = {
        'email': email,
        'reason': reason,
        'attempts': attempts,
        'limit': limit,
        'window_seconds': window,
        'rate_limited': attempts >= limit,
    }
    AuditService.record('auth', 'login_failed', user, details)
    return attempts >= limit


def clear_login_failures(email):
    cache.delete(login_rate_limit_identity(email))


@api_bp.post('/auth/login')
def api_login():
    payload = current_payload()
    email = (payload.get('email') or '').strip()
    password = payload.get('password') or ''
    if login_rate_limited(email):
        AuditService.record('auth', 'login_rate_limited', None, {'email': email})
        db.session.commit()
        return api_error('登录尝试过多，请稍后再试', status=429, error='login_rate_limited')
    user = User.query.filter_by(email=email).first()
    if not user:
        record_login_failure(email, reason='unknown_email')
        db.session.commit()
        return api_error('邮箱或密码错误', status=401, error='invalid_credentials')
    if user.is_locked():
        return api_error('账户已临时锁定，请稍后再试', status=403, error='account_locked')
    if not user.verify_password(password):
        user.record_failed_login(commit=False)
        record_login_failure(email, user, reason='bad_password')
        db.session.commit()
        return api_error('邮箱或密码错误', status=401, error='invalid_credentials')
    if not user.is_active:
        return api_error('账户不可用或已锁定', status=403, error='inactive_user')
    user.reset_failed_attempts(commit=False)
    clear_login_failures(email)
    AuditService.record('auth', 'login', user, {'email': email})
    db.session.commit()
    token = create_access_token(user, current_app.config.get('JWT_EXPIRES_HOURS', 12))
    return with_auth_cookies(
        {'user': serialize_model(user, user_extra), 'permissions': permission_summary(user)},
        '登录成功',
        token,
    )


@api_bp.post('/auth/register')
def api_register():
    payload = current_payload()
    gate_error = validate_register_gate(payload)
    if gate_error:
        return api_error(gate_error, status=400, error='register_gate_failed')
    values, field_errors = validate_register_profile(payload)
    if field_errors:
        return api_error('注册资料不完整或格式不符合要求', status=400, error='register_validation_failed', fields=field_errors)
    username = values['username']
    email = values['email']
    password = values['password']
    if User.query.filter_by(email=email).first():
        return api_error('邮箱已被注册', status=400, error='email_exists', fields={'email': '邮箱已被注册'})
    if User.query.filter(func.lower(User.username) == username.lower()).first():
        return api_error('用户名已被占用', status=400, error='username_exists', fields={'username': '用户名已被占用'})
    role = Role.query.filter_by(name='User').first()
    user = User(
        username=username,
        email=email,
        role=role,
        full_name=values['full_name'],
        phone=values['phone'] or None,
        department_name=values['department_name'],
        position=values['position'],
        bio=(payload.get('bio') or '').strip() or None,
        preferences={'theme': payload.get('theme') if payload.get('theme') in ('dark-cockpit', 'light-luxury') else 'dark-cockpit'},
    )
    user.password = password
    db.session.add(user)
    db.session.flush()
    AuditService.record('auth', 'register', user, {'email': email})
    db.session.commit()
    token = create_access_token(user, current_app.config.get('JWT_EXPIRES_HOURS', 12))
    return with_auth_cookies(
        {'user': serialize_model(user, user_extra), 'permissions': permission_summary(user)},
        '注册成功',
        token,
        status=201,
    )


@api_bp.get('/auth/register-policy')
def api_register_policy():
    return api_success({
        'terms_version': CAPTCHA_TERMS_VERSION,
        'permissions': [
            '普通账号默认进入成员角色，无法访问用户管理、审计删除和全局权限配置。',
            '注册资料需包含姓名、用户名、邮箱、部门、岗位和符合强度要求的密码。',
            '关键写入动作会保留审计记录；管理员可根据岗位调整采购、销售、文件、报表和 AI 权限。',
        ],
        'documents': [
            {
                'id': 'terms',
                'title': 'NEXUS Prime 服务许可',
                'summary': '普通成员准入、业务动作、文件上传、审计责任和管理员授权规则。',
                'items': [
                    '注册成功后系统创建普通成员账号，不自动授予用户管理、审计删除、全局权限配置、部署设置等高风险能力。',
                    '账号仅用于 NEXUS Prime 内的制造台账、采购审批、销售履约、财务应收、报表分析、文件归档和协同演示业务。',
                    '用户应使用真实邮箱、姓名或岗位昵称、所属部门和业务岗位；管理员可根据岗位补充分组、角色和业务权限。',
                    '用户名需为 3-32 位字母、数字、点、下划线或短横线；密码至少 8 位，并同时包含字母和数字。',
                    '禁止上传恶意脚本、伪装可执行文件、含敏感凭据的配置文件或与业务无关的大文件；文件中心会记录上传人、时间和类型。',
                    '采购审批、盘点调整、信用冻结、文件删除等关键动作会进入审计日志，便于课程演示、部署检查和责任追踪。',
                ],
            },
            {
                'id': 'privacy',
                'title': '隐私与身份资料说明',
                'summary': '账号资料、通知、头像、偏好设置、审计归属和前端安全边界说明。',
                'items': [
                    '注册资料包括邮箱、用户名、姓名或岗位昵称、手机号、部门、岗位和界面偏好设置。',
                    '这些资料用于登录识别、通知送达、头像展示、业务负责人展示和审计日志归属。',
                    '头像文件存放在专用头像目录或生产持久化存储，不与业务附件混放。',
                    '系统不会在浏览器端保存数据库连接串、部署 Token、Supabase secret、Cloudinary secret 或 AI API Key。',
                    '管理员可以查看业务审计与账号状态，但普通成员无法访问用户管理、角色配置和全局安全配置。',
                    '生产部署时应通过 HTTPS、SameSite Cookie、CSRF Token 和环境变量隔离保护登录会话。',
                ],
            },
            {
                'id': 'data_scope',
                'title': '数据使用范围',
                'summary': '库存、采购、履约、应收、文件、报表和 AI 经营分析的数据边界。',
                'items': [
                    '系统会把注册账号与后续上传、评论、报表生成、AI 会话、业务写入和审批动作建立关联。',
                    '库存、采购、销售、履约、应收、信用、盘点、质检和维护数据仅用于系统内业务流转、演示分析和审计追踪。',
                    'AI 分析只通过后端读取经营汇总和用户输入；外部模型调用由服务端统一转发，并可降级为本地分析。',
                    '文件附件存放在专用文件目录或生产持久化存储；Seed 图片和演示素材位于前端公共资源。',
                    '生产部署应使用 Supabase PostgreSQL、Vercel 环境变量和 Cloudinary 或等价对象存储承载持久文件。',
                    '管理员可按岗位分配采购、销售、文件、报表、AI、系统审计等权限，普通成员只能访问被授权的业务范围。',
                ],
            },
        ],
        'required_acceptances': ['accepted_terms', 'accepted_privacy', 'accepted_data_scope'],
    }, '注册策略')


@api_bp.get('/auth/captcha')
def api_captcha():
    return api_success(new_captcha_challenge(), '注册验证码')


@api_bp.post('/auth/logout')
@jwt_required
def api_logout():
    return response_with_cleared_auth({'revoked': True}, '已退出登录')


@api_bp.get('/auth/csrf')
def api_csrf():
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME) or generate_csrf_token()
    body, status = api_success({'csrf_token': csrf_token}, 'CSRF token')
    response = make_response(body.get_data(), status)
    response.content_type = body.content_type or 'application/json'
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=int(current_app.config.get('JWT_EXPIRES_HOURS', 12) * 3600),
        httponly=False,
        secure=bool(current_app.config.get('AUTH_COOKIE_SECURE', current_app.config.get('SESSION_COOKIE_SECURE', False))),
        samesite=current_app.config.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        path='/',
    )
    return response


@api_bp.post('/auth/change-password')
@jwt_required
def api_change_password():
    payload = request.get_json(silent=True) or {}
    current_password = payload.get('current_password', '')
    new_password = payload.get('new_password', '')
    if not current_password or not new_password:
        return api_error('请提供当前密码和新密码', status=400)
    from app.platform.auth import check_password_strength
    ok, msg = check_password_strength(new_password)
    if not ok:
        return api_error(msg, status=400)
    user = current_api_user()
    if not user.check_password(current_password):
        return api_error('当前密码不正确', status=400)
    user.password = new_password
    db.session.commit()
    return api_success({}, '密码修改成功')
