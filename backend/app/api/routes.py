import os
import base64
import hashlib
import hmac
import json
import random
import uuid
from datetime import datetime, date
from html import escape

from flask import Response, current_app, make_response, request, send_from_directory
from sqlalchemy import func, or_, Date as SqlDate, DateTime as SqlDateTime
from werkzeug.utils import secure_filename

from app.extensions import cache, db
from app.models.auth import User, Role, Department
from app.models.biz import Category, Product, Partner, Tag
from app.models.stock import Warehouse, Stock, InventoryLog
from app.models.trade import Order, OrderItem
from app.models.content import Article, ArticleComment, Attachment
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, SupplierPerformance
from app.models.finance import CustomerCredit, Receivable, PaymentRecord, AccountStatement
from app.models.stocktake import StockTake, StockTakeItem
from app.models.notification import Notification, StockAlert, ReplenishmentSuggestion, ReportSubscription, GeneratedReport
from app.models.sys import AuditLog, AiChatSession, AiChatMessage
from app.services.finance_service import FinanceService
from app.services.inventory_service import InventoryService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.stock_alert_service import StockAlertService
from app.services.stocktake_service import StockTakeService
from app.services.audit_service import AuditService
from app.utils.time import utcnow
from app.utils.cloud_storage import (
    is_cloud_storage_enabled,
    upload_avatar_to_cloud,
    uploads_require_cloud_storage,
)
from app.utils.upload_policy import upload_size, validate_upload_type

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


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace('Z', '+00:00')
    return datetime.fromisoformat(text)


def serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize_model(obj, extra=None):
    if obj is None:
        return None
    data = {}
    for column in obj.__table__.columns:
        if column.name == 'password_hash':
            continue
        data[column.name] = serialize_value(getattr(obj, column.name))
    if extra:
        data.update(extra(obj))
    return data


def current_payload():
    return request.get_json(silent=True) or {}


CAPTCHA_TTL_SECONDS = 5 * 60
CAPTCHA_TERMS_VERSION = '2026.06'
CAPTCHA_CHALLENGE_TYPES = ('sum', 'difference', 'phrase')


def captcha_secret():
    return current_app.config.get('SECRET_KEY', 'nexus-prime')


def captcha_signature(payload):
    message = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hmac.new(captcha_secret().encode('utf-8'), message, hashlib.sha256).hexdigest()


def normalize_captcha_answer(answer):
    return str(answer or '').strip().upper().replace(' ', '')


def captcha_answer_hash(answer, nonce):
    normalized = normalize_captcha_answer(answer)
    message = f'{nonce}:{normalized}'.encode('utf-8')
    return hmac.new(captcha_secret().encode('utf-8'), message, hashlib.sha256).hexdigest()


