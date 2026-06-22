from app import create_app
from app.domains.procurement.application.purchase_workflow import BUSINESS_TYPE, PROCESS_KEY
from app.domains.workflow.application import workflow_service
from app.extensions import db
from app.models.events import DomainEvent
from app.models.auth import Permission, Role, User
from app.models.biz import Category, Partner, Product
from app.models.purchase import PurchaseOrder
from app.models.stock import Warehouse
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowLog, WorkflowTask


def seed_workflow_users():
    role = Role(name="WorkflowOps", is_admin=False)
    permission = Permission(name="stocktake.write", description="工作流处理")
    role.permissions.append(permission)
    db.session.add_all([role, permission])
    db.session.flush()
    applicant = User(username="applicant", email="applicant@nexus.com", role=role)
    applicant.password = "applicant123"
    approver = User(username="approver", email="approver@nexus.com", role=role)
    approver.password = "approver123"
    db.session.add_all([applicant, approver])
    db.session.commit()
    return applicant, approver


def seed_procurement_context():
    writer_role = Role(name="ProcurementWriter", is_admin=False)
    approver_role = Role(name="ProcurementApprover", is_admin=False)
    purchase_write = Permission(name="purchase.write", description="采购创建")
    purchase_approve = Permission(name="purchase.approve", description="采购审批")
    purchase_receive = Permission(name="purchase.receive", description="采购收货")
    writer_role.permissions.append(purchase_write)
    approver_role.permissions.append(purchase_approve)
    approver_role.permissions.append(purchase_receive)
    db.session.add_all([writer_role, approver_role, purchase_write, purchase_approve, purchase_receive])
    db.session.flush()

    applicant = User(username="buyer", email="buyer@nexus.com", role=writer_role)
    applicant.password = "buyer123"
    approver = User(username="poapprover", email="poapprover@nexus.com", role=approver_role)
    approver.password = "poapprover123"
    category = Category(name="采购测试分类")
    supplier = Partner(name="工作流供应商", type=Partner.TYPE_SUPPLIER)
    warehouse = Warehouse(name="工作流测试仓", location="WF-A1")
    db.session.add_all([applicant, approver, category, supplier, warehouse])
    db.session.flush()

    product = Product(
        sku="PO-WF-001",
        name="采购审批测试物料",
        price=100,
        cost=40,
        category_id=category.id,
        supplier_id=supplier.id,
    )
    db.session.add(product)
    db.session.commit()
    return applicant, approver, product, supplier, warehouse


def login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": email.split("@", 1)[0] + "123"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def create_purchase_order_via_api(client, headers, product, supplier, warehouse):
    response = client.post(
        "/api/v1/procurement/orders",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "warehouse_id": warehouse.id,
            "items": [{"product_id": product.id, "quantity": 3, "unit_price": 40}],
        },
    )
    assert response.status_code == 201
    return response.json["data"]["id"]


def assert_purchase_order_created_event(po, product, supplier, warehouse, applicant):
    event = DomainEvent.query.filter_by(event_type="PurchaseOrderCreated").one()
    assert event.status == DomainEvent.STATUS_PENDING
    assert event.aggregate_type == "PurchaseOrder"
    assert event.aggregate_id == str(po.id)
    assert event.created_by == str(applicant.id)
    assert event.payload["purchase_order_id"] == po.id
    assert event.payload["po_no"] == po.po_no
    assert event.payload["supplier_id"] == supplier.id
    assert event.payload["warehouse_id"] == warehouse.id
    assert event.payload["status"] == PurchaseOrder.STATUS_DRAFT
    assert event.payload["total_amount"] == 120.0
    assert event.payload["created_by"] == applicant.id
    assert event.payload["expected_date"] is None
    assert event.payload["remark"] is None
    assert event.payload["items"] == [
        {
            "item_id": po.items[0].id,
            "product_id": product.id,
            "quantity": 3,
            "received_qty": 0,
            "unit_price": 40.0,
        }
    ]


