import os
from datetime import date, timedelta
from zipfile import ZipFile
from io import BytesIO

import pytest

from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.content import Attachment
from app.models.finance import Receivable
from app.models.notification import GeneratedReport, Notification, ReplenishmentSuggestion, ReportSubscription, StockAlert
from app.models.purchase import PurchaseOrder, SupplierPerformance
from app.models.stock import Stock, Warehouse
from app.models.stocktake import StockTake, StockTakeItem
from app.models.sys import AuditLog
from app.models.trade import Order
from app.services.ai_service import ai_service


@pytest.fixture()
def app(tmp_path):
    flask_app = create_app('testing')
    upload_root = tmp_path / 'uploads'
    flask_app.config.update({
        'UPLOAD_FOLDER': os.fspath(upload_root),
        'UPLOAD_FILES_FOLDER': os.fspath(upload_root / 'files'),
        'UPLOAD_AVATARS_FOLDER': os.fspath(upload_root / 'avatars'),
        'UPLOAD_LIBRARY_FOLDER': os.fspath(upload_root / 'library'),
        'REQUIRE_CLOUD_STORAGE_FOR_UPLOADS': 'false',
    })
    for key in ('UPLOAD_FOLDER', 'UPLOAD_FILES_FOLDER', 'UPLOAD_AVATARS_FOLDER', 'UPLOAD_LIBRARY_FOLDER'):
        os.makedirs(flask_app.config[key], exist_ok=True)
    with flask_app.app_context():
        db.create_all()
        admin_role = Role(name='Admin', is_admin=True)
        user_role = Role(name='User', is_admin=False)
        permissions = [
            Permission(name='inventory.adjust', description='库存调整'),
            Permission(name='purchase.write', description='采购创建'),
            Permission(name='purchase.approve', description='采购审批'),
            Permission(name='purchase.receive', description='采购收货'),
            Permission(name='finance.payment', description='财务收款'),
            Permission(name='finance.credit.write', description='信用管理'),
            Permission(name='reports.generate', description='报表生成'),
            Permission(name='files.manage', description='文件管理'),
            Permission(name='content.write', description='内容管理'),
            Permission(name='stocktake.write', description='盘点管理'),
            Permission(name='masterdata.write', description='主数据维护'),
            Permission(name='sales.write', description='销售履约'),
        ]
        admin_role.permissions.extend(permissions)
        db.session.add_all([admin_role, user_role, *permissions])
        db.session.flush()
        admin = User(username='admin', email='admin@nexus.com', role=admin_role, is_admin=True)
        admin.password = 'admin123'
        user = User(username='member', email='member@nexus.com', role=user_role)
        user.password = 'member123'
        category = Category(name='核心设备')
        supplier = Partner(name='测试供应商', type='supplier')
        customer = Partner(name='测试客户', type='customer')
        warehouse = Warehouse(name='主仓', location='A1')
        db.session.add_all([admin, user, category, supplier, customer, warehouse])
        db.session.flush()
        product = Product(
            sku='MFG-T-001',
            name='伺服电机组件 测试型',
            price=99,
            cost=40,
            category_id=category.id,
            supplier_id=supplier.id,
            min_stock=5,
            max_stock=100
        )
        db.session.add(product)
        db.session.flush()
        db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=20))
        db.session.commit()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email='admin@nexus.com', password='admin123'):
    response = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200
    assert 'token' not in response.json['data']
    return {
        'X-CSRF-Token': response.json['data']['csrf_token'],
    }


def office_zip_bytes(kind='xlsx'):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        if kind == 'docx':
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
        else:
            archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
    stream.seek(0)
    return stream.getvalue()


def test_auth_me_and_dashboard(client):
    headers = login(client)
    login_response = client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'admin123'})
    assert 'nexus_access_token' in login_response.headers.get('Set-Cookie', '')
    response = client.get('/api/v1/auth/me', headers=headers)
    assert response.status_code == 200
    assert response.json['data']['email'] == 'admin@nexus.com'
    assert 'token' not in response.json['data']
    assert 'nexus_access_token' in response.headers.get('Set-Cookie', '')

    summary = client.get('/api/v1/dashboard/summary', headers=headers)
    assert summary.status_code == 200
    assert summary.json['data']['products'] == 1


def test_manufacturing_workflow_board_contract(client):
    headers = login(client)
    product = Product.query.filter_by(sku='MFG-T-001').first()
    supplier = Partner.query.filter_by(type='supplier').first()
    customer = Partner.query.filter_by(type='customer').first()
    warehouse = Warehouse.query.first()
    admin = User.query.filter_by(email='admin@nexus.com').first()

    purchase = PurchaseOrder(
        po_no='PO-WORKFLOW-001',
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status=PurchaseOrder.STATUS_PENDING,
        total_amount=128800,
    )
    order = Order(
        order_no='SO-WORKFLOW-001',
        customer_id=customer.id,
        seller_id=admin.id,
        status=Order.STATUS_PENDING,
        total_amount=186500,
    )
    receivable = Receivable(
        receivable_no='AR-WORKFLOW-001',
        customer_id=customer.id,
        total_amount=186500,
        paid_amount=42000,
        due_date=date.today() - timedelta(days=12),
        status=Receivable.STATUS_OVERDUE,
    )
    db.session.add_all([
        purchase,
        order,
        receivable,
        StockAlert(
            product_id=product.id,
            warehouse_id=warehouse.id,
            alert_level=StockAlert.LEVEL_RED,
            status=StockAlert.STATUS_ACTIVE,
            current_qty=2,
            min_qty=8,
            suggested_qty=24,
        ),
        ReplenishmentSuggestion(
            product_id=product.id,
            warehouse_id=warehouse.id,
            supplier_id=supplier.id,
            current_qty=2,
            suggested_qty=24,
            status=ReplenishmentSuggestion.STATUS_PENDING,
        ),
        GeneratedReport(
            report_type='daily_operations',
            report_name='制造经营日报',
            generated_by=admin.id,
        ),
        AuditLog(user_id=admin.id, module='workflow', action='workflow_board_seed', details='contract coverage'),
    ])
    db.session.commit()

    response = client.get('/api/v1/manufacturing/workflow-board', headers=headers)
    assert response.status_code == 200
    payload = response.json['data']
    assert payload['summary']['title'] == '每日制造经营作战流'
    assert payload['summary']['active_stages'] == 8
    assert payload['summary']['attention_count'] >= 1
    assert {stage['key'] for stage in payload['stages']} >= {
        'inventory-signal',
        'procurement-approval',
        'cash-collection',
        'reporting',
        'audit',
    }
    assert len(payload['handoffs']) == 7
    assert any(item['key'] == 'cash-collection' for item in payload['bottlenecks'])
    assert payload['summary']['open_action_count'] == len(payload['action_queue'])
    assert payload['summary']['evidence_count'] >= 2
    assert {item['priority'] for item in payload['action_queue']} >= {'P0'}
    assert {item['name'] for item in payload['service_boundaries']} >= {
        '制造经营聚合 API',
        '库存与补货服务边界',
        '采购履约服务边界',
        '财务风控服务边界',
    }
    assert {item['key'] for item in payload['deployment_checks']} >= {'auth', 'evidence', 'notifications', 'cash'}
    assert {item['role'] for item in payload['role_command_center']} >= {
        '运营负责人',
        '仓配与采购',
        '财务风控',
        '经营分析',
    }
    assert any(item['module'] == '应收' and item['severity'] == 'blocked' for item in payload['execution_events'])
    assert {item['surface'] for item in payload['data_contracts']} >= {
        'GET /api/v1/manufacturing/command-center',
        'GET /api/v1/manufacturing/workflow-board',
        'GET /api/v1/health/ready',
    }


def test_erp_control_tower_contract(client):
    headers = login(client)
    product = Product.query.filter_by(sku='MFG-T-001').first()
    supplier = Partner.query.filter_by(type='supplier').first()
    customer = Partner.query.filter_by(type='customer').first()
    warehouse = Warehouse.query.first()
    admin = User.query.filter_by(email='admin@nexus.com').first()

    db.session.add_all([
        PurchaseOrder(
            po_no='PO-TOWER-001',
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            status=PurchaseOrder.STATUS_PENDING,
            total_amount=96000,
        ),
        Order(
            order_no='SO-TOWER-001',
            customer_id=customer.id,
            seller_id=admin.id,
            status=Order.STATUS_PENDING,
            total_amount=142000,
        ),
        Receivable(
            receivable_no='AR-TOWER-001',
            customer_id=customer.id,
            total_amount=142000,
            paid_amount=21000,
            due_date=date.today() - timedelta(days=18),
            status=Receivable.STATUS_OVERDUE,
        ),
        StockAlert(
            product_id=product.id,
            warehouse_id=warehouse.id,
            alert_level=StockAlert.LEVEL_RED,
            status=StockAlert.STATUS_ACTIVE,
            current_qty=1,
            min_qty=8,
            suggested_qty=30,
        ),
        ReplenishmentSuggestion(
            product_id=product.id,
            warehouse_id=warehouse.id,
            supplier_id=supplier.id,
            current_qty=1,
            suggested_qty=30,
            status=ReplenishmentSuggestion.STATUS_PENDING,
        ),
        GeneratedReport(
            report_type='erp_control',
            report_name='ERP 控制塔日报',
            generated_by=admin.id,
        ),
        AuditLog(user_id=admin.id, module='erp', action='control_tower_seed', details='tower contract coverage'),
    ])
    db.session.commit()

    response = client.get('/api/v1/erp/control-tower', headers=headers)
    assert response.status_code == 200
    payload = response.json['data']
    assert payload['source'] == 'erp-control-tower'
    assert payload['summary']['title'] == 'Nexus Prime ERP 控制塔'
    assert payload['summary']['control_score'] >= 0
    assert payload['summary']['total_records'] >= 1
    assert payload['summary']['service_boundaries'] >= 4
    assert {'master-data', 'supply-chain', 'manufacturing-flow', 'cash-risk', 'collaboration'} <= {
        item['key'] for item in payload['domain_health']
    }
    assert any(item['priority'] in {'P0', 'P1'} for item in payload['action_queue'])
    assert any(item['surface'].startswith('/api/v1/') for item in payload['readiness'])
    assert {item['label'] for item in payload['evidence_ledger']} >= {'业务对象', '证据链', '开放动作', '服务边界'}
    assert payload['workflow']['stages']
    assert payload['workflow']['handoffs']


