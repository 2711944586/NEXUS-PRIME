"""File domain event helpers."""

from app.platform.events import outbox


def file_deleted_payload(attachment, *, deleted_by=None):
    return {
        "attachment_id": attachment.id,
        "filename": attachment.filename,
        "filepath": attachment.filepath,
        "mimetype": attachment.mimetype,
        "size": int(attachment.size or 0),
        "uploader_id": attachment.uploader_id,
        "deleted_by": getattr(deleted_by, "id", deleted_by),
    }


def publish_file_deleted(attachment, *, deleted_by=None):
    return outbox.add(
        "FileDeleted",
        "Attachment",
        attachment.id,
        file_deleted_payload(attachment, deleted_by=deleted_by),
        created_by=getattr(deleted_by, "id", deleted_by),
    )
