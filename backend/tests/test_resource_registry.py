from collections import Counter

from app import create_app
from app.domains.resources import iter_domain_resources, register_resources
from app.platform.crud.resource_registry import ResourceRegistry


def test_domain_resource_keys_are_unique():
    keys = [key for resources in iter_domain_resources() for key in resources]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)

    assert duplicates == []


def test_resource_registry_resolves_domain_resources_and_aliases():
    registry = ResourceRegistry()
    registry.set_aliases({"reports": "generated-reports"})
    register_resources(registry, reset=True)

    expected = {
        "users",
        "products",
        "stock",
        "orders",
        "purchase-orders",
        "receivables",
        "stocktakes",
        "generated-reports",
        "files",
        "ai-sessions",
    }

    assert expected <= set(registry)
    assert registry.get("reports") == registry.get("generated-reports")
    assert registry.get("products")["permission"] == "masterdata.write"
    assert registry.get("stock")["blocked_write_fields"] == ["quantity", "product_id", "warehouse_id"]


def test_app_starts_with_registry_backed_generic_resource_routes():
    app = create_app("testing")

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/<resource>" in rules
    assert "/api/v1/<resource>/<int:item_id>" in rules

    with app.test_request_context("/"):
        from app.api.routes import RESOURCE_CONFIG, resource_config, serializer_for

        assert "products" in RESOURCE_CONFIG
        assert resource_config("reports") == resource_config("generated-reports")
        assert callable(serializer_for(resource_config("products")))


def test_inventory_domain_health_query_serializes_legacy_contract():
    from app.domains.inventory.application import InventoryHealthQuery

    class Product:
        id = 7
        sku = "LOW-001"
        name = "低库存物料"
        min_stock = 5

    class Repository:
        def product_stock_totals(self):
            return [(Product(), 3)]

    payload = InventoryHealthQuery(Repository()).execute().to_dict()

    assert payload == {
        "total_products": 1,
        "low_stock_products": 1,
        "out_of_stock_products": 0,
        "stock_quantity": 3,
        "risk_items": [
            {
                "id": 7,
                "sku": "LOW-001",
                "name": "低库存物料",
                "total_stock": 3,
                "min_stock": 5,
            }
        ],
    }


def test_identity_domain_register_profile_normalization_and_validation():
    from app.domains.identity.domain import normalize_register_payload, validate_register_profile

    values = normalize_register_payload({
        "email": "  Member@Nexus.COM ",
        "username": " member.ops ",
        "full_name": " 成员 ",
        "position": " 计划专员 ",
        "department_name": " 供应链 ",
        "phone": " +86 138 0000 0000 ",
        "password": "member123A",
    })

    assert values["email"] == "member@nexus.com"
    assert values["username"] == "member.ops"
    assert values["position"] == "计划专员"

    _values, errors = validate_register_profile({
        "email": "bad",
        "username": "x",
        "full_name": "A",
        "position": "",
        "department_name": "",
        "password": "short",
    })

    assert {"email", "username", "full_name", "position", "department_name", "password"} <= set(errors)


def test_platform_crud_helpers_are_reexported_for_legacy_routes():
    from app.api import routes
    from app.platform.crud.query_builder import invalid_write_fields, read_fields
    from app.platform.crud.serializers import parse_bool, serialize_model

    assert routes.parse_bool is parse_bool
    assert routes.serialize_model is serialize_model
    assert routes.read_fields is read_fields
    assert routes.invalid_write_fields is invalid_write_fields
    assert routes.parse_bool("yes") is True
    assert routes.invalid_write_fields({"create": ["name"], "blocked_write_fields": ["id"]}, {"id": 1, "name": "x"}, "create") == ["id"]


def test_platform_resource_api_powers_legacy_serializer_and_query_helpers():
    app = create_app("testing")

    with app.test_request_context("/?q=motor&sort=id&order=desc"):
        from app.api import routes
        from app.platform.crud.generic_resource_api import (
            query_for_resource as generic_query_for_resource,
            serializer_for_config as generic_serializer_for_config,
        )
        from app.models.biz import Product
        from app.platform.crud.resource_api import query_for_resource, serializer_for_config

        config = {
            "model": Product,
            "search": ["name"],
            "filterable": [],
            "serializer": lambda item: {"value": item},
        }

        assert generic_query_for_resource is query_for_resource
        assert generic_serializer_for_config is serializer_for_config
        assert routes.serializer_for(config)("placeholder") == serializer_for_config(config, routes.SERIALIZER_EXTRAS)("placeholder")
        assert routes.query_for(config).__class__ is query_for_resource(config, None, routes.request.args).__class__
