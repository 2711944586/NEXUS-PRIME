from datetime import datetime

from flask import current_app, request
from sqlalchemy import func, or_

from app.extensions import db
from app.models.auth import User
from app.models.biz import Category, Product, Partner
from app.models.content import Article, Attachment
from app.models.finance import PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion, ReportSubscription, StockAlert
from app.models.purchase import PurchaseOrder
from app.models.stock import InventoryLog, Stock
from app.models.stocktake import StockTake, StockTakeItem
from app.models.sys import AiChatMessage, AiChatSession, AuditLog
from app.models.trade import Order
from app.models.workflow import WorkflowTask
from app.models.jobs import BackgroundJob
from app.platform.jobs import create_background_job, get_background_job, serialize_background_job
from app.platform.jobs.data_quality import run_data_quality_scan
from app.platform.jobs.replenishment import run_replenishment_generation
from app.platform.policy import policy
from app.platform.search import search_service
from app.services.analytics_service import executive_analytics_payload
from app.services.ai_service import ai_service  # kept for local_ai_reply usage in ops
from app.services.capacity_service import capacity_governance_payload, select_capacity_review_context
from app.services.cost_service import cost_governance_payload, select_cost_review_context
from app.services.data_quality_service import data_quality_payload
from app.services.audit_service import AuditService
from app.services.deployment_service import deployment_readiness_payload
from app.services.maintenance_service import maintenance_reliability_payload, select_maintenance_workorder_context
from app.services.mobile_terminal_service import mobile_terminal_payload, select_mobile_task_context
from app.services.quality_inspection_service import quality_inspection_payload, select_quality_inspection_context
from app.services.rules_service import rules_governance_payload, select_rule_review_context
from app.services.service_catalog import SERVICE_CATALOG, integration_payload
from app.services.purchase_service import PurchaseService, procurement_control_payload, select_procurement_control_context
from app.services.supplier_service import supplier_collaboration_payload, select_supplier_collaboration_context
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .insights import dashboard_charts, dashboard_summary
from .routes import (
    api_accept_replenishment,
    api_generate_replenishment,
    api_record_payment,
    approve_purchase_order,
    create_resource,
    create_sales_order,
    delete_resource,
    get_resource,
    list_resource,
    notification_extra,
    receive_purchase_order,
    reject_purchase_order,
    resource_config,
    serialize_model,
    serialize_value,
    submit_purchase_order,
    update_resource,
    user_extra,
    require_permission,
)


NEW_RESOURCE_ROUTES = {
    'inventory/products': 'products',
    'inventory/stock': 'stock',
    'inventory/replenishment': 'replenishment-suggestions',
    'inventory/replenishment-suggestions': 'replenishment-suggestions',
    'sales/orders': 'orders',
    'procurement/orders': 'purchase-orders',
    'finance/receivables': 'receivables',
    'stocktakes': 'stocktakes',
    'notifications': 'notifications',
    'reports': 'generated-reports',
    'content/articles': 'articles',
    'files': 'files',
    'ai/sessions': 'ai-sessions',
    'system/users': 'users',
    'system/audit': 'audit-logs',
}


NAVIGATION = [
    {'key': 'overview', 'label': '制造运营驾驶舱', 'path': '/app/overview', 'group': '工作台', 'icon': 'dashboard'},
    {'key': 'inventory.products', 'label': '物料与成品中心', 'path': '/app/inventory/products', 'group': '仓配', 'icon': 'inbox', 'resource': 'products'},
    {'key': 'inventory.stock', 'label': '仓配流向图', 'path': '/app/inventory/stock', 'group': '仓配', 'icon': 'database', 'resource': 'stock'},
    {'key': 'inventory.replenishment', 'label': '采购补货中心', 'path': '/app/inventory/replenishment', 'group': '仓配', 'icon': 'alert', 'resource': 'replenishment-suggestions'},
    {'key': 'sales.orders', 'label': '销售履约中心', 'path': '/app/sales/orders', 'group': '营收', 'icon': 'file-done', 'resource': 'orders'},
    {'key': 'procurement.orders', 'label': '采购补货中心', 'path': '/app/procurement/orders', 'group': '仓配', 'icon': 'shopping-cart', 'resource': 'purchase-orders'},
    {'key': 'finance.receivables', 'label': '应收风控中心', 'path': '/app/finance/receivables', 'group': '营收', 'icon': 'account-book', 'resource': 'receivables'},
    {'key': 'stocktakes', 'label': '库存盘点中心', 'path': '/app/stocktakes', 'group': '仓配', 'icon': 'audit', 'resource': 'stocktakes'},
    {'key': 'notifications', 'label': '通知中心', 'path': '/app/notifications', 'group': '工作台', 'icon': 'bell', 'resource': 'notifications'},
    {'key': 'reports', 'label': '报表工作室', 'path': '/app/reports', 'group': '经营分析', 'icon': 'bar-chart', 'resource': 'generated-reports'},
    {'key': 'content.articles', 'label': '内容公告', 'path': '/app/content/articles', 'group': '工作台', 'icon': 'read', 'resource': 'articles'},
    {'key': 'files', 'label': '文件与内容中心', 'path': '/app/files', 'group': '工作台', 'icon': 'folder-open', 'resource': 'files'},
    {'key': 'ai', 'label': '经营分析', 'path': '/app/ai', 'group': '经营分析', 'icon': 'bar-chart', 'resource': 'ai-sessions'},
    {'key': 'system.users', 'label': '系统安全中心', 'path': '/app/system/users', 'group': '系统', 'icon': 'setting', 'resource': 'users', 'admin_only': True},
    {'key': 'system.audit', 'label': '审计日志', 'path': '/app/system/audit', 'group': '系统', 'icon': 'history', 'resource': 'audit-logs', 'admin_only': True},
]


def is_admin(user):
    return bool(user and (user.is_admin or (user.role and user.role.is_admin)))


def route_resource(path):
    return NEW_RESOURCE_ROUTES.get(path)


def resolve_resource(path):
    resource = route_resource(path)
    if resource:
        return resource
    return path if resource_config(path) else None


def resource_count(resource):
    config = resource_config(resource)
    if not config:
        return 0
    model = config['model']
    query = model.query
    if hasattr(model, 'is_deleted'):
        query = query.filter(model.is_deleted == False)
    user = current_api_user()
    if config.get('admin_only') and not is_admin(user):
        return None
    if model is Notification and not is_admin(user):
        query = query.filter(Notification.user_id == user.id)
    elif model is Attachment and not is_admin(user):
        query = query.filter(Attachment.uploader_id == user.id)
    elif model is AiChatSession and not is_admin(user):
        query = query.filter(AiChatSession.user_id == user.id)
    elif model is AiChatMessage and not is_admin(user):
        query = query.join(AiChatSession, AiChatMessage.session_id == AiChatSession.id).filter(AiChatSession.user_id == user.id)
    elif model is ReportSubscription and not is_admin(user):
        query = query.filter(ReportSubscription.user_id == user.id)
    elif model is GeneratedReport and not is_admin(user):
        query = (
            query.outerjoin(ReportSubscription, GeneratedReport.subscription_id == ReportSubscription.id)
            .filter(or_(GeneratedReport.generated_by == user.id, ReportSubscription.user_id == user.id))
        )
    return query.count()


def current_preferences():
    prefs = current_api_user().preferences
    return prefs if isinstance(prefs, dict) else {}


def require_policy_decision(decision):
    if not decision.allowed:
        return api_error(decision.reason or '权限不足', status=403, error=decision.error or 'forbidden')
    return None


def can_access_background_job(job, user):
    return bool(job and (job.created_by == user.id or is_admin(user)))


def data_quality_job_payload(job):
    return {
        'job_id': job.job_id,
        'job': serialize_background_job(job),
        'result': job.result or None,
    }


def replenishment_job_payload(job):
    return {
        'job_id': job.job_id,
        'job': serialize_background_job(job),
        'result': job.result or None,
        'created': (job.result or {}).get('created') if job.result else None,
    }


@api_bp.get('/overview/summary')
@jwt_required
def overview_summary():
    return dashboard_summary()


@api_bp.get('/overview/charts')
@jwt_required
def overview_charts():
    return dashboard_charts()


# AI routes moved to app/api/ai.py
# Operations routes: see individual @api_bp handlers below

