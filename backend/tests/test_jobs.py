import importlib

import pytest

from app import create_app
from app.extensions import db
from app.models.events import DomainEvent
from app.models.jobs import BackgroundJob
from app.platform.events import Outbox
from app.platform.jobs.background_jobs import create_background_job
from app.platform.jobs.events import dispatch_pending_events
from app.platform.jobs.reports import generate_report_job
from app.platform.jobs.schedules import beat_schedule
from app.platform.observability import metrics_snapshot, reset_metrics


def test_dispatch_pending_events_job_consumes_outbox():
    app = create_app("testing")
    reset_metrics()

    with app.app_context():
        db.create_all()
        event = Outbox().add("NoHandlers", "Test", "1", {})
        db.session.commit()
        event_id = event.id

        summary = dispatch_pending_events(limit=5)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        assert db.session.get(DomainEvent, event_id).status == DomainEvent.STATUS_PUBLISHED
        worker_metrics = metrics_snapshot()["domain_event_worker_total"]
        assert worker_metrics["runs"] == 1
        assert worker_metrics["processed"] == 1
        assert worker_metrics["published"] == 1
        assert worker_metrics["failed"] == 0
        assert worker_metrics["last_duration_ms"] >= 0

        db.session.remove()
        db.drop_all()


def test_celery_failed_task_records_failure_metric(monkeypatch):
    pytest.importorskip("celery")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    celery_module = importlib.import_module("app.platform.jobs.celery_app")
    celery_module = importlib.reload(celery_module)
    reset_metrics()

    task = celery_module.celery_app.tasks["nexus.reports.generate"]
    with celery_module.celery_app.flask_app.app_context():
        db.create_all()
        job = create_background_job("report.generate", {"report_type": "missing"}, created_by=None, queue="reports")
        db.session.commit()

        result = task.apply(
            kwargs={"job_id": job.job_id, "report_type": "missing", "params": {}, "user_id": None},
            throw=False,
        )

        assert result.failed()
        metrics = metrics_snapshot()
        assert any(
            item["task_name"] == "nexus.reports.generate"
            and item["status"] == "failed"
            and item["count"] == 1
            for item in metrics["celery_task_duration_seconds"]
        )
        assert metrics["celery_task_failed_total"] == [{"task_name": "nexus.reports.generate", "count": 1}]

        db.session.remove()
        db.drop_all()


def test_celery_dispatch_task_is_registered_and_runs_eager(monkeypatch):
    pytest.importorskip("celery")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    celery_module = importlib.import_module("app.platform.jobs.celery_app")
    celery_module = importlib.reload(celery_module)
    reset_metrics()

    task = celery_module.celery_app.tasks["nexus.events.dispatch_pending"]
    with celery_module.celery_app.flask_app.app_context():
        db.create_all()
        event = Outbox().add("NoHandlers", "Test", "1", {})
        db.session.commit()
        event_id = event.id

        result = task.apply(kwargs={"limit": 5})

        assert result.successful()
        assert result.result == {"processed": 1, "published": 1, "failed": 0}
        db.session.expire_all()
        assert db.session.get(DomainEvent, event_id).status == DomainEvent.STATUS_PUBLISHED
        metrics = metrics_snapshot()
        assert any(
            item["task_name"] == "nexus.events.dispatch_pending"
            and item["status"] == "success"
            and item["count"] == 1
            for item in metrics["celery_task_duration_seconds"]
        )
        assert metrics["celery_task_failed_total"] == []

        db.session.remove()
        db.drop_all()


def test_celery_retry_failed_events_task_requeues_filtered_events(monkeypatch):
    pytest.importorskip("celery")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    celery_module = importlib.import_module("app.platform.jobs.celery_app")
    celery_module = importlib.reload(celery_module)
    reset_metrics()

    task = celery_module.celery_app.tasks["nexus.events.retry_failed"]
    with celery_module.celery_app.flask_app.app_context():
        db.create_all()
        target = Outbox().add("RetryTarget", "Test", "1", {})
        other = Outbox().add("RetryOther", "Test", "2", {})
        db.session.flush()
        target.mark_failed("target failure")
        other.mark_failed("other failure")
        db.session.commit()
        target_event_id = target.event_id
        other_id = other.id

        result = task.apply(kwargs={"limit": 5, "event_type": "RetryTarget"})

        assert result.successful()
        assert result.result == {"retried": 1, "event_ids": [target_event_id]}
        db.session.expire_all()
        assert db.session.get(DomainEvent, target.id).status == DomainEvent.STATUS_PENDING
        assert db.session.get(DomainEvent, other_id).status == DomainEvent.STATUS_FAILED
        metrics = metrics_snapshot()
        assert any(
            item["task_name"] == "nexus.events.retry_failed"
            and item["status"] == "success"
            and item["count"] == 1
            for item in metrics["celery_task_duration_seconds"]
        )
        assert metrics["celery_task_failed_total"] == []

        db.session.remove()
        db.drop_all()