def test_workflow_service_starts_and_approves_single_node_flow():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver = seed_workflow_users()
        definition = workflow_service.create_definition(
            "purchase_order_approval",
            "采购审批",
            config={"default_assignee_id": approver.id},
        )
        instance, task = workflow_service.start(
            definition.process_key,
            "purchase_order",
            "PO-1",
            applicant,
            variables={"amount": 128800},
        )
        db.session.commit()

        assert instance.status == WorkflowInstance.STATUS_RUNNING
        assert task.status == WorkflowTask.STATUS_PENDING
        assert workflow_service.todo_tasks(approver)[0].id == task.id
        assert WorkflowLog.query.filter_by(instance_id=instance.id, action="started").count() == 1
        started_event = DomainEvent.query.filter_by(event_type="WorkflowStarted").one()
        assert started_event.status == DomainEvent.STATUS_PENDING
        assert started_event.aggregate_type == "WorkflowInstance"
        assert started_event.aggregate_id == str(instance.id)
        assert started_event.created_by == str(applicant.id)
        assert started_event.payload["workflow_instance_id"] == instance.id
        assert started_event.payload["workflow_task_id"] == task.id
        assert started_event.payload["definition_id"] == definition.id
        assert started_event.payload["process_key"] == definition.process_key
        assert started_event.payload["business_type"] == "purchase_order"
        assert started_event.payload["business_id"] == "PO-1"
        assert started_event.payload["applicant_id"] == applicant.id
        assert started_event.payload["assignee_id"] == approver.id
        assert started_event.payload["node_key"] == workflow_service.DEFAULT_NODE_KEY
        assert started_event.payload["task_title"] == "采购审批 #PO-1"
        assert started_event.payload["task_status"] == WorkflowTask.STATUS_PENDING
        assert started_event.payload["instance_status"] == WorkflowInstance.STATUS_RUNNING
        assert started_event.payload["current_node_key"] == workflow_service.DEFAULT_NODE_KEY
        assert started_event.payload["variables"] == {"amount": 128800}
        assert started_event.payload["started_at"]

        approved = workflow_service.approve_task(task.id, approver, comment="同意")
        db.session.commit()

        assert approved.status == WorkflowInstance.STATUS_APPROVED
        assert db.session.get(WorkflowTask, task.id).status == WorkflowTask.STATUS_APPROVED
        assert WorkflowLog.query.filter_by(instance_id=instance.id, action="approved").count() == 1
        event = DomainEvent.query.filter_by(event_type="WorkflowTaskApproved").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "WorkflowTask"
        assert event.aggregate_id == str(task.id)
        assert event.created_by == str(approver.id)
        assert event.payload["workflow_instance_id"] == instance.id
        assert event.payload["workflow_task_id"] == task.id
        assert event.payload["process_key"] == definition.process_key
        assert event.payload["business_type"] == "purchase_order"
        assert event.payload["business_id"] == "PO-1"
        assert event.payload["task_status"] == WorkflowTask.STATUS_APPROVED
        assert event.payload["instance_status"] == WorkflowInstance.STATUS_APPROVED
        assert event.payload["action_by"] == approver.id
        assert event.payload["comment"] == "同意"

        try:
            workflow_service.approve_task(task.id, approver, comment="重复审批")
        except ValueError as exc:
            assert "任务已处理" in str(exc)
        assert DomainEvent.query.filter_by(event_type="WorkflowTaskApproved").count() == 1
        assert DomainEvent.query.filter_by(event_type="WorkflowStarted").count() == 1

        db.session.remove()
        db.drop_all()


