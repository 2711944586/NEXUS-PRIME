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