@api_bp.post('/operations/dispatch-task')
@jwt_required
def operations_dispatch_task():
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '仓配调度任务').strip()[:128]
    content = (payload.get('content') or '请复核仓配流向、库存预警和库位热区。').strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_STOCK,
        related_type=payload.get('related_type') or 'stock',
        related_id=payload.get('related_id') or None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'dispatch_task', current_api_user(), {'notification_id': notification.id, 'title': title})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '调度任务已创建', status=201)


@api_bp.post('/operations/data-quality-notice')
@jwt_required
def operations_data_quality_notice():
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '数据质量复核任务').strip()[:128]
    content = (payload.get('content') or '请复核主数据、仓配、履约和财务链路的数据质量。').strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_SYSTEM,
        related_type='quality',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'data_quality_notice', current_api_user(), {'notification_id': notification.id, 'title': title})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '数据质量通知已创建', status=201)


@api_bp.get('/operations/procurement-control')
@jwt_required
def operations_procurement_control_payload():
    return api_success(procurement_control_payload(), '采购协同控制台')


@api_bp.post('/operations/procurement-control/task')
@jwt_required
def operations_procurement_control_task():
    payload = request.get_json(silent=True) or {}
    queue_item_id = (payload.get('queue_item_id') or payload.get('item_id') or '').strip()[:96]
    purchase_id = payload.get('purchase_id') or payload.get('related_id')
    supplier_id = payload.get('supplier_id')
    _, item = select_procurement_control_context(
        item_id=queue_item_id,
        title=payload.get('title'),
        purchase_id=purchase_id,
        supplier_id=supplier_id,
    )
    purchase_id = purchase_id or (item or {}).get('purchase_id')
    purchase = db.session.get(PurchaseOrder, int(purchase_id)) if purchase_id else None
    title = (payload.get('title') or (item or {}).get('title') or '采购协同复核任务').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '采购负责人').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '采购协同控制台发现待处理对象。').strip()[:300]
    action = (payload.get('action') or (item or {}).get('action') or '复核补货、审批、收货、供应商和预算承诺。').strip()[:360]
    path = (payload.get('path') or (item or {}).get('path') or '/app/procurement/orders').strip()[:180]
    kind = (payload.get('kind') or (item or {}).get('kind') or (item or {}).get('source') or '采购协同').strip()[:48]
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING if priority == 'P1' else Notification.TYPE_INFO
    notification = Notification(
        user_id=current_api_user().id,
        title=f'采购协同任务 - {title}' if not title.startswith('采购协同任务') else title,
        content=f'[{owner}/{priority}/{sla}/{kind}] {evidence}\n处理动作：{action}\n来源：{path}',
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else notification_type,
        category=Notification.CATEGORY_APPROVAL,
        related_type='procurement_control',
        related_id=purchase.id if purchase else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'procurement_control_task', current_api_user(), {
        'notification_id': notification.id,
        'queue_item_id': queue_item_id or (item or {}).get('id'),
        'purchase_id': purchase.id if purchase else purchase_id,
        'supplier_id': supplier_id or (item or {}).get('supplier_id'),
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '采购协同任务已创建', status=201)


@api_bp.get('/operations/supplier-collaboration')
@jwt_required
def operations_supplier_collaboration_payload():
    return api_success(supplier_collaboration_payload(), '供应商协同工作台')


@api_bp.post('/operations/supplier-collaboration/task')
@jwt_required
def operations_supplier_collaboration_task():
    payload = request.get_json(silent=True) or {}
    queue_item_id = (payload.get('queue_item_id') or payload.get('item_id') or '').strip()[:96]
    supplier_id = payload.get('supplier_id') or payload.get('related_id')
    _, item = select_supplier_collaboration_context(
        item_id=queue_item_id,
        supplier_id=supplier_id,
        title=payload.get('title'),
    )
    supplier_id = supplier_id or (item or {}).get('supplier_id')
    supplier = db.session.get(Partner, int(supplier_id)) if supplier_id else None
    title = (payload.get('title') or (item or {}).get('title') or '供应商协同复核任务').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '供应商经理').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '供应商协同工作台发现待处理对象。').strip()[:320]
    action = (payload.get('action') or (item or {}).get('action') or '复核供应商资质、交付、质量和商务风险。').strip()[:360]
    path = (payload.get('path') or (item or {}).get('path') or '/app/suppliers/performance').strip()[:180]
    kind = (payload.get('kind') or (item or {}).get('kind') or '供应商协同').strip()[:48]
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING if priority == 'P1' else Notification.TYPE_INFO
    notification = Notification(
        user_id=current_api_user().id,
        title=f'供应商协同任务 - {title}' if not title.startswith('供应商协同任务') else title,
        content=f'[{owner}/{priority}/{sla}/{kind}] {evidence}\n处理动作：{action}\n来源：{path}',
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else notification_type,
        category=Notification.CATEGORY_APPROVAL,
        related_type='supplier_collaboration',
        related_id=supplier.id if supplier else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'supplier_collaboration_task', current_api_user(), {
        'notification_id': notification.id,
        'queue_item_id': queue_item_id or (item or {}).get('id'),
        'supplier_id': supplier.id if supplier else supplier_id,
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '供应商协同任务已创建', status=201)


@api_bp.get('/operations/data-quality')
@jwt_required
def operations_data_quality():
    return api_success(data_quality_payload(), '数据质量治理')


@api_bp.post('/operations/data-quality/scan')
@jwt_required
def operations_data_quality_scan():
    user = current_api_user()
    job = create_background_job(
        'data_quality.scan',
        {'source': 'operations.data_quality'},
        created_by=user,
        queue='data-quality',
        task_name='nexus.data_quality.scan',
    )
    db.session.commit()
    job_id = job.job_id

    try:
        if current_app.config.get('CELERY_TASK_ALWAYS_EAGER', False):
            run_data_quality_scan(job_id=job_id, celery_task_id=f'eager-{job_id}')
        else:
            from app.platform.jobs.tasks.data_quality import data_quality_scan_task

            async_result = data_quality_scan_task.apply_async(kwargs={'job_id': job_id}, queue='data-quality')
            job.celery_task_id = async_result.id
            db.session.add(job)
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        job = get_background_job(job_id)
        if job and job.status != BackgroundJob.STATUS_FAILED:
            job.mark_failed(exc)
            db.session.add(job)
            db.session.commit()
        return api_error(str(exc), status=500, error='data_quality_job_failed', job=serialize_background_job(job) if job else None)

    job = get_background_job(job_id)
    if job.status == BackgroundJob.STATUS_SUCCESS:
        return api_success(data_quality_job_payload(job), '数据质量扫描完成')
    if job.status == BackgroundJob.STATUS_FAILED:
        return api_error(job.error_message or '数据质量扫描失败', status=500, error='data_quality_job_failed', job=serialize_background_job(job))
    return api_success(data_quality_job_payload(job), '数据质量扫描任务已入队', status=202)


@api_bp.get('/operations/data-quality/jobs/<job_id>')
@jwt_required
def operations_data_quality_job(job_id):
    job = get_background_job(job_id)
    if not job or job.job_type != 'data_quality.scan':
        return api_error('数据质量扫描任务不存在', status=404, error='job_not_found')
    if not can_access_background_job(job, current_api_user()):
        return api_error('权限不足', status=403, error='permission_denied')
    return api_success(data_quality_job_payload(job), '数据质量扫描任务状态')


@api_bp.post('/operations/data-quality/remediation')
@jwt_required
def operations_data_quality_remediation():
    payload = request.get_json(silent=True) or {}
    issue_id = (payload.get('issue_id') or 'data-quality').strip()[:64]
    title = (payload.get('title') or '数据质量整改任务').strip()[:128]
    owner = (payload.get('owner') or '数据治理台').strip()[:48]
    priority = (payload.get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or '数据质量体检发现记录需要治理。').strip()[:260]
    action = (payload.get('action') or '请进入来源模块修复记录并刷新数据质量中心。').strip()[:320]
    path = (payload.get('path') or '/app/data-quality').strip()[:160]
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING
    notification = Notification(
        user_id=current_api_user().id,
        title=f'数据质量整改 - {title}',
        content=f'[{owner}/{priority}/{sla}] {evidence}\n整改动作：{action}\n来源：{path}',
        type=notification_type,
        category=Notification.CATEGORY_SYSTEM,
        related_type='quality',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'data_quality_remediation', current_api_user(), {
        'notification_id': notification.id,
        'issue_id': issue_id,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '数据质量整改任务已创建', status=201)


@api_bp.post('/operations/customer-followup')
@jwt_required
def operations_customer_followup():
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get('customer_id') or payload.get('related_id')
    customer = db.session.get(Partner, int(customer_id)) if customer_id else None
    title = (payload.get('title') or f'客户经营跟进 - {customer.name if customer else "重点客户"}').strip()[:128]
    content = (
        payload.get('content')
        or '请复核客户订单履约、应收账龄、信用占用和近期协作记录。'
    ).strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_ORDER,
        related_type='customer',
        related_id=customer.id if customer else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'customer_followup', current_api_user(), {'notification_id': notification.id, 'customer_id': customer.id if customer else None})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '客户跟进任务已创建', status=201)


