from app import create_app
from app.extensions import db
from app.models.auth import Role, User
from app.platform import auth as platform_auth


def test_legacy_api_auth_exports_platform_auth_helpers():
    from app.api import auth as legacy_auth

    assert legacy_auth.jwt_required is platform_auth.jwt_required
    assert legacy_auth.csrf_required is platform_auth.csrf_required
    assert legacy_auth.create_access_token is platform_auth.create_access_token
    assert legacy_auth.current_api_user is platform_auth.current_api_user
    assert legacy_auth.ACCESS_COOKIE_NAME == platform_auth.ACCESS_COOKIE_NAME
    assert legacy_auth.CSRF_COOKIE_NAME == platform_auth.CSRF_COOKIE_NAME


def test_legacy_security_password_helper_uses_platform_policy():
    from app.utils.security import check_password_strength as legacy_check

    assert legacy_check is platform_auth.check_password_strength
    assert legacy_check('short') == (False, '密码长度至少8位')
    assert legacy_check('StrongPass1!') == (True, '')


def test_platform_auth_keeps_cookie_and_csrf_contract():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        role = Role(name='Admin', is_admin=True)
        user = User(username='admin', email='admin@nexus.com', role=role, is_admin=True)
        user.password = 'admin123'
        db.session.add_all([role, user])
        db.session.commit()

        client = app.test_client()
        login = client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'admin123'})
        assert login.status_code == 200
        assert 'token' not in login.json['data']
        assert 'csrf_token' in login.json['data']
        set_cookie_headers = '\n'.join(login.headers.getlist('Set-Cookie'))
        assert platform_auth.ACCESS_COOKIE_NAME in set_cookie_headers
        assert platform_auth.CSRF_COOKIE_NAME in set_cookie_headers

        blocked = client.post('/api/v1/products', json={'sku': 'AUTH-CSRF', 'name': '缺少 CSRF'})
        assert blocked.status_code == 403
        assert blocked.json['error'] == 'csrf_failed'

        db.session.remove()
        db.drop_all()


def test_platform_auth_accepts_trusted_origin_header_csrf_when_cookie_is_partitioned():
    app = create_app('testing')
    app.config.update(CORS_ORIGINS=['https://frontend.example.com'])

    with app.app_context():
        db.create_all()
        role = Role(name='Admin', is_admin=True)
        user = User(username='admin', email='admin@nexus.com', role=role, is_admin=True)
        user.password = 'admin123'
        db.session.add_all([role, user])
        db.session.commit()

        login_client = app.test_client()
        login = login_client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'admin123'})
        csrf_token = login.json['data']['csrf_token']
        access_cookie = next(
            header.split(';', 1)[0].split('=', 1)[1]
            for header in login.headers.getlist('Set-Cookie')
            if header.startswith(f'{platform_auth.ACCESS_COOKIE_NAME}=')
        )

        cloud_client = app.test_client(use_cookies=False)
        create = cloud_client.post(
            '/api/v1/products',
            headers={
                'Cookie': f'{platform_auth.ACCESS_COOKIE_NAME}={access_cookie}',
                'Origin': 'https://frontend.example.com',
                'X-CSRF-Token': csrf_token,
            },
            json={'sku': 'AUTH-CLOUD-CSRF', 'name': '云端 CSRF 分区兼容物料'},
        )
        assert create.status_code == 201

        blocked = cloud_client.post(
            '/api/v1/products',
            headers={
                'Cookie': f'{platform_auth.ACCESS_COOKIE_NAME}={access_cookie}',
                'Origin': 'https://evil.example.com',
                'X-CSRF-Token': csrf_token,
            },
            json={'sku': 'AUTH-CLOUD-BLOCK', 'name': '非可信来源'},
        )
        assert blocked.status_code == 403
        assert blocked.json['error'] == 'csrf_failed'

        db.session.remove()
        db.drop_all()
