from app import create_app
from app.extensions import db
from app.models.auth import Role, User
from app.models.events import DomainEvent
from app.models.sys import AiChatMessage, AiChatSession


def login(client, email="admin@nexus.com", password="admin123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_ai_user():
    role = Role(name="AiUser", is_admin=True)
    user = User(username="ai-admin", email="admin@nexus.com", role=role, is_admin=True)
    user.password = "admin123"
    db.session.add_all([role, user])
    db.session.commit()
    return user


def test_ai_chat_writes_ai_insight_requested_event_without_prompt_content():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        user = seed_ai_user()
        client = app.test_client()
        headers = login(client)
        prompt = "请分析当前库存和应收风险，并给出当班动作"

        response = client.post("/api/v1/ai/chat", headers=headers, json={"message": prompt})

        assert response.status_code == 200
        session = AiChatSession.query.one()
        user_message = AiChatMessage.query.filter_by(session_id=session.id, role="user").one()
        event = DomainEvent.query.filter_by(event_type="AiInsightRequested").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "AiChatSession"
        assert event.aggregate_id == str(session.id)
        assert event.created_by == str(user.id)
        assert event.payload["kind"] == "chat"
        assert event.payload["requested_by"] == user.id
        assert event.payload["session_id"] == session.id
        assert event.payload["user_message_id"] == user_message.id
        assert event.payload["message_length"] == len(prompt)
        assert prompt not in str(event.payload)

        empty = client.post("/api/v1/ai/chat", headers=headers, json={"message": ""})
        assert empty.status_code == 400
        assert DomainEvent.query.filter_by(event_type="AiInsightRequested").count() == 1

        db.session.remove()
        db.drop_all()


def test_ai_chat_stream_returns_sse_events_and_persists_messages():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        user = seed_ai_user()
        client = app.test_client()
        headers = login(client)
        prompt = "请流式分析库存风险"

        response = client.post("/api/v1/ai/chat/stream", headers=headers, json={"message": prompt})

        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        body = response.get_data(as_text=True)
        assert "event: status" in body
        assert "event: chunk" in body
        assert "event: done" in body
        assert "经营分析" in body or "库存" in body

        session = AiChatSession.query.one()
        assert AiChatMessage.query.filter_by(session_id=session.id, role="user").count() == 1
        assert AiChatMessage.query.filter_by(session_id=session.id, role="assistant").count() == 1
        event = DomainEvent.query.filter_by(event_type="AiInsightRequested").one()
        assert event.created_by == str(user.id)
        assert event.payload["kind"] == "chat"
        assert event.payload["stream"] is True
        assert event.payload["message_length"] == len(prompt)
        assert prompt not in str(event.payload)

        db.session.remove()
        db.drop_all()


def test_ai_chat_stream_validation_errors_are_sse_events():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_ai_user()
        client = app.test_client()
        headers = login(client)

        response = client.post("/api/v1/ai/chat/stream", headers=headers, json={"message": ""})

        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        body = response.get_data(as_text=True)
        assert "event: error" in body
        assert "empty_message" in body
        assert DomainEvent.query.filter_by(event_type="AiInsightRequested").count() == 0

        db.session.remove()
        db.drop_all()


def test_ai_analysis_endpoints_write_ai_insight_requested_events():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        user = seed_ai_user()
        client = app.test_client()
        headers = login(client)

        inventory = client.post("/api/v1/ai/analyze/inventory", headers=headers, json={"limit": 5})
        structured = client.post(
            "/api/v1/ai/analyze/structured",
            headers=headers,
            json={"scenario": "inventory", "limit": 4},
        )

        assert inventory.status_code == 200
        assert structured.status_code == 200
        events = DomainEvent.query.filter_by(event_type="AiInsightRequested").order_by(DomainEvent.id.asc()).all()
        assert [event.payload["kind"] for event in events] == ["inventory_analysis", "structured_analysis"]
        assert events[0].aggregate_type == "AiInsight"
        assert events[0].created_by == str(user.id)
        assert events[0].payload["requested_by"] == user.id
        assert events[0].payload["limit"] == 5
        assert events[1].payload["scenario"] == "inventory"
        assert events[1].payload["limit"] == 4

        db.session.remove()
        db.drop_all()