def test_workflow_api_definition_start_todo_transfer_and_reject():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver = seed_workflow_users()
        client = app.test_client()
        applicant_headers = login(client, applicant.email)

        definition = client.post(
            "/api/v1/workflows/definitions",
            headers=applicant_headers,
            json={
                "process_key": "purchase_order_approval",
                "name": "采购审批",
                "config": {"default_assignee_id": approver.id},
            },
        )
        assert definition.status_code == 201
        assert WorkflowDefinition.query.filter_by(process_key="purchase_order_approval").count() == 1

        started = client.post(
            "/api/v1/workflows/start",
            headers=applicant_headers,
            json={
                "process_key": "purchase_order_approval",
                "business_type": "purchase_order",
                "business_id": "42",
                "variables": {"amount": 64000},
                "title": "采购单 42 审批",
            },
        )
        assert started.status_code == 201
        task_id = started.json["data"]["task"]["id"]
        instance_id = started.json["data"]["instance"]["id"]

        approver_headers = login(client, approver.email)
        todo = client.get("/api/v1/workflows/tasks/todo", headers=approver_headers)
        assert todo.status_code == 200
        assert [item["id"] for item in todo.json["data"]["items"]] == [task_id]

        applicant_headers = login(client, applicant.email)
        forbidden = client.post(f"/api/v1/workflows/tasks/{task_id}/approve", headers=applicant_headers, json={})
        assert forbidden.status_code == 403

        approver_headers = login(client, approver.email)
        transfer = client.post(
            f"/api/v1/workflows/tasks/{task_id}/transfer",
            headers=approver_headers,
            json={"target_user_id": applicant.id, "comment": "转申请人复核"},
        )
        assert transfer.status_code == 200
        assert transfer.json["data"]["assignee_id"] == applicant.id

        applicant_headers = login(client, applicant.email)
        rejected = client.post(
            f"/api/v1/workflows/tasks/{task_id}/reject",
            headers=applicant_headers,
            json={"comment": "资料不足"},
        )
        assert rejected.status_code == 200
        assert rejected.json["data"]["status"] == WorkflowInstance.STATUS_REJECTED

        detail = client.get(f"/api/v1/workflows/instances/{instance_id}", headers=applicant_headers)
        assert detail.status_code == 200
        assert {log["action"] for log in detail.json["data"]["logs"]} >= {"started", "transferred", "rejected"}
        event = DomainEvent.query.filter_by(event_type="WorkflowTaskRejected").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "WorkflowTask"
        assert event.aggregate_id == str(task_id)
        assert event.payload["workflow_instance_id"] == instance_id
        assert event.payload["workflow_task_id"] == task_id
        assert event.payload["process_key"] == "purchase_order_approval"
        assert event.payload["business_type"] == "purchase_order"
        assert event.payload["business_id"] == "42"
        assert event.payload["task_status"] == WorkflowTask.STATUS_REJECTED
        assert event.payload["instance_status"] == WorkflowInstance.STATUS_REJECTED
        assert event.payload["comment"] == "资料不足"

        db.session.remove()
        db.drop_all()


def test_workflow_todo_stream_is_assignee_scoped_and_feeds_operations_queue():
    app = create_app("testing")
    app.config["WORKFLOW_TODO_STREAM_MAX_EVENTS"] = 1
    app.config["WORKFLOW_TODO_STREAM_INTERVAL_SECONDS"] = 0

    with app.app_context():
        db.create_all()
        applicant, approver = seed_workflow_users()
        definition = workflow_service.create_definition(
            "purchase_order_approval",
            "采购审批",
            config={"default_assignee_id": approver.id},
        )
        _instance, task = workflow_service.start(
            definition.process_key,
            "purchase_order",
            "42",
            applicant,
            variables={"amount": 64000},
            title="采购单 42 审批",
        )
        db.session.commit()

        client = app.test_client()
        applicant_headers = login(client, applicant.email)
        applicant_stream = client.get("/api/v1/workflows/tasks/todo/stream", headers=applicant_headers)
        assert applicant_stream.status_code == 200
        applicant_body = applicant_stream.get_data(as_text=True)
        assert "event: snapshot" in applicant_body
        assert '"total":0' in applicant_body
        assert "采购单 42 审批" not in applicant_body

        approver_headers = login(client, approver.email)
        approver_stream = client.get("/api/v1/workflows/tasks/todo/stream", headers=approver_headers)
        assert approver_stream.status_code == 200
        assert approver_stream.mimetype == "text/event-stream"
        approver_body = approver_stream.get_data(as_text=True)
        assert '"total":1' in approver_body
        assert "采购单 42 审批" in approver_body

        queue = client.get("/api/v1/operations/task-queue", headers=approver_headers)
        assert queue.status_code == 200
        workflow_items = [item for item in queue.json["data"]["items"] if item["source"] == "workflow"]
        assert workflow_items
        assert workflow_items[0]["id"] == f"workflow-{task.id}"
        assert workflow_items[0]["source_id"] == task.id
        assert workflow_items[0]["business_type"] == BUSINESS_TYPE
        assert workflow_items[0]["business_id"] == "42"
        assert workflow_items[0]["source_path"] == "/app/procurement/orders/42"
        assert workflow_items[0]["category"] == "approval"
        assert queue.json["data"]["summary"]["business_exceptions"] >= 1

        db.session.remove()
        db.drop_all()


def test_workflow_resources_are_registered():
    from app.domains.resources import register_resources
    from app.platform.crud.resource_registry import ResourceRegistry

    registry = ResourceRegistry()
    register_resources(registry, reset=True)

    assert {"workflow-definitions", "workflow-instances", "workflow-tasks", "workflow-logs"} <= set(registry)


