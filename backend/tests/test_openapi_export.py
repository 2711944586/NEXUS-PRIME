from app import create_app
from app.platform.openapi import build_openapi_schema, write_openapi_schema


def test_openapi_schema_expands_registry_resources():
    app = create_app("testing")
    schema = build_openapi_schema(app)

    assert schema["openapi"] == "3.0.3"
    assert "/api/v1/products" in schema["paths"]
    assert "/api/v1/products/{id}" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/ai/chat/stream" in schema["paths"]
    assert "/api/v1/ai/tools/run" in schema["paths"]
    assert "/api/v1/ai/drafts" in schema["paths"]
    assert "/api/v1/ai/drafts/{draft_id}/confirm" in schema["paths"]
    assert "/api/v1/ai/drafts/{draft_id}/reject" in schema["paths"]
    assert "/api/v1/operations/data-quality/scan" in schema["paths"]
    assert "/api/v1/operations/data-quality/jobs/{job_id}" in schema["paths"]
    assert "/api/v1/inventory/replenishment-suggestions/generate-job" in schema["paths"]
    assert "/api/v1/inventory/replenishment-suggestions/jobs/{job_id}" in schema["paths"]
    assert schema["paths"]["/api/v1/products"]["get"]["operationId"] == "list_products"
    assert schema["paths"]["/api/v1/inventory/replenishment-suggestions/generate-job"]["post"]["operationId"] == "post_api_replenishment_generate_job"
    assert schema["paths"]["/api/v1/inventory/replenishment-suggestions/jobs/{job_id}"]["parameters"] == [
        {"name": "job_id", "in": "path", "required": True, "schema": {"type": "string"}}
    ]
    assert schema["paths"]["/api/v1/products"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("ProductWrite")
    assert "Product" in schema["components"]["schemas"]
    assert "PageResult_Product" in schema["components"]["schemas"]


def test_openapi_schema_can_be_written_to_json(tmp_path):
    app = create_app("testing")
    output = write_openapi_schema(app, tmp_path / "openapi.json")

    text = output.read_text(encoding="utf-8")
    assert '"openapi": "3.0.3"' in text
    assert '"/api/v1/orders"' in text


def test_openapi_export_cli_writes_requested_file(tmp_path):
    app = create_app("testing")
    target = tmp_path / "contract.json"

    result = app.test_cli_runner().invoke(args=["openapi-export", "--output", str(target)])

    assert result.exit_code == 0
    assert target.exists()
    assert "OpenAPI schema exported" in result.output