@api_bp.post('/operations/capacity-plan')
@jwt_required
def operations_capacity_plan():
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '产能计划复核任务').strip()[:128]
    content = (
        payload.get('content')
        or '请复核产能负载、低库存物料、采购到货和销售履约窗口。'
    ).strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_INFO,
        category=Notification.CATEGORY_APPROVAL,
        related_type='capacity',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'capacity_plan', current_api_user(), {'notification_id': notification.id})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '产能计划任务已创建', status=201)


@api_bp.get('/operations/capacity')
@jwt_required
def operations_capacity():
    return api_success(capacity_governance_payload(), '产能计划治理')


@api_bp.post('/operations/capacity/review')
@jwt_required
def operations_capacity_review():
    payload = request.get_json(silent=True) or {}
    item_id = (payload.get('item_id') or payload.get('work_center_id') or '').strip()[:64]
    _, item = select_capacity_review_context(item_id=item_id, title=payload.get('title'))
    title = (payload.get('title') or (item or {}).get('title') or '产能计划复核任务').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '计划主管').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '请复核需求、供给、库存和班次负载。').strip()[:280]
    action = (payload.get('action') or (item or {}).get('action') or '回到来源模块释放约束，并刷新产能计划中心。').strip()[:320]
    path = (payload.get('path') or (item or {}).get('path') or '/app/capacity').strip()[:160]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    notification = Notification(
        user_id=current_api_user().id,
        title=f'产能计划复核 - {title}',
        content=f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n来源：{path}',
        type=Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_APPROVAL,
        related_type='capacity',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'capacity_review', current_api_user(), {
        'notification_id': notification.id,
        'item_id': item_id or (item or {}).get('id'),
        'work_center_id': (item or {}).get('work_center_id'),
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '产能计划复核任务已创建', status=201)


@api_bp.post('/operations/maintenance-workorder')
@jwt_required
def operations_maintenance_workorder():
    payload = request.get_json(silent=True) or {}
    queue_item_id = (payload.get('queue_item_id') or payload.get('item_id') or '').strip()[:80]
    product_id = payload.get('product_id') or payload.get('related_id')
    _, item = select_maintenance_workorder_context(queue_item_id=queue_item_id, product_id=product_id, title=payload.get('title'))
    title = (payload.get('title') or (item or {}).get('title') or '设备维护工单').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '设备主管').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '请检查 MRO 备件库存、库位状态、维修附件和异常流水。').strip()[:320]
    action = (payload.get('action') or (item or {}).get('action') or '核对备件库存、库位、维护资料和停机窗口。').strip()[:320]
    path = (payload.get('path') or (item or {}).get('path') or '/app/maintenance').strip()[:160]
    product_id = product_id or (item or {}).get('product_id')
    product = db.session.get(Product, int(product_id)) if product_id else None
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING if priority == 'P1' else Notification.TYPE_INFO
    content = (payload.get('content') or f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n来源：{path}').strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=f'设备维护工单 - {title}' if not title.startswith('设备维护工单') else title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else notification_type,
        category=Notification.CATEGORY_STOCK,
        related_type='maintenance',
        related_id=product.id if product else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'maintenance_workorder', current_api_user(), {
        'notification_id': notification.id,
        'queue_item_id': queue_item_id or (item or {}).get('id'),
        'product_id': product.id if product else None,
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'risk_score': (item or {}).get('risk_score'),
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '维护工单已创建', status=201)


@api_bp.get('/operations/maintenance')
@jwt_required
def operations_maintenance():
    return api_success(maintenance_reliability_payload(), '设备可靠性治理')


@api_bp.get('/operations/quality-inspection')
@jwt_required
def operations_quality_inspection_payload():
    return api_success(quality_inspection_payload(), '质量检验治理')


@api_bp.post('/operations/quality-inspection')
@jwt_required
def operations_quality_inspection():
    payload = request.get_json(silent=True) or {}
    queue_item_id = (payload.get('queue_item_id') or payload.get('item_id') or '').strip()[:80]
    product_id = payload.get('product_id') or payload.get('related_id')
    supplier_id = payload.get('supplier_id')
    purchase_id = payload.get('purchase_id')
    _, item = select_quality_inspection_context(
        queue_item_id=queue_item_id,
        product_id=product_id,
        supplier_id=supplier_id,
        purchase_id=purchase_id,
        title=payload.get('title'),
    )
    product_id = product_id or (item or {}).get('product_id')
    product = db.session.get(Product, int(product_id)) if product_id else None
    title = (payload.get('title') or (item or {}).get('title') or f'质量检验任务 - {product.name if product else "来料批次"}').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '质量工程师').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '请复核来料批次、供应商准点率、质检通过率和异常附件。').strip()[:320]
    action = (payload.get('action') or (item or {}).get('action') or '完成抽检、使用决策、缺陷遏制和整改闭环。').strip()[:320]
    path = (payload.get('path') or (item or {}).get('path') or '/app/quality').strip()[:160]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING if priority == 'P1' else Notification.TYPE_INFO
    content = (payload.get('content') or f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n使用决策：{(item or {}).get("decision") or "待判定"}\n来源：{path}').strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=f'质量检验任务 - {title}' if not title.startswith('质量检验任务') else title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else notification_type,
        category=Notification.CATEGORY_APPROVAL,
        related_type='quality_inspection',
        related_id=product.id if product else None,
    )
    db.session.add(notification)
    db.session.flush()
    result = (payload.get('result') or payload.get('inspection_result') or '').strip().lower()
    quality_event_type = None
    if result in {'passed', 'pass', 'qualified', 'ok'}:
        result = 'passed'
        quality_event_type = 'QualityInspectionPassed'
    elif result in {'failed', 'fail', 'rejected', 'ng'}:
        result = 'failed'
        quality_event_type = 'QualityInspectionFailed'
    AuditService.record('operations', 'quality_inspection', current_api_user(), {
        'notification_id': notification.id,
        'queue_item_id': queue_item_id or (item or {}).get('id'),
        'product_id': product.id if product else None,
        'supplier_id': supplier_id or (item or {}).get('supplier_id'),
        'purchase_id': purchase_id or (item or {}).get('purchase_id'),
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'risk_score': (item or {}).get('risk_score'),
        'decision': (item or {}).get('decision'),
        'evidence': evidence,
        'action': action,
    })
    if quality_event_type:
        from app.platform.events import outbox

        outbox.add(
            quality_event_type,
            "QualityInspectionTask",
            notification.id,
            {
                "notification_id": notification.id,
                "queue_item_id": queue_item_id or (item or {}).get('id'),
                "product_id": product.id if product else None,
                "supplier_id": supplier_id or (item or {}).get('supplier_id'),
                "purchase_id": purchase_id or (item or {}).get('purchase_id'),
                "title": title,
                "owner": owner,
                "priority": priority,
                "sla": sla,
                "path": path,
                "risk_score": (item or {}).get('risk_score'),
                "decision": (item or {}).get('decision'),
                "result": result,
                "evidence": evidence,
                "action": action,
            },
            created_by=current_api_user().id,
        )
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '质量检验任务已创建', status=201)


