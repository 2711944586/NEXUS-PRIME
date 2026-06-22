import uuid
from dataclasses import dataclass, field

from app.utils.time import utcnow


def event_uuid():
    return str(uuid.uuid4())


@dataclass(frozen=True)
class DomainEventMessage:
    """In-memory event shape for EventBus usage outside the database outbox."""

    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    event_id: str = field(default_factory=event_uuid)
    tenant_id: str | None = None
    created_by: str | None = None
    trace_id: str | None = None
    occurred_at: object = field(default_factory=utcnow)

    def __post_init__(self):
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if self.aggregate_id is None:
            raise ValueError("aggregate_id is required")

        object.__setattr__(self, "aggregate_id", str(self.aggregate_id))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        if self.tenant_id is not None:
            object.__setattr__(self, "tenant_id", str(self.tenant_id))
        if self.created_by is not None:
            object.__setattr__(self, "created_by", str(self.created_by))
        if self.trace_id is not None:
            object.__setattr__(self, "trace_id", str(self.trace_id))

    @classmethod
    def from_outbox_row(cls, event):
        return cls(
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload or {},
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            created_by=event.created_by,
            trace_id=event.trace_id,
            occurred_at=event.created_at,
        )


__all__ = ["DomainEventMessage", "event_uuid"]
