from datetime import datetime, timezone


def utcnow():
    """Return a naive UTC datetime for existing SQLAlchemy DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
