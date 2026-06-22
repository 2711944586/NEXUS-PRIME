from app.platform.policy import filter_fields, filter_query
from .query_builder import apply_search
from .serializers import serialize_model


def serializer_for_config(config, serializer_extras, user=None):
    extra_key = config.get("serializer_extra")
    if extra_key:
        extra = serializer_extras.get(extra_key)
        if extra:
            return lambda item: filter_fields(user, config["model"], serialize_model(item, extra))
    serializer = config.get("serializer") or (lambda item: serialize_model(item))
    return lambda item: filter_fields(user, config["model"], serializer(item))


def query_for_resource(config, user, request_args):
    model = config["model"]
    query = model.query
    if hasattr(model, "is_deleted"):
        query = query.filter(model.is_deleted == False)
    query = filter_query(query, model, user)
    query = apply_search(query, model, config.get("search", []))
    allowed_filters = set(config.get("filterable", []))
    sortable = allowed_filters | {"created_at", "updated_at", "id"}
    for field, value in request_args.items():
        if field in ("page", "page_size", "per_page", "q", "sort", "order"):
            continue
        if value != "" and field in allowed_filters and hasattr(model, field):
            query = query.filter(getattr(model, field) == value)
    sort = request_args.get("sort")
    if sort and sort in sortable and hasattr(model, sort):
        direction = request_args.get("order", "asc").lower()
        column = getattr(model, sort)
        query = query.order_by(column.desc() if direction == "desc" else column.asc())
    return query