def test_public_health_contracts(client):
    health = client.get('/api/v1/health')
    assert health.status_code == 200
    assert health.json['data']['status'] in {'ok', 'degraded'}
    assert health.json['data']['database']['status'] == 'ready'
    assert health.json['data']['ai']['request_timeout_seconds'] == 20.0
    assert health.json['data']['ai']['connect_timeout_seconds'] == 5.0
    assert health.json['data']['storage']['folders']['files'].endswith('files')
    assert health.json['data']['storage']['folders']['avatars'].endswith('avatars')
    assert health.json['data']['storage']['folders']['library'].endswith('library')
    assert health.json['data']['storage']['writable']['files'] is True
    assert health.json['data']['storage']['writable']['avatars'] is True
    assert health.json['data']['storage']['writable']['library'] is True
    assert health.json['data']['checks']['database'] is True
    assert 'X-Response-Time-Ms' in health.headers

    live = client.get('/api/v1/health/live')
    assert live.status_code == 200
    assert live.json['data']['probe'] == 'live'

    ready = client.get('/api/v1/health/ready')
    assert ready.status_code == 200
    assert ready.json['data']['probe'] == 'ready'
    assert ready.json['data']['database']['status'] == 'ready'


def test_requires_jwt_for_business_api(client):
    response = client.get('/api/v1/products')
    assert response.status_code == 401
    assert response.json['error'] == 'missing_token'


def test_cookie_auth_requires_csrf_for_mutations(client):
    client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'admin123'})
    response = client.post('/api/v1/products', json={'sku': 'MFG-CSRF-1', 'name': 'CSRF 测试物料'})
    assert response.status_code == 403
    assert response.json['error'] == 'csrf_failed'


def test_products_crud_and_pagination(client):
    headers = login(client)
    create = client.post('/api/v1/products', headers=headers, json={
        'sku': 'NX-T-002',
        'name': '新增商品',
        'price': 120,
        'cost': 60,
        'min_stock': 3,
        'max_stock': 50
    })
    assert create.status_code == 201
    product_id = create.json['data']['id']

    listing = client.get('/api/v1/products?page=1&page_size=5&q=新增', headers=headers)
    assert listing.status_code == 200
    assert listing.json['data']['pagination']['total'] == 1

    update = client.put(f'/api/v1/products/{product_id}', headers=headers, json={'price': 180})
    assert update.status_code == 200
    assert update.json['data']['price'] == 180

    delete = client.delete(f'/api/v1/products/{product_id}', headers=headers)
    assert delete.status_code == 200
    assert client.get(f'/api/v1/products/{product_id}', headers=headers).status_code == 404


def test_admin_only_resource_rejects_normal_user(client):
    headers = login(client, 'member@nexus.com', 'member123')
    response = client.get('/api/v1/users', headers=headers)
    assert response.status_code == 403

    assert client.get('/api/v1/users/1', headers=headers).status_code == 403
    assert client.put('/api/v1/users/2', headers=headers, json={'is_admin': True}).status_code == 403
    assert client.delete('/api/v1/users/1', headers=headers).status_code == 403
    assert User.query.filter_by(email='member@nexus.com').first().is_admin is False
    assert User.query.filter_by(email='admin@nexus.com').first().is_deleted is False


def test_login_failures_lock_account(client):
    for _ in range(5):
        response = client.post('/api/v1/auth/login', json={'email': 'member@nexus.com', 'password': 'bad'})
        assert response.status_code == 401

    locked = client.post('/api/v1/auth/login', json={'email': 'member@nexus.com', 'password': 'member123'})
    assert locked.status_code == 403
    assert locked.json['error'] == 'account_locked'


def test_login_rate_limit_covers_unknown_emails(app, client):
    app.config['LOGIN_RATE_LIMIT_ATTEMPTS'] = 3
    app.config['LOGIN_RATE_LIMIT_WINDOW_SECONDS'] = 60

    for _ in range(3):
        response = client.post('/api/v1/auth/login', json={'email': 'missing@nexus.com', 'password': 'bad'})
        assert response.status_code == 401

    limited = client.post('/api/v1/auth/login', json={'email': 'missing@nexus.com', 'password': 'bad'})
    assert limited.status_code == 429
    assert limited.json['error'] == 'login_rate_limited'

    logs = AuditLog.query.filter_by(module='auth').order_by(AuditLog.id.asc()).all()
    assert any(log.action == 'login_failed' and 'unknown_email' in (log.details or '') for log in logs)
    assert any(log.action == 'login_rate_limited' for log in logs)


def test_successful_login_clears_rate_limit_failures(app, client):
    app.config['LOGIN_RATE_LIMIT_ATTEMPTS'] = 3
    app.config['LOGIN_RATE_LIMIT_WINDOW_SECONDS'] = 60

    for _ in range(2):
        response = client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'bad'})
        assert response.status_code == 401

    successful = client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'admin123'})
    assert successful.status_code == 200

    response = client.post('/api/v1/auth/login', json={'email': 'admin@nexus.com', 'password': 'bad'})
    assert response.status_code == 401


def test_register_requires_captcha_and_terms(client, monkeypatch):
    policy = client.get('/api/v1/auth/register-policy')
    assert policy.status_code == 200
    assert policy.json['data']['terms_version'] == '2026.06'
    assert policy.json['data']['required_acceptances'] == ['accepted_terms', 'accepted_privacy', 'accepted_data_scope']
    assert {document['id'] for document in policy.json['data']['documents']} == {'terms', 'privacy', 'data_scope'}
    assert all(document['items'] for document in policy.json['data']['documents'])

    blocked = client.post('/api/v1/auth/register', json={
        'username': 'new_member',
        'email': 'new-member@nexus.com',
        'password': 'member123'
    })
    assert blocked.status_code == 400
    assert blocked.json['error'] == 'register_gate_failed'

    monkeypatch.setattr('app.api.routes.random.choice', lambda seq: 'sum')
    monkeypatch.setattr('app.api.routes.random.randint', lambda a, b: 12 if a == 12 else 4)
    captcha = client.get('/api/v1/auth/captcha')
    assert captcha.status_code == 200
    assert 'data:image/svg+xml;base64,' in captcha.json['data']['image_data_url']

    created = client.post('/api/v1/auth/register', json={
        'username': 'new_member',
        'email': 'new-member@nexus.com',
        'password': 'member123A',
        'full_name': '新成员',
        'position': '仓配运营专员',
        'department_name': '供应链运营部',
        'accepted_terms': True,
        'accepted_privacy': True,
        'accepted_data_scope': True,
        'terms_version': captcha.json['data']['terms_version'],
        'captcha_token': captcha.json['data']['token'],
        'captcha_answer': '16',
    })
    assert created.status_code == 201
    assert 'token' not in created.json['data']
    assert created.json['data']['user']['email'] == 'new-member@nexus.com'
    assert 'nexus_access_token' in created.headers.get('Set-Cookie', '')
    assert created.json['data']['csrf_token']
    created_user = User.query.filter_by(email='new-member@nexus.com').first()
    assert created_user.is_admin is False
    assert created_user.department_name == '供应链运营部'


def test_register_validates_profile_and_uniqueness(client, monkeypatch):
    monkeypatch.setattr('app.api.routes.random.choice', lambda seq: 'sum')
    monkeypatch.setattr('app.api.routes.random.randint', lambda a, b: 12 if a == 12 else 4)
    captcha = client.get('/api/v1/auth/captcha').json['data']

    invalid = client.post('/api/v1/auth/register', json={
        'username': 'x',
        'email': 'bad-email',
        'password': 'short',
        'full_name': 'A',
        'position': '',
        'department_name': '',
        'accepted_terms': True,
        'accepted_privacy': True,
        'accepted_data_scope': True,
        'terms_version': captcha['terms_version'],
        'captcha_token': captcha['token'],
        'captcha_answer': '16',
    })
    assert invalid.status_code == 400
    assert invalid.json['error'] == 'register_validation_failed'
    assert {'username', 'email', 'password', 'position', 'department_name'} <= set(invalid.json['fields'])

    duplicate_email = client.post('/api/v1/auth/register', json={
        'username': 'valid.member',
        'email': 'member@nexus.com',
        'password': 'member123A',
        'full_name': '重复邮箱成员',
        'position': '计划专员',
        'department_name': '供应链运营部',
        'accepted_terms': True,
        'accepted_privacy': True,
        'accepted_data_scope': True,
        'terms_version': captcha['terms_version'],
        'captcha_token': captcha['token'],
        'captcha_answer': '16',
    })
    assert duplicate_email.status_code == 400
    assert duplicate_email.json['error'] == 'email_exists'

    captcha = client.get('/api/v1/auth/captcha').json['data']
    duplicate_username = client.post('/api/v1/auth/register', json={
        'username': 'member',
        'email': 'another-member@nexus.com',
        'password': 'member123A',
        'full_name': '重复用户名成员',
        'position': '计划专员',
        'department_name': '供应链运营部',
        'accepted_terms': True,
        'accepted_privacy': True,
        'accepted_data_scope': True,
        'terms_version': captcha['terms_version'],
        'captcha_token': captcha['token'],
        'captcha_answer': '16',
    })
    assert duplicate_username.status_code == 400
    assert duplicate_username.json['error'] == 'username_exists'


