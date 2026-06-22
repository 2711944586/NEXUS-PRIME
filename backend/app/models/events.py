import uuid

from app.extensions import db
from app.utils.time import utcnow
from .base import BaseModel


def event_uuid():
    return str(uuid.uuid4())


class DomainEvent(BaseModel):
    __tablename__ = "domain_events"

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PUBLISHED = "published"
    STATUS_FAILED = "failed"

    event_id = db.Column(db.String(36), unique=True, nullable=False, default=event_uuid)
    event_type = db.Column(db.String(128), nullable=False, index=True)
    aggregate_type = db.Column(db.String(128), nullable=False)
    aggregate_id = db.Column(db.String(128), nullable=False)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(32), nullable=False, default=STATUS_PENDING, index=True)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    published_at = db.Column(db.DateTime)
    trace_id = db.Column(db.String(128))
    tenant_id = db.Column(db.String(128))
    created_by = db.Column(db.String(128))

    def mark_published(self):
        self.status = self.STATUS_PUBLISHED
        self.published_at = utcnow()
        self.error_message = None

    def mark_failed(self, error_message):
        self.status = self.STATUS_FAILED
        self.retry_count = (self.retry_count or 0) + 1
        self.error_message = str(error_message)

    def mark_pending_for_retry(self):
        self.status = self.STATUS_PENDING
        self.error_message = None
        self.published_at = None