def encode_captcha_token(payload):
    signed = {**payload, 'signature': captcha_signature(payload)}
    raw = json.dumps(signed, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def decode_captcha_token(token):
    if not token:
        return None
    try:
        padded = f"{token}{'=' * (-len(token) % 4)}"
        signed = json.loads(base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8'))
    except Exception:
        return None
    signature = signed.pop('signature', '')
    if not signature or not hmac.compare_digest(signature, captcha_signature(signed)):
        return None
    if int(utcnow().timestamp()) - int(signed.get('issued_at', 0)) > CAPTCHA_TTL_SECONDS:
        return None
    return signed


def captcha_svg(label, prompt):
    label = escape(label)
    prompt = escape(prompt)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="220" height="72" viewBox="0 0 220 72" role="img">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs>'
        '<rect width="220" height="72" rx="18" fill="#f8fafc"/>'
        '<path d="M18 54 C48 16, 72 64, 110 28 S166 26, 204 50" fill="none" stroke="#cbd5e1" stroke-width="2"/>'
        '<circle cx="35" cy="20" r="3" fill="#99f6e4"/><circle cx="188" cy="18" r="4" fill="#bfdbfe"/>'
        '<text x="18" y="28" fill="#64748b" font-family="Arial, sans-serif" font-size="11" font-weight="700">REGISTER CHECK</text>'
        f'<text x="18" y="54" fill="url(#g)" font-family="Arial, sans-serif" font-size="25" font-weight="900">{label}</text>'
        f'<title>{prompt}</title>'
        '</svg>'
    )


def new_captcha_challenge():
    challenge_type = random.choice(CAPTCHA_CHALLENGE_TYPES)
    if challenge_type == 'sum':
        a = random.randint(12, 38)
        b = random.randint(4, 18)
        answer = str(a + b)
        label = f'{a} + {b} = ?'
        prompt = '请输入算式结果'
    elif challenge_type == 'difference':
        a = random.randint(31, 69)
        b = random.randint(6, 24)
        answer = str(a - b)
        label = f'{a} - {b} = ?'
        prompt = '请输入算式结果'
    else:
        code = ''.join(random.choice('ABCDEFGHJKMNPQRSTUVWXYZ23456789') for _ in range(4))
        answer = code
        label = ' '.join(code)
        prompt = '请输入图中 4 位字符'
    issued_at = int(utcnow().timestamp())
    nonce = uuid.uuid4().hex
    token = encode_captcha_token({
        'answer_hash': captcha_answer_hash(answer, nonce),
        'issued_at': issued_at,
        'nonce': nonce,
        'type': challenge_type
    })
    image = captcha_svg(label, prompt)
    return {
        'token': token,
        'image': image,
        'image_data_url': 'data:image/svg+xml;base64,' + base64.b64encode(image.encode('utf-8')).decode('ascii'),
        'prompt': prompt,
        'expires_in': CAPTCHA_TTL_SECONDS,
        'terms_version': CAPTCHA_TERMS_VERSION,
    }


def validate_register_gate(payload):
    accepted_terms = bool(payload.get('accepted_terms'))
    accepted_privacy = bool(payload.get('accepted_privacy'))
    accepted_data_scope = bool(payload.get('accepted_data_scope'))
    if not (accepted_terms and accepted_privacy and accepted_data_scope):
        return '请先阅读并同意服务许可、隐私声明和数据使用范围'
    if payload.get('terms_version') != CAPTCHA_TERMS_VERSION:
        return '许可版本已更新，请刷新注册页后重新确认'
    challenge = decode_captcha_token(payload.get('captcha_token'))
    if not challenge:
        return '验证码已失效，请刷新验证码后重试'
    answer = normalize_captcha_answer(payload.get('captcha_answer'))
    expected_hash = str(challenge.get('answer_hash') or '')
    nonce = str(challenge.get('nonce') or '')
    if not answer or not nonce or not expected_hash or not hmac.compare_digest(captcha_answer_hash(answer, nonce), expected_hash):
        return '验证码识别失败，请重新输入'
    return None


def is_admin_user(user):
    return bool(user and (user.is_admin or (user.role and user.role.is_admin)))


def can_user(permission):
    user = current_api_user()
    return bool(user and (is_admin_user(user) or user.can(permission)))


PERMISSION_LABELS = {
    'inventory.adjust': '库存调整',
    'purchase.write': '采购创建',
    'purchase.approve': '采购审批',
    'purchase.receive': '采购收货',
    'finance.payment': '收款处理',
    'finance.credit.write': '信用管理',
    'reports.generate': '报表生成',
    'files.manage': '文件管理',
    'content.write': '内容管理',
    'stocktake.write': '盘点管理',
    'masterdata.write': '主数据维护',
    'sales.write': '销售履约',
    'admin': '系统管理',
}


def permission_summary(user):
    if not user:
        return []
    if is_admin_user(user):
        names = sorted(PERMISSION_LABELS)
    else:
        names = sorted({perm.name for perm in user.role.permissions}) if user.role else []
    return [{'name': name, 'label': PERMISSION_LABELS.get(name, name)} for name in names]


def require_permission(permission, message='权限不足'):
    if not can_user(permission):
        return api_error(message, status=403, error='permission_denied')
    return None


def require_resource_access(config, action, item=None):
    user = current_api_user()
    if config.get('admin_only') and not is_admin_user(user):
        return api_error('需要管理员权限', status=403, error='admin_required')
    if action in ('create', 'update', 'delete') and config.get('permission') and not can_user(config['permission']):
        return api_error('权限不足', status=403, error='permission_denied')

    model = config['model']
    if model is Notification:
        if item is not None and item.user_id != user.id and not is_admin_user(user):
            return api_error('权限不足', status=403, error='forbidden')
        if action in ('create', 'update', 'delete') and not is_admin_user(user):
            if action != 'update':
                return api_error('权限不足', status=403, error='forbidden')
    if model is Attachment and item is not None and item.uploader_id != user.id and not is_admin_user(user):
        return api_error('权限不足', status=403, error='forbidden')
    if model is ArticleComment and item is not None and action in ('update', 'delete') and item.author_id != user.id and not is_admin_user(user):
        return api_error('权限不足', status=403, error='forbidden')
    if model is AiChatSession and item is not None and item.user_id != user.id and not is_admin_user(user):
        return api_error('权限不足', status=403, error='forbidden')
    if model is AiChatMessage and item is not None:
        session = item.session
        if session and session.user_id != user.id and not is_admin_user(user):
            return api_error('权限不足', status=403, error='forbidden')
    if model is ReportSubscription and item is not None and item.user_id != user.id and not is_admin_user(user):
        return api_error('权限不足', status=403, error='forbidden')
    if model is GeneratedReport and item is not None and not is_admin_user(user):
        owner_id = item.generated_by
        subscription_user_id = item.subscription.user_id if item.subscription else None
        if owner_id != user.id and subscription_user_id != user.id:
            return api_error('权限不足', status=403, error='forbidden')

    return None


def pagination_args():
    page = max(int(request.args.get('page', 1) or 1), 1)
    page_size = int(request.args.get('page_size', request.args.get('per_page', 10)) or 10)
    page_size = min(max(page_size, 1), 100)
    return page, page_size


def paginate(query, serializer, default_sort=None):
    page, page_size = pagination_args()
    if default_sort is not None:
        query = query.order_by(default_sort)
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    return {
        'items': [serializer(item) for item in pagination.items],
        'pagination': {
            'page': pagination.page,
            'page_size': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        }
    }


def apply_search(query, model, fields):
    q = (request.args.get('q') or '').strip()
    if not q or not fields:
        return query
    filters = [getattr(model, field).ilike(f'%{q}%') for field in fields if hasattr(model, field)]
    return query.filter(or_(*filters)) if filters else query


def read_fields(model, payload, allowed):
    values = {}
    for field in allowed:
        if field in payload:
            values[field] = payload[field]
    return values


def invalid_write_fields(config, payload, action):
    allowed = set(config.get(action, []))
    blocked = set(config.get('blocked_write_fields', []))
    supplied = set(payload.keys())
    ignored = {'items'} if action == 'create' else set()
    unsafe = (supplied & blocked) | (supplied - allowed - ignored)
    return sorted(field for field in unsafe)


def normalize_model_values(model, values):
    for column in model.__table__.columns:
        if column.name not in values:
            continue
        if isinstance(column.type, SqlDateTime) and isinstance(values[column.name], str):
            values[column.name] = parse_datetime(values[column.name])
        elif isinstance(column.type, SqlDate) and isinstance(values[column.name], str):
            values[column.name] = parse_date(values[column.name])
    return values


def public_api_url(path):
    if not path:
        return None
    if str(path).startswith(('http://', 'https://')):
        return path
    normalized = '/' + str(path).lstrip('/')
    return f'{request.host_url.rstrip("/")}{normalized}'


def avatar_url_for(user):
    if not user:
        return None
    if user.avatar:
        return public_api_url(user.avatar)
    label = user.full_name or user.username or user.email or f'user-{user.id}'
    return public_api_url(f'/api/v1/avatars/initials/{user.id}-{label[:8]}')


def user_extra(user):
    return {
        'role_name': user.role.name if user.role else None,
        'department_name_display': user.department.name if user.department else user.department_name,
        'is_admin_effective': bool(user.is_admin or (user.role and user.role.is_admin)),
        'avatar': avatar_url_for(user),
    }


def product_extra(product):
    return {
        'category_name': product.category.name if product.category else None,
        'supplier_name': product.supplier.name if product.supplier else None,
        'total_stock': product.total_stock,
    }


def stock_extra(stock):
    return {
        'product_name': stock.product.name if stock.product else None,
        'product_sku': stock.product.sku if stock.product else None,
        'warehouse_name': stock.warehouse.name if stock.warehouse else None,
        'warehouse_location': stock.warehouse.location if stock.warehouse else None,
    }


def order_extra(order):
    return {
        'customer_name': order.customer.name if order.customer else None,
        'seller_name': order.seller.username if order.seller else None,
        'items': [serialize_model(item, order_item_extra) for item in order.items],
    }


def order_item_extra(item):
    return {
        'product_name': item.product.name if item.product else None,
        'product_sku': item.product.sku if item.product else None,
        'subtotal': item.subtotal,
    }


def purchase_extra(po):
    return {
        'supplier_name': po.supplier.name if po.supplier else None,
        'warehouse_name': po.warehouse.name if po.warehouse else None,
        'receive_progress': po.receive_progress,
        'received_amount': po.received_amount,
        'items': [serialize_model(item, purchase_item_extra) for item in po.items],
    }


def supplier_performance_extra(item):
    supplier = item.supplier
    pending_orders = PurchaseOrder.query.filter(
        PurchaseOrder.supplier_id == item.supplier_id,
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_([PurchaseOrder.STATUS_PENDING, PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL])
    ).count()
    return {
        'supplier_name': supplier.name if supplier else None,
        'contact_person': supplier.contact_person if supplier else None,
        'phone': supplier.phone if supplier else None,
        'email': supplier.email if supplier else None,
        'credit_score': supplier.credit_score if supplier else None,
        'on_time_rate': item.on_time_rate,
        'quality_rate': item.quality_rate,
        'pending_orders': pending_orders,
    }


def purchase_item_extra(item):
    return {
        'product_name': item.product.name if item.product else None,
        'product_sku': item.product.sku if item.product else None,
        'subtotal': item.subtotal,
        'pending_qty': item.pending_qty,
    }


def receivable_extra(item):
    return {
        'customer_name': item.customer.name if item.customer else None,
        'unpaid_amount': item.unpaid_amount,
        'overdue_days': item.overdue_days,
        'age_bucket': item.age_bucket,
    }


def credit_extra(item):
    return {
        'customer_name': item.customer.name if item.customer else None,
        'available_credit': item.available_credit,
        'usage_rate': item.usage_rate,
        'is_warning': item.is_warning,
    }


def stocktake_extra(item):
    return {
        'warehouse_name': item.warehouse.name if item.warehouse else None,
        'progress': item.progress,
        'total_variance_qty': item.total_variance_qty,
        'total_variance_value': item.total_variance_value,
        'items': [serialize_model(row, stocktake_item_extra) for row in item.items],
    }


def stocktake_item_extra(item):
    return {
        'product_name': item.product.name if item.product else None,
        'product_sku': item.product.sku if item.product else None,
        'variance_qty': item.variance_qty,
        'variance_value': item.variance_value,
        'variance_type': item.variance_type,
        'is_counted': item.is_counted,
    }


def replenishment_extra(item):
    return {
        'product_name': item.product.name if item.product else None,
        'product_sku': item.product.sku if item.product else None,
        'warehouse_name': item.warehouse.name if item.warehouse else None,
        'supplier_name': item.supplier.name if item.supplier else None,
    }


def notification_extra(item):
    return {
        'user_name': item.user.username if item.user else None,
    }


def attachment_extra(item):
    return {
        'download_url': f'/api/v1/files/{item.id}/download',
    }


def article_extra(item):
    return {
        'author_name': item.author.username if item.author else None,
        'author_avatar': avatar_url_for(item.author),
        'comment_count': item.comments.filter_by(is_deleted=False).count() if hasattr(item, 'comments') else 0,
        'latest_comment_at': serialize_value(
            item.comments.filter_by(is_deleted=False).order_by(ArticleComment.created_at.desc()).first().created_at
        ) if hasattr(item, 'comments') and item.comments.filter_by(is_deleted=False).first() else None,
    }


def comment_extra(item):
    return {
        'author_name': item.author.username if item.author else None,
        'author_full_name': item.author.full_name if item.author else None,
        'author_avatar': avatar_url_for(item.author),
        'article_title': item.article.title if item.article else None,
        'reply_count': item.replies.filter_by(is_deleted=False).count() if hasattr(item, 'replies') else 0,
    }


def report_extra(item):
    return {
        'generated_by_name': item.generator.username if item.generator else None,
    }


def audit_extra(item):
    return {
        'username': item.user.username if item.user else None,
    }


def ai_session_extra(item):
    return {
        'user_name': item.user.username if item.user else None,
        'message_count': item.messages.count(),
    }


def configured_storage_dir(key, fallback=None):
    folder = current_app.config.get(key)
    if folder:
        return folder
    upload_root = current_app.config['UPLOAD_FOLDER']
    return os.path.join(upload_root, fallback) if fallback else upload_root


def avatar_storage_dir():
    return configured_storage_dir('UPLOAD_AVATARS_FOLDER', 'avatars')


def file_storage_dir():
    return configured_storage_dir('UPLOAD_FILES_FOLDER', 'files')


def library_storage_dir():
    return configured_storage_dir('UPLOAD_LIBRARY_FOLDER', 'library')


def safe_join_existing(root, relative_path):
    if not relative_path:
        return None
    root_abs = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(root_abs, relative_path))
    try:
        if os.path.commonpath([root_abs, candidate]) != root_abs:
            return None
    except ValueError:
        return None
    return candidate if os.path.exists(candidate) else None


