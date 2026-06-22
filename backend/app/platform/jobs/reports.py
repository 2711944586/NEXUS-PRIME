from app.extensions import db
from app.models.jobs import BackgroundJob
from app.models.auth import User
from app.services.audit_service import AuditService
from app.services.report_service import ReportService


def generate_report_job(job_id, report_type, params=None, user_id=None, celery_task_id=None):
    job = BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()
    if not job:
        raise ValueError(f"background job not found: {job_id}")

    try:
        job.mark_running(celery_task_id=celery_task_id)
        db.session.add(job)
        db.session.commit()

        report, data, error = ReportService.create_generated_report(report_type, params=params, generated_by=user_id)
        if error:
            raise ValueError(error)

        result = {
            "report_id": report.id,
            "report_type": report.report_type,
            "report_name": report.report_name,
            "data": data,
        }
        job.mark_success(result, resource_type="generated_report", resource_id=report.id)
        db.session.add(job)
        user = db.session.get(User, user_id) if user_id else None
        AuditService.record("reports", "generate", user, {"id": report.id, "report_type": report_type, "job_id": job.job_id})
        db.session.commit()
        return result
    except Exception as exc:
        db.session.rollback()
        job = BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()
        if job:
            job.mark_failed(exc)
            db.session.add(job)
            db.session.commit()
        raise
