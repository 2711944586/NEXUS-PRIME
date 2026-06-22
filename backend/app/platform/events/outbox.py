from app.extensions import db
from app.models.events import DomainEvent
from app.platform.observability import current_trace_id


class Outbox:
    def add(self, event_type, aggregate_type, aggregate_id, payload, *, tenant_id=None, created_by=None, trace_id=None):
        event = DomainEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload or {},
            tenant_id=tenant_id,
            created_by=str(created_by) if created_by is not None else None,
            trace_id=trace_id or current_trace_id(),
        )
        db.session.add(event)
        return event

    def pending(self, limit=100):
        return (
            DomainEvent.query
            .filter(DomainEvent.status == DomainEvent.STATUS_PENDING)
            .order_by(DomainEvent.created_at.asc(), DomainEvent.id.asc())
            .limit(limit)
            .all()
        )

    def failed(self, limit=100, event_type=None):
        query = DomainEvent.query.filter(DomainEvent.status == DomainEvent.STATUS_FAILED)
        if event_type:
            query = query.filter(DomainEvent.event_type == event_type)
        return query.order_by(DomainEvent.updated_at.asc(), DomainEvent.id.asc()).limit(limit).all()

    def retry_failed(self, limit=100, event_type=None):
        events = self.failed(limit=limit, event_type=event_type)
        for event in events:
            event.mark_pending_for_retry()
            db.session.add(event)
        return events


outbox = Outbox()
