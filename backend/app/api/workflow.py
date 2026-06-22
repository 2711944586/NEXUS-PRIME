import json
import time

from flask import Response, current_app, stream_with_context

from app.domains.workflow.application import workflow_service
from app.extensions import db
from app.models.workflow import WorkflowInstance, WorkflowLog, WorkflowTask
from app.services.audit_service import AuditService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .resource_support import current_payload, require_permission, serialize_model, workflow_instance_extra, workflow_task_extra
from .responses import api_error, api_success


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f"event: {event}\ndata: {payload}\n\n"


def workflow_todo_payload(user, *, limit=100) -> dict:
    all_rows = workflow_service.todo_tasks(user)
    rows = all_rows[:limit]
    return {
        "items": [serialize_model(item, workflow_task_extra) for item in rows],
        "total": len(all_rows),
        "generated_at": utcnow().isoformat(),
    }


@api_bp.post("/workflows/definitions")
@jwt_required
def create_workflow_definition():
    denied = require_permission("stocktake.write", "需要工作流管理权限")
    if denied:
        return denied
    payload = current_payload()
    process_key = (payload.get("process_key") or "").strip()
    name = (payload.get("name") or "").strip()
    if not process_key or not name:
        return api_error("请提供流程 key 和名称", status=400, error="invalid_workflow_definition")
    definition = workflow_service.create_definition(
        process_key,
        name,
        description=payload.get("description"),
        config=payload.get("config") or {},
    )
    AuditService.record("workflow", "definition_upsert", current_api_user(), {"process_key": process_key})
    db.session.commit()
    return api_success(serialize_model(definition), "工作流定义已保存", status=201)


@api_bp.post("/workflows/start")
@jwt_required
def start_workflow():
    denied = require_permission("stocktake.write", "需要工作流处理权限")
    if denied:
        return denied
    payload = current_payload()
    try:
        instance, task = workflow_service.start(
            payload.get("process_key"),
            payload.get("business_type"),
            payload.get("business_id"),
            current_api_user(),
            variables=payload.get("variables") or {},
            assignee_id=payload.get("assignee_id"),
            title=payload.get("title"),
        )
        AuditService.record("workflow", "start", current_api_user(), {"instance_id": instance.id, "task_id": task.id})
        db.session.commit()
        return api_success(
            {"instance": serialize_model(instance, workflow_instance_extra), "task": serialize_model(task, workflow_task_extra)},
            "工作流已启动",
            status=201,
        )
    except ValueError as exc:
        db.session.rollback()
        return api_error(str(exc), status=400, error="workflow_start_failed")


@api_bp.get("/workflows/tasks/todo")
@jwt_required
def workflow_todo_tasks():
    return api_success(workflow_todo_payload(current_api_user()), "待办任务")


@api_bp.get("/workflows/tasks/todo/stream")
@jwt_required
def workflow_todo_tasks_stream():
    user = current_api_user()
    max_events = max(1, int(current_app.config.get("WORKFLOW_TODO_STREAM_MAX_EVENTS", 25)))
    interval_seconds = max(0.0, float(current_app.config.get("WORKFLOW_TODO_STREAM_INTERVAL_SECONDS", 2.0)))
    limit = min(200, max(1, int(current_app.config.get("WORKFLOW_TODO_STREAM_LIMIT", 100))))

    def generate():
        for index in range(max_events):
            yield _sse_event("snapshot", workflow_todo_payload(user, limit=limit))
            if index < max_events - 1 and interval_seconds:
                time.sleep(interval_seconds)

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@api_bp.post("/workflows/tasks/<int:task_id>/approve")
@jwt_required
def approve_workflow_task(task_id):
    return _complete_task(task_id, "approve")


@api_bp.post("/workflows/tasks/<int:task_id>/reject")
@jwt_required
def reject_workflow_task(task_id):
    return _complete_task(task_id, "reject")


@api_bp.post("/workflows/tasks/<int:task_id>/transfer")
@jwt_required
def transfer_workflow_task(task_id):
    payload = current_payload()
    try:
        task = workflow_service.transfer_task(task_id, current_api_user(), payload.get("target_user_id"), comment=payload.get("comment"))
        AuditService.record("workflow", "transfer", current_api_user(), {"task_id": task.id, "target_user_id": payload.get("target_user_id")})
        db.session.commit()
        return api_success(serialize_model(task, workflow_task_extra), "任务已转交")
    except PermissionError as exc:
        db.session.rollback()
        return api_error(str(exc), status=403, error="workflow_forbidden")
    except ValueError as exc:
        db.session.rollback()
        return api_error(str(exc), status=400, error="workflow_transfer_failed")


@api_bp.get("/workflows/instances/<int:instance_id>")
@jwt_required
def get_workflow_instance(instance_id):
    instance = db.session.get(WorkflowInstance, instance_id)
    if not instance or instance.is_deleted:
        return api_error("工作流实例不存在", status=404, error="not_found")
    data = serialize_model(instance, workflow_instance_extra)
    data["tasks"] = [serialize_model(task, workflow_task_extra) for task in instance.tasks.order_by(WorkflowTask.id.asc()).all()]
    data["logs"] = [serialize_model(log) for log in instance.logs.order_by(WorkflowLog.id.asc()).all()]
    return api_success(data, "工作流实例")


def _complete_task(task_id, action):
    denied = require_permission("stocktake.write", "需要工作流处理权限")
    if denied:
        return denied
    payload = current_payload()
    try:
        if action == "approve":
            instance = workflow_service.approve_task(task_id, current_api_user(), comment=payload.get("comment"))
            audit_action = "approve"
            message = "任务已审批通过"
        else:
            instance = workflow_service.reject_task(task_id, current_api_user(), comment=payload.get("comment"))
            audit_action = "reject"
            message = "任务已驳回"
        AuditService.record("workflow", audit_action, current_api_user(), {"task_id": task_id, "instance_id": instance.id})
        db.session.commit()
        return api_success(serialize_model(instance, workflow_instance_extra), message)
    except PermissionError as exc:
        db.session.rollback()
        return api_error(str(exc), status=403, error="workflow_forbidden")
    except ValueError as exc:
        db.session.rollback()
        return api_error(str(exc), status=400, error="workflow_action_failed")
