from app.extensions import db
from app.utils.time import utcnow
from .base import BaseModel


class WorkflowDefinition(BaseModel):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        db.UniqueConstraint("process_key", name="uq_workflow_definition_process_key"),
    )

    process_key = db.Column(db.String(128), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    version = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    config = db.Column(db.JSON)

    instances = db.relationship("WorkflowInstance", backref="definition", lazy="dynamic")


class WorkflowInstance(BaseModel):
    __tablename__ = "workflow_instances"

    STATUS_RUNNING = "running"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    definition_id = db.Column(db.Integer, db.ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    business_type = db.Column(db.String(128), nullable=False, index=True)
    business_id = db.Column(db.String(128), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_RUNNING, index=True)
    current_node_key = db.Column(db.String(128))
    applicant_id = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=False, index=True)
    variables = db.Column(db.JSON)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)

    applicant = db.relationship("User", foreign_keys=[applicant_id])
    tasks = db.relationship("WorkflowTask", backref="instance", cascade="all, delete-orphan", lazy="dynamic")
    logs = db.relationship("WorkflowLog", backref="instance", cascade="all, delete-orphan", lazy="dynamic")


class WorkflowTask(BaseModel):
    __tablename__ = "workflow_tasks"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_TRANSFERRED = "transferred"

    instance_id = db.Column(db.Integer, db.ForeignKey("workflow_instances.id"), nullable=False, index=True)
    node_key = db.Column(db.String(128), nullable=False, default="approval")
    title = db.Column(db.String(180), nullable=False)
    status = db.Column(db.String(32), nullable=False, default=STATUS_PENDING, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=False, index=True)
    action_by = db.Column(db.Integer, db.ForeignKey("auth_users.id"))
    action_at = db.Column(db.DateTime)
    comment = db.Column(db.Text)

    assignee = db.relationship("User", foreign_keys=[assignee_id])
    actor = db.relationship("User", foreign_keys=[action_by])


class WorkflowLog(BaseModel):
    __tablename__ = "workflow_logs"

    instance_id = db.Column(db.Integer, db.ForeignKey("workflow_instances.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("workflow_tasks.id"))
    action = db.Column(db.String(64), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("auth_users.id"))
    comment = db.Column(db.Text)
    payload = db.Column(db.JSON)

    task = db.relationship("WorkflowTask")
    actor = db.relationship("User")