def test_celery_beat_schedule_covers_outbox_retry_and_ai_embedding():
    schedule = beat_schedule({})

    assert schedule["outbox-dispatch-pending-events"]["task"] == "nexus.events.dispatch_pending"
    assert schedule["outbox-dispatch-pending-events"]["options"] == {"queue": "events"}
    assert schedule["outbox-retry-failed-events"]["task"] == "nexus.events.retry_failed"
    assert schedule["outbox-retry-failed-events"]["kwargs"] == {"limit": 25}
    assert schedule["ai-embed-pending-document-chunks"]["task"] == "nexus.ai.embed_document_chunks"
    assert schedule["ai-embed-pending-document-chunks"]["options"] == {"queue": "ai"}

    configured = beat_schedule(
        {
            "CELERY_OUTBOX_DISPATCH_SECONDS": "9",
            "CELERY_OUTBOX_DISPATCH_LIMIT": "11",
            "CELERY_OUTBOX_RETRY_SECONDS": "15",
            "CELERY_AI_EMBEDDING_SECONDS": "21",
            "CELERY_AI_EMBEDDING_LIMIT": "7",
        }
    )
    assert configured["outbox-dispatch-pending-events"]["schedule"] == 9
    assert configured["outbox-dispatch-pending-events"]["kwargs"] == {"limit": 11}
    assert configured["outbox-retry-failed-events"]["schedule"] == 15
    assert configured["ai-embed-pending-document-chunks"]["schedule"] == 21
    assert configured["ai-embed-pending-document-chunks"]["kwargs"] == {"limit": 7}


def test_celery_app_loads_platform_beat_schedule(monkeypatch):
    pytest.importorskip("celery")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    celery_module = importlib.import_module("app.platform.jobs.celery_app")
    celery_module = importlib.reload(celery_module)

    schedule = celery_module.celery_app.conf.beat_schedule
    assert schedule["outbox-dispatch-pending-events"]["task"] == "nexus.events.dispatch_pending"
    assert schedule["outbox-retry-failed-events"]["task"] == "nexus.events.retry_failed"
    assert schedule["ai-embed-pending-document-chunks"]["task"] == "nexus.ai.embed_document_chunks"


def test_celery_data_quality_scan_task_marks_job_success(monkeypatch):
    pytest.importorskip("celery")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    celery_module = importlib.import_module("app.platform.jobs.celery_app")
    celery_module = importlib.reload(celery_module)
    reset_metrics()

    task = celery_module.celery_app.tasks["nexus.data_quality.scan"]
    with celery_module.celery_app.flask_app.app_context():
        db.create_all()
        job = create_background_job("data_quality.scan", {"source": "manual"}, queue="data-quality")
        db.session.commit()
        job_id = job.job_id

        result = task.apply(kwargs={"job_id": job_id})

        assert result.successful()
        assert result.result["source"] == "database_quality_contract"
        assert result.result["summary"]["total_tests"] >= 8
        db.session.expire_all()
        stored = BackgroundJob.query.filter_by(job_id=job_id).one()
        assert stored.status == BackgroundJob.STATUS_SUCCESS
        assert stored.queue == "data-quality"
        assert stored.resource_type == "data_quality_scan"
        assert stored.resource_id == job_id
        assert stored.result["source"] == "database_quality_contract"
        metrics = metrics_snapshot()
        assert any(
            item["task_name"] == "nexus.data_quality.scan"
            and item["status"] == "success"
            and item["count"] == 1
            for item in metrics["celery_task_duration_seconds"]
        )

        db.session.remove()
        db.drop_all()


def test_report_job_marks_success_with_generated_report():
    app = create_app("testing")
    reset_metrics()

    with app.app_context():
        db.create_all()
        job = create_background_job("report.generate", {"report_type": "sales_daily"}, created_by=None, queue="reports")
        db.session.commit()
        job_id = job.job_id

        result = generate_report_job(job_id, "sales_daily", params={}, user_id=None, celery_task_id="test-task")

        stored = BackgroundJob.query.filter_by(job_id=job_id).one()
        assert stored.status == BackgroundJob.STATUS_SUCCESS
        assert stored.resource_type == "generated_report"
        assert stored.resource_id == str(result["report_id"])
        assert stored.result["report_type"] == "sales_daily"
        assert stored.celery_task_id == "test-task"

        db.session.remove()
        db.drop_all()


def test_report_job_marks_failed_when_generator_errors():
    app = create_app("testing")
    reset_metrics()

    with app.app_context():
        db.create_all()
        job = create_background_job("report.generate", {"report_type": "missing"}, created_by=None, queue="reports")
        db.session.commit()
        job_id = job.job_id

        with pytest.raises(ValueError, match="报表生成器不存在"):
            generate_report_job(job_id, "missing", params={}, user_id=None, celery_task_id="test-task")

        stored = BackgroundJob.query.filter_by(job_id=job_id).one()
        assert stored.status == BackgroundJob.STATUS_FAILED
        assert "报表生成器不存在" in stored.error_message
        assert stored.finished_at is not None

        db.session.remove()
        db.drop_all()