def resolve_attachment_path(filepath):
    if not filepath or str(filepath).startswith(('http://', 'https://')):
        return None
    relative = str(filepath).replace('\\', '/').lstrip('/')
    upload_root = current_app.config['UPLOAD_FOLDER']
    candidates = []
    if relative.startswith('files/'):
        candidates.append((upload_root, relative))
        candidates.append((file_storage_dir(), relative.split('/', 1)[1]))
    elif relative.startswith('library/'):
        candidates.append((upload_root, relative))
        candidates.append((library_storage_dir(), relative.split('/', 1)[1]))
    else:
        candidates.append((file_storage_dir(), relative))
        candidates.append((upload_root, relative))
    for root, path in candidates:
        resolved = safe_join_existing(root, path)
        if resolved:
            relative_path = os.path.relpath(resolved, os.path.abspath(root)).replace(os.sep, '/')
            return root, relative_path
    return None


def remove_local_avatar(avatar_path):
    if not avatar_path or not str(avatar_path).startswith('/api/v1/avatars/'):
        return
    filename = secure_filename(str(avatar_path).rsplit('/', 1)[-1])
    if not filename:
        return
    avatar_dir = avatar_storage_dir()
    avatar_root = os.path.abspath(avatar_dir)
    filepath = os.path.abspath(os.path.join(avatar_root, filename))
    try:
        inside_avatar_dir = os.path.commonpath([avatar_root, filepath]) == avatar_root
    except ValueError:
        inside_avatar_dir = False
    if inside_avatar_dir and os.path.exists(filepath):
        os.remove(filepath)


def safe_upload_name(filename):
    original = (filename or '').replace('\\', '/').split('/')[-1].strip()
    original = ''.join(ch for ch in original if ch.isprintable() and ch not in '\x00\r\n\t')
    ext = os.path.splitext(original)[1].lower()
    if original and ext:
        return original[:240]
    safe_name = secure_filename(filename or '')
    if safe_name and os.path.splitext(safe_name)[1]:
        return safe_name[:240]
    if ext:
        return f'file-{uuid.uuid4().hex[:10]}{ext}'
    return ''


