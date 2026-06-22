from app.extensions import db
from app.models.jobs import BackgroundJob


def create_background_job(job_type, payload=None, *, created_by=None, queue="celery", task_name=None):
    job = BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        created_by=getattr(created_by, "id", created_by),
        queue=queue,
        task_name=task_name,
    )
    db.session.add(job)
    db.session.flush()
    return job


def get_background_job(job_id):
    return BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()


def serialize_background_job(job):
    data = job.to_dict()
    data["database_id"] = data["id"]
    data["id"] = job.job_id
    return data