def test_workflow_generic_resources_require_read_permission():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver = seed_workflow_users()
        no_access_role = Role(name="NoWorkflowAccess", is_admin=False)
        no_access = User(username="workflow-viewer", email="workflow-viewer@nexus.com", role=no_access_role)
        no_access.password = "workflow-viewer123"
        db.session.add_all([no_access_role, no_access])
        db.session.flush()
        definition = workflow_service.create_definition(
            "purchase_order_approval",
            "采购审批",
            config={"default_assignee_id": approver.id},
        )
        instance, task = workflow_service.start(
            definition.process_key,
            "purchase_order",
            "42",
            applicant,
            variables={"amount": 64000},
            title="采购单 42 审批",
        )
        db.session.commit()
        log = WorkflowLog.query.filter_by(instance_id=instance.id, action="started").one()

        client = app.test_client()
        no_access_headers = login(client, no_access.email)
        protected_resources = (
            ("workflow-definitions", definition.id),
            ("workflow-instances", instance.id),
            ("workflow-tasks", task.id),
            ("workflow-logs", log.id),
        )
        for resource, item_id in protected_resources:
            denied_list = client.get(f"/api/v1/{resource}?page=1&page_size=20", headers=no_access_headers)
            assert denied_list.status_code == 403
            assert denied_list.json["error"] == "permission_denied"
            denied_detail = client.get(f"/api/v1/{resource}/{item_id}", headers=no_access_headers)
            assert denied_detail.status_code == 403
            assert denied_detail.json["error"] == "permission_denied"

        applicant_headers = login(client, applicant.email)
        for resource, item_id in protected_resources:
            allowed_list = client.get(f"/api/v1/{resource}?page=1&page_size=20", headers=applicant_headers)
            assert allowed_list.status_code == 200
            assert item_id in {row["id"] for row in allowed_list.json["data"]["items"]}
            allowed_detail = client.get(f"/api/v1/{resource}/{item_id}", headers=applicant_headers)
            assert allowed_detail.status_code == 200
            assert allowed_detail.json["data"]["id"] == item_id

        db.session.remove()
        db.drop_all()


