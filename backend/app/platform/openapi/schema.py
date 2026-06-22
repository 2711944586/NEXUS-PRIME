from __future__ import annotations

import re
from collections.abc import Iterable

from flask import Flask
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, Text, Time
from sqlalchemy.sql.sqltypes import JSON, String


PATH_PARAM_RE = re.compile(r"<(?:(?P<converter>[A-Za-z_][A-Za-z0-9_]*):)?(?P<name>[^>]+)>")


def build_openapi_schema(app: Flask) -> dict:
    """Build an OpenAPI document from Flask routes and registered CRUD resources."""
    from app.api.resource_support import RESOURCE_ALIASES, RESOURCE_CONFIG

    components = base_components()
    paths: dict[str, dict] = {}
    resource_components: dict[str, str] = {}

    for resource, config in RESOURCE_CONFIG.items():
        model = config["model"]
        component_name = unique_component_name(components["schemas"], model.__name__)
        if component_name not in components["schemas"]:
            components["schemas"][component_name] = model_schema(model)
        resource_components[resource] = component_name
        add_resource_paths(paths, components, resource, config, component_name)

    for alias, canonical in RESOURCE_ALIASES.items():
        if canonical in resource_components:
            add_resource_paths(paths, components, alias, RESOURCE_CONFIG[canonical], resource_components[canonical])

    add_runtime_routes(paths, app.url_map.iter_rules())

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "NEXUS PRIME API",
            "version": "0.1.0",
            "description": "Runtime API contract generated from Flask routes and ResourceRegistry.",
        },
        "servers": [{"url": "/"}],
        "paths": dict(sorted(paths.items())),
        "components": components,
    }


def base_components() -> dict:
    return {
        "schemas": {
            "ApiEnvelope": api_envelope_schema({"description": "Endpoint payload."}),
            "ErrorEnvelope": api_envelope_schema({"nullable": True}),
            "PageMeta": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                    "total": {"type": "integer"},
                    "pages": {"type": "integer"},
                    "has_next": {"type": "boolean"},
                    "has_prev": {"type": "boolean"},
                },
                "required": ["page", "page_size", "total", "pages", "has_next", "has_prev"],
            },
            "DataRecord": {
                "type": "object",
                "additionalProperties": True,
            },
        }
    }


def add_resource_paths(paths: dict[str, dict], components: dict, resource: str, config: dict, component_name: str) -> None:
    list_response = ensure_page_component(components, component_name)
    write_component = ensure_write_component(components, component_name, config)
    item_ref = schema_ref(component_name)

    collection_path = f"/api/v1/{resource}"
    detail_path = f"/api/v1/{resource}/{{id}}"

    paths.setdefault(collection_path, {})
    paths[collection_path]["get"] = {
        "operationId": operation_id("list", resource),
        "tags": [resource],
        "parameters": list_query_parameters(config),
        "responses": success_response(list_response, f"{resource} list"),
    }
    paths[collection_path]["post"] = {
        "operationId": operation_id("create", resource),
        "tags": [resource],
        "requestBody": json_request_body(schema_ref(write_component)),
        "responses": success_response(item_ref, f"{resource} created", status="201"),
    }

    paths.setdefault(detail_path, {})
    paths[detail_path]["parameters"] = [path_parameter("id", "integer")]
    for method, action in (("get", "get"), ("put", "update"), ("patch", "patch"), ("delete", "delete")):
        operation = {
            "operationId": operation_id(action, resource),
            "tags": [resource],
            "responses": success_response(item_ref if method != "delete" else {"type": "object", "additionalProperties": True}, f"{resource} {action}"),
        }
        if method in {"put", "patch"}:
            operation["requestBody"] = json_request_body(schema_ref(write_component))
        paths[detail_path][method] = operation


def add_runtime_routes(paths: dict[str, dict], rules: Iterable) -> None:
    for rule in rules:
        if not rule.rule.startswith("/api/v1"):
            continue
        if "<resource>" in rule.rule or "<path:new_path>" in rule.rule:
            continue
        path = flask_rule_to_openapi_path(rule.rule)
        path_item = paths.setdefault(path, {})
        parameters = path_parameters(rule.rule)
        if parameters:
            existing = {item["name"] for item in path_item.get("parameters", [])}
            path_item.setdefault("parameters", [])
            path_item["parameters"].extend(item for item in parameters if item["name"] not in existing)
        for method in sorted((rule.methods or set()) - {"HEAD", "OPTIONS"}):
            key = method.lower()
            path_item.setdefault(key, {
                "operationId": operation_id(method.lower(), rule.endpoint),
                "tags": [path.strip("/").split("/", 2)[1] if path.startswith("/api/") else "api"],
                "responses": success_response(schema_ref("DataRecord"), "success"),
            })