@api_bp.post('/operations/contract-review')
@jwt_required
def operations_contract_review():
    payload = request.get_json(silent=True) or {}
    receivable_id = payload.get('receivable_id') or payload.get('related_id')
    receivable = db.session.get(Receivable, int(receivable_id)) if receivable_id else None
    customer_name = receivable.customer.name if receivable and receivable.customer else '重点客户'
    title = (payload.get('title') or f'合同回款复核 - {customer_name}').strip()[:128]
    if receivable:
        default_content = f'请复核 {receivable.receivable_no} 合同节点、未收金额 {receivable.unpaid_amount:.2f} 元和回款承诺。'
    else:
        default_content = '请复核重点客户合同节点、应收账龄、开票状态和回款承诺。'
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=(payload.get('content') or default_content).strip(),
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_ORDER,
        related_type='contract',
        related_id=receivable.id if receivable else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'contract_review', current_api_user(), {'notification_id': notification.id, 'receivable_id': receivable.id if receivable else None})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '合同回款任务已创建', status=201)


@api_bp.post('/operations/service-workorder')
@jwt_required
def operations_service_workorder():
    payload = request.get_json(silent=True) or {}
    order_id = payload.get('order_id') or payload.get('related_id')
    order = db.session.get(Order, int(order_id)) if order_id else None
    customer_name = order.customer.name if order and order.customer else '客户现场'
    title = (payload.get('title') or f'售后服务工单 - {customer_name}').strip()[:128]
    content = (
        payload.get('content')
        or '请复核客户订单、发货批次、服务资料、备件库存和回访节点。'
    ).strip()
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=content,
        type=payload.get('type') if payload.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_INFO,
        category=Notification.CATEGORY_ORDER,
        related_type='service',
        related_id=order.id if order else None,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'service_workorder', current_api_user(), {'notification_id': notification.id, 'order_id': order.id if order else None})
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '售后服务工单已创建', status=201)


@api_bp.get('/<path:new_path>')
@jwt_required
def list_new_resource(new_path):
    resource = resolve_resource(new_path)
    if resource:
        return list_resource(resource)
    return api_error('资源不存在', status=404, error='resource_not_found')


@api_bp.get('/<path:new_path>/<int:item_id>')
@jwt_required
def get_new_resource(new_path, item_id):
    resource = resolve_resource(new_path)
    if resource:
        return get_resource(resource, item_id)
    return api_error('资源不存在', status=404, error='resource_not_found')


@api_bp.post('/<path:new_path>')
@jwt_required
def create_new_resource(new_path):
    resource = resolve_resource(new_path)
    if resource:
        return create_resource(resource)
    return api_error('资源不存在', status=404, error='resource_not_found')


@api_bp.put('/<path:new_path>/<int:item_id>')
@api_bp.patch('/<path:new_path>/<int:item_id>')
@jwt_required
def update_new_resource(new_path, item_id):
    resource = resolve_resource(new_path)
    if resource:
        return update_resource(resource, item_id)
    return api_error('资源不存在', status=404, error='resource_not_found')


@api_bp.delete('/<path:new_path>/<int:item_id>')
@jwt_required
def delete_new_resource(new_path, item_id):
    resource = resolve_resource(new_path)
    if resource:
        return delete_resource(resource, item_id)
    return api_error('资源不存在', status=404, error='resource_not_found')


@api_bp.post('/procurement/orders/<int:po_id>/submit')
@jwt_required
def procurement_submit(po_id):
    return submit_purchase_order(po_id)


@api_bp.post('/procurement/orders/<int:po_id>/approve')
@jwt_required
def procurement_approve(po_id):
    return approve_purchase_order(po_id)


@api_bp.post('/procurement/orders/<int:po_id>/reject')
@jwt_required
def procurement_reject(po_id):
    return reject_purchase_order(po_id)


@api_bp.post('/procurement/orders/<int:po_id>/receive')
@jwt_required
def procurement_receive(po_id):
    return receive_purchase_order(po_id)


@api_bp.post('/finance/receivables/<int:receivable_id>/payment')
@jwt_required
def finance_payment(receivable_id):
    return api_record_payment(receivable_id)


@api_bp.post('/inventory/replenishment-suggestions/generate')
@jwt_required
def replenishment_generate():
    return api_generate_replenishment()


@api_bp.post('/inventory/replenishment-suggestions/generate-job')
@jwt_required
def replenishment_generate_job():
    denied = require_permission('purchase.write', '需要采购创建权限')
    if denied:
        return denied
    user = current_api_user()
    job = create_background_job(
        'replenishment.generate',
        {'source': 'inventory.replenishment'},
        created_by=user,
        queue='replenishment',
        task_name='nexus.replenishment.generate',
    )
    db.session.commit()
    job_id = job.job_id

    try:
        if current_app.config.get('CELERY_TASK_ALWAYS_EAGER', False):
            run_replenishment_generation(job_id=job_id, user_id=user.id, celery_task_id=f'eager-{job_id}')
        else:
            from app.platform.jobs.tasks.replenishment import replenishment_generate_task

            async_result = replenishment_generate_task.apply_async(
                kwargs={'job_id': job_id, 'user_id': user.id},
                queue='replenishment',
            )
            job.celery_task_id = async_result.id
            db.session.add(job)
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        job = get_background_job(job_id)
        if job and job.status != BackgroundJob.STATUS_FAILED:
            job.mark_failed(exc)
            db.session.add(job)
            db.session.commit()
        return api_error(str(exc), status=500, error='replenishment_job_failed', job=serialize_background_job(job) if job else None)

    job = get_background_job(job_id)
    if job.status == BackgroundJob.STATUS_SUCCESS:
        return api_success(replenishment_job_payload(job), '补货建议生成完成')
    if job.status == BackgroundJob.STATUS_FAILED:
        return api_error(job.error_message or '补货建议生成失败', status=500, error='replenishment_job_failed', job=serialize_background_job(job))
    return api_success(replenishment_job_payload(job), '补货建议生成任务已入队', status=202)


@api_bp.get('/inventory/replenishment-suggestions/jobs/<job_id>')
@jwt_required
def replenishment_generation_job(job_id):
    job = get_background_job(job_id)
    if not job or job.job_type != 'replenishment.generate':
        return api_error('补货建议生成任务不存在', status=404, error='job_not_found')
    if not can_access_background_job(job, current_api_user()):
        return api_error('权限不足', status=403, error='permission_denied')
    return api_success(replenishment_job_payload(job), '补货建议生成任务状态')


@api_bp.post('/replenishment-suggestions/<int:suggestion_id>/generate')
@jwt_required
def api_generate_single_replenishment(suggestion_id):
    return api_generate_replenishment()


@api_bp.post('/inventory/replenishment-suggestions/<int:suggestion_id>/accept')
@jwt_required
def replenishment_accept(suggestion_id):
    return api_accept_replenishment(suggestion_id)


@api_bp.get('/meta/navigation')
@jwt_required
def meta_navigation():
    user = current_api_user()
    items = []
    for item in NAVIGATION:
        if item.get('admin_only') and not is_admin(user):
            continue
        payload = dict(item)
        resource = payload.get('resource')
        if resource:
            payload['count'] = resource_count(resource)
        items.append(payload)
    return api_success({'items': items}, '导航元数据')


@api_bp.get('/me/preferences')
@jwt_required
def get_preferences():
    return api_success(current_preferences(), '用户偏好')


@api_bp.put('/me/preferences')
@jwt_required
def update_preferences():
    payload = request.get_json(silent=True) or {}
    allowed_keys = {
        'views',
        'density',
        'columns',
        'recent',
        'last_module',
        'default_workspace',
        'command_history',
        'theme',
        'theme_source',
        'charts_motion',
        'dock_labels',
        'context_panel',
    }
    prefs = current_preferences()
    for key, value in payload.items():
        if key in allowed_keys:
            if key == 'theme' and value not in ('dark-cockpit', 'light-luxury'):
                continue
            if key == 'theme_source' and value not in ('system', 'dark-cockpit', 'light-luxury'):
                continue
            if key == 'density' and value not in ('compact', 'comfortable'):
                continue
            if key == 'charts_motion' and value not in ('standard', 'reduced'):
                continue
            if key == 'dock_labels' and value not in ('hover', 'always'):
                continue
            if key == 'context_panel' and value not in ('visible', 'compact'):
                continue
            prefs[key] = value
    current_api_user().preferences = prefs
    AuditService.record('profile', 'update_preferences', current_api_user(), {'keys': list(payload.keys())})
    db.session.commit()
    return api_success(prefs, '偏好已保存')




@api_bp.get('/search')
@jwt_required
def global_search():
    term = (request.args.get('q') or '').strip()
    # Attachment scoping is enforced in SearchService._file_scope for non-admins:
    # attachment_query = attachment_query.filter(Attachment.uploader_id == user.id)
    return api_success({'items': search_service.search(term, user=current_api_user())}, '搜索结果')


