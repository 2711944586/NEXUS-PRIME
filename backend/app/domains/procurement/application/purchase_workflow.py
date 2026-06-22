from app.domains.workflow.application import workflow_service
from app.domains.workflow.application.workflow_service import record_workflow_task_event
from app.extensions import db
from app.models.auth import User
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowLog, WorkflowTask
from app.utils.time import utcnow


PROCESS_KEY = "purchase_order_approval"
BUSINESS_TYPE = "purchase_order"


class PurchaseApprovalWorkflow:
    def ensure_definition(self, *, default_assignee_id=None):
        config = {}
        if default_assignee_id:
            config["default_assignee_id"] = int(default_assignee_id)
        return workflow_service.create_definition(
            PROCESS_KEY,
            "采购审批",
            description="采购订单提交后进入单节点审批流程",
            config=config,
        )

    def start_for_purchase_order(self, po, applicant, *, assignee_id=None):
        task = self.pending_task_for_purchase_order(po.id)
        if task:
            return task.instance, task, False

        instance = self.running_instance_for_purchase_order(po.id)
        if instance:
            return instance, None, False

        resolved_assignee_id = assignee_id or self.default_assignee_id(applicant)
        self.ensure_definition(default_assignee_id=resolved_assignee_id)
        instance, task = workflow_service.start(
            PROCESS_KEY,
            BUSINESS_TYPE,
            po.id,
            applicant,
            variables=self.variables_for_purchase_order(po),
            assignee_id=resolved_assignee_id,
            title=f"采购单 {po.po_no} 审批",
        )
        return instance, task, True

    def complete_for_purchase_order(self, po, user, *, approved=True, comment=None):
        task = self.pending_task_for_purchase_order(po.id)
        if not task:
            return None
        if task.assignee_id != user.id and not user.can("purchase.approve"):
            raise PermissionError("只能处理自己的待办任务")
        if task.assignee_id != user.id:
            return self._complete_legacy_task(task, user, approved=approved, comment=comment)
        if approved:
            return workflow_service.approve_task(task.id, user, comment=comment)
        return workflow_service.reject_task(task.id, user, comment=comment)

    def _complete_legacy_task(self, task, user, *, approved=True, comment=None):
        task.status = WorkflowTask.STATUS_APPROVED if approved else WorkflowTask.STATUS_REJECTED
        task.action_by = user.id
        task.action_at = utcnow()
        task.comment = comment
        instance = task.instance
        instance.status = WorkflowInstance.STATUS_APPROVED if approved else WorkflowInstance.STATUS_REJECTED
        instance.completed_at = utcnow()
        instance.current_node_key = None
        db.session.add(WorkflowLog(
            instance_id=instance.id,
            task_id=task.id,
            action="approved" if approved else "rejected",
            actor_id=user.id,
            comment=comment,
            payload={"legacy_purchase_action": True},
        ))
        record_workflow_task_event(
            task,
            "WorkflowTaskApproved" if approved else "WorkflowTaskRejected",
            created_by=user.id,
            extra={"legacy_purchase_action": True},
        )
        return instance

    def pending_task_for_purchase_order(self, po_id):
        return (
            WorkflowTask.query
            .join(WorkflowInstance, WorkflowTask.instance_id == WorkflowInstance.id)
            .filter(
                WorkflowInstance.business_type == BUSINESS_TYPE,
                WorkflowInstance.business_id == str(po_id),
                WorkflowInstance.status == WorkflowInstance.STATUS_RUNNING,
                WorkflowInstance.is_deleted == False,
                WorkflowTask.status == WorkflowTask.STATUS_PENDING,
                WorkflowTask.is_deleted == False,
            )
            .order_by(WorkflowTask.id.desc())
            .first()
        )

    def running_instance_for_purchase_order(self, po_id):
        return (
            WorkflowInstance.query
            .join(WorkflowDefinition, WorkflowInstance.definition_id == WorkflowDefinition.id)
            .filter(
                WorkflowDefinition.process_key == PROCESS_KEY,
                WorkflowInstance.business_type == BUSINESS_TYPE,
                WorkflowInstance.business_id == str(po_id),
                WorkflowInstance.status == WorkflowInstance.STATUS_RUNNING,
                WorkflowInstance.is_deleted == False,
            )
            .order_by(WorkflowInstance.id.desc())
            .first()
        )

    def default_assignee_id(self, applicant):
        applicant_id = getattr(applicant, "id", applicant)
        if applicant and hasattr(applicant, "can") and applicant.can("purchase.approve"):
            return applicant_id

        users = (
            User.query
            .filter(User.is_deleted == False, User.is_active_user == True)
            .order_by(User.is_admin.desc(), User.id.asc())
            .all()
        )
        for user in users:
            if user.can("purchase.approve"):
                return user.id
        return applicant_id

    def variables_for_purchase_order(self, po):
        return {
            "po_no": po.po_no,
            "amount": float(po.total_amount or 0),
            "supplier_id": po.supplier_id,
            "warehouse_id": po.warehouse_id,
        }


purchase_approval_workflow = PurchaseApprovalWorkflow()


__all__ = [
    "BUSINESS_TYPE",
    "PROCESS_KEY",
    "PurchaseApprovalWorkflow",
    "purchase_approval_workflow",
]
