from app.platform.jobs.ai import embed_document_chunks
from app.platform.jobs.celery_app import celery_app


@celery_app.task(name="nexus.ai.embed_document_chunks")
def embed_document_chunks_task(source_type=None, source_id=None, limit=50):
    return embed_document_chunks(source_type=source_type, source_id=source_id, limit=limit)


__all__ = ["embed_document_chunks_task"]