def test_sales_purchase_export_and_upload(app, client):
    headers = login(client)
    product_id = Product.query.filter_by(sku='MFG-T-001').first().id
    customer_id = Partner.query.filter_by(type='customer').first().id
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id

    order = client.post('/api/v1/orders', headers=headers, json={
        'customer_id': customer_id,
        'items': [{'product_id': product_id, 'quantity': 2}],
        'status': 'pending'
    })
    assert order.status_code == 201
    assert order.json['data']['items'][0]['product_id'] == product_id

    purchase = client.post('/api/v1/purchase-orders', headers=headers, json={
        'supplier_id': supplier_id,
        'warehouse_id': warehouse_id,
        'items': [{'product_id': product_id, 'quantity': 5, 'unit_price': 40}]
    })
    assert purchase.status_code == 201
    assert purchase.json['data']['items'][0]['quantity'] == 5

    export = client.get('/api/v1/export/products/pdf', headers=headers)
    assert export.status_code == 200
    assert export.content_type == 'application/pdf'

    upload = client.post(
        '/api/v1/files/upload',
        headers=headers,
        data={'file': (BytesIO(b'NEXUS test file'), 'nexus.txt')},
        content_type='multipart/form-data'
    )
    assert upload.status_code == 201
    assert upload.json['data']['filename'] == 'nexus.txt'
    assert upload.json['data']['filepath'].startswith('files/')
    stored_name = upload.json['data']['filepath'].split('/', 1)[1]
    assert os.path.exists(os.path.join(app.config['UPLOAD_FILES_FOLDER'], stored_name))

    download = client.get(f"/api/v1/files/{upload.json['data']['id']}/download", headers=headers)
    assert download.status_code == 200
    assert download.data == b'NEXUS test file'

    bad_upload = client.post(
        '/api/v1/files/upload',
        headers=headers,
        data={'file': (BytesIO(b'<script>alert(1)</script>'), 'payload.pdf', 'text/html')},
        content_type='multipart/form-data'
    )
    assert bad_upload.status_code == 400


def test_profile_avatar_and_member_file_upload(client):
    member_headers = login(client, 'member@nexus.com', 'member123')

    avatar = client.post(
        '/api/v1/me/avatar',
        headers=member_headers,
        data={'file': (BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'), '头像.png', 'application/octet-stream')},
        content_type='multipart/form-data'
    )
    assert avatar.status_code == 200
    assert avatar.json['data']['avatar'].endswith('.png')
    avatar_filename = avatar.json['data']['avatar'].rsplit('/', 1)[-1]
    assert os.path.exists(os.path.join(client.application.config['UPLOAD_AVATARS_FOLDER'], avatar_filename))
    stale_avatar = client.get('/api/v1/avatars/avatar-2-missing.png')
    assert stale_avatar.status_code == 200
    assert stale_avatar.mimetype == 'image/svg+xml'

    injected_avatar = client.put('/api/v1/me/profile', headers=member_headers, json={'avatar': 'data:image/svg+xml,<svg></svg>'})
    assert injected_avatar.status_code == 200
    assert injected_avatar.json['data']['avatar'].endswith('.png')

    oversize_avatar = client.post(
        '/api/v1/me/avatar',
        headers=member_headers,
        data={'file': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * (3 * 1024 * 1024 + 1)), 'large.png', 'image/png')},
        content_type='multipart/form-data'
    )
    assert oversize_avatar.status_code == 400
    assert oversize_avatar.json['error'] == 'avatar_too_large'

    reset_avatar = client.delete('/api/v1/me/avatar', headers=member_headers)
    assert reset_avatar.status_code == 200
    assert '/avatars/initials/' in reset_avatar.json['data']['avatar']

    office_file = client.post(
        '/api/v1/files/upload',
        headers=member_headers,
        data={'file': (BytesIO(office_zip_bytes('xlsx')), '供应商绩效.xlsx', 'application/octet-stream')},
        content_type='multipart/form-data'
    )
    assert office_file.status_code == 201
    assert office_file.json['data']['filename'] == '供应商绩效.xlsx'
    assert office_file.json['data']['filepath'].startswith('files/')
    office_stored_name = office_file.json['data']['filepath'].split('/', 1)[1]
    assert os.path.exists(os.path.join(client.application.config['UPLOAD_FILES_FOLDER'], office_stored_name))
    assert office_file.json['data']['uploader_id'] == User.query.filter_by(email='member@nexus.com').first().id

    dangerous = client.post(
        '/api/v1/files/upload',
        headers=member_headers,
        data={'file': (BytesIO(b'<svg onload=alert(1)>'), 'payload.svg', 'image/svg+xml')},
        content_type='multipart/form-data'
    )
    assert dangerous.status_code == 400