def bulk_query(resource, ids):
    config = resource_config(resource)
    if not config:
        return None, None
    if config.get('admin_only') and not is_admin(current_api_user()):
        return None, 'admin_required'
    model = config['model']
    query = model.query.filter(model.id.in_(ids))
    if hasattr(model, 'is_deleted'):
        query = query.filter(model.is_deleted == False)
    return query.all(), None


@api_bp.post('/bulk-actions')
@jwt_required
def bulk_actions():
    payload = request.get_json(silent=True) or {}
    action = payload.get('action')
    ids = [int(item) for item in payload.get('ids', []) if str(item).isdigit()]
    params = payload.get('params') or {}
    no_id_actions = {
        'operations.dispatch_task',
        'operations.data_quality_notice',
        'operations.customer_followup',
        'operations.capacity_plan',
        'operations.maintenance_workorder',
    }
    if not action or (not ids and action not in no_id_actions):
        return api_error('批量动作和记录 ID 不能为空', status=400, error='invalid_bulk_action')

    changed = 0
    if action == 'products.delete':
        denied = require_permission('masterdata.write', '需要主数据维护权限')
        if denied:
            return denied
        items, error = bulk_query('products', ids)
        if error:
            return api_error('需要管理员权限', status=403, error=error)
        for item in items:
            item.is_deleted = True
            changed += 1
    elif action == 'orders.update_status':
        denied = require_permission('sales.write', '需要销售订单权限')
        if denied:
            return denied
        items, error = bulk_query('orders', ids)
        if error:
            return api_error('资源不可用', status=400, error=error)
        status = params.get('status', 'done')
        for item in items:
            from app.services.sales_service import SalesService
            try:
                SalesService.transition_order(item, status, current_api_user())
                changed += 1
            except ValueError:
                continue
    elif action == 'purchase_orders.approve':
        denied = require_permission('purchase.approve', '需要采购审批权限')
        if denied:
            return denied
        for po_id in ids:
            ok, _ = PurchaseService.approve(po_id, current_api_user(), True, params.get('remark'))
            if ok:
                changed += 1
        if changed:
            db.session.commit()
    elif action == 'notifications.mark_read':
        items, error = bulk_query('notifications', ids)
        if error:
            return api_error('资源不可用', status=400, error=error)
        if not is_admin(current_api_user()):
            items = [item for item in items if item.user_id == current_api_user().id]
        for item in items:
            item.is_read = True
            item.read_at = utcnow()
            changed += 1
    elif action == 'files.delete':
        denied = require_permission('files.manage', '需要文件管理权限')
        if denied:
            return denied
        items, error = bulk_query('files', ids)
        if error:
            return api_error('资源不可用', status=400, error=error)
        if not is_admin(current_api_user()):
            items = [item for item in items if item.uploader_id == current_api_user().id]
        for item in items:
            item.is_deleted = True
            changed += 1
    elif action == 'operations.dispatch_task':
        params = params or {}
        notification = Notification(
            user_id=current_api_user().id,
            title=(params.get('title') or '仓配调度任务').strip()[:128],
            content=(params.get('content') or '请复核仓配流向、库存预警和库位热区。').strip(),
            type=params.get('type') if params.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
            category=Notification.CATEGORY_STOCK,
            related_type=params.get('related_type') or 'stock',
            related_id=params.get('related_id') or (ids[0] if ids else None),
        )
        db.session.add(notification)
        db.session.flush()
        changed = 1
    elif action == 'operations.data_quality_notice':
        params = params or {}
        notification = Notification(
            user_id=current_api_user().id,
            title=(params.get('title') or '数据质量复核任务').strip()[:128],
            content=(params.get('content') or '请复核主数据、仓配、履约和财务链路的数据质量。').strip(),
            type=params.get('type') if params.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
            category=Notification.CATEGORY_SYSTEM,
            related_type='quality',
        )
        db.session.add(notification)
        db.session.flush()
        changed = 1
    elif action == 'operations.customer_followup':
        params = params or {}
        customer_id = params.get('customer_id') or params.get('related_id') or (ids[0] if ids else None)
        customer = db.session.get(Partner, int(customer_id)) if customer_id else None
        notification = Notification(
            user_id=current_api_user().id,
            title=(params.get('title') or f'客户经营跟进 - {customer.name if customer else "重点客户"}').strip()[:128],
            content=(params.get('content') or '请复核客户订单履约、应收账龄、信用占用和近期协作记录。').strip(),
            type=params.get('type') if params.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
            category=Notification.CATEGORY_ORDER,
            related_type='customer',
            related_id=customer.id if customer else None,
        )
        db.session.add(notification)
        db.session.flush()
        changed = 1
    elif action == 'operations.capacity_plan':
        params = params or {}
        notification = Notification(
            user_id=current_api_user().id,
            title=(params.get('title') or '产能计划复核任务').strip()[:128],
            content=(params.get('content') or '请复核产能负载、低库存物料、采购到货和销售履约窗口。').strip(),
            type=params.get('type') if params.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_INFO,
            category=Notification.CATEGORY_APPROVAL,
            related_type='capacity',
        )
        db.session.add(notification)
        db.session.flush()
        changed = 1
    elif action == 'operations.maintenance_workorder':
        params = params or {}
        product_id = params.get('product_id') or params.get('related_id') or (ids[0] if ids else None)
        product = db.session.get(Product, int(product_id)) if product_id else None
        notification = Notification(
            user_id=current_api_user().id,
            title=(params.get('title') or f'设备维护工单 - {product.name if product else "产线设备"}').strip()[:128],
            content=(params.get('content') or '请检查 MRO 备件库存、库位状态、维修附件和异常流水。').strip(),
            type=params.get('type') if params.get('type') in {Notification.TYPE_INFO, Notification.TYPE_WARNING, Notification.TYPE_ALERT, Notification.TYPE_SUCCESS} else Notification.TYPE_WARNING,
            category=Notification.CATEGORY_STOCK,
            related_type='maintenance',
            related_id=product.id if product else None,
        )
        db.session.add(notification)
        db.session.flush()
        changed = 1
    else:
        return api_error('不支持的批量动作', status=400, error='unsupported_bulk_action')

    AuditService.record('bulk', action, current_api_user(), {'ids': ids, 'params': params, 'changed': changed})
    db.session.commit()
    return api_success({'changed': changed, 'ids': ids}, '批量动作已完成')


# ============== Finance: Credits ==============

@api_bp.get('/finance/credits')
@jwt_required
def finance_credits():
    from app.models.finance import CustomerCredit
    from app.services.finance_service import FinanceService
    credits = CustomerCredit.query.join(Partner, Partner.id == CustomerCredit.customer_id).filter(Partner.is_deleted == False).all()
    items = []
    for c in credits:
        items.append({
            'id': c.id,
            'customer_id': c.customer_id,
            'customer_name': c.customer.name if c.customer else '',
            'credit_limit': c.credit_limit,
            'used_credit': c.used_credit,
            'available_credit': c.available_credit,
            'usage_rate': c.usage_rate,
            'is_frozen': c.is_frozen,
            'frozen_reason': c.frozen_reason,
            'is_warning': c.is_warning,
            'warning_threshold': c.warning_threshold,
        })
    return api_success({'items': items, 'total': len(items)}, '客户信用列表')


@api_bp.put('/finance/credits/<int:credit_id>')
@jwt_required
def finance_credit_update(credit_id):
    denied = require_permission('finance.credit.write', '需要信用管理权限')
    if denied:
        return denied
    from app.models.finance import CustomerCredit
    credit = db.session.get(CustomerCredit, credit_id)
    if not credit:
        return api_error('信用记录不存在', status=404)
    payload = request.get_json(silent=True) or {}
    if 'credit_limit' in payload:
        credit.credit_limit = float(payload['credit_limit'])
    if 'warning_threshold' in payload:
        credit.warning_threshold = float(payload['warning_threshold'])
    AuditService.record('finance', 'credit_update', current_api_user(), {'credit_id': credit_id, 'fields': list(payload.keys())})
    db.session.commit()
    return api_success({'id': credit.id}, '信用额度已更新')


