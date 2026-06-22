"""AI chat and analysis routes — extracted from experience.py."""
from __future__ import annotations

import concurrent.futures
import json
from typing import Any

from flask import Response, current_app, request, stream_with_context
from sqlalchemy import func

from app.extensions import cache, db
from app.domains.ai.application import (
    AiActionDraftService,
    AiToolRunner,
    RagAnswerService,
    serialize_action_draft,
)
from app.models.ai import AiActionDraft
from app.models.auth import User
from app.models.biz import Product
from app.models.finance import Receivable
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock
from app.models.sys import AiChatMessage, AiChatSession
from app.services.ai_service import ai_service
from app.services.audit_service import AuditService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success

_AI_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix='ai_chat')


class AiChatFailure(Exception):
    def __init__(self, message: str, *, status: int = 400, error: str = "ai_chat_failed"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.error = error


def _chat_with_app_context(app, message, user_id, context):
    with app.app_context():
        user = db.session.get(User, user_id) if user_id else None
        return ai_service.chat(message=message, user=user, context=context)


def serialize_ai_session(session: AiChatSession) -> dict[str, Any]:
    return {
        'id': session.id,
        'title': session.title,
        'last_message_at': session.last_message_at.isoformat() if session.last_message_at else None,
        'created_at': session.created_at.isoformat() if session.created_at else None,
        'message_count': session.messages.count(),
    }


def serialize_ai_message(message: AiChatMessage) -> dict[str, Any]:
    return {
        'id': message.id,
        'role': message.role,
        'content': message.content,
        'tokens': message.tokens or 0,
        'created_at': message.created_at.isoformat() if message.created_at else None,
    }


def sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f"event: {event}\ndata: {payload}\n\n"


def answer_chunks(answer: str, *, size: int = 120):
    text = answer or ""
    for index in range(0, len(text), size):
        yield text[index:index + size]


def record_ai_insight_requested(kind: str, *, user, aggregate_type="AiInsight", aggregate_id=None, **metadata):
    from app.platform.events import outbox

    payload = {
        "kind": kind,
        "requested_by": user.id if user else None,
        **metadata,
    }
    return outbox.add(
        "AiInsightRequested",
        aggregate_type,
        aggregate_id or f"{kind}:{user.id if user else 'anonymous'}",
        payload,
        created_by=user.id if user else None,
    )


def _local_ai_reply(message: str) -> str:
    order_amount = db.session.query(func.coalesce(func.sum(
        db.session.query(func.coalesce(func.sum(Product.price), 0)).scalar().__class__(0)
    ), 0)).scalar()
    from app.models.trade import Order
    order_amount = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    low_stock = (
        db.session.query(Product.id)
        .outerjoin(Stock, Stock.product_id == Product.id)
        .filter(Product.is_deleted == False)
        .group_by(Product.id)
        .having(func.coalesce(func.sum(Stock.quantity), 0) <= func.coalesce(Product.min_stock, 0))
        .count()
    )
    overdue = Receivable.query.filter(
        Receivable.is_deleted == False,
        Receivable.status.in_([Receivable.STATUS_OVERDUE, Receivable.STATUS_BAD_DEBT])
    ).count()
    pending = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_PENDING, is_deleted=False).count()
    return (
        f'当前销售金额约 {float(order_amount or 0):,.2f} 元；'
        f'低库存商品 {low_stock} 个；逾期应收 {overdue} 笔；待审批采购 {pending} 张。\n\n'
        f'针对"{message[:80]}"，优先处理补货、采购审批队列和逾期应收。'
    )


