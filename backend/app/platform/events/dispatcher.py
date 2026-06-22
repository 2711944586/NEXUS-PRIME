from time import perf_counter

from app.extensions import db
from app.platform.observability import record_event_worker_summary

from .event_bus import event_bus
from .handlers import register_default_handlers
from .outbox import outbox


class EventDispatcher:
    def __init__(self, *, bus=None, store=None):
        self.bus = bus or event_bus
        self.store = store or outbox
        if bus is None:
            register_default_handlers(self.bus)

    def dispatch_pending(self, limit=100):
        started = perf_counter()
        summary = {"processed": 0, "published": 0, "failed": 0}
        try:
            for event in self.store.pending(limit=limit):
                summary["processed"] += 1
                try:
                    event.status = event.STATUS_PROCESSING
                    self.bus.publish(event)
                    event.mark_published()
                    summary["published"] += 1
                except Exception as exc:
                    event.mark_failed(exc)
                    summary["failed"] += 1
                finally:
                    db.session.add(event)
                    db.session.commit()
        finally:
            duration_ms = int(max((perf_counter() - started) * 1000, 0))
            record_event_worker_summary(summary, duration_ms)
        return summary

    def retry_failed(self, limit=100, event_type=None):
        events = self.store.retry_failed(limit=limit, event_type=event_type)
        db.session.commit()
        return {"retried": len(events), "event_ids": [event.event_id for event in events]}


event_dispatcher = EventDispatcher()
