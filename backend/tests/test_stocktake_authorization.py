from app import create_app
from app.extensions import db
from app.models.auth import Permission, Role, User
from app.models.biz import Product
from app.models.stock import Stock, Warehouse
from app.models.stocktake import StockTake, StockTakeItem


def login(client, email, password):
    response = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json['data']['csrf_token']}


def seed_stocktake_auth_context():
    permission = Permission(name='stocktake.write', description='盘点管理')
    owner_role = Role(name='OwnerRole', is_admin=False)
    other_role = Role(name='OtherRole', is_admin=False)
    owner_role.permissions.append(permission)
    other_role.permissions.append(permission)
    owner = User(username='stocktake-owner', email='stocktake-owner@nexus.com', role=owner_role)
    owner.password = 'owner123'
    other = User(username='stocktake-other', email='stocktake-other@nexus.com', role=other_role)
    other.password = 'other123'
    db.session.add_all([permission, owner_role, other_role, owner, other])
    db.session.flush()

    warehouse = Warehouse(name='盘点仓')
    product = Product(sku='ST-AUTH-001', name='盘点授权物料', cost=12)
    db.session.add_all([warehouse, product])
    db.session.flush()
    db.session.add(Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=10))
    db.session.commit()
    return owner, other, warehouse, product


def test_stocktake_resources_require_read_permission():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        owner, other, warehouse, _product = seed_stocktake_auth_context()
        no_access_role = Role(name='NoStocktakeAccess', is_admin=False)
        no_access = User(username='stocktake-no-access', email='stocktake-no-access@nexus.com', role=no_access_role)
        no_access.password = 'noaccess123'
        db.session.add_all([no_access_role, no_access])
        db.session.flush()
        take = StockTake(take_no='ST-READ-PERM', warehouse_id=warehouse.id, take_type=StockTake.TYPE_CYCLE, created_by=owner.id)
        db.session.add(take)
        db.session.flush()
        item = StockTakeItem(take_id=take.id, product_id=None, system_qty=0, unit_cost=0)
        db.session.add(item)
        db.session.commit()

        client = app.test_client()
        no_access_headers = login(client, no_access.email, 'noaccess123')
        for resource, item_id in (('stocktakes', take.id), ('stocktake-items', item.id)):
            denied_list = client.get(f'/api/v1/{resource}?page=1&page_size=20', headers=no_access_headers)
            assert denied_list.status_code == 403
            assert denied_list.json['error'] == 'permission_denied'
            denied_detail = client.get(f'/api/v1/{resource}/{item_id}', headers=no_access_headers)
            assert denied_detail.status_code == 403
            assert denied_detail.json['error'] in {'permission_denied', 'forbidden'}

        owner_headers = login(client, owner.email, 'owner123')
        owner_list = client.get('/api/v1/stocktakes?page=1&page_size=20', headers=owner_headers)
        assert owner_list.status_code == 200
        assert take.id in {row['id'] for row in owner_list.json['data']['items']}

        other_headers = login(client, other.email, 'other123')
        other_list = client.get('/api/v1/stocktakes?page=1&page_size=20', headers=other_headers)
        assert other_list.status_code == 200
        assert take.id not in {row['id'] for row in other_list.json['data']['items']}
        other_detail = client.get(f'/api/v1/stocktakes/{take.id}', headers=other_headers)
        assert other_detail.status_code == 403
        assert other_detail.json['error'] == 'forbidden'

        db.session.remove()
        db.drop_all()


def test_stocktake_resources_are_scoped_to_creator():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        owner, other, warehouse, _product = seed_stocktake_auth_context()
        owner_client = app.test_client()
        other_client = app.test_client()
        owner_headers = login(owner_client, owner.email, 'owner123')
        other_headers = login(other_client, other.email, 'other123')

        created = owner_client.post(
            '/api/v1/stocktakes/create',
            headers=owner_headers,
            json={'warehouse_id': warehouse.id, 'take_type': StockTake.TYPE_CYCLE, 'product_ids': []},
        )
        assert created.status_code == 201
        take_id = created.json['data']['id']

        owner_list = owner_client.get('/api/v1/stocktakes?page=1&page_size=20', headers=owner_headers)
        other_list = other_client.get('/api/v1/stocktakes?page=1&page_size=20', headers=other_headers)

        assert owner_list.status_code == 200
        assert take_id in {item['id'] for item in owner_list.json['data']['items']}
        assert other_list.status_code == 200
        assert take_id not in {item['id'] for item in other_list.json['data']['items']}
        assert other_client.get(f'/api/v1/stocktakes/{take_id}', headers=other_headers).status_code == 403

        db.session.remove()
        db.drop_all()


def test_stocktake_actions_reject_cross_creator_operations():
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        owner, other, warehouse, _product = seed_stocktake_auth_context()
        owner_client = app.test_client()
        other_client = app.test_client()
        owner_headers = login(owner_client, owner.email, 'owner123')
        other_headers = login(other_client, other.email, 'other123')

        created = owner_client.post(
            '/api/v1/stocktakes/create',
            headers=owner_headers,
            json={'warehouse_id': warehouse.id, 'take_type': StockTake.TYPE_CYCLE, 'product_ids': []},
        )
        assert created.status_code == 201
        take_id = created.json['data']['id']
        item = StockTakeItem.query.filter_by(take_id=take_id).one()

        blocked_start = other_client.post(f'/api/v1/stocktakes/{take_id}/start', headers=other_headers, json={})
        assert blocked_start.status_code == 403
        assert blocked_start.json['error'] == 'forbidden'
        assert db.session.get(StockTake, take_id).status == StockTake.STATUS_DRAFT

        assert owner_client.post(f'/api/v1/stocktakes/{take_id}/start', headers=owner_headers, json={}).status_code == 200

        blocked_batch_count = other_client.post(
            f'/api/v1/stocktakes/{take_id}/count',
            headers=other_headers,
            json={'items': [{'item_id': item.id, 'actual_qty': 10}]},
        )
        assert blocked_batch_count.status_code == 403
        db.session.refresh(item)
        assert item.actual_qty is None

        blocked_variance = other_client.get(f'/api/v1/stocktakes/{take_id}/variance', headers=other_headers)
        assert blocked_variance.status_code == 403

        blocked_count = other_client.post(
            f'/api/v1/stocktake-items/{item.id}/count',
            headers=other_headers,
            json={'actual_qty': 10},
        )
        assert blocked_count.status_code == 403
        db.session.refresh(item)
        assert item.actual_qty is None

        assert owner_client.post(
            f'/api/v1/stocktake-items/{item.id}/count',
            headers=owner_headers,
            json={'actual_qty': 10},
        ).status_code == 200

        blocked_complete = other_client.post(f'/api/v1/stocktakes/{take_id}/complete', headers=other_headers, json={})
        assert blocked_complete.status_code == 403
        assert db.session.get(StockTake, take_id).status == StockTake.STATUS_IN_PROGRESS

        db.session.remove()
        db.drop_all()