def prepare_ai_chat(payload: dict[str, Any], user) -> dict[str, Any]:
    message = (payload.get('message') or '').strip()
    if not message:
        raise AiChatFailure('消息不能为空', status=400, error='empty_message')
    if len(message) > 4000:
        raise AiChatFailure('消息过长，请控制在4000字以内', status=400, error='message_too_long')

    rate_key = f'ai_rate:{user.id}'
    rate_count = int(cache.get(rate_key) or 0)
    if rate_count >= 20:
        raise AiChatFailure('AI 请求过于频繁，请稍后再试', status=429, error='ai_rate_limited')
    cache.set(rate_key, rate_count + 1, timeout=60)

    session_id = payload.get('session_id')
    session = None
    if session_id:
        session = AiChatSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not session:
        session = AiChatSession(user_id=user.id, title=message[:24] + ('…' if len(message) > 24 else ''))
        db.session.add(session)
        db.session.flush()

    user_message = AiChatMessage(session_id=session.id, role='user', content=message)
    db.session.add(user_message)
    db.session.flush()
    history = session.messages.order_by(AiChatMessage.created_at.asc()).limit(20).all()
    context = [{'role': m.role, 'content': m.content} for m in history if m.id != user_message.id]

    rag_service = RagAnswerService()
    rag_result = rag_service.retrieve(message, user, limit=int(current_app.config.get('AI_RAG_CONTEXT_LIMIT', 4)))
    rag_context = rag_service.context_message(rag_result)
    if rag_context:
        context.append({'role': 'system', 'content': rag_context})

    record_ai_insight_requested(
        "chat",
        user=user,
        aggregate_type="AiChatSession",
        aggregate_id=session.id,
        session_id=session.id,
        user_message_id=user_message.id,
        message_length=len(message),
        context_messages=len(context),
        rag_source_count=len(rag_result.sources),
        stream=bool(payload.get('stream')),
    )
    AuditService.record(
        'ai',
        'rag_search',
        user,
        {
            'session_id': session.id,
            'user_message_id': user_message.id,
            'source_count': len(rag_result.sources),
            'source_ids': [source.source_id for source in rag_result.sources],
            'stream': bool(payload.get('stream')),
        },
    )
    db.session.commit()

    return {
        'message': message,
        'session': session,
        'user_message': user_message,
        'context': context,
        'rag_service': rag_service,
        'rag_result': rag_result,
    }


def complete_ai_chat(prepared: dict[str, Any], user) -> dict[str, Any]:
    timeout = float(current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS', 20))
    app = current_app._get_current_object()
    try:
        future = _AI_EXECUTOR.submit(_chat_with_app_context, app, prepared['message'], user.id, prepared['context'])
        result: dict = future.result(timeout=timeout + 2)
    except concurrent.futures.TimeoutError as exc:
        db.session.rollback()
        raise AiChatFailure('AI 响应超时，请重试', status=504, error='ai_timeout') from exc

    rag_result = prepared['rag_result']
    rag_service = prepared['rag_service']
    if result.get('success'):
        answer = result.get('content') or ''
        usage = result.get('usage') or {}
        source = result.get('source') or 'analysis_provider'
        provider_warning = result.get('provider_warning')
    else:
        db.session.rollback()
        if result.get('source') == 'analysis_provider':
            raise AiChatFailure(
                result.get('error') or '外部分析服务不可用',
                status=502,
                error='ai_provider_unavailable',
            )
        answer = ai_service.local_operations_reply(prepared['message'], user=user)
        usage, source, provider_warning = {}, 'operations_engine', result.get('error')

    if rag_result.has_sources and source == 'operations_engine':
        answer = rag_service.compose_local_answer(prepared['message'], rag_result, base_answer=answer)

    session = db.session.get(AiChatSession, prepared['session'].id)
    assistant_message = AiChatMessage(
        session_id=session.id,
        role='assistant',
        content=answer,
        tokens=int(usage.get('total_tokens') or 0),
    )
    db.session.add(assistant_message)
    session.last_message_at = utcnow()
    db.session.commit()
    return {
        'session': serialize_ai_session(session),
        'message': serialize_ai_message(assistant_message),
        'usage': usage,
        'source': source,
        'provider_warning': provider_warning,
        'rag_sources': rag_result.to_dicts(),
    }


@api_bp.get('/ai/sessions')
@jwt_required
def ai_sessions():
    sessions = (
        AiChatSession.query
        .filter_by(user_id=current_api_user().id, is_archived=False, is_deleted=False)
        .order_by(AiChatSession.last_message_at.desc())
        .limit(50)
        .all()
    )
    return api_success({'items': [serialize_ai_session(s) for s in sessions]}, '分析会话')


@api_bp.post('/ai/sessions')
@jwt_required
def ai_create_session():
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '新对话').strip()[:128] or '新对话'
    session = AiChatSession(user_id=current_api_user().id, title=title)
    db.session.add(session)
    db.session.commit()
    return api_success(serialize_ai_session(session), '分析会话已创建', status=201)