def test_uploads_require_persistent_storage_when_configured(app, client):
    headers = login(client)
    app.config['REQUIRE_CLOUD_STORAGE_FOR_UPLOADS'] = 'true'

    avatar = client.post(
        '/api/v1/me/avatar',
        headers=headers,
        data={'file': (BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'), 'avatar.png', 'application/octet-stream')},
        content_type='multipart/form-data'
    )
    assert avatar.status_code == 503
    assert avatar.json['error'] == 'persistent_storage_required'

    uploaded = client.post(
        '/api/v1/files/upload',
        headers=headers,
        data={'file': (BytesIO(b'NEXUS persistent file'), 'persistent.txt')},
        content_type='multipart/form-data'
    )
    assert uploaded.status_code == 503
    assert uploaded.json['error'] == 'persistent_storage_required'


def test_attachment_download_supports_dedicated_and_legacy_storage(app, client):
    headers = login(client)
    admin = User.query.filter_by(email='admin@nexus.com').first()

    file_dir = app.config['UPLOAD_FILES_FOLDER']
    library_dir = app.config['UPLOAD_LIBRARY_FOLDER']
    upload_root = app.config['UPLOAD_FOLDER']
    os.makedirs(file_dir, exist_ok=True)
    os.makedirs(library_dir, exist_ok=True)

    with open(os.path.join(file_dir, 'new-path.txt'), 'wb') as handle:
        handle.write(b'new dedicated file')
    with open(os.path.join(upload_root, 'legacy-root.txt'), 'wb') as handle:
        handle.write(b'legacy root file')
    with open(os.path.join(library_dir, 'seed-library.txt'), 'wb') as handle:
        handle.write(b'seed library file')

    attachments = [
        Attachment(filename='new-path.txt', filepath='files/new-path.txt', mimetype='text/plain', size=18, uploader_id=admin.id),
        Attachment(filename='legacy-root.txt', filepath='legacy-root.txt', mimetype='text/plain', size=16, uploader_id=admin.id),
        Attachment(filename='seed-library.txt', filepath='library/seed-library.txt', mimetype='text/plain', size=17, uploader_id=admin.id),
    ]
    db.session.add_all(attachments)
    db.session.commit()

    for attachment, expected in zip(attachments, [b'new dedicated file', b'legacy root file', b'seed library file']):
        response = client.get(f'/api/v1/files/{attachment.id}/download', headers=headers)
        assert response.status_code == 200
        assert response.data == expected


def test_competitive_experience_api_paths(client):
    headers = login(client)

    overview = client.get('/api/v1/overview/summary', headers=headers)
    assert overview.status_code == 200
    assert overview.json['data']['products'] == 1

    products = client.get('/api/v1/inventory/products?page=1&page_size=5&q=测试', headers=headers)
    assert products.status_code == 200
    assert products.json['data']['pagination']['total'] == 1

    generated = client.post('/api/v1/reports/generate/sales_daily', headers=headers, json={})
    assert generated.status_code == 200

    reports = client.get('/api/v1/reports?page=1&page_size=5', headers=headers)
    assert reports.status_code == 200
    assert reports.json['data']['pagination']['total'] == 1

    navigation = client.get('/api/v1/meta/navigation', headers=headers)
    assert navigation.status_code == 200
    assert any(item['path'] == '/app/inventory/products' for item in navigation.json['data']['items'])

    integrations = client.get('/api/v1/operations/integrations', headers=headers)
    assert integrations.status_code == 200
    assert integrations.json['data']['summary']['contracts'] >= 3
    assert integrations.json['data']['summary']['dependencies'] >= 1
    assert integrations.json['data']['summary']['api_surfaces'] >= 10
    assert integrations.json['data']['summary']['runbook_steps'] >= 20
    assert integrations.json['data']['summary']['avg_contract_coverage'] >= 90
    assert integrations.json['data']['topology']['probe_count'] == len(integrations.json['data']['items'])
    assert integrations.json['data']['topology']['edge_count'] == integrations.json['data']['summary']['dependencies']
    assert integrations.json['data']['summary']['avg_readiness'] >= 45
    assert integrations.json['data']['observability']['coverage'] >= 60
    assert {item['key'] for item in integrations.json['data']['observability']['signals']} == {'metrics', 'logs', 'traces'}
    assert integrations.json['data']['incident_queue']
    assert integrations.json['data']['readiness']['level'] in {'ready', 'attention'}
    assert integrations.json['data']['dependencies']
    inventory_service = next(item for item in integrations.json['data']['items'] if item['id'] == 'inventory')
    assert inventory_service['contracts']
    assert inventory_service['dependencies']
    assert inventory_service['api_surface']
    assert inventory_service['runtime']['probe'] == '/api/v1/inventory/health'
    assert inventory_service['contract_coverage'] >= 90
    assert len(inventory_service['runbook']) >= 2
    assert inventory_service['readiness'] >= 45
    assert inventory_service['observability']['metric_name'] == 'nexus_inventory_latency_ms'

    incident = integrations.json['data']['incident_queue'][0]
    resync = client.post('/api/v1/operations/integrations/resync', headers=headers, json={
        'service_id': incident['service_id'],
        'system_name': incident['title'],
        'owner': incident['owner'],
        'priority': incident['priority'],
        'evidence': incident['evidence'],
        'action': incident['action'],
    })
    assert resync.status_code == 201
    resync_notification = resync.json['data']
    assert resync_notification['related_type'] == 'integration'
    assert resync_notification['category'] == Notification.CATEGORY_SYSTEM
    assert incident['owner'] in resync_notification['content']
    integration_audit = AuditLog.query.filter_by(module='operations', action='integration_resync').order_by(AuditLog.id.desc()).first()
    assert integration_audit is not None
    assert incident['service_id'] in integration_audit.details
    queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert queue.status_code == 200
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/integrations' for item in queue.json['data']['items'])

    data_quality = client.get('/api/v1/operations/data-quality', headers=headers)
    assert data_quality.status_code == 200
    quality_payload = data_quality.json['data']
    assert quality_payload['summary']['total_tests'] >= 8
    assert quality_payload['summary']['score'] >= 58
    assert {item['key'] for item in quality_payload['dimensions']} >= {'masterdata', 'warehouse', 'procurement', 'fulfillment', 'finance'}
    assert quality_payload['runbook']
    assert quality_payload['lineage']
    quality_issue = quality_payload['issue_queue'][0]
    remediation = client.post('/api/v1/operations/data-quality/remediation', headers=headers, json={
        'issue_id': quality_issue['id'],
        'title': quality_issue['title'],
        'owner': quality_issue['owner'],
        'priority': quality_issue['priority'],
        'sla': quality_issue['sla'],
        'evidence': quality_issue['evidence'],
        'action': quality_issue['action'],
        'path': quality_issue['path'],
    })
    assert remediation.status_code == 201
    remediation_notification = remediation.json['data']
    assert remediation_notification['related_type'] == 'quality'
    assert remediation_notification['category'] == Notification.CATEGORY_SYSTEM
    assert quality_issue['owner'] in remediation_notification['content']
    quality_audit = AuditLog.query.filter_by(module='operations', action='data_quality_remediation').order_by(AuditLog.id.desc()).first()
    assert quality_audit is not None
    assert quality_issue['id'] in quality_audit.details
    quality_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/data-quality' for item in quality_queue.json['data']['items'])

    product = Product.query.filter_by(sku='MFG-T-001').first()
    supplier = Partner.query.filter_by(type='supplier').first()
    customer = Partner.query.filter_by(type='customer').first()
    warehouse = Warehouse.query.first()
    admin = User.query.filter_by(email='admin@nexus.com').first()
    db.session.add_all([
        StockAlert(
            product_id=product.id,
            warehouse_id=warehouse.id,
            alert_level=StockAlert.LEVEL_RED,
            status=StockAlert.STATUS_ACTIVE,
            current_qty=1,
            min_qty=8,
            suggested_qty=24,
        ),
        ReplenishmentSuggestion(
            product_id=product.id,
            warehouse_id=warehouse.id,
            supplier_id=supplier.id,
            current_qty=1,
            suggested_qty=24,
            status=ReplenishmentSuggestion.STATUS_PENDING,
        ),
        PurchaseOrder(
            po_no='PO-RULE-001',
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            status=PurchaseOrder.STATUS_PENDING,
            total_amount=168000,
        ),
        SupplierPerformance(
            supplier_id=supplier.id,
            total_orders=12,
            on_time_orders=9,
            quality_pass_orders=8,
            total_amount=268000,
        ),
        Receivable(
            receivable_no='AR-RULE-001',
            customer_id=customer.id,
            total_amount=88000,
            paid_amount=12000,
            due_date=date.today() - timedelta(days=45),
            status=Receivable.STATUS_OVERDUE,
        ),
        ReportSubscription(
            user_id=admin.id,
            report_type=ReportSubscription.REPORT_RECEIVABLE,
            report_name='规则治理应收日报',
            is_active=False,
        ),
        AuditLog(user_id=admin.id, module='rules', action='delete_rule_probe', details='rule governance risk seed'),
    ])
    db.session.commit()

    quality_inspection = client.get('/api/v1/operations/quality-inspection', headers=headers)
    assert quality_inspection.status_code == 200
    quality_inspection_payload = quality_inspection.json['data']
    assert quality_inspection_payload['source'] == 'quality_inspection_contract'
    assert quality_inspection_payload['summary']['quality_score'] >= 0
    assert quality_inspection_payload['summary']['queue_count'] >= 1
    assert {item['id'] for item in quality_inspection_payload['inspection_lanes']} >= {
        'incoming-lots',
        'in-process',
        'supplier-quality',
        'defect-containment',
    }
    assert quality_inspection_payload['inspection_queue']
    assert quality_inspection_payload['supplier_quality']
    assert quality_inspection_payload['defect_taxonomy']
    assert quality_inspection_payload['inspection_lots']
    assert quality_inspection_payload['document_set'] is not None
    assert quality_inspection_payload['quality_flow']
    assert quality_inspection_payload['runbook']
    assert quality_inspection_payload['service_boundary']
    quality_item = quality_inspection_payload['inspection_queue'][0]
    quality_task = client.post('/api/v1/operations/quality-inspection', headers=headers, json={
        'queue_item_id': quality_item['id'],
        'product_id': quality_item['product_id'],
        'supplier_id': quality_item['supplier_id'],
        'purchase_id': quality_item['purchase_id'],
        'title': quality_item['title'],
        'owner': quality_item['owner'],
        'priority': quality_item['priority'],
        'sla': quality_item['sla'],
        'evidence': quality_item['evidence'],
        'action': quality_item['action'],
        'path': quality_item['path'],
    })
    assert quality_task.status_code == 201
    quality_notification = quality_task.json['data']
    assert quality_notification['related_type'] == 'quality_inspection'
    assert quality_notification['category'] == Notification.CATEGORY_APPROVAL
    assert quality_item['owner'] in quality_notification['content']
    assert quality_item['path'] in quality_notification['content']
    inspection_audit = AuditLog.query.filter_by(module='operations', action='quality_inspection').order_by(AuditLog.id.desc()).first()
    assert inspection_audit is not None
    assert quality_item['id'] in inspection_audit.details
    inspection_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/quality' for item in inspection_queue.json['data']['items'])

    rules = client.get('/api/v1/operations/rules', headers=headers)
    assert rules.status_code == 200
    rules_payload = rules.json['data']
    assert rules_payload['source'] == 'rules_governance_contract'
    assert rules_payload['summary']['total'] >= 5
    assert rules_payload['summary']['queue_count'] >= 1
    assert rules_payload['summary']['automation_rate'] >= 0
    assert {item['key'] for item in rules_payload['domains']} >= {
        'replenishment-low-stock',
        'purchase-approval',
        'receivable-credit',
        'report-archive',
        'audit-write',
    }
    assert rules_payload['decision_queue']
    assert rules_payload['decision_map']
    assert rules_payload['runbook']
    rule_item = next(item for item in rules_payload['items'] if item['id'] == rules_payload['decision_queue'][0]['rule_id'])
    assert rule_item['decision_table']['hit_policy']
    assert rule_item['decision_table']['inputs']
    assert rule_item['decision_table']['outputs']
    assert rule_item['decision_table']['rows']
    assert rule_item['service_boundary']['contract']
    assert rule_item['governance']['monitoring_metric'].startswith('nexus_rule_')

    rule_queue_item = rules_payload['decision_queue'][0]
    review = client.post('/api/v1/operations/rules/review', headers=headers, json={
        'rule_id': rule_queue_item['rule_id'],
        'rule_name': rule_queue_item['title'],
        'owner': rule_queue_item['owner'],
        'priority': rule_queue_item['priority'],
        'sla': rule_queue_item['sla'],
        'evidence': rule_queue_item['evidence'],
        'action': rule_queue_item['action'],
        'path': rule_queue_item['path'],
    })
    assert review.status_code == 201
    review_notification = review.json['data']
    assert review_notification['related_type'] == 'rules'
    assert review_notification['category'] == Notification.CATEGORY_SYSTEM
    assert rule_queue_item['owner'] in review_notification['content']
    rule_audit = AuditLog.query.filter_by(module='operations', action='rules_review').order_by(AuditLog.id.desc()).first()
    assert rule_audit is not None
    assert rule_queue_item['rule_id'] in rule_audit.details
    rules_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/rules' for item in rules_queue.json['data']['items'])

    costs = client.get('/api/v1/operations/costs', headers=headers)
    assert costs.status_code == 200
    cost_payload = costs.json['data']
    assert cost_payload['source'] == 'cost_governance_contract'
    assert cost_payload['summary']['budget_total'] >= 1
    assert cost_payload['summary']['burn_rate'] >= 0
    assert {item['id'] for item in cost_payload['cost_centers']} >= {
        'cash-collection',
        'procurement-commitment',
        'inventory-capital',
        'gross-margin-guardrail',
    }
    assert cost_payload['variance_queue']
    assert cost_payload['runbook']
    assert cost_payload['service_boundary']
    cost_item = cost_payload['variance_queue'][0]
    cost_review = client.post('/api/v1/operations/costs/review', headers=headers, json={
        'item_id': cost_item['id'],
        'cost_center_id': cost_item['cost_center_id'],
        'title': cost_item['title'],
        'owner': cost_item['owner'],
        'priority': cost_item['priority'],
        'sla': cost_item['sla'],
        'evidence': cost_item['evidence'],
        'action': cost_item['action'],
        'path': cost_item['path'],
    })
    assert cost_review.status_code == 201
    cost_notification = cost_review.json['data']
    assert cost_notification['related_type'] == 'cost'
    assert cost_notification['category'] == Notification.CATEGORY_REPORT
    assert cost_item['owner'] in cost_notification['content']
    cost_audit = AuditLog.query.filter_by(module='operations', action='cost_review').order_by(AuditLog.id.desc()).first()
    assert cost_audit is not None
    assert cost_item['cost_center_id'] in cost_audit.details
    cost_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/budget' for item in cost_queue.json['data']['items'])

    capacity = client.get('/api/v1/operations/capacity', headers=headers)
    assert capacity.status_code == 200
    capacity_payload = capacity.json['data']
    assert capacity_payload['source'] == 'capacity_governance_contract'
    assert capacity_payload['summary']['load_score'] >= 0
    assert {item['id'] for item in capacity_payload['work_centers']} >= {
        'material-kitting',
        'procurement-inbound',
        'warehouse-release',
        'assembly-fulfillment',
    }
    assert capacity_payload['shift_plan']
    assert capacity_payload['bottleneck_queue']
    assert capacity_payload['runbook']
    assert capacity_payload['service_boundary']
    capacity_item = capacity_payload['bottleneck_queue'][0]
    capacity_review = client.post('/api/v1/operations/capacity/review', headers=headers, json={
        'item_id': capacity_item['id'],
        'work_center_id': capacity_item['work_center_id'],
        'title': capacity_item['title'],
        'owner': capacity_item['owner'],
        'priority': capacity_item['priority'],
        'sla': capacity_item['sla'],
        'evidence': capacity_item['evidence'],
        'action': capacity_item['action'],
        'path': capacity_item['path'],
    })
    assert capacity_review.status_code == 201
    capacity_notification = capacity_review.json['data']
    assert capacity_notification['related_type'] == 'capacity'
    assert capacity_notification['category'] == Notification.CATEGORY_APPROVAL
    assert capacity_item['owner'] in capacity_notification['content']
    capacity_audit = AuditLog.query.filter_by(module='operations', action='capacity_review').order_by(AuditLog.id.desc()).first()
    assert capacity_audit is not None
    assert capacity_item['work_center_id'] in capacity_audit.details
    capacity_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/capacity' for item in capacity_queue.json['data']['items'])

    mobile = client.get('/api/v1/operations/mobile-terminal', headers=headers)
    assert mobile.status_code == 200
    mobile_payload = mobile.json['data']
    assert mobile_payload['source'] == 'mobile_terminal_governance_contract'
    assert mobile_payload['summary']['total_tasks'] >= 1
    assert {item['id'] for item in mobile_payload['lanes']} >= {'receiving', 'counting', 'shipping', 'exceptions'}
    assert mobile_payload['scan_queue']
    assert mobile_payload['device_sessions']
    assert mobile_payload['warehouse_zones']
    assert mobile_payload['scan_flow']
    assert mobile_payload['runbook']
    assert mobile_payload['service_boundary']
    mobile_item = mobile_payload['scan_queue'][0]
    mobile_task = client.post('/api/v1/operations/mobile-terminal/task', headers=headers, json={
        'queue_item_id': mobile_item['id'],
        'task_type': mobile_item['type'],
        'title': mobile_item['title'],
        'owner': mobile_item['owner'],
        'priority': mobile_item['priority'],
        'sla': mobile_item['sla'],
        'evidence': mobile_item['evidence'],
        'next_action': mobile_item['next_action'],
        'path': mobile_item['path'],
    })
    assert mobile_task.status_code == 201
    mobile_notification = mobile_task.json['data']
    assert mobile_notification['related_type'] == 'mobile_terminal'
    assert mobile_notification['category'] == Notification.CATEGORY_STOCK
    assert mobile_item['owner'] in mobile_notification['content']
    assert mobile_item['scan_code'] in mobile_notification['content']
    mobile_audit = AuditLog.query.filter_by(module='operations', action='mobile_task').order_by(AuditLog.id.desc()).first()
    assert mobile_audit is not None
    assert mobile_item['id'] in mobile_audit.details
    mobile_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/mobile-terminal' for item in mobile_queue.json['data']['items'])

    maintenance = client.get('/api/v1/operations/maintenance', headers=headers)
    assert maintenance.status_code == 200
    maintenance_payload = maintenance.json['data']
    assert maintenance_payload['source'] == 'maintenance_reliability_contract'
    assert maintenance_payload['summary']['health_score'] >= 0
    assert {item['id'] for item in maintenance_payload['asset_lines']} >= {
        'critical-line',
        'mro-spares',
        'inspection-docs',
        'warehouse-maintenance',
    }
    assert maintenance_payload['workorder_queue']
    assert maintenance_payload['spare_parts']
    assert maintenance_payload['technician_roster']
    assert maintenance_payload['downtime_windows']
    assert maintenance_payload['maintenance_flow']
    assert maintenance_payload['runbook']
    assert maintenance_payload['service_boundary']
    maintenance_item = maintenance_payload['workorder_queue'][0]
    maintenance_task = client.post('/api/v1/operations/maintenance-workorder', headers=headers, json={
        'queue_item_id': maintenance_item['id'],
        'product_id': maintenance_item['product_id'],
        'title': maintenance_item['title'],
        'owner': maintenance_item['owner'],
        'priority': maintenance_item['priority'],
        'sla': maintenance_item['sla'],
        'evidence': maintenance_item['evidence'],
        'action': maintenance_item['action'],
        'path': maintenance_item['path'],
    })
    assert maintenance_task.status_code == 201
    maintenance_notification = maintenance_task.json['data']
    assert maintenance_notification['related_type'] == 'maintenance'
    assert maintenance_notification['category'] == Notification.CATEGORY_STOCK
    assert maintenance_item['owner'] in maintenance_notification['content']
    assert maintenance_item['path'] in maintenance_notification['content']
    maintenance_audit = AuditLog.query.filter_by(module='operations', action='maintenance_workorder').order_by(AuditLog.id.desc()).first()
    assert maintenance_audit is not None
    assert maintenance_item['id'] in maintenance_audit.details
    maintenance_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/maintenance' for item in maintenance_queue.json['data']['items'])

    readiness = client.get('/api/v1/operations/deployment-readiness', headers=headers)
    assert readiness.status_code == 200
    readiness_payload = readiness.json['data']
    assert readiness_payload['summary']['total'] >= 10
    assert readiness_payload['summary']['level'] in {'ready', 'attention', 'blocked'}
    assert readiness_payload['summary']['frontend_boundary'] == 'NEXUS_API_BASE_URL only'
    assert readiness_payload['service_snapshot']['services'] >= 8
    assert readiness_payload['service_snapshot']['api_surfaces'] >= 10
    assert readiness_payload['service_snapshot']['avg_split_score'] >= 45
    assert readiness_payload['service_snapshot']['split_plan']
    assert readiness_payload['service_snapshot']['observability']['coverage'] >= 60
    assert {item['key'] for item in readiness_payload['service_snapshot']['observability']['signals']} == {'metrics', 'logs', 'traces'}
    assert readiness_payload['service_snapshot']['incident_queue']
    assert {item['key'] for item in readiness_payload['checks']} >= {
        'frontend-api-url',
        'database-url',
        'secret-key',
        'database-probe',
        'microservice-catalog',
        'deployment-scripts',
    }
    assert readiness_payload['maturity']['summary']['target'] == '行业头部级制造开发管理 ERP'
    assert readiness_payload['maturity']['summary']['dimensions'] == 6
    assert readiness_payload['maturity']['summary']['score'] >= 60
    assert {item['key'] for item in readiness_payload['maturity']['dimensions']} >= {
        'front-back',
        'business-closure',
        'microservices',
        'deployment',
        'security',
        'delivery-assets',
    }
    assert any(item['domain'] == 'supply' for item in readiness_payload['maturity']['capability_map'])
    assert any(item['id'] == 'inventory' for item in readiness_payload['maturity']['topology_nodes'])
    assert any(item['from'] == 'inventory' for item in readiness_payload['maturity']['topology_edges'])
    assert any(item['path'] == 'docs/final-delivery-report.md' for item in readiness_payload['maturity']['evidence'])
    assert any(item['command'].startswith('powershell') for item in readiness_payload['runbook'])

    readiness_task = client.post('/api/v1/operations/deployment-readiness/task', headers=headers, json={
        'key': 'secret-key',
        'label': '后端 SECRET_KEY',
        'scope': 'backend',
        'status': 'blocked',
        'evidence': '生产环境未配置 SECRET_KEY。',
        'action': '在后端 Vercel 项目写入 SECRET_KEY production sensitive 后重新部署。'
    })
    assert readiness_task.status_code == 201
    readiness_notification = readiness_task.json['data']
    assert readiness_notification['title'] == '部署预检任务 - 后端 SECRET_KEY'
    assert readiness_notification['type'] == Notification.TYPE_ALERT
    assert readiness_notification['category'] == Notification.CATEGORY_SYSTEM
    assert readiness_notification['related_type'] == 'deployment_readiness'
    assert 'SECRET_KEY' in readiness_notification['content']
    readiness_audit = AuditLog.query.filter_by(module='operations', action='deployment_readiness_task').order_by(AuditLog.id.desc()).first()
    assert readiness_audit is not None
    assert 'secret-key' in readiness_audit.details

    assert client.post('/api/v1/operations/dispatch-task-legacy', headers=headers, json={}).status_code == 404
    assert client.post('/api/v1/operations/data-quality-notice-legacy', headers=headers, json={}).status_code == 404

    search = client.get('/api/v1/search?q=测试', headers=headers)
    assert search.status_code == 200
    assert any(item['type'] == 'product' for item in search.json['data']['items'])

    prefs = client.put('/api/v1/me/preferences', headers=headers, json={
        'density': 'compact',
        'views': {'inventory.products': [{'name': '低库存', 'filters': {'stock': 'low'}}]},
        'ignored': True
    })
    assert prefs.status_code == 200
    assert prefs.json['data']['density'] == 'compact'
    assert 'ignored' not in prefs.json['data']

    product_id = Product.query.filter_by(sku='MFG-T-001').first().id
    bulk = client.post('/api/v1/bulk-actions', headers=headers, json={
        'action': 'orders.update_status',
        'ids': [],
        'params': {'status': 'done'}
    })
    assert bulk.status_code == 400

    delete = client.post('/api/v1/bulk-actions', headers=headers, json={
        'action': 'products.delete',
        'ids': [product_id]
    })
    assert delete.status_code == 200
    assert delete.json['data']['changed'] == 1


def test_ai_chat_api_uses_business_analysis(client):
    headers = login(client)

    created = client.post('/api/v1/ai/sessions', headers=headers, json={'title': '经营分析'})
    assert created.status_code == 201
    session_id = created.json['data']['id']

    reply = client.post('/api/v1/ai/chat', headers=headers, json={
        'session_id': session_id,
        'message': '请分析当前库存和应收风险'
    })
    assert reply.status_code == 200
    assert reply.json['data']['session']['id'] == session_id
    assert 'message' in reply.json['data']
    assert reply.json['data']['message']['role'] == 'assistant'
    assert 'fallback' not in reply.json['data']
    assert reply.json['data']['source'] == 'operations_engine'

    messages = client.get(f'/api/v1/ai/sessions/{session_id}/messages', headers=headers)
    assert messages.status_code == 200
    assert len(messages.json['data']['items']) >= 2

    inventory = client.post('/api/v1/ai/analyze/inventory', headers=headers, json={'limit': 5})
    assert inventory.status_code == 200
    assert inventory.json['data']['content']

    settings = client.get('/api/v1/ai/settings', headers=headers)
    assert settings.status_code == 200
    assert settings.json['data']['analysis_mode'] in ['local', 'hybrid', 'external']

    updated = client.put('/api/v1/ai/settings', headers=headers, json={
        'analysis_mode': 'hybrid',
        'ai_api_base': 'https://api.deepseek.com',
        'ai_api_key': 'sk-test-user-credential-123456',
    })
    assert updated.status_code == 200
    assert updated.json['data']['analysis_mode'] == 'hybrid'
    assert updated.json['data']['external_source'] == 'user'
    assert updated.json['data']['has_user_credential'] is True

    diagnostics = client.post('/api/v1/ai/diagnostics', headers=headers, json={})
    assert diagnostics.status_code == 200
    assert diagnostics.json['data']['snapshot']['low_stock_count'] >= 0
    assert diagnostics.json['data']['analysis_mode'] == 'hybrid'

    structured = client.post('/api/v1/ai/analyze/structured', headers=headers, json={'scenario': 'inventory', 'limit': 5})
    assert structured.status_code == 200
    assert structured.json['data']['scenario'] == 'inventory'
    assert 'insight_cards' in structured.json['data']
    assert 'action_items' in structured.json['data']

    external_only = client.put('/api/v1/ai/settings', headers=headers, json={
        'analysis_mode': 'external',
        'ai_api_base': 'https://127.0.0.1:9',
        'ai_api_key': 'sk-test-user-credential-123456',
    })
    assert external_only.status_code == 200
    provider_failure = client.post('/api/v1/ai/chat', headers=headers, json={'message': '请调用外部模型确认服务'})
    assert provider_failure.status_code == 502
    assert provider_failure.json['error'] == 'ai_provider_unavailable'


def test_ai_external_mode_calls_openai_compatible_chat_api(client, monkeypatch):
    headers = login(client)
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                'choices': [{'message': {'content': '外部模型已完成经营分析。'}}],
                'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18},
            }

    class FakeClient:
        def post(self, url, headers=None, json=None):
            captured['url'] = url
            captured['headers'] = headers or {}
            captured['json'] = json or {}
            return FakeResponse()

    monkeypatch.setattr(ai_service, '_get_http_client', lambda: FakeClient())

    updated = client.put('/api/v1/ai/settings', headers=headers, json={
        'analysis_mode': 'external',
        'ai_api_base': 'https://api.openai.com',
        'ai_api_key': 'sk-test-openai-compatible-credential',
        'ai_model': 'gpt-4.1-mini',
    })
    assert updated.status_code == 200

    reply = client.post('/api/v1/ai/chat', headers=headers, json={'message': '请调用外部模型生成摘要'})
    assert reply.status_code == 200
    assert reply.json['data']['source'] == 'analysis_provider'
    assert reply.json['data']['message']['content'] == '外部模型已完成经营分析。'
    assert captured['url'] == 'https://api.openai.com/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer sk-test-openai-compatible-credential'
    assert captured['json']['model'] == 'gpt-4.1-mini'
    assert captured['json']['messages'][-1]['content'] == '请调用外部模型生成摘要'


def test_ai_diagnostics_uses_short_timeout_and_cache(client, monkeypatch):
    ai_service._diagnostic_cache.clear()
    calls = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def get(self, url, headers=None, timeout=None):
            calls.append({'url': url, 'timeout': timeout, 'headers': headers or {}})
            return FakeResponse()

    monkeypatch.setattr(ai_service, '_get_http_client', lambda: FakeClient())

    first = ai_service._external_diagnostics('sk-test-diagnostics-credential', 'https://api.openai.com')
    second = ai_service._external_diagnostics('sk-test-diagnostics-credential', 'https://api.openai.com')

    assert first['status'] == 'ready'
    assert second['status'] == 'ready'
    assert second['cached'] is True
    assert len(calls) == 1
    assert calls[0]['url'] == 'https://api.openai.com/v1/models'
    assert calls[0]['timeout'] == 2.0


def test_phase_two_business_api_paths(client):
    headers = login(client)
    product_id = Product.query.filter_by(sku='MFG-T-001').first().id
    customer_id = Partner.query.filter_by(type='customer').first().id
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id

    health = client.get('/api/v1/inventory/health', headers=headers)
    assert health.status_code == 200
    assert health.json['data']['total_products'] == 1

    order = client.post('/api/v1/sales/orders', headers=headers, json={
        'customer_id': customer_id,
        'items': [{'product_id': product_id, 'quantity': 1}],
        'status': 'pending'
    })
    order_id = order.json['data']['id']
    transition = client.post(f'/api/v1/sales/orders/{order_id}/transition', headers=headers, json={'status': 'paid'})
    assert transition.status_code == 200
    assert transition.json['data']['status'] == 'paid'

    purchase = client.post('/api/v1/procurement/orders', headers=headers, json={
        'supplier_id': supplier_id,
        'warehouse_id': warehouse_id,
        'items': [{'product_id': product_id, 'quantity': 3, 'unit_price': 40}]
    })
    po_id = purchase.json['data']['id']
    summary = client.get('/api/v1/procurement/summary', headers=headers)
    assert summary.status_code == 200
    assert summary.json['data']['draft'] >= 1
    assert client.post(f'/api/v1/procurement/orders/{po_id}/submit', headers=headers, json={}).status_code == 200

    receivable = Receivable(
        receivable_no='AR-TEST-001',
        customer_id=customer_id,
        total_amount=100,
        paid_amount=25,
        status=Receivable.STATUS_PENDING,
    )
    notification = Notification(user_id=User.query.filter_by(email='admin@nexus.com').first().id, title='测试通知', content='需要处理')
    db.session.add_all([receivable, notification])
    db.session.commit()

    aging = client.get('/api/v1/finance/receivables/aging', headers=headers)
    assert aging.status_code == 200
    assert aging.json['data']['unpaid_amount'] >= 75

    mark_read = client.post('/api/v1/notifications/mark-read', headers=headers, json={'ids': [notification.id]})
    assert mark_read.status_code == 200
    assert mark_read.json['data']['changed'] == 1

    deployment_notification = Notification(
        user_id=User.query.filter_by(email='admin@nexus.com').first().id,
        title='部署预检任务 - 前端 API 地址',
        content='请写入 NEXUS_API_BASE_URL',
        category=Notification.CATEGORY_SYSTEM,
        type=Notification.TYPE_WARNING,
        related_type='deployment_readiness',
        is_read=False,
    )
    db.session.add(deployment_notification)
    db.session.commit()
    complete = client.post('/api/v1/notifications/complete', headers=headers, json={
        'id': deployment_notification.id,
        'resolution': '已进入设置页完成环境变量复核。',
        'source_path': '/app/settings'
    })
    assert complete.status_code == 200
    assert complete.json['data']['is_read'] is True
    assert complete.json['data']['related_type'] == 'deployment_readiness'
    complete_audit = AuditLog.query.filter_by(module='notifications', action='complete_task').order_by(AuditLog.id.desc()).first()
    assert complete_audit is not None
    assert '/app/settings' in complete_audit.details

    upload = client.post(
        '/api/v1/files/upload',
        headers=headers,
        data={'file': (BytesIO(b'NEXUS phase two'), 'phase-two.txt')},
        content_type='multipart/form-data'
    )
    file_id = upload.json['data']['id']
    bulk_delete = client.post('/api/v1/files/bulk-delete', headers=headers, json={'ids': [file_id]})
    assert bulk_delete.status_code == 200
    assert bulk_delete.json['data']['changed'] == 1


def test_procurement_control_contract_and_task(client):
    headers = login(client)
    product = Product.query.filter_by(sku='MFG-T-001').first()
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id
    purchase = client.post('/api/v1/procurement/orders', headers=headers, json={
        'supplier_id': supplier_id,
        'warehouse_id': warehouse_id,
        'expected_date': (date.today() + timedelta(days=1)).isoformat(),
        'items': [{'product_id': product.id, 'quantity': 6, 'unit_price': 40}]
    })
    assert purchase.status_code == 201
    po_id = purchase.json['data']['id']
    assert client.post(f'/api/v1/procurement/orders/{po_id}/submit', headers=headers, json={}).status_code == 200
    suggestion = ReplenishmentSuggestion(
        product_id=product.id,
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
        current_qty=2,
        suggested_qty=12,
        avg_daily_sales=2.5,
        lead_time_days=5,
        safety_stock=8,
        status=ReplenishmentSuggestion.STATUS_PENDING,
    )
    supplier_perf = SupplierPerformance(
        supplier_id=supplier_id,
        total_orders=8,
        on_time_orders=5,
        quality_pass_orders=5,
        total_amount=360000,
    )
    db.session.add_all([suggestion, supplier_perf])
    db.session.commit()

    response = client.get('/api/v1/operations/procurement-control', headers=headers)
    assert response.status_code == 200
    payload = response.json['data']
    assert payload['source'] == 'procurement_control_contract'
    assert payload['summary']['pending_approvals'] >= 1
    assert payload['summary']['replenishment_pending'] >= 1
    assert {lane['id'] for lane in payload['procurement_lanes']} >= {'demand', 'approval', 'receiving', 'quality', 'supplier', 'finance'}
    assert any(item['purchase_id'] == po_id for item in payload['approval_queue'])
    assert any(item['supplier_id'] == supplier_id for item in payload['supplier_risk_cards'])
    assert any(boundary['deploy_unit'] == 'procurement-api' for boundary in payload['service_boundaries'])
    assert {'api-contract', 'domain-actions', 'quality-handoff', 'budget-exposure'} <= {item['key'] for item in payload['deployment_checks']}

    queue_item = payload['control_queue'][0]
    task = client.post('/api/v1/operations/procurement-control/task', headers=headers, json={
        'queue_item_id': queue_item['id'],
        'title': queue_item['title'],
        'priority': queue_item['priority'],
        'purchase_id': queue_item.get('purchase_id'),
    })
    assert task.status_code == 201
    assert task.json['data']['related_type'] == 'procurement_control'
    audit = AuditLog.query.filter_by(module='operations', action='procurement_control_task').order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert 'procurement_control' in audit.details or '采购' in audit.details


def test_supplier_collaboration_contract_and_task(client):
    headers = login(client)
    product = Product.query.filter_by(sku='MFG-T-001').first()
    supplier = Partner.query.filter_by(type='supplier').first()
    warehouse_id = Warehouse.query.first().id
    po = PurchaseOrder(
        po_no='PO-SUPPLIER-001',
        supplier_id=supplier.id,
        warehouse_id=warehouse_id,
        status=PurchaseOrder.STATUS_APPROVED,
        expected_date=(date.today() + timedelta(days=1)),
        total_amount=128000,
    )
    supplier.credit_score = 66
    perf = SupplierPerformance(
        supplier_id=supplier.id,
        total_orders=10,
        on_time_orders=6,
        quality_pass_orders=6,
        total_amount=520000,
    )
    suggestion = ReplenishmentSuggestion(
        product_id=product.id,
        warehouse_id=warehouse_id,
        supplier_id=supplier.id,
        current_qty=1,
        suggested_qty=18,
        avg_daily_sales=3.2,
        lead_time_days=6,
        safety_stock=9,
        status=ReplenishmentSuggestion.STATUS_PENDING,
    )
    db.session.add_all([po, perf, suggestion])
    db.session.commit()

    response = client.get('/api/v1/operations/supplier-collaboration', headers=headers)
    assert response.status_code == 200
    payload = response.json['data']
    assert payload['source'] == 'supplier_collaboration_contract'
    assert payload['summary']['active_suppliers'] >= 1
    assert payload['summary']['risk_suppliers'] >= 1
    assert {lane['id'] for lane in payload['collaboration_lanes']} >= {'qualification', 'delivery', 'quality', 'commercial', 'collaboration'}
    assert any(card['supplier_id'] == supplier.id and card['priority'] in {'P0', 'P1'} for card in payload['supplier_cards'])
    assert any(item['supplier_id'] == supplier.id for item in payload['risk_queue'])
    assert any(item['supplier_id'] == supplier.id for item in payload['delivery_windows'])
    assert any(boundary['deploy_unit'] == 'supplier-api' for boundary in payload['service_boundaries'])
    assert {'api-contract', 'task-writeback', 'quality-capa', 'concentration-risk'} <= {item['key'] for item in payload['deployment_checks']}

    queue_item = payload['risk_queue'][0]
    task = client.post('/api/v1/operations/supplier-collaboration/task', headers=headers, json={
        'queue_item_id': queue_item['id'],
        'supplier_id': queue_item.get('supplier_id'),
        'title': queue_item['title'],
        'priority': queue_item['priority'],
    })
    assert task.status_code == 201
    assert task.json['data']['related_type'] == 'supplier_collaboration'
    assert task.json['data']['category'] == Notification.CATEGORY_APPROVAL
    audit = AuditLog.query.filter_by(module='operations', action='supplier_collaboration_task').order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert queue_item['id'] in audit.details
    task_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert any(item['source'] == 'notification' and item['source_path'] == '/app/suppliers/performance' for item in task_queue.json['data']['items'])


def test_sensitive_business_actions_require_permissions(client):
    admin_headers = login(client)
    product_id = Product.query.filter_by(sku='MFG-T-001').first().id
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id

    purchase = client.post('/api/v1/procurement/orders', headers=admin_headers, json={
        'supplier_id': supplier_id,
        'warehouse_id': warehouse_id,
        'items': [{'product_id': product_id, 'quantity': 3, 'unit_price': 40}]
    })
    po_id = purchase.json['data']['id']
    assert client.post(f'/api/v1/procurement/orders/{po_id}/submit', headers=admin_headers, json={}).status_code == 200
    member_headers = login(client, 'member@nexus.com', 'member123')
    assert client.post(f'/api/v1/procurement/orders/{po_id}/approve', headers=member_headers, json={}).status_code == 403

    customer_id = Partner.query.filter_by(type='customer').first().id
    receivable = Receivable(
        receivable_no='AR-PERM-001',
        customer_id=customer_id,
        total_amount=100,
        paid_amount=0,
        status=Receivable.STATUS_PENDING,
    )
    db.session.add(receivable)
    db.session.commit()
    payment = client.post(
        f'/api/v1/finance/receivables/{receivable.id}/payment',
        headers=member_headers,
        json={'amount': 10, 'payment_method': 'bank'}
    )
    assert payment.status_code == 403
    reminder = client.post(f'/api/v1/finance/receivables/{receivable.id}/reminder', headers=member_headers, json={})
    assert reminder.status_code == 403


def test_generic_dangerous_business_writes_are_rejected(client):
    headers = login(client)
    product_id = Product.query.filter_by(sku='MFG-T-001').first().id
    stock = Stock.query.filter_by(product_id=product_id).first()
    customer_id = Partner.query.filter_by(type='customer').first().id
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id

    stock_write = client.put(f'/api/v1/stock/{stock.id}', headers=headers, json={'quantity': 999})
    assert stock_write.status_code == 403
    assert db.session.get(Stock, stock.id).quantity == 20

    order = client.post('/api/v1/sales/orders', headers=headers, json={
        'customer_id': customer_id,
        'items': [{'product_id': product_id, 'quantity': 1}],
        'status': 'pending'
    })
    order_write = client.put(f"/api/v1/orders/{order.json['data']['id']}", headers=headers, json={'status': 'done', 'total_amount': 1})
    assert order_write.status_code == 403

    purchase = client.post('/api/v1/procurement/orders', headers=headers, json={
        'supplier_id': supplier_id,
        'warehouse_id': warehouse_id,
        'items': [{'product_id': product_id, 'quantity': 3, 'unit_price': 40}]
    })
    po_id = purchase.json['data']['id']
    assert client.post(f'/api/v1/procurement/orders/{po_id}/submit', headers=headers, json={}).status_code == 200
    assert client.post(f'/api/v1/procurement/orders/{po_id}/approve', headers=headers, json={}).status_code == 200
    item_id = db.session.get(PurchaseOrder, po_id).items[0].id
    over_receive = client.post(
        f'/api/v1/procurement/orders/{po_id}/receive',
        headers=headers,
        json={'items': [{'item_id': item_id, 'receive_qty': 99}]}
    )
    assert over_receive.status_code == 400


def test_sales_order_requires_valid_items_and_deducts_stock_on_ship(client):
    headers = login(client)
    product = Product.query.filter_by(sku='MFG-T-001').first()
    stock = Stock.query.filter_by(product_id=product.id).first()
    before = stock.quantity
    customer_id = Partner.query.filter_by(type='customer').first().id

    empty_order = client.post('/api/v1/sales/orders', headers=headers, json={'customer_id': customer_id, 'items': []})
    assert empty_order.status_code == 400

    order = client.post('/api/v1/sales/orders', headers=headers, json={
        'customer_id': customer_id,
        'items': [{'product_id': product.id, 'quantity': 2}],
        'status': 'pending'
    })
    assert order.status_code == 201
    order_id = order.json['data']['id']
    assert client.post(f'/api/v1/sales/orders/{order_id}/transition', headers=headers, json={'status': 'paid'}).status_code == 200
    shipped = client.post(f'/api/v1/sales/orders/{order_id}/transition', headers=headers, json={'status': 'shipped'})
    assert shipped.status_code == 200
    assert Stock.query.filter_by(product_id=product.id).first().quantity == before - 2


def test_stocktake_cycle_count_workflow_creates_items_and_completes(client):
    headers = login(client)
    warehouse = Warehouse.query.first()

    created = client.post('/api/v1/stocktakes/create', headers=headers, json={
        'warehouse_id': warehouse.id,
        'take_type': 'cycle',
        'product_ids': [],
        'remark': '周期盘点闭环测试'
    })
    assert created.status_code == 201
    take_id = created.json['data']['id']
    assert created.json['data']['total_items'] >= 1
    assert StockTakeItem.query.filter_by(take_id=take_id).count() >= 1

    premature_count = client.post(f'/api/v1/stocktakes/{take_id}/count', headers=headers, json={'items': [{}]})
    assert premature_count.status_code == 400

    started = client.post(f'/api/v1/stocktakes/{take_id}/start', headers=headers, json={})
    assert started.status_code == 200

    counted = client.post(f'/api/v1/stocktakes/{take_id}/count', headers=headers, json={'items': [{}]})
    assert counted.status_code == 200
    assert counted.json['data']['counted'] == 1

    take = db.session.get(StockTake, take_id)
    remaining = StockTakeItem.query.filter(
        StockTakeItem.take_id == take_id,
        StockTakeItem.actual_qty.is_(None)
    ).all()
    if remaining:
        fill_all = client.post(f'/api/v1/stocktakes/{take_id}/count', headers=headers, json={
            'items': [{'item_id': item.id, 'actual_qty': item.system_qty} for item in remaining]
        })
        assert fill_all.status_code == 200
    assert take.counted_items == take.total_items

    completed = client.post(f'/api/v1/stocktakes/{take_id}/complete', headers=headers, json={'auto_adjust': True})
    assert completed.status_code == 200
    assert db.session.get(StockTake, take_id).status == StockTake.STATUS_COMPLETED


def test_user_scoped_files_and_reports_are_not_exposed_cross_account(client):
    admin_headers = login(client)
    member_headers = login(client, 'member@nexus.com', 'member123')
    admin = User.query.filter_by(email='admin@nexus.com').first()
    member = User.query.filter_by(email='member@nexus.com').first()

    attachment = Attachment(filename='admin-only.txt', filepath='admin-only.txt', mimetype='text/plain', size=8, uploader_id=admin.id)
    admin_report = GeneratedReport(report_type='sales_daily', report_name='管理员报表', report_data={'secret': True}, generated_by=admin.id)
    member_subscription = ReportSubscription(
        user_id=member.id,
        report_type='inventory_summary',
        report_name='成员订阅',
        frequency=ReportSubscription.FREQUENCY_DAILY,
    )
    db.session.add_all([attachment, admin_report, member_subscription])
    db.session.commit()

    assert client.get(f'/api/v1/files/{attachment.id}/download', headers=member_headers).status_code == 403
    assert client.get(f'/api/v1/generated-reports/{admin_report.id}', headers=member_headers).status_code == 403

    reports = client.get('/api/v1/generated-reports?page=1&page_size=20', headers=member_headers)
    assert reports.status_code == 200
    assert all(item['id'] != admin_report.id for item in reports.json['data']['items'])

    search = client.get('/api/v1/search?q=admin-only', headers=member_headers)
    assert search.status_code == 200
    assert all(item['type'] != 'file' or item['label'] != 'admin-only.txt' for item in search.json['data']['items'])

    subscriptions = client.get('/api/v1/report-subscriptions?page=1&page_size=20', headers=member_headers)
    assert subscriptions.status_code == 200
    assert subscriptions.json['data']['pagination']['total'] == 1
    assert subscriptions.json['data']['items'][0]['user_id'] == member.id

    created = client.post('/api/v1/report-subscriptions', headers=member_headers, json={
        'user_id': admin.id,
        'report_type': 'sales_daily',
        'report_name': '伪造订阅',
        'frequency': ReportSubscription.FREQUENCY_DAILY,
    })
    assert created.status_code == 201
    assert created.json['data']['user_id'] == member.id

    admin_headers = login(client)
    assert client.get(f'/api/v1/generated-reports/{admin_report.id}', headers=admin_headers).status_code == 200


def test_operations_exceptions_preferences_and_audit(client):
    headers = login(client)
    admin = User.query.filter_by(email='admin@nexus.com').first()
    member = User.query.filter_by(email='member@nexus.com').first()
    product = Product.query.filter_by(sku='MFG-T-001').first()
    stock = Stock.query.filter_by(product_id=product.id).first()
    stock.quantity = 1
    product.min_stock = 5
    supplier_id = Partner.query.filter_by(type='supplier').first().id
    warehouse_id = Warehouse.query.first().id
    po = PurchaseOrder(
        po_no='PO-AUDIT-001',
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        status=PurchaseOrder.STATUS_PENDING,
        total_amount=360
    )
    db.session.add(po)
    db.session.add_all([
        Notification(user_id=admin.id, title='管理员专属通知', content='仅管理员可见', is_read=False),
        Notification(user_id=member.id, title='成员专属通知', content='成员待办', is_read=False),
    ])
    db.session.commit()

    exceptions = client.get('/api/v1/operations/exceptions', headers=headers)
    assert exceptions.status_code == 200
    assert exceptions.json['data']['total'] >= 1
    assert any(item['type'] in ['库存', '采购'] for item in exceptions.json['data']['items'])

    todo = client.get('/api/v1/operations/todo', headers=headers)
    assert todo.status_code == 200
    unread_todo = next(item for item in todo.json['data']['items'] if item['label'] == '未读通知')
    assert unread_todo['value'] >= 2
    task_queue = client.get('/api/v1/operations/task-queue', headers=headers)
    assert task_queue.status_code == 200
    task_payload = task_queue.json['data']
    assert task_payload['summary']['total'] >= 1
    assert task_payload['summary']['deployment_attention'] >= 0
    assert any(item['source'] == 'notification' and item['action_kind'] == 'complete_notification' for item in task_payload['items'])
    assert any(item['source'] == 'deployment' and item['action_kind'] == 'create_deployment_task' for item in task_payload['items'])
    assert any(item['source_path'].startswith('/app/') for item in task_payload['items'])
    visible_action_kinds = {item['action_kind'] for item in task_payload['items'][:12]}
    assert 'complete_notification' in visible_action_kinds
    assert 'create_deployment_task' in visible_action_kinds

    member_headers = login(client, 'member@nexus.com', 'member123')
    member_todo = client.get('/api/v1/operations/todo', headers=member_headers)
    assert member_todo.status_code == 200
    member_unread_todo = next(item for item in member_todo.json['data']['items'] if item['label'] == '未读通知')
    assert member_unread_todo['value'] == 1
    member_queue = client.get('/api/v1/operations/task-queue', headers=member_headers)
    assert member_queue.status_code == 200
    member_notifications = [item for item in member_queue.json['data']['items'] if item['source'] == 'notification']
    assert member_notifications
    assert all('管理员专属通知' not in item['title'] for item in member_notifications)
    member_exceptions = client.get('/api/v1/operations/exceptions', headers=member_headers)
    assert member_exceptions.status_code == 200
    notification_titles = [item['title'] for item in member_exceptions.json['data']['items'] if item['type'] == '通知']
    assert '成员专属通知' in notification_titles
    assert '管理员专属通知' not in notification_titles

    headers = login(client)
    prefs = client.put('/api/v1/me/preferences', headers=headers, json={
        'default_workspace': '供应链',
        'command_history': ['inventory.products'],
        'theme': 'light',
        'unsafe': True
    })
    assert prefs.status_code == 200
    assert prefs.json['data']['default_workspace'] == '供应链'
    assert 'unsafe' not in prefs.json['data']

    transition_source = client.post('/api/v1/sales/orders', headers=headers, json={
        'customer_id': Partner.query.filter_by(type='customer').first().id,
        'items': [{'product_id': product.id, 'quantity': 1}],
        'status': 'pending'
    })
    order_id = transition_source.json['data']['id']
    transition = client.post(f'/api/v1/sales/orders/{order_id}/transition', headers=headers, json={'status': 'paid'})
    assert transition.status_code == 200
    assert AuditLog.query.filter_by(module='sales', action='transition').count() >= 1


def test_seed_enterprise_command_generates_realistic_related_data(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['seed-enterprise', '--scale', '1', '--multiplier', '1', '--reset', '--seed', '20241334'])
    assert result.exit_code == 0, result.output

    assert User.query.filter_by(email='admin@nexus.com').first().verify_password('admin123')
    assert Product.query.count() >= 36
    assert Product.query.filter(Product.name.ilike('%伺服%')).first()
    assert Product.query.filter(Product.name.ilike('%铝合金%')).first()
    assert Product.query.filter(Product.name.ilike('%MRO%')).first()
    assert Warehouse.query.filter(Warehouse.name.ilike('%工厂仓%')).first()
    assert Warehouse.query.filter(Warehouse.name.ilike('%区域仓%')).first()
    assert Order.query.count() >= 60
    assert PurchaseOrder.query.count() >= 24
    assert Receivable.query.count() >= 1
    assert StockAlert.query.count() >= 1
    assert ReplenishmentSuggestion.query.count() >= 1
    assert Notification.query.count() >= 18
    assert AuditLog.query.filter_by(action='seed_enterprise').count() == 1
    assert not Product.query.filter(Product.name.ilike('%量子%')).first()
    assert not Product.query.filter(Product.name.ilike('%人体工学椅%')).first()


def test_seed_enterprise_accepts_custom_demo_passwords(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=[
        'seed-enterprise',
        '--scale', '1',
        '--multiplier', '1',
        '--reset',
        '--seed', '20241334',
        '--admin-password', 'remote-admin-demo-123',
        '--user-password', 'remote-user-demo-123',
    ])
    assert result.exit_code == 0, result.output

    assert User.query.filter_by(email='admin@nexus.com').first().verify_password('remote-admin-demo-123')
    assert User.query.filter_by(email='user001@nexus.com').first().verify_password('remote-user-demo-123')
    assert '<已自定义>' in result.output


def test_seed_enterprise_rejects_default_passwords_for_production_remote_seed(app, monkeypatch):
    monkeypatch.setenv('FLASK_CONFIG', 'production')
    runner = app.test_cli_runner()
    result = runner.invoke(args=[
        'seed-enterprise',
        '--scale', '1',
        '--multiplier', '50',
        '--reset',
        '--seed', '20241334',
    ])

    assert result.exit_code != 0
    assert 'NEXUS_DEMO_ADMIN_PASSWORD' in result.output