def model_schema(model) -> dict:
    properties = {}
    required = []
    for column in model.__table__.columns:
        properties[column.name] = column_schema(column.type)
        if not column.nullable and not column.primary_key and column.default is None and column.server_default is None:
            required.append(column.name)
    schema = {
        "type": "object",
        "additionalProperties": True,
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def column_schema(column_type) -> dict:
    if isinstance(column_type, Boolean):
        return {"type": "boolean"}
    if isinstance(column_type, Integer):
        return {"type": "integer"}
    if isinstance(column_type, (Float, Numeric)):
        return {"type": "number"}
    if isinstance(column_type, DateTime):
        return {"type": "string", "format": "date-time"}
    if isinstance(column_type, Date):
        return {"type": "string", "format": "date"}
    if isinstance(column_type, Time):
        return {"type": "string", "format": "time"}
    if isinstance(column_type, JSON):
        return {"type": "object", "additionalProperties": True}
    if isinstance(column_type, (String, Text)):
        schema = {"type": "string"}
        length = getattr(column_type, "length", None)
        if length:
            schema["maxLength"] = length
        return schema
    return {"nullable": True}


def ensure_page_component(components: dict, item_component: str) -> dict:
    name = f"PageResult_{item_component}"
    schemas = components["schemas"]
    if name not in schemas:
        schemas[name] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {
                    "type": "array",
                    "items": schema_ref(item_component),
                },
                "pagination": schema_ref("PageMeta"),
            },
            "required": ["items", "pagination"],
        }
    return schema_ref(name)


def ensure_write_component(components: dict, item_component: str, config: dict) -> str:
    name = f"{item_component}Write"
    schemas = components["schemas"]
    if name in schemas:
        return name
    source = schemas[item_component]
    write_fields = sorted(set(config.get("create", [])) | set(config.get("update", [])))
    if not write_fields:
        schemas[name] = {"type": "object", "additionalProperties": True}
        return name
    schemas[name] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            field: source.get("properties", {}).get(field, {"nullable": True})
            for field in write_fields
        },
    }
    return name


def api_envelope_schema(data_schema: dict) -> dict:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "data": data_schema,
            "message": {"type": "string"},
            "error": {"type": "string", "nullable": True},
        },
        "required": ["data", "message", "error"],
    }


def success_response(data_schema: dict, description: str, status: str = "200") -> dict:
    return {
        status: {
            "description": description,
            "content": {
                "application/json": {
                    "schema": api_envelope_schema(data_schema),
                }
            },
        },
        "400": {"description": "Bad request", "content": {"application/json": {"schema": schema_ref("ErrorEnvelope")}}},
        "401": {"description": "Unauthorized", "content": {"application/json": {"schema": schema_ref("ErrorEnvelope")}}},
        "403": {"description": "Forbidden", "content": {"application/json": {"schema": schema_ref("ErrorEnvelope")}}},
        "404": {"description": "Not found", "content": {"application/json": {"schema": schema_ref("ErrorEnvelope")}}},
    }


def json_request_body(schema: dict) -> dict:
    return {
        "required": False,
        "content": {
            "application/json": {
                "schema": schema,
            }
        },
    }


def list_query_parameters(config: dict) -> list[dict]:
    params = [
        query_parameter("page", "integer"),
        query_parameter("page_size", "integer"),
        query_parameter("q", "string"),
        query_parameter("sort", "string"),
        query_parameter("order", "string"),
    ]
    params.extend(query_parameter(field, "string") for field in config.get("filterable", []))
    return params


def query_parameter(name: str, value_type: str) -> dict:
    return {
        "name": name,
        "in": "query",
        "required": False,
        "schema": {"type": value_type},
    }


def path_parameter(name: str, value_type: str) -> dict:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": value_type},
    }


def path_parameters(rule: str) -> list[dict]:
    return [
        path_parameter(match.group("name"), "integer" if match.group("converter") == "int" else "string")
        for match in PATH_PARAM_RE.finditer(rule)
    ]


def flask_rule_to_openapi_path(rule: str) -> str:
    return PATH_PARAM_RE.sub(lambda match: "{" + match.group("name") + "}", rule)


def schema_ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def operation_id(action: str, target: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", f"{action}_{target}").strip("_")
    return value or "operation"


def unique_component_name(schemas: dict, preferred: str) -> str:
    if preferred not in schemas:
        return preferred
    index = 2
    while f"{preferred}{index}" in schemas:
        index += 1
    return f"{preferred}{index}"
