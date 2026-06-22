from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.content import Attachment


def login(client, email, password):
    response = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json['data']['csrf_token']}


def seed_file_scope_users():
    file_permission = Permission(name='files.manage', description='文件管理')
    manager_role = Role(name='FileManager', is_admin=False)
    member_role = Role(name='Member', is_admin=False)
    manager_role.permissions.append(file_permission)
    owner = User(username='file-owner', email='owner@nexus.com', role=manager_role)
    owner.password = 'owner123'
    other = User(username='file-other', email='other@nexus.com', role=member_role)
    other.password = 'other123'
    db.session.add_all([file_permission, manager_role, member_role, owner, other])
    db.session.flush()
    own_attachment = Attachment(
        filename='owner.txt',
        filepath='files/owner.txt',
        mimetype='text/plain',
        size=5,
        uploader_id=owner.id,
    )
    other_attachment = Attachment(
        filename='other.txt',
        filepath='files/other.txt',
        mimetype='text/plain',
        size=5,
        uploader_id=other.id,
    )
    db.session.add_all([own_attachment, other_attachment])
    db.session.commit()
    return owner, own_attachment, other_attachment


def test_file_download_uses_object_authorization_policy():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        owner, _own_attachment, other_attachment = seed_file_scope_users()
        client = app.test_client()
        headers = login(client, owner.email, 'owner123')

        response = client.get(f'/api/v1/files/{other_attachment.id}/download', headers=headers)

        assert response.status_code == 403
        assert response.json['error'] == 'forbidden'

        db.session.remove()
        db.drop_all()


def test_bulk_delete_rejects_mixed_owner_file_ids_without_partial_delete():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        owner, own_attachment, other_attachment = seed_file_scope_users()
        client = app.test_client()
        headers = login(client, owner.email, 'owner123')

        blocked = client.post(
            '/api/v1/files/bulk-delete',
            headers=headers,
            json={'ids': [own_attachment.id, other_attachment.id]},
        )

        assert blocked.status_code == 403
        assert blocked.json['error'] == 'forbidden'
        db.session.refresh(own_attachment)
        db.session.refresh(other_attachment)
        assert own_attachment.is_deleted is False
        assert other_attachment.is_deleted is False

        allowed = client.post('/api/v1/files/bulk-delete', headers=headers, json={'ids': [own_attachment.id]})
        assert allowed.status_code == 200
        assert allowed.json['data']['changed'] == 1
        db.session.refresh(own_attachment)
        db.session.refresh(other_attachment)
        assert own_attachment.is_deleted is True
        assert other_attachment.is_deleted is False

        db.session.remove()
        db.drop_all()
