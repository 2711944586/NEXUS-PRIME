from app.extensions import db
from app.models.auth import User
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowLog, WorkflowTask
from app.utils.time import utcnow


def workflow_task_event_payload(task):
    instance = task.instance
    definition = instance.definition if instance else None
    return {
        "workflow_instance_id": instance.id if instance else None,
        "workflow_task_id": task.id,
        "definition_id": instance.definition_id if instance else None,
        "process_key": definition.process_key if definition else None,
        "business_type": instance.business_type if instance else None,
        "business_id": instance.business_id if instance else None,
        "node_key": task.node_key,
        "task_title": task.title,
        "task_status": task.status,
        "instance_status": instance.status if instance else None,
        "assignee_id": task.assignee_id,
        "action_by": task.action_by,
        "action_at": task.action_at.isoformat() if task.action_at else None,
        "comment": task.comment,
    }


def workflow_started_event_payload(instance, task):
    definition = instance.definition if instance else None
    return {
        "workflow_instance_id": instance.id,
        "workflow_task_id": task.id if task else None,
        "definition_id": instance.definition_id,
        "process_key": definition.process_key if definition else None,
        "business_type": instance.business_type,
        "business_id": instance.business_id,
        "applicant_id": instance.applicant_id,
        "assignee_id": task.assignee_id if task else None,
        "node_key": task.node_key if task else instance.current_node_key,
        "task_title": task.title if task else None,
        "task_status": task.status if task else None,
        "instance_status": instance.status,
        "current_node_key": instance.current_node_key,
        "variables": instance.variables or {},
        "started_at": instance.started_at.isoformat() if instance.started_at else None,
    }


def record_workflow_started_event(instance, task, *, created_by=None, extra=None):
    from app.platform.events import outbox

    payload = workflow_started_event_payload(instance, task)
    if extra:
        payload.update(extra)
    return outbox.add(
        "WorkflowStarted",
        "WorkflowInstance",
        instance.id,
        payload,
        created_by=created_by,
    )


def record_workflow_task_event(task, event_type, *, created_by=None, extra=None):
    from app.platform.events import outbox

    payload = workflow_task_event_payload(task)
    if extra:
        payload.update(extra)
    return outbox.add(
        event_type,
        "WorkflowTask",
        task.id,
        payload,
        created_by=created_by,
    )


class WorkflowService:
    DEFAULT_NODE_KEY = "approval"

    def create_definition(self, process_key, name, *, description=None, config=None):
        existing = WorkflowDefinition.query.filter_by(process_key=process_key, is_deleted=False).first()
        if existing:
            existing.name = name
            existing.description = description
            existing.config = config or existing.config
            existing.is_active = True
            return existing
        definition = WorkflowDefinition(
            process_key=process_key,
            name=name,
            description=description,
            config=config or {},
            is_active=True,
        )
        db.session.add(definition)
        db.session.flush()
        return definition

    def start(self, process_key, business_type, business_id, applicant, *, variables=None, assignee_id=None, title=None):
        definition = WorkflowDefinition.query.filter_by(process_key=process_key, is_active=True, is_deleted=False).first()
        if not definition:
            raise ValueError("工作流定义不存在或未启用")
        assignee_id = assignee_id or (definition.config or {}).get("default_assignee_id") or getattr(applicant, "id", applicant)
        assignee = db.session.get(User, int(assignee_id)) if assignee_id else None
        if not assignee or assignee.is_deleted:
            raise ValueError("审批人不存在")

        instance = WorkflowInstance(
            definition_id=definition.id,
            business_type=business_type,
            business_id=str(business_id),
            applicant_id=getattr(applicant, "id", applicant),
            status=WorkflowInstance.STATUS_RUNNING,
            current_node_key=self.DEFAULT_NODE_KEY,
            variables=variables or {},
        )
        db.session.add(instance)
        db.session.flush()

        task = WorkflowTask(
            instance_id=instance.id,
            node_key=self.DEFAULT_NODE_KEY,
            title=title or f"{definition.name} #{business_id}",
            assignee_id=assignee.id,
            status=WorkflowTask.STATUS_PENDING,
        )
        db.session.add(task)
        db.session.flush()
        applicant_id = getattr(applicant, "id", applicant)
        self._log(instance, "started", applicant_id, payload={"task_id": task.id})
        record_workflow_started_event(instance, task, created_by=applicant_id)
        return instance, task

    def todo_tasks(self, user):
        return (
            WorkflowTask.query
            .filter_by(assignee_id=user.id, status=WorkflowTask.STATUS_PENDING, is_deleted=False)
            .order_by(WorkflowTask.created_at.asc())
            .all()
        )

    def approve_task(self, task_id, user, *, comment=None):
        task = self._pending_task_for_action(task_id, user)
        task.status = WorkflowTask.STATUS_APPROVED
        task.action_by = user.id
        task.action_at = utcnow()
        task.comment = comment
        instance = task.instance
        instance.status = WorkflowInstance.STATUS_APPROVED
        instance.completed_at = utcnow()
        instance.current_node_key = None
        self._log(instance, "approved", user.id, task=task, comment=comment)
        record_workflow_task_event(task, "WorkflowTaskApproved", created_by=user.id)
        return instance

    def reject_task(self, task_id, user, *, comment=None):
        task = self._pending_task_for_action(task_id, user)
        task.status = WorkflowTask.STATUS_REJECTED
        task.action_by = user.id
        task.action_at = utcnow()
        task.comment = comment
        instance = task.instance
        instance.status = WorkflowInstance.STATUS_REJECTED
        instance.completed_at = utcnow()
        instance.current_node_key = None
        self._log(instance, "rejected", user.id, task=task, comment=comment)
        record_workflow_task_event(task, "WorkflowTaskRejected", created_by=user.id)
        return instance

    def transfer_task(self, task_id, user, target_user_id, *, comment=None):
        task = self._pending_task_for_action(task_id, user)
        target = db.session.get(User, int(target_user_id))
        if not target or target.is_deleted:
            raise ValueError("转交目标用户不存在")
        old_assignee = task.assignee_id
        task.assignee_id = target.id
        task.comment = comment
        self._log(task.instance, "transferred", user.id, task=task, comment=comment, payload={"from": old_assignee, "to": target.id})
        return task

    def _pending_task_for_action(self, task_id, user):
        task = db.session.get(WorkflowTask, task_id)
        if not task or task.is_deleted:
            raise ValueError("工作流任务不存在")
        if task.status != WorkflowTask.STATUS_PENDING:
            raise ValueError("任务已处理")
        if task.assignee_id != user.id:
            raise PermissionError("只能处理自己的待办任务")
        return task

    def _log(self, instance, action, actor_id, *, task=None, comment=None, payload=None):
        log = WorkflowLog(
            instance_id=instance.id,
            task_id=task.id if task else None,
            action=action,
            actor_id=actor_id,
            comment=comment,
            payload=payload or {},
        )
        db.session.add(log)
        return log


workflow_service = WorkflowService()
