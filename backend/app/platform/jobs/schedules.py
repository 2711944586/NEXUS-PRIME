DEFAULT_OUTBOX_DISPATCH_SECONDS = 30
DEFAULT_OUTBOX_RETRY_SECONDS = 300
DEFAULT_EMBEDDING_SECONDS = 120


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def beat_schedule(config):
    """Build Celery beat schedule from Flask config values."""

    dispatch_seconds = _positive_int(
        config.get("CELERY_OUTBOX_DISPATCH_SECONDS"),
        DEFAULT_OUTBOX_DISPATCH_SECONDS,
    )
    retry_seconds = _positive_int(
        config.get("CELERY_OUTBOX_RETRY_SECONDS"),
        DEFAULT_OUTBOX_RETRY_SECONDS,
    )
    embedding_seconds = _positive_int(
        config.get("CELERY_AI_EMBEDDING_SECONDS"),
        DEFAULT_EMBEDDING_SECONDS,
    )
    dispatch_limit = _positive_int(config.get("CELERY_OUTBOX_DISPATCH_LIMIT"), 100)
    retry_limit = _positive_int(config.get("CELERY_OUTBOX_RETRY_LIMIT"), 25)
    embedding_limit = _positive_int(config.get("CELERY_AI_EMBEDDING_LIMIT"), 50)

    return {
        "outbox-dispatch-pending-events": {
            "task": "nexus.events.dispatch_pending",
            "schedule": dispatch_seconds,
            "kwargs": {"limit": dispatch_limit},
            "options": {"queue": "events"},
        },
        "outbox-retry-failed-events": {
            "task": "nexus.events.retry_failed",
            "schedule": retry_seconds,
            "kwargs": {"limit": retry_limit},
            "options": {"queue": "events"},
        },
        "ai-embed-pending-document-chunks": {
            "task": "nexus.ai.embed_document_chunks",
            "schedule": embedding_seconds,
            "kwargs": {"limit": embedding_limit},
            "options": {"queue": "ai"},
        },
    }
