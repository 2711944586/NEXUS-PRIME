from app.extensions import db
from app.models.auth import User
from app.models.jobs import BackgroundJob
from app.services.audit_service import AuditService
from app.services.stock_alert_service import StockAlertService


def run_replenishment_generation(job_id=None, user_id=None, celery_task_id=None):
    job = None
    if job_id:
        job = BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()
        if not job:
            raise ValueError(f"background job not found: {job_id}")

    try:
        if job:
            job.mark_running(celery_task_id=celery_task_id)
            db.session.add(job)
            db.session.commit()

        alerts_created = StockAlertService.check_all_stock_alerts()
        suggestions_created = StockAlertService.generate_replenishment_suggestions()
        result = {
            "source": "stock_alerts",
            "alerts_created": alerts_created,
            "created": suggestions_created,
            "suggestion_count": suggestions_created,
        }
        if job:
            result["job_id"] = job.job_id

        user = db.session.get(User, user_id) if user_id else None
        AuditService.record(
            "inventory",
            "generate_replenishment",
            user,
            {
                "created": suggestions_created,
                "alerts_created": alerts_created,
                "job_id": job.job_id if job else None,
            },
        )
        if job:
            job.mark_success(result, resource_type="replenishment_generation", resource_id=job.job_id)
            db.session.add(job)
        db.session.commit()
        return result
    except Exception as exc:
        db.session.rollback()
        if job:
            job = BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()
            if job:
                job.mark_failed(exc)
                db.session.add(job)
                db.session.commit()
        raise
