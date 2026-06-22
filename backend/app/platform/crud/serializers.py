from datetime import date, datetime
from decimal import Decimal


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_model(obj, extra=None):
    if obj is None:
        return None
    data = {}
    for column in obj.__table__.columns:
        if column.name == "password_hash":
            continue
        data[column.name] = serialize_value(getattr(obj, column.name))
    if extra:
        data.update(extra(obj))
    return data