def test_procurement_submit_starts_workflow_from_legacy_url():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver, product, supplier, warehouse = seed_procurement_context()
        client = app.test_client()
        applicant_headers = login(client, applicant.email)
        po_id = create_purchase_order_via_api(client, applicant_headers, product, supplier, warehouse)
        po = db.session.get(PurchaseOrder, po_id)
        assert_purchase_order_created_event(po, product, supplier, warehouse, applicant)

        submitted = client.post(
            f"/api/v1/procurement/orders/{po_id}/submit",
            headers=applicant_headers,
            json={"assignee_id": approver.id},
        )
        assert submitted.status_code == 200

        po = db.session.get(PurchaseOrder, po_id)
        assert po.status == PurchaseOrder.STATUS_PENDING
        assert po.submitted_by == applicant.id
        definition = WorkflowDefinition.query.filter_by(process_key=PROCESS_KEY).one()
        instance = WorkflowInstance.query.filter_by(
            definition_id=definition.id,
            business_type=BUSINESS_TYPE,
            business_id=str(po_id),
        ).one()
        task = WorkflowTask.query.filter_by(instance_id=instance.id).one()
        assert instance.status == WorkflowInstance.STATUS_RUNNING
        assert instance.variables["po_no"] == po.po_no
        assert instance.variables["amount"] == 120.0
        assert task.status == WorkflowTask.STATUS_PENDING
        assert task.assignee_id == approver.id
        event = DomainEvent.query.filter_by(event_type="WorkflowStarted").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "WorkflowInstance"
        assert event.aggregate_id == str(instance.id)
        assert event.created_by == str(applicant.id)
        assert event.payload["workflow_instance_id"] == instance.id
        assert event.payload["workflow_task_id"] == task.id
        assert event.payload["process_key"] == PROCESS_KEY
        assert event.payload["business_type"] == BUSINESS_TYPE
        assert event.payload["business_id"] == str(po_id)
        assert event.payload["applicant_id"] == applicant.id
        assert event.payload["assignee_id"] == approver.id
        assert event.payload["task_status"] == WorkflowTask.STATUS_PENDING
        assert event.payload["instance_status"] == WorkflowInstance.STATUS_RUNNING
        assert event.payload["variables"]["po_no"] == po.po_no
        assert event.payload["variables"]["amount"] == 120.0

        duplicate = client.post(
            f"/api/v1/procurement/orders/{po_id}/submit",
            headers=applicant_headers,
            json={"assignee_id": approver.id},
        )
        assert duplicate.status_code == 400
        assert DomainEvent.query.filter_by(event_type="WorkflowStarted").count() == 1
        assert DomainEvent.query.filter_by(event_type="PurchaseOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_procurement_approve_legacy_url_completes_workflow_task():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver, product, supplier, warehouse = seed_procurement_context()
        client = app.test_client()
        applicant_headers = login(client, applicant.email)
        po_id = create_purchase_order_via_api(client, applicant_headers, product, supplier, warehouse)
        assert_purchase_order_created_event(db.session.get(PurchaseOrder, po_id), product, supplier, warehouse, applicant)

        submitted = client.post(
            f"/api/v1/procurement/orders/{po_id}/submit",
            headers=applicant_headers,
            json={"assignee_id": applicant.id},
        )
        assert submitted.status_code == 200
        task = WorkflowTask.query.one()
        assert task.assignee_id == applicant.id

        approver_headers = login(client, approver.email)
        approved = client.post(
            f"/api/v1/procurement/orders/{po_id}/approve",
            headers=approver_headers,
            json={"remark": "同意采购"},
        )
        assert approved.status_code == 200

        po = db.session.get(PurchaseOrder, po_id)
        db.session.refresh(task)
        assert po.status == PurchaseOrder.STATUS_APPROVED
        assert po.approved_by == approver.id
        assert task.status == WorkflowTask.STATUS_APPROVED
        assert task.action_by == approver.id
        assert task.instance.status == WorkflowInstance.STATUS_APPROVED
        assert WorkflowLog.query.filter_by(
            instance_id=task.instance_id,
            action="approved",
        ).count() == 1
        event = DomainEvent.query.filter_by(event_type="PurchaseOrderApproved").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "PurchaseOrder"
        assert event.aggregate_id == str(po_id)
        assert event.payload["purchase_order_id"] == po_id
        assert event.payload["po_no"] == po.po_no
        assert event.payload["supplier_id"] == supplier.id
        assert event.payload["warehouse_id"] == warehouse.id
        assert event.payload["status"] == PurchaseOrder.STATUS_APPROVED
        assert event.payload["total_amount"] == 120.0
        assert event.payload["approved_by"] == approver.id
        assert event.payload["remark"] == "同意采购"
        assert event.payload["items"] == [
            {
                "item_id": po.items[0].id,
                "product_id": product.id,
                "quantity": 3,
                "received_qty": 0,
                "unit_price": 40.0,
            }
        ]
        workflow_event = DomainEvent.query.filter_by(event_type="WorkflowTaskApproved").one()
        assert workflow_event.aggregate_type == "WorkflowTask"
        assert workflow_event.aggregate_id == str(task.id)
        assert workflow_event.created_by == str(approver.id)
        assert workflow_event.payload["business_type"] == BUSINESS_TYPE
        assert workflow_event.payload["business_id"] == str(po_id)
        assert workflow_event.payload["task_status"] == WorkflowTask.STATUS_APPROVED
        assert workflow_event.payload["instance_status"] == WorkflowInstance.STATUS_APPROVED
        assert workflow_event.payload["action_by"] == approver.id
        assert workflow_event.payload["comment"] == "同意采购"
        assert workflow_event.payload["legacy_purchase_action"] is True
        assert DomainEvent.query.filter_by(event_type="PurchaseOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_procurement_reject_legacy_url_completes_workflow_task():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver, product, supplier, warehouse = seed_procurement_context()
        client = app.test_client()
        applicant_headers = login(client, applicant.email)
        po_id = create_purchase_order_via_api(client, applicant_headers, product, supplier, warehouse)
        assert_purchase_order_created_event(db.session.get(PurchaseOrder, po_id), product, supplier, warehouse, applicant)

        submitted = client.post(
            f"/api/v1/procurement/orders/{po_id}/submit",
            headers=applicant_headers,
            json={"assignee_id": applicant.id},
        )
        assert submitted.status_code == 200

        approver_headers = login(client, approver.email)
        rejected = client.post(
            f"/api/v1/procurement/orders/{po_id}/reject",
            headers=approver_headers,
            json={"remark": "资料不足"},
        )
        assert rejected.status_code == 200

        po = db.session.get(PurchaseOrder, po_id)
        task = WorkflowTask.query.one()
        assert po.status == PurchaseOrder.STATUS_DRAFT
        assert po.approved_by == approver.id
        assert "[审批驳回] 资料不足" in po.remark
        assert task.status == WorkflowTask.STATUS_REJECTED
        assert task.instance.status == WorkflowInstance.STATUS_REJECTED
        assert DomainEvent.query.filter_by(event_type="PurchaseOrderApproved").count() == 0
        workflow_event = DomainEvent.query.filter_by(event_type="WorkflowTaskRejected").one()
        assert workflow_event.aggregate_type == "WorkflowTask"
        assert workflow_event.aggregate_id == str(task.id)
        assert workflow_event.created_by == str(approver.id)
        assert workflow_event.payload["business_type"] == BUSINESS_TYPE
        assert workflow_event.payload["business_id"] == str(po_id)
        assert workflow_event.payload["task_status"] == WorkflowTask.STATUS_REJECTED
        assert workflow_event.payload["instance_status"] == WorkflowInstance.STATUS_REJECTED
        assert workflow_event.payload["comment"] == "资料不足"
        assert workflow_event.payload["legacy_purchase_action"] is True
        assert DomainEvent.query.filter_by(event_type="PurchaseOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()


def test_procurement_approve_legacy_pending_order_without_workflow_still_works():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        _, approver, _, supplier, warehouse = seed_procurement_context()
        po = PurchaseOrder(
            po_no="PO-LEGACY-PENDING",
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            status=PurchaseOrder.STATUS_PENDING,
            total_amount=360,
        )
        db.session.add(po)
        db.session.commit()

        client = app.test_client()
        approver_headers = login(client, approver.email)
        approved = client.post(f"/api/v1/procurement/orders/{po.id}/approve", headers=approver_headers, json={})
        assert approved.status_code == 200

        assert db.session.get(PurchaseOrder, po.id).status == PurchaseOrder.STATUS_APPROVED
        assert WorkflowInstance.query.count() == 0
        assert WorkflowTask.query.count() == 0
        event = DomainEvent.query.filter_by(event_type="PurchaseOrderApproved").one()
        assert event.payload["purchase_order_id"] == po.id
        assert event.payload["approved_by"] == approver.id

        db.session.remove()
        db.drop_all()


def test_procurement_receive_legacy_url_writes_goods_received_event():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        applicant, approver, product, supplier, warehouse = seed_procurement_context()
        client = app.test_client()
        applicant_headers = login(client, applicant.email)
        po_id = create_purchase_order_via_api(client, applicant_headers, product, supplier, warehouse)
        assert_purchase_order_created_event(db.session.get(PurchaseOrder, po_id), product, supplier, warehouse, applicant)

        assert client.post(
            f"/api/v1/procurement/orders/{po_id}/submit",
            headers=applicant_headers,
            json={"assignee_id": applicant.id},
        ).status_code == 200
        approver_headers = login(client, approver.email)
        assert client.post(f"/api/v1/procurement/orders/{po_id}/approve", headers=approver_headers, json={}).status_code == 200

        po = db.session.get(PurchaseOrder, po_id)
        item = po.items[0]
        received = client.post(
            f"/api/v1/procurement/orders/{po_id}/receive",
            headers=approver_headers,
            json={"items": [{"item_id": item.id, "receive_qty": 2}]},
        )
        assert received.status_code == 200

        event = DomainEvent.query.filter_by(event_type="PurchaseGoodsReceived").one()
        assert event.status == DomainEvent.STATUS_PENDING
        assert event.aggregate_type == "PurchaseOrder"
        assert event.aggregate_id == str(po_id)
        assert event.payload["purchase_order_id"] == po_id
        assert event.payload["po_no"] == po.po_no
        assert event.payload["supplier_id"] == supplier.id
        assert event.payload["warehouse_id"] == warehouse.id
        assert event.payload["status"] == PurchaseOrder.STATUS_PARTIAL
        assert event.payload["received_by"] == approver.id
        assert event.payload["all_received"] is False
        assert event.payload["received_lines"] == [
            {
                "item_id": item.id,
                "product_id": product.id,
                "warehouse_id": warehouse.id,
                "receive_qty": 2,
                "received_qty": 2,
                "pending_qty": 1,
            }
        ]

        failed = client.post(
            f"/api/v1/procurement/orders/{po_id}/receive",
            headers=approver_headers,
            json={"items": [{"item_id": item.id, "receive_qty": 99}]},
        )
        assert failed.status_code == 400
        assert DomainEvent.query.filter_by(event_type="PurchaseGoodsReceived").count() == 1
        assert DomainEvent.query.filter_by(event_type="PurchaseOrderCreated").count() == 1

        db.session.remove()
        db.drop_all()