@api_bp.post('/finance/credits/<int:credit_id>/freeze')
@jwt_required
def finance_credit_freeze(credit_id):
    denied = require_permission('finance.credit.write', '需要信用管理权限')
    if denied:
        return denied
    from app.services.finance_service import FinanceService
    from app.models.finance import CustomerCredit
    credit = db.session.get(CustomerCredit, credit_id)
    if not credit:
        return api_error('信用记录不存在', status=404)
    payload = request.get_json(silent=True) or {}
    reason = payload.get('reason', '管理员冻结')
    ok, msg = FinanceService.freeze_credit(credit.customer_id, reason, current_api_user())
    if ok:
        db.session.commit()
    return api_success({}, msg) if ok else api_error(msg, status=400)


@api_bp.post('/finance/credits/<int:credit_id>/unfreeze')
@jwt_required
def finance_credit_unfreeze(credit_id):
    denied = require_permission('finance.credit.write', '需要信用管理权限')
    if denied:
        return denied
    from app.services.finance_service import FinanceService
    from app.models.finance import CustomerCredit
    credit = db.session.get(CustomerCredit, credit_id)
    if not credit:
        return api_error('信用记录不存在', status=404)
    ok, msg = FinanceService.unfreeze_credit(credit.customer_id)
    if ok:
        db.session.commit()
    return api_success({}, msg) if ok else api_error(msg, status=400)


# ============== Finance: Receivables Reminder ==============

@api_bp.post('/finance/receivables/<int:receivable_id>/reminder')
@jwt_required
def finance_receivable_reminder(receivable_id):
    denied = require_permission('finance.payment', '需要收款权限')
    if denied:
        return denied
    receivable = db.session.get(Receivable, receivable_id)
    if not receivable:
        return api_error('应收记录不存在', status=404)
    customer = receivable.customer
    notification = Notification(
        user_id=current_api_user().id,
        title=f'催款提醒 - {customer.name if customer else "客户"}',
        content=f'应收单 {receivable.receivable_no}，未收金额 ¥{receivable.unpaid_amount:.2f}',
        type=Notification.TYPE_WARNING,
        category=Notification.CATEGORY_ORDER,
        related_type='receivable',
        related_id=receivable.id,
    )
    db.session.add(notification)
    db.session.commit()
    return api_success({}, '催款提醒已发送')


# ============== Stocktake: Count Input ==============

@api_bp.post('/stocktakes/<int:take_id>/count')
@jwt_required
def stocktake_count_input(take_id):
    from app.services.stocktake_service import StockTakeService
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    items = payload.get('items', [])
    if not items:
        return api_error('请提供录入数据', status=400)
    stocktake = db.session.get(StockTake, take_id)
    if not stocktake or stocktake.is_deleted:
        return api_error('盘点单不存在', status=404)
    denied = require_policy_decision(policy.can(current_api_user(), 'update', resource=stocktake))
    if denied:
        return denied
    if stocktake.status != StockTake.STATUS_IN_PROGRESS:
        return api_error('盘点单不在进行中状态', status=400)
    normalized_items = []
    for item in items:
        item_id = item.get('item_id')
        if not item_id:
            target = StockTakeItem.query.filter(
                StockTakeItem.take_id == take_id,
                StockTakeItem.actual_qty.is_(None)
            ).order_by(StockTakeItem.id.asc()).first()
            if not target:
                target = StockTakeItem.query.filter_by(take_id=take_id).order_by(StockTakeItem.id.asc()).first()
            if target:
                item_id = target.id
                if item.get('actual_qty') is None:
                    item['actual_qty'] = target.system_qty
        if item_id:
            if item.get('actual_qty') is None:
                target = db.session.get(StockTakeItem, int(item_id))
                if target:
                    item['actual_qty'] = target.system_qty
            normalized_items.append({**item, 'item_id': item_id})
    if not normalized_items:
        return api_error('没有可录入的盘点明细', status=400)
    count = StockTakeService.batch_input_count(take_id, normalized_items, current_api_user())
    db.session.commit()
    return api_success({'counted': count}, f'已录入 {count} 项')


@api_bp.get('/stocktakes/<int:take_id>/variance')
@jwt_required
def stocktake_variance(take_id):
    from app.services.stocktake_service import StockTakeService
    denied = require_permission('stocktake.write', '需要盘点管理权限')
    if denied:
        return denied
    stocktake = db.session.get(StockTake, take_id)
    if not stocktake or stocktake.is_deleted:
        return api_error('盘点单不存在', status=404)
    denied = require_policy_decision(policy.can(current_api_user(), 'get', resource=stocktake))
    if denied:
        return denied
    summary = StockTakeService.get_variance_summary(take_id)
    return api_success(summary, '差异汇总')


@api_bp.get('/operations/todo')
@jwt_required
def operations_todo():
    user = current_api_user()
    unread_query = Notification.query.filter_by(is_read=False, is_deleted=False)
    if not is_admin(user):
        unread_query = unread_query.filter(Notification.user_id == user.id)
    todos = [
        {'label': '待审批采购单', 'value': PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).count(), 'path': '/app/procurement/orders?status=pending'},
        {'label': '活跃库存预警', 'value': StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE, is_deleted=False).count(), 'path': '/app/inventory/replenishment'},
        {'label': '未读通知', 'value': unread_query.count(), 'path': '/app/notifications'},
        {'label': '逾期应收', 'value': Receivable.query.filter(Receivable.is_deleted == False, Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])).count(), 'path': '/app/finance/receivables'},
    ]
    stock_total = db.session.query(func.coalesce(func.sum(Stock.quantity), 0)).scalar()
    return api_success({'items': todos, 'stock_quantity': int(stock_total or 0)}, '运营待办')


@api_bp.get('/operations/exceptions')
@jwt_required
def operations_exceptions():
    user = current_api_user()
    stock_rows = (
        db.session.query(StockAlert, Product.name)
        .outerjoin(Product, Product.id == StockAlert.product_id)
        .filter(StockAlert.is_deleted == False, StockAlert.status == StockAlert.STATUS_ACTIVE)
        .order_by(StockAlert.alert_level.desc(), StockAlert.current_qty.asc(), StockAlert.created_at.desc())
        .limit(8)
        .all()
    )
    low_stock = [
        {
            'type': '库存',
            'level': '高' if alert.alert_level == StockAlert.LEVEL_RED else '中',
            'title': name or f'商品 #{alert.product_id}',
            'description': f'当前库存 {alert.current_qty or 0}，安全库存 {alert.min_qty or 0}，建议补货 {alert.suggested_qty or 0}',
            'path': f'/app/inventory/products/{alert.product_id}',
        }
        for alert, name in stock_rows
    ]

    overdue = [
        {
            'type': '应收',
            'level': '高' if item.overdue_days > 60 else '中',
            'title': item.receivable_no,
            'description': f'{item.customer.name if item.customer else "客户"} 未收 {item.unpaid_amount:.2f} 元，逾期 {item.overdue_days} 天',
            'path': f'/app/finance/receivables/{item.id}',
        }
        for item in Receivable.query.filter(
            Receivable.is_deleted == False,
            Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
        ).order_by(Receivable.due_date.asc()).limit(8)
    ]

    pending = [
        {
            'type': '采购',
            'level': '中',
            'title': item.po_no,
            'description': f'{item.supplier.name if item.supplier else "供应商"} 待审批，金额 {item.total_amount:.2f} 元',
            'path': f'/app/procurement/orders/{item.id}',
        }
        for item in PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).order_by(PurchaseOrder.created_at.asc()).limit(8)
    ]

    unread_query = Notification.query.filter_by(is_read=False, is_deleted=False)
    if not is_admin(user):
        unread_query = unread_query.filter(Notification.user_id == user.id)
    unread = [
        {
            'type': '通知',
            'level': '低',
            'title': item.title,
            'description': item.content[:80] if item.content else '',
            'path': f'/app/notifications/{item.id}',
        }
        for item in unread_query.order_by(Notification.created_at.desc()).limit(8)
    ]

    items = [*low_stock, *overdue, *pending, *unread]
    priority = {'高': 0, '中': 1, '低': 2}
    items.sort(key=lambda item: priority.get(item['level'], 3))
    return api_success({'items': items[:20], 'total': len(items), 'overdue_updated': False}, '运营异常')


