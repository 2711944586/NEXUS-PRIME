import os
from io import BytesIO

from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.ai import DocumentChunk
from app.models.content import Attachment
from app.models.events import DomainEvent
from app.platform.events import EventDispatcher


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_file_user():
    role = Role(name="FileAdmin", is_admin=True)
    permission = Permission(name="files.manage", description="文件管理")
    role.permissions.append(permission)
    user = User(username="file-admin", email="admin@nexus.com", role=role, is_admin=True)
    user.password = "admin123"
    db.session.add_all([role, permission, user])
    db.session.commit()
    return user


def test_file_upload_writes_file_uploaded_event(tmp_path):
    app = create_app("testing")
    upload_root = tmp_path / "uploads"
    app.config.update(
        {
            "UPLOAD_FOLDER": os.fspath(upload_root),
            "UPLOAD_FILES_FOLDER": os.fspath(upload_root / "files"),
            "UPLOAD_AVATARS_FOLDER": os.fspath(upload_root / "avatars"),
            "UPLOAD_LIBRARY_FOLDER": os.fspath(upload_root / "library"),
            "REQUIRE_CLOUD_STORAGE_FOR_UPLOADS": "false",
        }
    )
    for key in ("UPLOAD_FOLDER", "UPLOAD_FILES_FOLDER", "UPLOAD_AVATARS_FOLDER", "UPLOAD_LIBRARY_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)

    with app.app_context():
        db.create_all()
        user = seed_file_user()
        client = app.test_client()
        headers = login(client)

        upload = client.post(
            "/api/v1/files/upload",
            headers=headers,
            data={"file": (BytesIO(b"NEXUS uploaded file event"), "event-file.txt")},
            content_type="multipart/form-data",
        )

        assert upload.status_code == 201
        attachment_id = upload.json["data"]["id"]
        attachment = db.session.get(Attachment, attachment_id)
        assert attachment.filename == "event-file.txt"
        assert attachment.filepath.startswith("files/")
        assert os.path.exists(os.path.join(app.config["UPLOAD_FILES_FOLDER"], attachment.filepath.split("/", 1)[1]))

        event = DomainEvent.query.filter_by(event_type="FileUploaded").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "Attachment"
        assert event.aggregate_id == str(attachment_id)
        assert event.created_by == str(user.id)
        assert event.payload == {
            "attachment_id": attachment_id,
            "filename": "event-file.txt",
            "filepath": attachment.filepath,
            "mimetype": "text/plain",
            "size": len(b"NEXUS uploaded file event"),
            "storage_provider": "local",
            "uploader_id": user.id,
        }

        bad_upload = client.post(
            "/api/v1/files/upload",
            headers=headers,
            data={"file": (BytesIO(b"<svg onload=alert(1)>"), "payload.svg", "image/svg+xml")},
            content_type="multipart/form-data",
        )

        assert bad_upload.status_code == 400
        assert DomainEvent.query.filter_by(event_type="FileUploaded").count() == 1

        db.session.remove()
        db.drop_all()


def test_file_uploaded_event_indexes_text_attachment_chunks(tmp_path):
    app = create_app("testing")
    upload_root = tmp_path / "uploads"
    app.config.update(
        {
            "UPLOAD_FOLDER": os.fspath(upload_root),
            "UPLOAD_FILES_FOLDER": os.fspath(upload_root / "files"),
            "UPLOAD_AVATARS_FOLDER": os.fspath(upload_root / "avatars"),
            "UPLOAD_LIBRARY_FOLDER": os.fspath(upload_root / "library"),
            "REQUIRE_CLOUD_STORAGE_FOR_UPLOADS": "false",
        }
    )
    for key in ("UPLOAD_FOLDER", "UPLOAD_FILES_FOLDER", "UPLOAD_AVATARS_FOLDER", "UPLOAD_LIBRARY_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)

    with app.app_context():
        db.create_all()
        seed_file_user()
        client = app.test_client()
        headers = login(client)

        content = b"NEXUS RAG upload\nsupplier quality report enters retrieval."
        upload = client.post(
            "/api/v1/files/upload",
            headers=headers,
            data={"file": (BytesIO(content), "rag-note.txt")},
            content_type="multipart/form-data",
        )

        assert upload.status_code == 201
        attachment_id = upload.json["data"]["id"]
        assert DocumentChunk.query.count() == 0

        summary = EventDispatcher().dispatch_pending(limit=10)

        assert summary == {"processed": 1, "published": 1, "failed": 0}
        chunk = DocumentChunk.query.filter_by(source_type="attachment", source_id=str(attachment_id), chunk_index=0).one()
        assert chunk.title == "rag-note.txt"
        assert "supplier quality report" in chunk.content
        assert chunk.metadata_json["filename"] == "rag-note.txt"
        assert chunk.metadata_json["storage_provider"] == "local"
        assert chunk.metadata_json["embedding_status"] == "embedded"
        assert chunk.embedding_model == "local-hash-v1"
        assert len(chunk.embedding) == 32
        assert DomainEvent.query.filter_by(event_type="FileUploaded").one().status == DomainEvent.STATUS_PUBLISHED

        replay_summary = EventDispatcher().dispatch_pending(limit=10)
        assert replay_summary == {"processed": 0, "published": 0, "failed": 0}
        assert DocumentChunk.query.count() == 1

        event = DomainEvent.query.filter_by(event_type="FileUploaded").one()
        event.mark_pending_for_retry()
        db.session.add(event)
        db.session.commit()

        retry_summary = EventDispatcher().dispatch_pending(limit=10)
        assert retry_summary == {"processed": 1, "published": 1, "failed": 0}
        assert DocumentChunk.query.count() == 1

        db.session.remove()
        db.drop_all()


def test_file_deleted_event_soft_deletes_attachment_chunks(tmp_path):
    app = create_app("testing")
    upload_root = tmp_path / "uploads"
    app.config.update(
        {
            "UPLOAD_FOLDER": os.fspath(upload_root),
            "UPLOAD_FILES_FOLDER": os.fspath(upload_root / "files"),
            "UPLOAD_AVATARS_FOLDER": os.fspath(upload_root / "avatars"),
            "UPLOAD_LIBRARY_FOLDER": os.fspath(upload_root / "library"),
            "REQUIRE_CLOUD_STORAGE_FOR_UPLOADS": "false",
        }
    )
    for key in ("UPLOAD_FOLDER", "UPLOAD_FILES_FOLDER", "UPLOAD_AVATARS_FOLDER", "UPLOAD_LIBRARY_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)

    with app.app_context():
        db.create_all()
        user = seed_file_user()
        client = app.test_client()
        headers = login(client)

        upload = client.post(
            "/api/v1/files/upload",
            headers=headers,
            data={"file": (BytesIO(b"delete me from RAG retrieval"), "delete-rag.txt")},
            content_type="multipart/form-data",
        )
        assert upload.status_code == 201
        attachment_id = upload.json["data"]["id"]

        assert EventDispatcher().dispatch_pending(limit=10) == {"processed": 1, "published": 1, "failed": 0}
        chunk = DocumentChunk.query.filter_by(source_type="attachment", source_id=str(attachment_id)).one()
        assert chunk.is_deleted is False

        delete = client.delete(f"/api/v1/files/{attachment_id}", headers=headers)
        assert delete.status_code == 200
        deleted_event = DomainEvent.query.filter_by(event_type="FileDeleted").one()
        assert deleted_event.aggregate_type == "Attachment"
        assert deleted_event.aggregate_id == str(attachment_id)
        assert deleted_event.created_by == str(user.id)
        assert deleted_event.payload["attachment_id"] == attachment_id
        assert deleted_event.payload["deleted_by"] == user.id

        assert EventDispatcher().dispatch_pending(limit=10) == {"processed": 1, "published": 1, "failed": 0}
        db.session.refresh(chunk)
        assert chunk.is_deleted is True
        assert chunk.metadata_json["source_deleted"] is True
        assert chunk.metadata_json["deleted_event_id"] == deleted_event.event_id

        db.session.remove()
        db.drop_all()


def test_file_bulk_delete_writes_file_deleted_events(tmp_path):
    app = create_app("testing")
    upload_root = tmp_path / "uploads"
    app.config.update(
        {
            "UPLOAD_FOLDER": os.fspath(upload_root),
            "UPLOAD_FILES_FOLDER": os.fspath(upload_root / "files"),
            "UPLOAD_AVATARS_FOLDER": os.fspath(upload_root / "avatars"),
            "UPLOAD_LIBRARY_FOLDER": os.fspath(upload_root / "library"),
            "REQUIRE_CLOUD_STORAGE_FOR_UPLOADS": "false",
        }
    )
    for key in ("UPLOAD_FOLDER", "UPLOAD_FILES_FOLDER", "UPLOAD_AVATARS_FOLDER", "UPLOAD_LIBRARY_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)

    with app.app_context():
        db.create_all()
        user = seed_file_user()
        client = app.test_client()
        headers = login(client)
        first = Attachment(
            filename="bulk-a.txt",
            filepath="files/bulk-a.txt",
            mimetype="text/plain",
            size=6,
            uploader_id=user.id,
        )
        second = Attachment(
            filename="bulk-b.txt",
            filepath="files/bulk-b.txt",
            mimetype="text/plain",
            size=6,
            uploader_id=user.id,
        )
        db.session.add_all([first, second])
        db.session.commit()

        response = client.post("/api/v1/files/bulk-delete", headers=headers, json={"ids": [first.id, second.id]})

        assert response.status_code == 200
        assert response.json["data"]["changed"] == 2
        events = DomainEvent.query.filter_by(event_type="FileDeleted").order_by(DomainEvent.id.asc()).all()
        assert [event.aggregate_id for event in events] == [str(first.id), str(second.id)]
        assert all(event.created_by == str(user.id) for event in events)
        assert {event.payload["filename"] for event in events} == {"bulk-a.txt", "bulk-b.txt"}

        db.session.remove()
        db.drop_all()
