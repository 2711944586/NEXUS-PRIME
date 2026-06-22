from collections import defaultdict

from app import create_app


def test_api_url_map_has_no_duplicate_method_routes():
    app = create_app("testing")
    seen = defaultdict(list)

    for rule in app.url_map.iter_rules():
        methods = tuple(sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"}))
        seen[(str(rule.rule), methods)].append(rule.endpoint)

    duplicates = {
        key: endpoints
        for key, endpoints in seen.items()
        if len(endpoints) > 1
    }

    assert duplicates == {}


def test_split_route_modules_keep_legacy_routes_imports_compatible():
    app = create_app("testing")
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    assert "api.list_resource" in endpoints
    assert "api.api_login" in endpoints
    assert "api.api_me" in endpoints
    assert "api.adjust_inventory" in endpoints

    from app.api import routes

    assert routes.list_resource.__module__ == "app.api.generic_crud_routes"
    assert routes.api_login.__module__ == "app.api.auth_routes"
    assert routes.api_me.__module__ == "app.api.profile_routes"
    assert routes.adjust_inventory.__module__ == "app.api.business_action_routes"
