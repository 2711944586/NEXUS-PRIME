from app import create_app
from app.extensions import db
from app.models.auth import Role, User
from app.models.notification import Notification


def login(client, email="member@nexus.com", password="member123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def seed_notification_users():
    admin_role = Role(name="Admin", is_admin=True)
    user_role = Role(name="User", is_admin=False)
    db.session.add_all([admin_role, user_role])
    db.session.flush()

    admin = User(username="admin", email="admin@nexus.com", role=admin_role, is_admin=True)
    admin.password = "admin123"
    member = User(username="member", email="member@nexus.com", role=user_role)
    member.password = "member123"
    other = User(username="other", email="other@nexus.com", role=user_role)
    other.password = "other123"
    db.session.add_all([admin, member, other])
    db.session.flush()

    db.session.add_all([
        Notification(user_id=member.id, title="成员库存预警", content="库存低于安全线", category=Notification.CATEGORY_STOCK, is_read=False),
        Notification(user_id=member.id, title="成员已读消息", content="已处理", category=Notification.CATEGORY_SYSTEM, is_read=True),
        Notification(user_id=other.id, title="他人审批提醒", content="不可见", category=Notification.CATEGORY_APPROVAL, is_read=False),
    ])
    db.session.commit()
    return admin, member, other


def test_notification_stream_emits_user_scoped_snapshot():
    app = create_app("testing")
    app.config["NOTIFICATION_STREAM_MAX_EVENTS"] = 1
    app.config["NOTIFICATION_STREAM_INTERVAL_SECONDS"] = 0

    with app.app_context():
        db.create_all()
        seed_notification_users()
        client = app.test_client()
        headers = login(client)

        stream = client.get("/api/v1/notifications/stream", headers=headers)

        assert stream.status_code == 200
        assert stream.mimetype == "text/event-stream"
        body = stream.get_data(as_text=True)
        assert "event: snapshot" in body
        assert '"unread":1' in body
        assert "成员库存预警" in body
        assert "成员已读消息" in body
        assert "他人审批提醒" not in body

        db.session.remove()
        db.drop_all()


def test_notification_stream_admin_can_see_all_notifications():
    app = create_app("testing")
    app.config["NOTIFICATION_STREAM_MAX_EVENTS"] = 1
    app.config["NOTIFICATION_STREAM_INTERVAL_SECONDS"] = 0

    with app.app_context():
        db.create_all()
        seed_notification_users()
        client = app.test_client()
        headers = login(client, email="admin@nexus.com", password="admin123")

        stream = client.get("/api/v1/notifications/stream", headers=headers)

        assert stream.status_code == 200
        body = stream.get_data(as_text=True)
        assert '"unread":2' in body
        assert "成员库存预警" in body
        assert "他人审批提醒" in body

        db.session.remove()
        db.drop_all()


def test_notification_stream_requires_authentication():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        client = app.test_client()

        stream = client.get("/api/v1/notifications/stream")

        assert stream.status_code == 401

        db.session.remove()
        db.drop_all()
