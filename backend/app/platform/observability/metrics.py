from __future__ import annotations

from collections import Counter
from threading import Lock

from flask import has_app_context

from app.models.events import DomainEvent
from app.platform.observability.tracing import tracing_status

_lock = Lock()
_http_total: Counter[tuple[str, str, int]] = Counter()
_last_duration_ms: dict[tuple[str, str, int], int] = {}
_task_total: Counter[tuple[str, str]] = Counter()
_task_failed_total: Counter[str] = Counter()
_task_last_duration_ms: dict[tuple[str, str], int] = {}
_event_worker_total: Counter[str] = Counter()


def reset_metrics() -> None:
    with _lock:
        _http_total.clear()
        _last_duration_ms.clear()
        _task_total.clear()
        _task_failed_total.clear()
        _task_last_duration_ms.clear()
        _event_worker_total.clear()


def record_http_request(method: str, path: str, status_code: int, duration_ms: int) -> None:
    key = (method.upper(), path, int(status_code))
    with _lock:
        _http_total[key] += 1
        _last_duration_ms[key] = int(max(duration_ms, 0))


def record_task_execution(task_name: str, status: str, duration_ms: int) -> None:
    normalized_status = status or "unknown"
    key = (task_name or "unknown", normalized_status)
    with _lock:
        _task_total[key] += 1
        _task_last_duration_ms[key] = int(max(duration_ms, 0))
        if normalized_status == "failed":
            _task_failed_total[task_name or "unknown"] += 1


def record_event_worker_summary(summary: dict[str, int], duration_ms: int) -> None:
    with _lock:
        _event_worker_total["runs"] += 1
        _event_worker_total["processed"] += int(summary.get("processed", 0) or 0)
        _event_worker_total["published"] += int(summary.get("published", 0) or 0)
        _event_worker_total["failed"] += int(summary.get("failed", 0) or 0)
        _event_worker_total["last_duration_ms"] = int(max(duration_ms, 0))


def _http_snapshot() -> list[dict[str, object]]:
    with _lock:
        return [
            {
                "method": method,
                "path": path,
                "status_code": status_code,
                "count": count,
                "last_duration_ms": _last_duration_ms.get((method, path, status_code), 0),
            }
            for (method, path, status_code), count in sorted(_http_total.items())
        ]


def _task_snapshot() -> list[dict[str, object]]:
    with _lock:
        return [
            {
                "task_name": task_name,
                "status": status,
                "count": count,
                "last_duration_seconds": round(_task_last_duration_ms.get((task_name, status), 0) / 1000, 6),
            }
            for (task_name, status), count in sorted(_task_total.items())
        ]


def _task_failed_snapshot() -> list[dict[str, object]]:
    with _lock:
        return [
            {"task_name": task_name, "count": count}
            for task_name, count in sorted(_task_failed_total.items())
        ]


def _event_worker_snapshot() -> dict[str, int]:
    with _lock:
        return dict(_event_worker_total)


def _domain_event_counts() -> dict[str, int]:
    if not has_app_context():
        return {"pending": 0, "failed": 0}
    return {
        "pending": DomainEvent.query.filter_by(status=DomainEvent.STATUS_PENDING).count(),
        "failed": DomainEvent.query.filter_by(status=DomainEvent.STATUS_FAILED).count(),
    }


def metrics_snapshot() -> dict[str, object]:
    domain_events = _domain_event_counts()
    return {
        "http_request_total": _http_snapshot(),
        "celery_task_duration_seconds": _task_snapshot(),
        "celery_task_failed_total": _task_failed_snapshot(),
        "domain_event_worker_total": _event_worker_snapshot(),
        "domain_event_pending_total": domain_events["pending"],
        "domain_event_failed_total": domain_events["failed"],
        "tracing": tracing_status(),
    }
