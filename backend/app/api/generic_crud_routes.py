from app.extensions import db
from app.models.auth import User
from app.domains.files.application.events import publish_file_deleted
from app.models.content import Article, ArticleComment, Attachment
from app.models.finance import AccountStatement, PaymentRecord, Receivable
from app.models.notification import Notification, ReportSubscription
from app.models.purchase import PurchaseOrder
from app.models.stocktake import StockTake
from app.models.sys import AiChatSession
from app.models.trade import Order
from app.services.audit_service import AuditService
from app.services.finance_service import FinanceService
from app.services.purchase_service import PurchaseService
from app.services.stocktake_service import StockTakeService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .resource_support import (
    comment_extra,
    current_payload,
    invalid_write_fields,
    is_admin_user,
    normalize_model_values,
    paginate,
    parse_date,
    purchase_extra,
    query_for,
    read_fields,
    require_permission,
    require_resource_access,
    resource_config,
    serializer_for,
    serialize_model,
)


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
    denied = require_resource_access(resource_config('articles'), 'get', article)
    if denied:
        return denied
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
    denied = require_resource_access(resource_config('articles'), 'get', article)
    if denied:
        return denied
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
        from .business_action_routes import create_sales_order
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
    if isinstance(item, Attachment):
        publish_file_deleted(item, deleted_by=current_api_user())
    AuditService.record(resource, 'delete', current_api_user(), {'id': item_id})
    db.session.commit()
    return api_success({'id': item_id}, '删除成功')
