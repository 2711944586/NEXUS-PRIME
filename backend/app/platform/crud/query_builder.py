from flask import request
from sqlalchemy import Date as SqlDate
from sqlalchemy import DateTime as SqlDateTime
from sqlalchemy import or_

from .serializers import parse_date, parse_datetime


def pagination_args():
    page = max(int(request.args.get("page", 1) or 1), 1)
    page_size = int(request.args.get("page_size", request.args.get("per_page", 10)) or 10)
    page_size = min(max(page_size, 1), 100)
    return page, page_size


def paginate(query, serializer, default_sort=None):
    page, page_size = pagination_args()
    if default_sort is not None:
        query = query.order_by(default_sort)
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    return {
        "items": [serializer(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "page_size": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }


def apply_search(query, model, fields):
    q = (request.args.get("q") or "").strip()
    if not q or not fields:
        return query
    filters = [getattr(model, field).ilike(f"%{q}%") for field in fields if hasattr(model, field)]
    return query.filter(or_(*filters)) if filters else query


def read_fields(model, payload, allowed):
    values = {}
    for field in allowed:
        if field in payload:
            values[field] = payload[field]
    return values


def invalid_write_fields(config, payload, action):
    allowed = set(config.get(action, []))
    blocked = set(config.get("blocked_write_fields", []))
    supplied = set(payload.keys())
    ignored = {"items"} if action == "create" else set()
    unsafe = (supplied & blocked) | (supplied - allowed - ignored)
    return sorted(field for field in unsafe)


def normalize_model_values(model, values):
    for column in model.__table__.columns:
        if column.name not in values:
            continue
        if isinstance(column.type, SqlDateTime) and isinstance(values[column.name], str):
            values[column.name] = parse_datetime(values[column.name])
        elif isinstance(column.type, SqlDate) and isinstance(values[column.name], str):
            values[column.name] = parse_date(values[column.name])
    return values
