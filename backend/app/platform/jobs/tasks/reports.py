from app.platform.jobs.celery_app import celery_app
from app.platform.jobs.reports import generate_report_job


@celery_app.task(name="nexus.reports.generate", bind=True)
def generate_report_task(self, job_id, report_type, params=None, user_id=None):
    return generate_report_job(
        job_id,
        report_type,
        params=params,
        user_id=user_id,
        celery_task_id=self.request.id,
    )


__all__ = ["generate_report_task"]