@api_bp.delete('/ai/sessions/<int:session_id>')
@jwt_required
def ai_delete_session(session_id: int):
    user = current_api_user()
    session = AiChatSession.query.filter_by(id=session_id).first()
    if not session:
        return api_error('会话不存在', status=404, error='not_found')
    if session.user_id != user.id and not (user.is_admin or (user.role and user.role.is_admin)):
        return api_error('权限不足', status=403, error='forbidden')
    session.is_deleted = True
    db.session.commit()
    return api_success({}, '会话已删除')


@api_bp.get('/ai/sessions/<int:session_id>/messages')
@jwt_required
def ai_session_messages(session_id: int):
    session = AiChatSession.query.filter_by(id=session_id, user_id=current_api_user().id).first()
    if not session:
        return api_error('会话不存在', status=404, error='not_found')
    messages = session.messages.order_by(AiChatMessage.created_at.asc()).all()
    return api_success({'session': serialize_ai_session(session), 'items': [serialize_ai_message(m) for m in messages]}, '分析消息')


@api_bp.post('/ai/chat')
@jwt_required
def ai_chat():
    payload = request.get_json(silent=True) or {}
    user = current_api_user()
    try:
        prepared = prepare_ai_chat(payload, user)
        data = complete_ai_chat(prepared, user)
    except AiChatFailure as exc:
        return api_error(exc.message, status=exc.status, error=exc.error)
    return api_success(data, '分析完成')


@api_bp.post('/ai/chat/stream')
@jwt_required
def ai_chat_stream():
    payload = request.get_json(silent=True) or {}
    payload['stream'] = True
    user_id = current_api_user().id

    def generate():
        try:
            user = db.session.get(User, user_id)
            prepared = prepare_ai_chat(payload, user)
            yield sse_event('status', {
                'phase': 'accepted',
                'session': serialize_ai_session(prepared['session']),
                'rag_sources': prepared['rag_result'].to_dicts(),
            })
            data = complete_ai_chat(prepared, user)
            for chunk in answer_chunks(data['message']['content']):
                yield sse_event('chunk', {'content': chunk})
            yield sse_event('done', data)
        except AiChatFailure as exc:
            yield sse_event('error', {'message': exc.message, 'error': exc.error, 'status': exc.status})
        except Exception as exc:
            current_app.logger.exception('AI stream failed')
            db.session.rollback()
            yield sse_event('error', {'message': 'AI 流式响应失败，请重试', 'error': 'ai_stream_failed', 'status': 500})

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@api_bp.post('/ai/tools/run')
@jwt_required
def ai_run_tool():
    payload = request.get_json(silent=True) or {}
    tool_name = (payload.get('tool') or '').strip()
    params = payload.get('params') if isinstance(payload.get('params'), dict) else {}
    result = AiToolRunner().run(tool_name, params, current_api_user())
    db.session.commit()
    if result.payload.get('ok'):
        return api_success(result.payload, 'AI 工具调用完成', status=result.status)
    return api_error(
        result.payload.get('message') or 'AI 工具调用失败',
        status=result.status,
        error=result.payload.get('error') or 'ai_tool_failed',
        tool_result=result.payload,
    )


def _is_admin_user(user) -> bool:
    return bool(user and (user.is_admin or (user.role and user.role.is_admin)))


def _draft_query_for_user(user):
    query = AiActionDraft.query.filter(AiActionDraft.is_deleted == False)
    if not _is_admin_user(user):
        query = query.filter(AiActionDraft.created_by == user.id)
    return query


