import uuid

from app.extensions import db
from app.utils.time import utcnow

from .base import BaseModel


def job_uuid():
    return str(uuid.uuid4())


class BackgroundJob(BaseModel):
    __tablename__ = "background_jobs"

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    job_id = db.Column(db.String(36), unique=True, nullable=False, default=job_uuid)
    job_type = db.Column(db.String(128), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_PENDING, index=True)
    queue = db.Column(db.String(64), nullable=False, default="celery")
    task_name = db.Column(db.String(128))
    celery_task_id = db.Column(db.String(128), index=True)
    resource_type = db.Column(db.String(128))
    resource_id = db.Column(db.String(128))
    payload = db.Column(db.JSON, nullable=False, default=dict)
    result = db.Column(db.JSON)
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=True, index=True)

    creator = db.relationship("User")

    def mark_running(self, celery_task_id=None):
        self.status = self.STATUS_RUNNING
        self.started_at = self.started_at or utcnow()
        if celery_task_id:
            self.celery_task_id = celery_task_id

    def mark_success(self, result=None, *, resource_type=None, resource_id=None):
        self.status = self.STATUS_SUCCESS
        self.result = result or {}
        self.error_message = None
        self.finished_at = utcnow()
        if resource_type:
            self.resource_type = resource_type
        if resource_id is not None:
            self.resource_id = str(resource_id)

    def mark_failed(self, error_message):
        self.status = self.STATUS_FAILED
        self.error_message = str(error_message)
        self.finished_at = utcnow()
