from app.platform.jobs.celery_app import celery_app
from app.platform.jobs.replenishment import run_replenishment_generation


@celery_app.task(name="nexus.replenishment.generate", bind=True)
def replenishment_generate_task(self, job_id=None, user_id=None):
    return run_replenishment_generation(job_id=job_id, user_id=user_id, celery_task_id=self.request.id)


__all__ = ["replenishment_generate_task"]