RESOURCE_CONFIG = {
    'users': {
        'model': User,
        'serializer': lambda item: serialize_model(item, user_extra),
        'search': ['username', 'email', 'full_name'],
        'create': ['username', 'email', 'phone', 'full_name', 'role_id', 'department_id', 'is_admin', 'is_active_user', 'password'],
        'update': ['username', 'email', 'phone', 'full_name', 'department_name', 'position', 'bio', 'role_id', 'department_id', 'is_admin', 'is_active_user'],
        'admin_only': True,
    },
    'roles': {'model': Role, 'search': ['name'], 'create': ['name', 'is_admin'], 'update': ['name', 'is_admin'], 'admin_only': True},
    'departments': {'model': Department, 'search': ['name', 'code'], 'create': ['name', 'code', 'parent_id'], 'update': ['name', 'code', 'parent_id'], 'admin_only': True},
    'categories': {'model': Category, 'search': ['name'], 'create': ['name', 'icon'], 'update': ['name', 'icon'], 'permission': 'masterdata.write'},
    'partners': {'model': Partner, 'search': ['name', 'contact_person', 'phone', 'email'], 'create': ['name', 'type', 'contact_person', 'phone', 'email', 'address', 'credit_score'], 'update': ['name', 'contact_person', 'phone', 'email', 'address', 'credit_score'], 'permission': 'masterdata.write'},
    'products': {'model': Product, 'serializer': lambda item: serialize_model(item, product_extra), 'search': ['name', 'sku', 'description'], 'create': ['sku', 'name', 'price', 'cost', 'description', 'ai_summary', 'specs', 'min_stock', 'max_stock', 'category_id', 'supplier_id'], 'update': ['name', 'price', 'cost', 'description', 'ai_summary', 'specs', 'min_stock', 'max_stock', 'category_id', 'supplier_id'], 'permission': 'masterdata.write'},
    'warehouses': {'model': Warehouse, 'search': ['name', 'location'], 'create': ['name', 'location', 'capacity'], 'update': ['name', 'location', 'capacity'], 'permission': 'inventory.adjust'},
    'stock': {'model': Stock, 'serializer': lambda item: serialize_model(item, stock_extra), 'search': [], 'create': [], 'update': ['shelf_location'], 'blocked_write_fields': ['quantity', 'product_id', 'warehouse_id'], 'permission': 'inventory.adjust'},
    'inventory-logs': {'model': InventoryLog, 'search': ['transaction_code', 'move_type', 'remark'], 'create': [], 'update': []},
    'orders': {'model': Order, 'serializer': lambda item: serialize_model(item, order_extra), 'search': ['order_no', 'status'], 'create': [], 'update': [], 'blocked_write_fields': ['total_amount', 'status', 'seller_id'], 'permission': 'sales.write'},
    'order-items': {'model': OrderItem, 'serializer': lambda item: serialize_model(item, order_item_extra), 'search': [], 'create': [], 'update': [], 'blocked_write_fields': ['quantity', 'price_snapshot', 'product_id', 'order_id'], 'permission': 'sales.write'},
    'purchase-orders': {'model': PurchaseOrder, 'serializer': lambda item: serialize_model(item, purchase_extra), 'search': ['po_no', 'status', 'remark'], 'create': [], 'update': ['expected_date', 'remark'], 'blocked_write_fields': ['status', 'total_amount', 'supplier_id', 'warehouse_id'], 'permission': 'purchase.write'},
    'purchase-order-items': {'model': PurchaseOrderItem, 'serializer': lambda item: serialize_model(item, purchase_item_extra), 'search': [], 'create': [], 'update': [], 'blocked_write_fields': ['received_qty', 'quantity', 'unit_price', 'product_id', 'order_id'], 'permission': 'purchase.write'},
    'supplier-performance': {'model': SupplierPerformance, 'serializer': lambda item: serialize_model(item, supplier_performance_extra), 'search': [], 'create': [], 'update': []},
    'receivables': {'model': Receivable, 'serializer': lambda item: serialize_model(item, receivable_extra), 'search': ['receivable_no', 'status', 'remark'], 'create': [], 'update': ['due_date', 'remark'], 'blocked_write_fields': ['total_amount', 'paid_amount', 'status', 'customer_id'], 'permission': 'finance.payment'},
    'payments': {'model': PaymentRecord, 'search': ['payment_no', 'payment_method', 'reference_no'], 'create': [], 'update': [], 'blocked_write_fields': ['amount', 'customer_id', 'receivable_id'], 'permission': 'finance.payment'},
    'statements': {'model': AccountStatement, 'search': ['statement_no'], 'create': [], 'update': ['confirmed'], 'permission': 'reports.generate'},
    'credits': {'model': CustomerCredit, 'serializer': lambda item: serialize_model(item, credit_extra), 'search': [], 'create': [], 'update': ['credit_limit', 'warning_threshold'], 'blocked_write_fields': ['used_credit', 'is_frozen', 'frozen_reason'], 'permission': 'finance.credit.write'},
    'stocktakes': {'model': StockTake, 'serializer': lambda item: serialize_model(item, stocktake_extra), 'search': ['take_no', 'take_type', 'status', 'remark'], 'create': [], 'update': ['planned_date', 'remark'], 'blocked_write_fields': ['status'], 'permission': 'stocktake.write'},
    'stocktake-items': {'model': StockTakeItem, 'serializer': lambda item: serialize_model(item, stocktake_item_extra), 'search': ['remark'], 'create': [], 'update': ['remark'], 'blocked_write_fields': ['system_qty', 'actual_qty', 'unit_cost'], 'permission': 'stocktake.write'},
    'notifications': {'model': Notification, 'serializer': lambda item: serialize_model(item, notification_extra), 'search': ['title', 'content', 'type', 'category'], 'create': ['user_id', 'title', 'content', 'type', 'category', 'related_type', 'related_id'], 'update': ['title', 'content', 'type', 'category', 'is_read']},
    'stock-alerts': {'model': StockAlert, 'search': ['alert_level', 'status'], 'create': [], 'update': ['resolution_note'], 'blocked_write_fields': ['current_qty', 'min_qty', 'suggested_qty', 'status'], 'permission': 'inventory.adjust'},
    'replenishment-suggestions': {'model': ReplenishmentSuggestion, 'serializer': lambda item: serialize_model(item, replenishment_extra), 'search': ['status'], 'create': [], 'update': [], 'blocked_write_fields': ['status', 'processed_at', 'processed_by', 'purchase_order_id'], 'permission': 'purchase.write'},
    'report-subscriptions': {'model': ReportSubscription, 'search': ['report_type', 'report_name'], 'create': ['user_id', 'report_type', 'report_name', 'frequency', 'send_email', 'send_notification', 'send_hour', 'send_weekday', 'send_day', 'params'], 'update': ['frequency', 'send_email', 'send_notification', 'send_hour', 'send_weekday', 'send_day', 'params', 'is_active']},
    'generated-reports': {'model': GeneratedReport, 'serializer': lambda item: serialize_model(item, report_extra), 'search': ['report_type', 'report_name'], 'create': [], 'update': []},
    'articles': {'model': Article, 'serializer': lambda item: serialize_model(item, article_extra), 'search': ['title', 'content', 'category'], 'create': ['title', 'content', 'content_raw', 'category', 'status'], 'update': ['title', 'content', 'content_raw', 'category', 'status'], 'permission': 'content.write'},
    'article-comments': {'model': ArticleComment, 'serializer': lambda item: serialize_model(item, comment_extra), 'search': ['content', 'status'], 'create': ['article_id', 'content', 'parent_id', 'status'], 'update': ['content', 'status']},
    'files': {'model': Attachment, 'serializer': lambda item: serialize_model(item, attachment_extra), 'search': ['filename', 'mimetype'], 'create': [], 'update': []},
    'audit-logs': {'model': AuditLog, 'serializer': lambda item: serialize_model(item, audit_extra), 'search': ['module', 'action', 'details'], 'create': [], 'update': [], 'admin_only': True},
    'ai-sessions': {'model': AiChatSession, 'serializer': lambda item: serialize_model(item, ai_session_extra), 'search': ['title'], 'create': ['title'], 'update': ['title', 'is_archived']},
    'ai-messages': {'model': AiChatMessage, 'search': ['role', 'content'], 'create': [], 'update': []},
}


