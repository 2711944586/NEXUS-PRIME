from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TracingState:
    enabled: bool = False
    configured: bool = False
    reason: str = "not_configured"
    service_name: str = "nexus-prime-backend"
    exporter: str = "none"


_state = TracingState()


def tracing_status() -> dict[str, object]:
    return {
        "enabled": _state.enabled,
        "configured": _state.configured,
        "reason": _state.reason,
        "service_name": _state.service_name,
        "exporter": _state.exporter,
    }


def configure_tracing(app, db=None) -> dict[str, object]:
    enabled = bool(app.config.get("OTEL_TRACES_ENABLED", False))
    service_name = app.config.get("OTEL_SERVICE_NAME") or "nexus-prime-backend"
    endpoint = app.config.get("OTEL_EXPORTER_OTLP_ENDPOINT") or ""
    _state.enabled = enabled
    _state.configured = False
    _state.reason = "disabled" if not enabled else "not_configured"
    _state.service_name = service_name
    _state.exporter = "none"

    if not enabled:
        return tracing_status()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        _state.reason = f"missing_dependency:{exc.__class__.__name__}"
        app.logger.warning("opentelemetry_disabled", extra={"error_code": _state.reason})
        return tracing_status()

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        _state.exporter = "otlp-http"
    else:
        _state.exporter = "none"
    trace.set_tracer_provider(provider)
    _install_request_spans(app, trace.get_tracer(service_name))

    _state.configured = True
    _state.reason = "configured"
    return tracing_status()


def _install_request_spans(app, tracer) -> None:
    from flask import g, request
    from opentelemetry.trace import SpanKind, Status, StatusCode

    @app.before_request
    def start_request_span():
        name = f"{request.method} {request.path}"
        span_context = tracer.start_as_current_span(name, kind=SpanKind.SERVER)
        span = span_context.__enter__()
        g.otel_span_context = span_context
        g.otel_span = span
        g.otel_span_finished = False
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.target", request.full_path.rstrip("?"))
        span.set_attribute("http.route", request.url_rule.rule if request.url_rule else request.path)
        span.set_attribute("url.path", request.path)
        span.set_attribute("request_id", getattr(g, "request_id", ""))
        span.set_attribute("trace_id", getattr(g, "trace_id", ""))

    @app.after_request
    def finish_request_span(response):
        _finish_request_span(status_code=response.status_code)
        return response

    @app.teardown_request
    def finish_request_span_on_exception(exc):
        if exc is not None:
            _finish_request_span(exception=exc)


def _finish_request_span(status_code: int | None = None, exception: BaseException | None = None) -> None:
    from flask import g
    from opentelemetry.trace import Status, StatusCode

    span = getattr(g, "otel_span", None)
    span_context = getattr(g, "otel_span_context", None)
    if not span or not span_context or getattr(g, "otel_span_finished", False):
        return
    if status_code is not None:
        span.set_attribute("http.status_code", int(status_code))
        if status_code >= 500:
            span.set_status(Status(StatusCode.ERROR))
    if exception is not None:
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR))
    span_context.__exit__(None, None, None)
    g.otel_span_finished = True
