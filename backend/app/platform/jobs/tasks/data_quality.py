from app.platform.jobs.celery_app import celery_app
from app.platform.jobs.data_quality import run_data_quality_scan


@celery_app.task(name="nexus.data_quality.scan", bind=True)
def data_quality_scan_task(self, job_id=None):
    return run_data_quality_scan(job_id=job_id, celery_task_id=self.request.id)


__all__ = ["data_quality_scan_task"]
