import os
import random
import uuid

from flask import Response, current_app, make_response, request, send_from_directory
from sqlalchemy import func, or_
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
from app.domains.identity.domain.captcha import (
    CAPTCHA_CHALLENGE_TYPES,
    CAPTCHA_TERMS_VERSION,
    CAPTCHA_TTL_SECONDS,
    captcha_answer_hash,
    captcha_secret,
    captcha_signature,
    captcha_svg,
    decode_captcha_token,
    encode_captcha_token,
    new_captcha_challenge as identity_new_captcha_challenge,
    normalize_captcha_answer,
)
from app.domains.identity.domain.registration import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    USERNAME_PATTERN,
    normalize_register_payload,
    validate_register_gate,
    validate_register_profile,
)
from app.domains.resources import register_resources
from app.platform.crud.permissions import (
    PERMISSION_LABELS,
    can_user as platform_can_user,
    is_admin_user,
    permission_summary,
    resource_access_error,
)
from app.platform.crud.query_builder import (
    apply_search,
    invalid_write_fields,
    paginate,
    pagination_args,
    read_fields,
    normalize_model_values,
)
from app.platform.crud.resource_api import query_for_resource, serializer_for_config
from app.platform.crud.resource_registry import registry as resource_registry
from app.platform.crud.serializers import parse_bool, parse_date, parse_datetime, serialize_model, serialize_value
from app.platform.storage.local_storage import resolve_local_object
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


def current_payload():
    return request.get_json(silent=True) or {}


def new_captcha_challenge():
    return identity_new_captcha_challenge(random)


def can_user(permission):
    return platform_can_user(current_api_user(), permission)


def require_permission(permission, message='权限不足'):
    if not can_user(permission):
        return api_error(message, status=403, error='permission_denied')
    return None


def require_resource_access(config, action, item=None):
    user = current_api_user()
    denied = resource_access_error(config, action, user, item)
    if denied:
        message, error = denied
        return api_error(message, status=403, error=error)
    return None


def public_api_url(path):
    if not path:
        return None
    if str(path).startswith(('http://', 'https://')):
        return path
    normalized = '/' + str(path).lstrip('/')
    root = request.host_url.rstrip('/')
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip()
    if forwarded_proto in {'http', 'https'} and root.startswith(('http://', 'https://')):
        root = root.replace('http://', f'{forwarded_proto}://', 1).replace('https://', f'{forwarded_proto}://', 1)
    elif request.is_secure and root.startswith('http://'):
        root = root.replace('http://', 'https://', 1)
    return f'{root}{normalized}'


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


def workflow_instance_extra(item):
    return {
        'process_key': item.definition.process_key if item.definition else None,
        'definition_name': item.definition.name if item.definition else None,
        'applicant_name': item.applicant.username if item.applicant else None,
    }


def workflow_task_extra(item):
    instance = item.instance
    return {
        'business_type': instance.business_type if instance else None,
        'business_id': instance.business_id if instance else None,
        'process_key': instance.definition.process_key if instance and instance.definition else None,
        'assignee_name': item.assignee.username if item.assignee else None,
        'action_by_name': item.actor.username if item.actor else None,
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
    resolved_object = resolve_local_object(relative)
    if resolved_object:
        return resolved_object
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


RESOURCE_ALIASES = {
    'reports': 'generated-reports',
}

resource_registry.set_aliases(RESOURCE_ALIASES)
register_resources(resource_registry, reset=True)
RESOURCE_CONFIG = resource_registry


SERIALIZER_EXTRAS = {
    'ai_session': ai_session_extra,
    'article': article_extra,
    'attachment': attachment_extra,
    'audit': audit_extra,
    'comment': comment_extra,
    'credit': credit_extra,
    'notification': notification_extra,
    'order': order_extra,
    'order_item': order_item_extra,
    'product': product_extra,
    'purchase': purchase_extra,
    'purchase_item': purchase_item_extra,
    'receivable': receivable_extra,
    'replenishment': replenishment_extra,
    'report': report_extra,
    'stock': stock_extra,
    'stocktake': stocktake_extra,
    'stocktake_item': stocktake_item_extra,
    'supplier_performance': supplier_performance_extra,
    'user': user_extra,
    'workflow_instance': workflow_instance_extra,
    'workflow_task': workflow_task_extra,
}


def resource_config(resource):
    return resource_registry.get(resource)


def serializer_for(config):
    return serializer_for_config(config, SERIALIZER_EXTRAS, current_api_user())


def query_for(config):
    return query_for_resource(config, current_api_user(), request.args)