RESOURCE_ALIASES = {
    'reports': 'generated-reports',
}


def resource_config(resource):
    return RESOURCE_CONFIG.get(RESOURCE_ALIASES.get(resource, resource))


def serializer_for(config):
    return config.get('serializer') or (lambda item: serialize_model(item))


def query_for(config):
    model = config['model']
    query = model.query
    if hasattr(model, 'is_deleted'):
        query = query.filter(model.is_deleted == False)
    user = current_api_user()
    if model is Notification and not is_admin_user(user):
        query = query.filter(Notification.user_id == user.id)
    elif model is Attachment and not is_admin_user(user):
        query = query.filter(Attachment.uploader_id == user.id)
    elif model is AiChatSession and not is_admin_user(user):
        query = query.filter(AiChatSession.user_id == user.id)
    elif model is AiChatMessage and not is_admin_user(user):
        query = query.join(AiChatSession, AiChatMessage.session_id == AiChatSession.id).filter(AiChatSession.user_id == user.id)
    elif model is ReportSubscription and not is_admin_user(user):
        query = query.filter(ReportSubscription.user_id == user.id)
    elif model is GeneratedReport and not is_admin_user(user):
        query = (
            query.outerjoin(ReportSubscription, GeneratedReport.subscription_id == ReportSubscription.id)
            .filter(or_(GeneratedReport.generated_by == user.id, ReportSubscription.user_id == user.id))
        )
    query = apply_search(query, model, config.get('search', []))
    for field, value in request.args.items():
        if field in ('page', 'page_size', 'per_page', 'q'):
            continue
        if value != '' and hasattr(model, field):
            query = query.filter(getattr(model, field) == value)
    sort = request.args.get('sort')
    if sort:
        direction = request.args.get('order', 'asc').lower()
        if hasattr(model, sort):
            column = getattr(model, sort)
            query = query.order_by(column.desc() if direction == 'desc' else column.asc())
    return query


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
    username = (payload.get('username') or '').strip()
    email = (payload.get('email') or '').strip()
    password = payload.get('password') or ''
    gate_error = validate_register_gate(payload)
    if gate_error:
        return api_error(gate_error, status=400, error='register_gate_failed')
    if not username or not email or len(password) < 6:
        return api_error('用户名、邮箱和至少6位密码为必填项', status=400)
    if User.query.filter_by(email=email).first():
        return api_error('邮箱已被注册', status=400, error='email_exists')
    role = Role.query.filter_by(name='User').first()
    user = User(
        username=username,
        email=email,
        role=role,
        full_name=(payload.get('full_name') or username).strip(),
        phone=(payload.get('phone') or '').strip() or None,
        position=(payload.get('position') or '业务协同成员').strip(),
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
            '注册资料会用于身份识别、业务审计和消息通知，头像与联系方式可在个人工作台修改。',
            '关键写入动作会保留审计记录；管理员可根据岗位调整采购、销售、文件和报表权限。',
        ],
        'documents': [
            {
                'id': 'terms',
                'title': 'NEXUS Prime 服务许可',
                'summary': '账号仅用于本系统制造仓配、采购、销售、财务与分析演示业务。',
                'items': [
                    '注册后系统创建普通成员账号，不自动授予系统管理、审计删除、全局权限配置等高风险能力。',
                    '用户应使用真实邮箱、姓名或岗位昵称；管理员可根据岗位补充分组、角色和业务权限。',
                    '禁止上传恶意脚本、伪装可执行文件或与业务无关的大文件；文件中心会记录上传人、时间和类型。',
                    '采购审批、盘点调整、信用冻结、文件删除等关键动作会进入审计日志，便于课程演示和责任追踪。',
                ],
            },
            {
                'id': 'privacy',
                'title': '隐私与身份资料说明',
                'summary': '系统保存最少必要的身份资料，用于登录、通知、头像和审计归属。',
                'items': [
                    '注册资料包括邮箱、用户名、姓名或岗位昵称、手机号、岗位和偏好设置。',
                    '头像文件存放在专用头像目录或生产持久化存储，不与业务附件混放。',
                    '系统不会在前端保存数据库连接串、部署 Token、Supabase secret、Cloudinary secret 或 AI API Key。',
                    '管理员可以查看业务审计与账号状态，但普通成员无法访问用户管理和全局安全配置。',
                ],
            },
            {
                'id': 'data_scope',
                'title': '数据使用范围',
                'summary': '业务数据用于库存、采购、履约、应收、报表和 AI 经营分析闭环。',
                'items': [
                    '系统会把注册账号与后续上传、评论、报表生成、AI 会话、业务写入动作建立关联。',
                    'AI 分析只通过后端读取经营汇总和用户输入；外部模型调用由服务端统一转发并可降级为本地分析。',
                    '文件附件存放在专用文件目录或生产持久化存储；Seed 图片和演示素材位于前端公共资源。',
                    '生产部署应使用 Supabase PostgreSQL、Vercel 环境变量和 Cloudinary 或等价对象存储承载持久文件。',
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
    if len(new_password) < 6:
        return api_error('新密码长度至少 6 位', status=400)
    user = current_api_user()
    if not user.check_password(current_password):
        return api_error('当前密码不正确', status=400)
    user.password = new_password
    db.session.commit()
    return api_success({}, '密码修改成功')


@api_bp.get('/auth/me')
@jwt_required
def api_me():
    user = current_api_user()
    payload = serialize_model(user, user_extra)
    token = create_access_token(user, current_app.config.get('JWT_EXPIRES_HOURS', 12))
    return with_auth_cookies({**payload, 'user': payload, 'permissions': permission_summary(user)}, '当前用户', token)


@api_bp.put('/me/profile')
@jwt_required
def api_update_profile():
    user = current_api_user()
    payload = current_payload()
    allowed = ['username', 'full_name', 'phone', 'position', 'bio', 'department_name']
    for field in allowed:
        if field in payload:
            value = payload.get(field)
            setattr(user, field, str(value).strip() if value is not None else None)
    prefs = payload.get('preferences')
    if isinstance(prefs, dict):
        current = user.preferences or {}
        for key in ('theme', 'density', 'default_workspace'):
            if key in prefs:
                current[key] = prefs[key]
        user.preferences = current
    AuditService.record('profile', 'update', user, {'fields': [field for field in allowed if field in payload]})
    db.session.commit()
    return api_success(serialize_model(user, user_extra), '个人资料已更新')


@api_bp.post('/me/avatar')
@jwt_required
def api_upload_avatar():
    file = request.files.get('file')
    if not file or not file.filename:
        return api_error('请选择头像文件', status=400, error='missing_file')
    safe_name = safe_upload_name(file.filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext.lstrip('.') not in {'png', 'jpg', 'jpeg', 'gif'}:
        return api_error('头像仅支持 png、jpg、jpeg、gif', status=400, error='unsupported_avatar_type')
    max_bytes = int(current_app.config.get('AVATAR_MAX_BYTES', 3 * 1024 * 1024))
    if upload_size(file) > max_bytes:
        return api_error('头像文件不能超过 3MB', status=400, error='avatar_too_large')
    if not validate_upload_type(file, ext):
        return api_error('头像内容类型不允许', status=400, error='unsupported_mime_type')
    user = current_api_user()
    old_avatar = user.avatar
    if is_cloud_storage_enabled():
        cloud_url = upload_avatar_to_cloud(file)
        if not cloud_url:
            return api_error('头像保存失败，请稍后重试', status=500, error='avatar_store_failed')
        user.avatar = cloud_url
    elif uploads_require_cloud_storage():
        return api_error('当前运行环境需要配置 Cloudinary 才能长期保存头像', status=503, error='persistent_storage_required')
    else:
        avatar_dir = avatar_storage_dir()
        os.makedirs(avatar_dir, exist_ok=True)
        stored_name = f'avatar-{user.id}-{uuid.uuid4().hex}{ext}'
        filepath = os.path.join(avatar_dir, stored_name)
        file.save(filepath)
        user.avatar = f'/api/v1/avatars/{stored_name}'
    AuditService.record('profile', 'avatar_upload', current_api_user(), {'filename': safe_name})
    db.session.commit()
    remove_local_avatar(old_avatar)
    return api_success(serialize_model(current_api_user(), user_extra), '头像已更新')


@api_bp.delete('/me/avatar')
@jwt_required
def api_delete_avatar():
    user = current_api_user()
    old_avatar = user.avatar
    user.avatar = None
    AuditService.record('profile', 'avatar_delete', user, {})
    db.session.commit()
    remove_local_avatar(old_avatar)
    return api_success(serialize_model(user, user_extra), '头像已恢复默认')


@api_bp.get('/avatars/<path:filename>')
def api_avatar_file(filename):
    if filename.startswith('initials/'):
        return initials_avatar_response(filename.split('/', 1)[1])
    safe_name = secure_filename(filename)
    avatar_dir = avatar_storage_dir()
    avatar_root = os.path.abspath(avatar_dir)
    filepath = os.path.abspath(os.path.join(avatar_dir, safe_name))
    if safe_name and os.path.commonpath([avatar_root, filepath]) == avatar_root and os.path.exists(filepath):
        return send_from_directory(avatar_dir, safe_name)
    return initials_avatar_response(avatar_fallback_key(safe_name))


@api_bp.get('/avatars/initials/<path:key>')
def api_initials_avatar(key):
    return initials_avatar_response(key)


def avatar_fallback_key(filename):
    parts = (filename or '').split('-')
    if len(parts) >= 3 and parts[0] == 'avatar' and parts[1].isdigit():
        user = db.session.get(User, int(parts[1]))
        if user:
            label = user.full_name or user.username or user.email or f'user-{user.id}'
            return f'{user.id}-{label[:8]}'
    return os.path.splitext(filename or '')[0] or 'nexus-user'


def initials_avatar_response(key):
    label = key.split('-', 1)[1] if '-' in key else key
    initials = ''.join(ch for ch in label if ch.isalnum())[:2].upper() or 'NX'
    palette = ['#62d8cb', '#9aa8ff', '#f0b76a', '#ff8fa3', '#c5a8ff', '#67d19b']
    accent = palette[sum(ord(ch) for ch in key) % len(palette)]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="{accent}" offset="0"/>
      <stop stop-color="#111827" offset="1"/>
    </linearGradient>
  </defs>
  <rect width="128" height="128" rx="36" fill="url(#g)"/>
  <circle cx="96" cy="28" r="30" fill="rgba(255,255,255,.22)"/>
  <text x="64" y="76" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="34" font-weight="800" fill="#fff">{initials}</text>
</svg>'''
    return Response(svg, mimetype='image/svg+xml')


@api_bp.get('/<resource>')
@jwt_required
def list_resource(resource):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404, error='resource_not_found')
    denied = require_resource_access(config, 'list')
    if denied:
        return denied
    model = config['model']
    data = paginate(query_for(config), serializer_for(config), getattr(model, 'created_at', None).desc() if hasattr(model, 'created_at') else None)
    return api_success(data, f'{resource} 列表')


@api_bp.get('/<resource>/<int:item_id>')
@jwt_required
def get_resource(resource, item_id):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404, error='resource_not_found')
    item = db.session.get(config['model'], item_id)
    if not item or getattr(item, 'is_deleted', False):
        return api_error('记录不存在', status=404, error='not_found')
    denied = require_resource_access(config, 'get', item)
    if denied:
        return denied
    return api_success(serializer_for(config)(item), f'{resource} 详情')


@api_bp.get('/articles/<int:article_id>/comments')
@jwt_required
def list_article_comments(article_id):
    article = db.session.get(Article, article_id)
    if not article or article.is_deleted:
        return api_error('文章不存在', status=404, error='article_not_found')
    rows = (
        ArticleComment.query
        .filter_by(article_id=article_id, is_deleted=False)
        .order_by(ArticleComment.created_at.asc())
        .limit(200)
        .all()
    )
    return api_success({'items': [serialize_model(item, comment_extra) for item in rows]}, '协作讨论')


@api_bp.post('/articles/<int:article_id>/comments')
@jwt_required
def create_article_comment(article_id):
    article = db.session.get(Article, article_id)
    if not article or article.is_deleted:
        return api_error('文章不存在', status=404, error='article_not_found')
    payload = current_payload()
    content = (payload.get('content') or '').strip()
    if len(content) < 2:
        return api_error('请输入有效评论内容', status=400, error='empty_comment')
    comment = ArticleComment(
        article_id=article_id,
        author_id=current_api_user().id,
        parent_id=payload.get('parent_id'),
        content=content,
        status='published',
    )
    article.view_count = (article.view_count or 0) + 1
    db.session.add(comment)
    db.session.flush()
    AuditService.record('content', 'comment', current_api_user(), {'article_id': article_id, 'comment_id': comment.id})
    db.session.commit()
    return api_success(serialize_model(comment, comment_extra), '评论已发布', status=201)


@api_bp.post('/<resource>')
@jwt_required
def create_resource(resource):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404, error='resource_not_found')
    denied = require_resource_access(config, 'create')
    if denied:
        return denied
    model = config['model']
    payload = current_payload()
    if model is Order and payload.get('items'):
        return create_sales_order()
    if model is PurchaseOrder and payload.get('items'):
        denied = require_permission('purchase.write', '需要采购创建权限')
        if denied:
            return denied
        ok, result = PurchaseService.create_purchase_order(
            int(payload.get('supplier_id')),
            int(payload.get('warehouse_id')),
            payload.get('items', []),
            current_api_user(),
            expected_date=parse_date(payload.get('expected_date')),
            remark=payload.get('remark')
        )
        if ok:
            AuditService.record('procurement', 'create_order', current_api_user(), {'id': result.id, 'po_no': result.po_no})
            db.session.commit()
        return api_success(serialize_model(result, purchase_extra), '采购单创建成功', status=201) if ok else api_error(result, status=400)
    if model is PurchaseOrder and not payload.get('items'):
        return api_error('采购单必须包含明细，请通过采购领域接口创建', status=400, error='missing_items')
    if not config.get('create'):
        return api_error('该资源必须通过领域动作接口写入', status=403, error='unsafe_resource_write')
    unsafe_fields = invalid_write_fields(config, payload, 'create')
    if unsafe_fields:
        return api_error('该资源必须通过领域动作接口写入', status=403, error='unsafe_resource_write', fields=unsafe_fields)
    values = normalize_model_values(model, read_fields(model, payload, config.get('create', [])))
    if model is Article:
        values['author_id'] = current_api_user().id
    if model is ArticleComment:
        article = db.session.get(Article, values.get('article_id'))
        if not article or article.is_deleted:
            return api_error('文章不存在', status=404, error='article_not_found')
        values['author_id'] = current_api_user().id
    if model is Notification and not values.get('user_id'):
        values['user_id'] = current_api_user().id
    if model is AiChatSession:
        values['user_id'] = current_api_user().id
    if model is ReportSubscription and (not is_admin_user(current_api_user()) or not values.get('user_id')):
        values['user_id'] = current_api_user().id
    if model is Receivable and not values.get('receivable_no'):
        values['receivable_no'] = FinanceService.generate_receivable_no()
    if model is PaymentRecord and not values.get('payment_no'):
        values['payment_no'] = FinanceService.generate_payment_no()
    if model is AccountStatement and not values.get('statement_no'):
        values['statement_no'] = FinanceService.generate_statement_no()
    if model is PurchaseOrder and not values.get('po_no'):
        values['po_no'] = PurchaseService.generate_po_no()
    if model is StockTake and not values.get('take_no'):
        values['take_no'] = StockTakeService.generate_take_no()
        values['created_by'] = current_api_user().id
    if model is User:
        values.pop('password', None)
    item = model(**values)
    if model is User and payload.get('password'):
        item.password = payload['password']
    db.session.add(item)
    db.session.flush()
    AuditService.record(resource, 'create', current_api_user(), {'id': item.id})
    db.session.commit()
    return api_success(serializer_for(config)(item), '创建成功', status=201)


@api_bp.put('/<resource>/<int:item_id>')
@api_bp.patch('/<resource>/<int:item_id>')
@jwt_required
def update_resource(resource, item_id):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404, error='resource_not_found')
    item = db.session.get(config['model'], item_id)
    if not item or getattr(item, 'is_deleted', False):
        return api_error('记录不存在', status=404, error='not_found')
    denied = require_resource_access(config, 'update', item)
    if denied:
        return denied
    payload = current_payload()
    allowed_update = config.get('update', [])
    if config['model'] is Notification and not is_admin_user(current_api_user()):
        allowed_update = ['is_read']
    ignored_fields = {'items'}
    unsafe_fields = sorted((set(payload.keys()) & set(config.get('blocked_write_fields', []))) | (set(payload.keys()) - set(allowed_update) - ignored_fields))
    if unsafe_fields:
        return api_error('该资源必须通过领域动作接口写入', status=403, error='unsafe_resource_write', fields=unsafe_fields)
    for field, value in read_fields(config['model'], payload, allowed_update).items():
        values = normalize_model_values(config['model'], {field: value})
        value = values[field]
        setattr(item, field, value)
    if config['model'] is Notification and item.is_read and item.read_at is None:
        item.read_at = utcnow()
    if isinstance(item, User) and payload.get('password'):
        item.password = payload['password']
    AuditService.record(resource, 'update', current_api_user(), {'id': item_id, 'fields': list(payload.keys())})
    db.session.commit()
    return api_success(serializer_for(config)(item), '更新成功')


@api_bp.delete('/<resource>/<int:item_id>')
@jwt_required
def delete_resource(resource, item_id):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404, error='resource_not_found')
    item = db.session.get(config['model'], item_id)
    if not item or getattr(item, 'is_deleted', False):
        return api_error('记录不存在', status=404, error='not_found')
    denied = require_resource_access(config, 'delete', item)
    if denied:
        return denied
    if hasattr(item, 'is_deleted'):
        item.is_deleted = True
    else:
        db.session.delete(item)
    AuditService.record(resource, 'delete', current_api_user(), {'id': item_id})
    db.session.commit()
    return api_success({'id': item_id}, '删除成功')


@api_bp.post('/inventory/adjust')
@jwt_required
def adjust_inventory():
    denied = require_permission('inventory.adjust', '需要库存调整权限')
    if denied:
        return denied
    payload = current_payload()
    ok, message = InventoryService.adjust_stock(
        int(payload.get('product_id')),
        int(payload.get('warehouse_id')),
        int(payload.get('quantity')),
        payload.get('move_type', 'inbound'),
        current_api_user(),
        payload.get('remark', '')
    )
    if not ok:
        return api_error(message, status=400)
    AuditService.record('inventory', 'adjust', current_api_user(), payload)
    db.session.commit()
    return api_success(None, message)


@api_bp.post('/sales/orders')
@jwt_required
def create_sales_order():
    denied = require_permission('sales.write', '需要销售订单权限')
    if denied:
        return denied
    payload = current_payload()
    customer_id = payload.get('customer_id')
    if not customer_id:
        name = (payload.get('customer_name') or '').strip()
        if not name:
            return api_error('请选择或输入客户', status=400)
        partner = Partner.query.filter_by(name=name).first()
        if not partner:
            partner = Partner(name=name, type='customer')
            db.session.add(partner)
            db.session.flush()
        customer_id = partner.id
    try:
        order = SalesService.create_order(int(customer_id), current_api_user(), payload.get('items', []), payload.get('status', 'pending'))
        AuditService.record('sales', 'create_order', current_api_user(), {'id': order.id, 'order_no': order.order_no})
        db.session.commit()
        return api_success(serialize_model(order, order_extra), '订单创建成功', status=201)
    except Exception as exc:
        return api_error(str(exc) if isinstance(exc, ValueError) else '订单创建失败', status=400, error='order_create_failed')


@api_bp.post('/purchase-orders/<int:po_id>/submit')
@jwt_required
def submit_purchase_order(po_id):
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    ok, message = PurchaseService.submit_for_approval(po_id, current_api_user())
    if ok:
        AuditService.record('procurement', 'submit', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/approve')
@jwt_required
def approve_purchase_order(po_id):
    denied = require_permission('purchase.approve', '需要采购审批权限')
    if denied:
        return denied
    ok, message = PurchaseService.approve(po_id, current_api_user(), True, current_payload().get('remark'))
    if ok:
        AuditService.record('procurement', 'approve', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/reject')
@jwt_required
def reject_purchase_order(po_id):
    denied = require_permission('purchase.approve', '需要采购审批权限')
    if denied:
        return denied
    ok, message = PurchaseService.approve(po_id, current_api_user(), False, current_payload().get('remark'))
    if ok:
        AuditService.record('procurement', 'reject', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/purchase-orders/<int:po_id>/receive')
@jwt_required
def receive_purchase_order(po_id):
    denied = require_permission('purchase.receive', '需要采购收货权限')
    if denied:
        return denied
    ok, message = PurchaseService.receive_items(po_id, current_payload().get('items', []), current_api_user())
    if ok:
        AuditService.record('procurement', 'receive', current_api_user(), {'id': po_id})
        db.session.commit()
    return api_success(None, message) if ok else api_error(message, status=400)


@api_bp.post('/receivables/<int:receivable_id>/payment')
@jwt_required
def api_record_payment(receivable_id):
    denied = require_permission('finance.payment', '需要收款权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = FinanceService.record_payment(
        receivable_id,
        float(payload.get('amount', 0)),
        payload.get('payment_method', 'bank'),
        current_api_user(),
        payload.get('reference_no'),
        payload.get('remark')
    )
    if ok:
        AuditService.record('finance', 'record_payment', current_api_user(), {'receivable_id': receivable_id, 'amount': payload.get('amount')})
        db.session.commit()
    return api_success(serialize_model(result), '收款成功') if ok else api_error(result, status=400)


@api_bp.post('/statements/generate')
@jwt_required
def api_generate_statement():
    denied = require_permission('reports.generate', '需要报表生成权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = FinanceService.generate_statement(
        int(payload.get('customer_id')),
        parse_date(payload.get('period_start')),
        parse_date(payload.get('period_end')),
        current_api_user()
    )
    if ok:
        AuditService.record('reports', 'generate_statement', current_api_user(), {'id': result.id, 'customer_id': payload.get('customer_id')})
        db.session.commit()
    return api_success(serialize_model(result), '对账单生成成功', status=201) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/create')
@jwt_required
def api_create_stocktake():
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    payload = current_payload()
    ok, result = StockTakeService.create_stocktake(
        int(payload.get('warehouse_id')),
        payload.get('take_type', StockTake.TYPE_FULL),
        payload.get('product_ids') or [],
        current_api_user(),
        payload.get('remark'),
        payload.get('planned_date')
    )
    if ok:
        AuditService.record('stocktake', 'create', current_api_user(), {'id': result.id})
        db.session.commit()
    return api_success(serialize_model(result, stocktake_extra), '盘点单创建成功', status=201) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/<int:take_id>/start')
@jwt_required
def api_start_stocktake(take_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    ok, result = StockTakeService.start_stocktake(take_id, current_api_user())
    if ok:
        AuditService.record('stocktake', 'start', current_api_user(), {'id': take_id})
        db.session.commit()
    return api_success(None, result) if ok else api_error(result, status=400)


@api_bp.post('/stocktakes/<int:take_id>/complete')
@jwt_required
def api_complete_stocktake(take_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    ok, result = StockTakeService.complete_stocktake(take_id, current_api_user(), parse_bool(current_payload().get('auto_adjust'), True))
    if ok:
        AuditService.record('stocktake', 'complete', current_api_user(), {'id': take_id})
        db.session.commit()
    return api_success(None, result) if ok else api_error(result, status=400)


@api_bp.post('/stocktake-items/<int:item_id>/count')
@jwt_required
def api_count_stocktake_item(item_id):
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    payload = current_payload()
    item = db.session.get(StockTakeItem, item_id)
    if not item:
        return api_error('盘点明细不存在', status=404)
    ok, result = StockTakeService.input_count(item.take_id, item_id, int(payload.get('actual_qty')), current_api_user(), payload.get('remark'))
    if ok:
        db.session.commit()
    return api_success(serialize_model(result), '录入成功') if ok else api_error(result, status=400)


@api_bp.post('/stock-alerts/check')
@jwt_required
def api_check_alerts():
    denied = require_permission('inventory.adjust', '需要库存预警权限')
    if denied:
        return denied
    count = StockAlertService.check_all_stock_alerts()
    AuditService.record('inventory', 'check_alerts', current_api_user(), {'created': count})
    db.session.commit()
    return api_success({'created': count}, '库存预警检查完成')


@api_bp.post('/replenishment-suggestions/generate')
@jwt_required
def api_generate_replenishment():
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    StockAlertService.check_all_stock_alerts()
    count = StockAlertService.generate_replenishment_suggestions()
    AuditService.record('inventory', 'generate_replenishment', current_api_user(), {'created': count})
    db.session.commit()
    return api_success({'created': count}, '补货建议生成完成')


@api_bp.post('/replenishment-suggestions/<int:suggestion_id>/accept')
@jwt_required
def api_accept_replenishment(suggestion_id):
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    suggestion = db.session.get(ReplenishmentSuggestion, suggestion_id)
    if not suggestion:
        return api_error('补货建议不存在', status=404)
    items = [{
        'product_id': suggestion.product_id,
        'quantity': suggestion.suggested_qty or 1,
        'unit_price': suggestion.product.cost or 0,
    }]
    ok, result = PurchaseService.create_purchase_order(
        suggestion.supplier_id,
        suggestion.warehouse_id or Warehouse.query.first().id,
        items,
        current_api_user(),
        remark=f'由补货建议 #{suggestion.id} 自动创建'
    )
    if not ok:
        return api_error(result, status=400)
    suggestion.status = ReplenishmentSuggestion.STATUS_ORDERED
    suggestion.processed_at = utcnow()
    suggestion.processed_by = current_api_user().id
    suggestion.purchase_order_id = result.id
    AuditService.record('inventory', 'accept_replenishment', current_api_user(), {'suggestion_id': suggestion_id, 'purchase_order_id': result.id})
    db.session.commit()
    return api_success({'purchase_order': serialize_model(result, purchase_extra)}, '已接受建议并创建采购单')

