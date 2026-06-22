from app.extensions import db
from app.models.jobs import BackgroundJob
from app.services.data_quality_service import data_quality_payload


def run_data_quality_scan(job_id=None, celery_task_id=None):
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

        payload = data_quality_payload()
        result = {
            "source": payload.get("source"),
            "generated_at": payload.get("generated_at"),
            "summary": payload.get("summary", {}),
            "issue_count": payload.get("summary", {}).get("issue_count", 0),
            "failed_tests": payload.get("summary", {}).get("failed_tests", 0),
        }

        if job:
            job.mark_success(result, resource_type="data_quality_scan", resource_id=job.job_id)
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