@api_bp.get('/ai/drafts')
@jwt_required
def ai_list_drafts():
    user = current_api_user()
    query = _draft_query_for_user(user)
    status = (request.args.get('status') or '').strip()
    draft_type = (request.args.get('type') or '').strip()
    if status:
        query = query.filter(AiActionDraft.status == status)
    if draft_type:
        query = query.filter(AiActionDraft.draft_type == draft_type)
    rows = query.order_by(AiActionDraft.created_at.desc(), AiActionDraft.id.desc()).limit(50).all()
    return api_success({'items': [serialize_action_draft(row) for row in rows]}, 'AI 草稿')


@api_bp.post('/ai/drafts/<int:draft_id>/confirm')
@jwt_required
def ai_confirm_draft(draft_id: int):
    user = current_api_user()
    if not user.can('purchase.write'):
        return api_error('需要采购创建权限', status=403, error='permission_denied')
    payload = request.get_json(silent=True) or {}
    try:
        draft, suggestions = AiActionDraftService.confirm_replenishment_draft(
            draft_id,
            user,
            note=(payload.get('note') or '').strip() or None,
        )
    except LookupError as exc:
        return api_error(str(exc), status=404, error='not_found')
    except PermissionError as exc:
        return api_error(str(exc), status=403, error='forbidden')
    except ValueError as exc:
        return api_error(str(exc), status=400, error='invalid_ai_draft')
    db.session.commit()
    return api_success(
        {
            'draft': serialize_action_draft(draft),
            'replenishment_suggestion_ids': [item.id for item in suggestions],
            'created_purchase_order': False,
            'requires_next_human_confirmation': True,
        },
        'AI 草稿已确认并转为补货建议',
    )


@api_bp.post('/ai/drafts/<int:draft_id>/reject')
@jwt_required
def ai_reject_draft(draft_id: int):
    user = current_api_user()
    payload = request.get_json(silent=True) or {}
    try:
        draft = AiActionDraftService.reject_draft(
            draft_id,
            user,
            note=(payload.get('note') or '').strip() or None,
        )
    except LookupError as exc:
        return api_error(str(exc), status=404, error='not_found')
    except PermissionError as exc:
        return api_error(str(exc), status=403, error='forbidden')
    except ValueError as exc:
        return api_error(str(exc), status=400, error='invalid_ai_draft')
    db.session.commit()
    return api_success({'draft': serialize_action_draft(draft)}, 'AI 草稿已拒绝')


@api_bp.post('/ai/analyze/inventory')
@jwt_required
def ai_inventory_analysis():
    limit = int((request.get_json(silent=True) or {}).get('limit') or 10)
    record_ai_insight_requested(
        "inventory_analysis",
        user=current_api_user(),
        limit=limit,
    )
    result = ai_service.analyze_inventory(limit=limit, user=current_api_user())
    if not result or result.startswith('库存分析失败'):
        result = ai_service.local_operations_reply('请分析当前库存风险', user=current_api_user())
    db.session.commit()
    return api_success({'content': result}, '库存分析')


@api_bp.get('/ai/settings')
@jwt_required
def ai_settings():
    return api_success(ai_service.get_settings(current_api_user()), '分析服务设置')


@api_bp.put('/ai/settings')
@jwt_required
def ai_update_settings():
    payload = request.get_json(silent=True) or {}
    try:
        settings = ai_service.update_settings(current_api_user(), payload)
    except ValueError as exc:
        return api_error(str(exc), status=400, error='invalid_ai_settings')
    AuditService.record('ai', 'update_settings', current_api_user(), {'keys': list(payload.keys())})
    db.session.commit()
    return api_success(settings, '分析服务设置已保存')


@api_bp.post('/ai/diagnostics')
@jwt_required
def ai_diagnostics():
    return api_success(ai_service.run_diagnostics(current_api_user()), '分析服务诊断')


@api_bp.post('/ai/analyze/structured')
@jwt_required
def ai_structured_analysis():
    payload = request.get_json(silent=True) or {}
    scenario = str(payload.get('scenario') or 'daily_brief').strip()
    limit = int(payload.get('limit') or 8)
    record_ai_insight_requested(
        "structured_analysis",
        user=current_api_user(),
        scenario=scenario,
        limit=limit,
    )
    result = ai_service.structured_operations_analysis(scenario=scenario, limit=limit, user=current_api_user())
    db.session.commit()
    return api_success(result, '结构化经营分析')
