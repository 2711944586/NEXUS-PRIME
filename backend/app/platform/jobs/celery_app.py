import os
from time import perf_counter

try:
    from celery import Celery
except ImportError as exc:  # pragma: no cover - exercised only before deps are installed
    Celery = None
    _celery_import_error = exc
else:
    _celery_import_error = None


def _require_celery():
    if Celery is None:
        raise RuntimeError("Celery is not installed. Install backend requirements before starting a worker.") from _celery_import_error


def create_celery_app(flask_app=None):
    _require_celery()
    if flask_app is None:
        from app import create_app

        flask_app = create_app(os.environ.get("FLASK_CONFIG", "default"))
    from app.platform.jobs.schedules import beat_schedule

    celery = Celery(
        "nexus_prime",
        broker=flask_app.config["CELERY_BROKER_URL"],
        backend=flask_app.config["CELERY_RESULT_BACKEND"],
    )
    celery.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=flask_app.config.get("CELERY_TASK_ALWAYS_EAGER", False),
        task_eager_propagates=flask_app.config.get("CELERY_TASK_EAGER_PROPAGATES", False),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_default_queue="celery",
        task_routes={
            "nexus.ai.*": {"queue": "ai"},
            "nexus.data_quality.*": {"queue": "data-quality"},
            "nexus.events.*": {"queue": "events"},
            "nexus.replenishment.*": {"queue": "replenishment"},
            "nexus.reports.*": {"queue": "reports"},
        },
        beat_schedule=beat_schedule(flask_app.config),
        worker_prefetch_multiplier=1,
        task_track_started=True,
    )

    class FlaskContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            from app.platform.observability import record_task_execution

            started = perf_counter()
            status = "success"
            with flask_app.app_context():
                try:
                    return self.run(*args, **kwargs)
                except Exception:
                    status = "failed"
                    raise
                finally:
                    duration_ms = int(max((perf_counter() - started) * 1000, 0))
                    record_task_execution(getattr(self, "name", None) or self.__class__.__name__, status, duration_ms)

    celery.Task = FlaskContextTask
    celery.flask_app = flask_app
    return celery


celery_app = create_celery_app()
app = celery_app

import app.platform.jobs.tasks.events  # noqa: E402,F401
import app.platform.jobs.tasks.reports  # noqa: E402,F401
import app.platform.jobs.tasks.ai  # noqa: E402,F401
import app.platform.jobs.tasks.data_quality  # noqa: E402,F401
import app.platform.jobs.tasks.replenishment  # noqa: E402,F401
