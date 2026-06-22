from app import create_app
from app.extensions import db
from app.models.auth import Role, User
from app.models.biz import Partner, Product
from app.models.content import Attachment
from app.models.stock import InventoryLog, Warehouse
from app.models.sys import AuditLog
from app.platform.search import SEARCH_TARGETS, SearchService


def make_user(email: str, *, admin: bool = False) -> User:
    role = Role(name=f"role-{email}", is_admin=admin)
    user = User(username=email.split("@", 1)[0], email=email, role=role, is_admin=admin)
    user.password = "password123"
    db.session.add_all([role, user])
    db.session.flush()
    return user


def test_search_service_returns_empty_for_short_terms():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        assert SearchService().search("测", user=None) == []
        db.session.remove()
        db.drop_all()


def test_search_service_finds_products():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        user = make_user("searcher@nexus.com")
        product = Product(name="测试平台搜索产品", sku="SEARCH-001")
        db.session.add(product)
        db.session.commit()

        items = SearchService().search("平台搜索", user=user)

        assert any(item["type"] == "product" and item["label"] == "测试平台搜索产品" for item in items)
        db.session.remove()
        db.drop_all()


def test_search_service_declares_plan_search_targets():
    target_keys = {target.key for target in SEARCH_TARGETS}

    assert {
        "product",
        "partner",
        "order",
        "purchase",
        "receivable",
        "inventory-log",
        "file",
        "audit-log",
    }.issubset(target_keys)


def test_search_service_finds_partners_inventory_logs_and_audit_logs():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        user = make_user("ops-search@nexus.com", admin=True)
        partner = Partner(
            name="平台搜索供应商",
            type=Partner.TYPE_SUPPLIER,
            contact_person="林经理",
            phone="13800000000",
            email="supplier@example.com",
        )
        product = Product(name="搜索用零件", sku="PART-SEARCH-001")
        warehouse = Warehouse(name="华东仓", location="上海")
        db.session.add_all([partner, product, warehouse])
        db.session.flush()
        log = InventoryLog(
            transaction_code="INV-SEARCH-001",
            move_type=InventoryLog.TYPE_IN,
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_change=10,
            balance_after=10,
            operator_id=user.id,
            remark="平台搜索库存流水",
        )
        audit = AuditLog(user_id=user.id, module="search", action="target", details="平台搜索审计日志")
        db.session.add_all([log, audit])
        db.session.commit()

        items = SearchService().search("搜索", user=user)

        assert any(item["type"] == "partner" and item["label"] == "平台搜索供应商" for item in items)
        assert any(item["type"] == "inventory-log" and item["label"] == "INV-SEARCH-001" for item in items)
        assert any(item["type"] == "audit-log" and item["label"] == "search.target" for item in items)
        db.session.remove()
        db.drop_all()


def test_search_service_scopes_file_hits_to_owner_unless_admin():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        owner = make_user("owner@nexus.com")
        member = make_user("member@nexus.com")
        admin = make_user("admin-search@nexus.com", admin=True)
        attachment = Attachment(
            filename="restricted-search-file.txt",
            filepath="files/restricted-search-file.txt",
            mimetype="text/plain",
            size=4,
            uploader_id=owner.id,
        )
        db.session.add(attachment)
        db.session.commit()

        member_items = SearchService().search("restricted-search", user=member)
        admin_items = SearchService().search("restricted-search", user=admin)

        assert all(item["type"] != "file" or item["label"] != attachment.filename for item in member_items)
        assert any(item["type"] == "file" and item["label"] == attachment.filename for item in admin_items)
        db.session.remove()
        db.drop_all()


def test_search_service_scopes_audit_hits_to_owner_unless_admin():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        owner = make_user("audit-owner@nexus.com")
        member = make_user("audit-member@nexus.com")
        admin = make_user("audit-admin@nexus.com", admin=True)
        audit = AuditLog(user_id=owner.id, module="restricted", action="audit-search", details="audit search")
        db.session.add(audit)
        db.session.commit()

        member_items = SearchService().search("restricted", user=member)
        admin_items = SearchService().search("restricted", user=admin)

        assert all(item["type"] != "audit-log" or item["label"] != "restricted.audit-search" for item in member_items)
        assert any(item["type"] == "audit-log" and item["label"] == "restricted.audit-search" for item in admin_items)
        db.session.remove()
        db.drop_all()
