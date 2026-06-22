def _coerce_limit(limit):
    try:
        return max(int(limit or 1), 1)
    except (TypeError, ValueError):
        return 100


def dispatch_pending_events(limit=100):
    from app.platform.events import event_dispatcher

    return event_dispatcher.dispatch_pending(limit=_coerce_limit(limit))


def retry_failed_events(limit=100, event_type=None):
    from app.platform.events import event_dispatcher

    normalized_event_type = str(event_type).strip() if event_type else None
    return event_dispatcher.retry_failed(
        limit=_coerce_limit(limit),
        event_type=normalized_event_type or None,
    )
