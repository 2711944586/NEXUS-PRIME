import json

from app import create_app
from app.extensions import db
from app.domains.ai.infrastructure.vector_repository import ChunkInput, DocumentChunkRepository
from app.models.auth import Role, User
from app.models.content import Attachment
from app.models.events import DomainEvent
from app.models.sys import AuditLog


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_ai_rag_fixture():
    role = Role(name="AiRagUser", is_admin=False)
    owner = User(username="rag-owner", email="owner@nexus.com", role=role)
    owner.password = "owner123"
    other = User(username="rag-other", email="other@nexus.com", role=role)
    other.password = "other123"
    db.session.add_all([role, owner, other])
    db.session.flush()

    attachment = Attachment(
        filename="quality-policy.txt",
        filepath="files/quality-policy.txt",
        mimetype="text/plain",
        size=128,
        uploader_id=owner.id,
    )
    db.session.add(attachment)
    db.session.flush()

    DocumentChunkRepository().upsert_chunk(
        ChunkInput(
            source_type="attachment",
            source_id=str(attachment.id),
            chunk_index=0,
            title=attachment.filename,
            content="质检报告必须记录供应商批次、抽检结论和整改闭环编号。",
            metadata={
                "filename": attachment.filename,
                "mimetype": attachment.mimetype,
                "storage_provider": "local",
            },
        )
    )
    db.session.commit()
    return owner, other, attachment


def test_ai_chat_uses_authorized_document_chunks_for_rag():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        owner, _other, attachment = seed_ai_rag_fixture()
        client = app.test_client()
        headers = login(client, "owner@nexus.com", "owner123")

        response = client.post("/api/v1/ai/chat", headers=headers, json={"message": "质检报告需要记录什么？"})

        assert response.status_code == 200
        data = response.json["data"]
        assert data["source"] == "operations_engine"
        assert len(data["rag_sources"]) == 1
        assert data["rag_sources"][0]["source_type"] == "attachment"
        assert data["rag_sources"][0]["source_id"] == str(attachment.id)
        assert "供应商批次" in data["message"]["content"]
        assert "quality-policy.txt" in data["message"]["content"]

        event = DomainEvent.query.filter_by(event_type="AiInsightRequested").one()
        assert event.payload["kind"] == "chat"
        assert event.payload["rag_source_count"] == 1
        assert "质检报告需要记录什么" not in str(event.payload)

        audit = AuditLog.query.filter_by(module="ai", action="rag_search", user_id=owner.id).one()
        details = json.loads(audit.details)
        assert details["source_count"] == 1
        assert details["source_ids"] == [str(attachment.id)]

        db.session.remove()
        db.drop_all()


def test_ai_chat_does_not_retrieve_unauthorized_document_chunks():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _owner, other, _attachment = seed_ai_rag_fixture()
        client = app.test_client()
        headers = login(client, "other@nexus.com", "other123")

        response = client.post("/api/v1/ai/chat", headers=headers, json={"message": "质检报告需要记录什么？"})

        assert response.status_code == 200
        data = response.json["data"]
        assert data["rag_sources"] == []
        assert "供应商批次" not in data["message"]["content"]

        event = DomainEvent.query.filter_by(event_type="AiInsightRequested").one()
        assert event.payload["rag_source_count"] == 0
        audit = AuditLog.query.filter_by(module="ai", action="rag_search", user_id=other.id).one()
        assert json.loads(audit.details)["source_count"] == 0

        db.session.remove()
        db.drop_all()
