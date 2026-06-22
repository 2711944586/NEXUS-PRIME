from app.platform.jobs.celery_app import celery_app
from app.platform.jobs.events import dispatch_pending_events, retry_failed_events


@celery_app.task(name="nexus.events.dispatch_pending")
def dispatch_pending_events_task(limit=100):
    return dispatch_pending_events(limit=limit)


@celery_app.task(name="nexus.events.retry_failed")
def retry_failed_events_task(limit=100, event_type=None):
    return retry_failed_events(limit=limit, event_type=event_type)


__all__ = ["dispatch_pending_events_task", "retry_failed_events_task"]