def notification_source_path(item):
    related_type = item.related_type or ''
    related_id = item.related_id
    if 'deployment_readiness' in related_type:
        return '/app/settings'
    if 'integration' in related_type:
        return '/app/integrations'
    if 'quality_inspection' in related_type:
        return '/app/quality'
    if 'procurement_control' in related_type:
        return f'/app/procurement/orders/{related_id}' if related_id else '/app/procurement/orders'
    if 'supplier_collaboration' in related_type:
        return '/app/suppliers/performance'
    if 'quality' in related_type:
        return '/app/data-quality'
    if 'cost' in related_type:
        return '/app/budget'
    if 'capacity' in related_type:
        return '/app/capacity'
    if 'maintenance' in related_type:
        return '/app/maintenance'
    if 'mobile_terminal' in related_type:
        return '/app/mobile-terminal'
    if 'rules' in related_type:
        return '/app/rules'
    if 'purchase' in related_type and related_id:
        return f'/app/procurement/orders/{related_id}'
    if 'order' in related_type and related_id:
        return f'/app/sales/orders/{related_id}'
    if 'report' in related_type and related_id:
        return f'/app/reports/{related_id}'
    if 'product' in related_type and related_id:
        return f'/app/inventory/products/{related_id}'
    return f'/app/notifications/{item.id}'


def workflow_task_source_path(item):
    instance = item.instance
    if instance and instance.business_type == 'purchase_order' and instance.business_id:
        return f'/app/procurement/orders/{instance.business_id}'
    return f'/app/tasks?workflow_task={item.id}'


def workflow_task_queue_item(item):
    instance = item.instance
    definition = instance.definition if instance else None
    source_path = workflow_task_source_path(item)
    business_type = instance.business_type if instance else None
    business_id = instance.business_id if instance else None
    return {
        'id': f'workflow-{item.id}',
        'source_id': item.id,
        'source': 'workflow',
        'business_type': business_type,
        'business_id': business_id,
        'title': item.title or '工作流审批待办',
        'description': (
            f'{definition.name if definition else "工作流"} · '
            f'{business_type if business_type else "business"} #{business_id if business_id else item.id}'
        ),
        'priority': 'P1',
        'status': 'open',
        'owner': item.assignee.username if item.assignee else 'workflow',
        'source_path': source_path,
        'detail_path': source_path,
        'action_label': '查看审批',
        'action_kind': 'navigate',
        'category': 'approval',
        'created_at': serialize_value(item.created_at),
    }


@api_bp.get('/operations/task-queue')
@jwt_required
def operations_task_queue():
    user = current_api_user()
    notification_query = Notification.query.filter_by(is_read=False, is_deleted=False)
    if not is_admin(user):
        notification_query = notification_query.filter(Notification.user_id == user.id)
    notifications = notification_query.order_by(Notification.created_at.desc()).limit(10).all()
    items = [
        {
            'id': f'notification-{item.id}',
            'source_id': item.id,
            'source': 'notification',
            'title': item.title or '系统通知',
            'description': (item.content or '')[:140],
            'priority': 'P0' if item.type == Notification.TYPE_ALERT else 'P1' if item.type == Notification.TYPE_WARNING else 'P2',
            'status': 'open',
            'owner': item.user.username if item.user else 'system',
            'source_path': notification_source_path(item),
            'detail_path': f'/app/notifications/{item.id}',
            'action_label': '处理完成',
            'action_kind': 'complete_notification',
            'category': item.category or Notification.CATEGORY_SYSTEM,
            'created_at': serialize_value(item.created_at),
        }
        for item in notifications
    ]

    workflow_tasks = (
        WorkflowTask.query
        .filter_by(assignee_id=user.id, status=WorkflowTask.STATUS_PENDING, is_deleted=False)
        .order_by(WorkflowTask.created_at.asc())
        .limit(8)
        .all()
    )
    items.extend(workflow_task_queue_item(item) for item in workflow_tasks)

    readiness = deployment_readiness_payload()
    deployment_attention = [item for item in readiness.get('checks', []) if item.get('status') in {'attention', 'blocked'}]
    for check in deployment_attention[:6]:
        items.append({
            'id': f"deployment-{check.get('key', 'check')}",
            'source': 'deployment',
            'title': check.get('label') or '部署预检项',
            'description': check.get('evidence') or check.get('action') or '请复核部署预检项。',
            'priority': 'P0' if check.get('status') == 'blocked' else 'P1',
            'status': check.get('status') or 'attention',
            'owner': check.get('scope') or 'platform',
            'source_path': '/app/settings',
            'detail_path': '/app/settings',
            'action_label': '创建预检任务',
            'action_kind': 'create_deployment_task',
            'category': 'deployment',
            'payload': {
                'key': check.get('key'),
                'label': check.get('label'),
                'scope': check.get('scope'),
                'status': check.get('status'),
                'evidence': check.get('evidence'),
                'action': check.get('action'),
            },
            'created_at': readiness.get('generated_at'),
        })

    stock_alerts = (
        db.session.query(StockAlert, Product.name)
        .outerjoin(Product, Product.id == StockAlert.product_id)
        .filter(StockAlert.is_deleted == False, StockAlert.status == StockAlert.STATUS_ACTIVE)
        .order_by(StockAlert.alert_level.desc(), StockAlert.current_qty.asc())
        .limit(4)
        .all()
    )
    for alert, product_name in stock_alerts:
        items.append({
            'id': f'stock-alert-{alert.id}',
            'source': 'stock',
            'title': product_name or f'库存预警 #{alert.id}',
            'description': f'当前库存 {alert.current_qty or 0}，安全库存 {alert.min_qty or 0}，建议补货 {alert.suggested_qty or 0}',
            'priority': 'P0' if alert.alert_level == StockAlert.LEVEL_RED else 'P1',
            'status': 'open',
            'owner': 'warehouse',
            'source_path': f'/app/inventory/products/{alert.product_id}',
            'detail_path': f'/app/inventory/products/{alert.product_id}',
            'action_label': '处理库存',
            'action_kind': 'navigate',
            'category': 'stock',
            'created_at': serialize_value(alert.created_at),
        })

    pending_purchase = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).order_by(PurchaseOrder.created_at.asc()).limit(4)
    for order in pending_purchase:
        items.append({
            'id': f'purchase-{order.id}',
            'source': 'purchase',
            'title': order.po_no,
            'description': f'{order.supplier.name if order.supplier else "供应商"} 待审批，金额 {order.total_amount:.2f} 元',
            'priority': 'P1',
            'status': 'open',
            'owner': 'procurement',
            'source_path': f'/app/procurement/orders/{order.id}',
            'detail_path': f'/app/procurement/orders/{order.id}',
            'action_label': '审批采购',
            'action_kind': 'navigate',
            'category': 'approval',
            'created_at': serialize_value(order.created_at),
        })

    priority_rank = {'P0': 0, 'P1': 1, 'P2': 2}
    action_rank = {'complete_notification': 0, 'create_deployment_task': 1, 'navigate': 2}
    source_rank = {'notification': 0, 'workflow': 1, 'deployment': 2, 'stock': 3, 'purchase': 4}
    items.sort(key=lambda item: (
        0 if item.get('priority') == 'P0' else 1,
        priority_rank.get(item.get('priority'), 3),
        action_rank.get(item.get('action_kind'), 9),
        source_rank.get(item.get('source'), 9),
        item.get('created_at') or '',
    ))
    summary = {
        'total': len(items),
        'open_notifications': len(notifications),
        'deployment_attention': len(deployment_attention),
        'business_exceptions': len(workflow_tasks) + len(stock_alerts) + pending_purchase.count(),
        'p0': sum(1 for item in items if item['priority'] == 'P0'),
        'p1': sum(1 for item in items if item['priority'] == 'P1'),
        'p2': sum(1 for item in items if item['priority'] == 'P2'),
        'generated_at': serialize_value(utcnow()),
        'next_action': '先处理 P0，再完成部署预检和业务异常。' if items else '当前没有待处理任务。',
    }
    return api_success({'summary': summary, 'items': items[:24]}, '当班任务队列')


@api_bp.get('/operations/rules')
@jwt_required
def operations_rules():
    return api_success(rules_governance_payload(), '规则治理工作台')


@api_bp.post('/operations/rules/review')
@jwt_required
def operations_rules_review():
    payload = request.get_json(silent=True) or {}
    rule_id = (payload.get('rule_id') or '').strip()[:64]
    rule_name = (payload.get('rule_name') or '').strip()[:96]
    _, rule, queue_item = select_rule_review_context(rule_id=rule_id, rule_name=rule_name)
    rule_name = (payload.get('rule_name') or (rule or {}).get('name') or '经营规则复核').strip()[:96]
    owner = (payload.get('owner') or (queue_item or rule or {}).get('owner') or '规则治理台').strip()[:48]
    priority = (payload.get('priority') or (queue_item or rule or {}).get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or (queue_item or rule or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (queue_item or rule or {}).get('evidence') or '规则命中和风险对象需要复核。').strip()[:280]
    action = (payload.get('action') or (queue_item or rule or {}).get('action') or '复核规则命中数量、风险对象和后续业务动作。').strip()[:320]
    path = (payload.get('path') or (queue_item or rule or {}).get('path') or '/app/rules').strip()[:160]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    notification = Notification(
        user_id=current_api_user().id,
        title=f'规则复核 - {rule_name}',
        content=f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n来源：{path}',
        type=Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_SYSTEM,
        related_type='rules',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'rules_review', current_api_user(), {
        'notification_id': notification.id,
        'rule_id': rule_id or (rule or {}).get('id'),
        'rule_name': rule_name,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '规则复核任务已创建', status=201)


@api_bp.get('/operations/integrations')
@jwt_required
def operations_integrations():
    return api_success(integration_payload(), '集成监控')


@api_bp.get('/operations/deployment-readiness')
@jwt_required
def operations_deployment_readiness():
    return api_success(deployment_readiness_payload(), '部署就绪看板')


@api_bp.post('/operations/deployment-readiness/task')
@jwt_required
def operations_deployment_readiness_task():
    payload = request.get_json(silent=True) or {}
    key = (payload.get('key') or 'deployment-readiness').strip()[:64]
    label = (payload.get('label') or '部署就绪检查').strip()[:96]
    scope = (payload.get('scope') or 'platform').strip()[:32]
    status = (payload.get('status') or 'attention').strip()[:32]
    evidence = (payload.get('evidence') or '部署预检项需要复核。').strip()[:240]
    action = (payload.get('action') or '请复核部署就绪检查项，并在目标平台完成配置后重新部署。').strip()[:320]
    valid_statuses = {'ready', 'attention', 'blocked'}
    if status not in valid_statuses:
        status = 'attention'
    notification_type = Notification.TYPE_ALERT if status == 'blocked' else Notification.TYPE_WARNING
    notification = Notification(
        user_id=current_api_user().id,
        title=f'部署预检任务 - {label}',
        content=f'[{scope}/{status}] {evidence}\n处理动作：{action}',
        type=notification_type,
        category=Notification.CATEGORY_SYSTEM,
        related_type='deployment_readiness',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'deployment_readiness_task', current_api_user(), {
        'notification_id': notification.id,
        'key': key,
        'label': label,
        'scope': scope,
        'status': status,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '部署预检任务已创建', status=201)


@api_bp.post('/operations/integrations/resync')
@jwt_required
def operations_integrations_resync():
    payload = request.get_json(silent=True) or {}
    service_id = (payload.get('service_id') or '').strip()[:64]
    service = next((item for item in SERVICE_CATALOG if item['id'] == service_id), None)
    system_name = (payload.get('system_name') or (service or {}).get('name') or '经营系统接口').strip()[:96]
    owner = (payload.get('owner') or (service or {}).get('owner') or '运营协同').strip()[:48]
    action = (payload.get('action') or ((service or {}).get('runbook') or ['复核接口记录数、失败重试和最近业务对象。'])[0]).strip()[:180]
    evidence = (payload.get('evidence') or '请复核接口记录数、失败重试和最近业务对象，确认云端数据链路保持一致。').strip()[:260]
    priority = (payload.get('priority') or 'P1').strip()[:8]
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING
    notification = Notification(
        user_id=current_api_user().id,
        title=f'接口重同步任务 - {system_name}',
        content=f'[{owner}/{priority}] {evidence}\n处理动作：{action}',
        type=notification_type,
        category=Notification.CATEGORY_SYSTEM,
        related_type='integration',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'integration_resync', current_api_user(), {
        'notification_id': notification.id,
        'system_name': system_name,
        'service_id': service_id or None,
        'owner': owner,
        'priority': priority,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '接口重同步任务已创建', status=201)


@api_bp.get('/operations/costs')
@jwt_required
def operations_costs():
    return api_success(cost_governance_payload(), '预算成本治理')


@api_bp.post('/operations/costs/review')
@jwt_required
def operations_costs_review():
    payload = request.get_json(silent=True) or {}
    item_id = (payload.get('item_id') or payload.get('cost_center_id') or '').strip()[:64]
    _, item = select_cost_review_context(item_id=item_id, title=payload.get('title'))
    title = (payload.get('title') or (item or {}).get('title') or '预算成本复核任务').strip()[:128]
    owner = (payload.get('owner') or (item or {}).get('owner') or '经营财务').strip()[:48]
    priority = (payload.get('priority') or (item or {}).get('priority') or 'P1').strip()[:8]
    sla = (payload.get('sla') or (item or {}).get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or (item or {}).get('evidence') or '请复核库存资金占用、采购投入、销售收入和应收回款差额。').strip()[:280]
    action = (payload.get('action') or (item or {}).get('action') or '核对预算、实际和采购承诺，必要时创建经营复盘。').strip()[:320]
    path = (payload.get('path') or (item or {}).get('path') or '/app/budget').strip()[:160]
    if priority not in {'P0', 'P1', 'P2'}:
        priority = 'P1'
    notification = Notification(
        user_id=current_api_user().id,
        title=title,
        content=f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n来源：{path}',
        type=Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING,
        category=Notification.CATEGORY_REPORT,
        related_type='cost',
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'cost_review', current_api_user(), {
        'notification_id': notification.id,
        'item_id': item_id or (item or {}).get('id'),
        'cost_center_id': (item or {}).get('cost_center_id'),
        'title': title,
        'owner': owner,
        'priority': priority,
        'sla': sla,
        'path': path,
        'evidence': evidence,
        'action': action,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '成本复核任务已创建', status=201)


@api_bp.get('/operations/mobile-terminal')
@jwt_required
def operations_mobile_terminal():
    return api_success(mobile_terminal_payload(), '移动扫码终端')


@api_bp.post('/operations/mobile-terminal/task')
@jwt_required
def operations_mobile_terminal_task():
    payload = request.get_json(silent=True) or {}
    _, item = select_mobile_task_context(
        queue_item_id=(payload.get('queue_item_id') or payload.get('item_id') or '').strip()[:64],
        task_type=(payload.get('task_type') or '').strip()[:64],
        title=(payload.get('title') or '').strip()[:128],
    )
    task_type = (payload.get('task_type') or item.get('type') or '扫码任务').strip()[:64]
    title = (payload.get('title') or item.get('title') or f'{task_type}现场任务').strip()[:128]
    owner = (payload.get('owner') or item.get('owner') or '现场主管').strip()[:48]
    priority = (payload.get('priority') or item.get('priority') or 'P2').strip()[:8]
    sla = (payload.get('sla') or item.get('sla') or '1d').strip()[:16]
    evidence = (payload.get('evidence') or item.get('evidence') or '现场任务已写入系统。').strip()[:280]
    action = (payload.get('action') or payload.get('next_action') or item.get('next_action') or '请在移动端完成扫码、数量确认和异常备注。').strip()[:320]
    path = (payload.get('path') or item.get('path') or '/app/mobile-terminal').strip()[:160]
    notification_type = Notification.TYPE_ALERT if priority == 'P0' else Notification.TYPE_WARNING if priority == 'P1' else Notification.TYPE_INFO
    notification = Notification(
        user_id=current_api_user().id,
        title=f'现场扫码任务 - {title}',
        content=f'[{owner}/{priority}/{sla}] {evidence}\n处理动作：{action}\n扫码口令：{item.get("scan_code") or task_type}\n来源：{path}',
        type=notification_type,
        category=Notification.CATEGORY_STOCK,
        related_type='mobile_terminal',
        related_id=item.get('source_id'),
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.record('operations', 'mobile_task', current_api_user(), {
        'notification_id': notification.id,
        'queue_item_id': item.get('id'),
        'source': item.get('source'),
        'source_id': item.get('source_id'),
        'task_type': task_type,
        'owner': owner,
        'priority': priority,
        'path': path,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '现场任务已创建', status=201)
