import os

from flask import current_app

from app.extensions import db
from app.domains.ai.infrastructure.vector_repository import ChunkInput, DocumentChunkRepository
from app.domains.inventory.application import InventoryApplicationService
from app.domains.reporting.application import project_reporting_event
from app.models.ai import DocumentChunk
from app.models.content import Attachment
from app.models.biz import Product
from app.models.finance import PaymentRecord, Receivable
from app.models.jobs import BackgroundJob
from app.models.notification import Notification, ReplenishmentSuggestion
from app.models.stock import Stock, StockMovement
from app.models.workflow import WorkflowInstance
from app.services.finance_service import FinanceService
from app.platform.events.registry import EventHandlerRegistry


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _limited_notification_title(prefix, label):
    return f"{prefix} - {label or '工作流任务'}"[:128]


def _find_notification(related_type, related_id, title):
    query = Notification.query.filter_by(
        related_type=related_type,
        title=title,
        is_deleted=False,
    )
    if related_id is not None:
        query = query.filter(Notification.related_id == related_id)
    return query.first()


def _workflow_business_text(payload):
    business_type = payload.get("business_type") or "业务对象"
    business_id = payload.get("business_id") or "待定"
    process_key = payload.get("process_key") or "workflow"
    return f"{process_key} / {business_type} #{business_id}"


def _workflow_applicant_id(payload):
    applicant_id = _safe_int(payload.get("applicant_id"))
    if applicant_id:
        return applicant_id
    instance_id = _safe_int(payload.get("workflow_instance_id"))
    if not instance_id:
        return None
    instance = db.session.get(WorkflowInstance, instance_id)
    return instance.applicant_id if instance else None


def _is_indexable_text_attachment(filename, mimetype):
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in {".txt", ".csv", ".md", ".markdown", ".json", ".log"}:
        return True
    normalized = (mimetype or "").split(";", 1)[0].strip().lower()
    return normalized.startswith("text/") or normalized in {"application/json", "application/x-ndjson"}


def _decode_text_payload(data):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _chunk_text(content, *, chunk_size=1600, overlap=160):
    text = "\n".join(line.rstrip() for line in (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n\n", start, end), text.rfind("\n", start, end), text.rfind(" ", start, end))
            if split_at > start + (chunk_size // 2):
                end = split_at
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _read_local_attachment_text(object_key):
    if not object_key or str(object_key).startswith(("http://", "https://", "cloudinary:")):
        return None

    from app.platform.storage.local_storage import resolve_local_object, safe_local_path

    resolved = resolve_local_object(object_key)
    if not resolved:
        return None
    root, relative_path = resolved
    target = safe_local_path(root, relative_path)
    max_bytes = int(current_app.config.get("AI_DOCUMENT_INDEX_MAX_BYTES", 2 * 1024 * 1024))
    with open(target, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if b"\x00" in data[:4096]:
        return None
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    text, encoding = _decode_text_payload(data)
    return text, {"truncated": truncated, "encoding": encoding}


def index_uploaded_file_chunks(event):
    payload = event.payload or {}
    attachment_id = _safe_int(payload.get("attachment_id")) or _safe_int(event.aggregate_id)
    if not attachment_id:
        return []

    attachment = db.session.get(Attachment, attachment_id)
    if not attachment or attachment.is_deleted:
        return []

    filename = payload.get("filename") or attachment.filename
    mimetype = payload.get("mimetype") or attachment.mimetype
    if not _is_indexable_text_attachment(filename, mimetype):
        return []

    storage_provider = payload.get("storage_provider") or "local"
    if storage_provider != "local":
        return []

    loaded = _read_local_attachment_text(payload.get("filepath") or attachment.filepath)
    if not loaded:
        return []
    text, read_metadata = loaded
    chunks = _chunk_text(
        text,
        chunk_size=int(current_app.config.get("AI_DOCUMENT_CHUNK_SIZE", 1600)),
        overlap=int(current_app.config.get("AI_DOCUMENT_CHUNK_OVERLAP", 160)),
    )
    if not chunks:
        return []

    tenant_id = event.tenant_id or payload.get("tenant_id") or "default"
    repository = DocumentChunkRepository()
    indexed = []
    for index, chunk in enumerate(chunks):
        indexed.append(
            repository.upsert_chunk(
                ChunkInput(
                    source_type="attachment",
                    source_id=str(attachment.id),
                    chunk_index=index,
                    title=attachment.filename,
                    content=chunk,
                    tenant_id=tenant_id,
                    metadata={
                        "event_id": event.event_id,
                        "filename": attachment.filename,
                        "filepath": attachment.filepath,
                        "mimetype": attachment.mimetype,
                        "size": int(attachment.size or 0),
                        "storage_provider": storage_provider,
                        "uploader_id": attachment.uploader_id,
                        "chunk_count": len(chunks),
                        "embedding_status": "pending",
                        **read_metadata,
                    },
                )
            )
        )
    if indexed:
        if current_app.config.get("CELERY_TASK_ALWAYS_EAGER", False):
            from app.platform.jobs.ai import embed_document_chunks

            embed_document_chunks(source_type="attachment", source_id=str(attachment.id), limit=len(indexed))
        else:
            from app.platform.jobs.tasks.ai import embed_document_chunks_task

            embed_document_chunks_task.apply_async(
                kwargs={"source_type": "attachment", "source_id": str(attachment.id), "limit": len(indexed)},
                queue="ai",
            )
    return indexed


def mark_file_chunks_deleted(event):
    payload = event.payload or {}
    attachment_id = _safe_int(payload.get("attachment_id")) or _safe_int(event.aggregate_id)
    if not attachment_id:
        return []

    chunks = (
        DocumentChunk.query
        .filter(
            DocumentChunk.source_type == "attachment",
            DocumentChunk.source_id == str(attachment_id),
            DocumentChunk.is_deleted == False,
        )
        .all()
    )
    for chunk in chunks:
        metadata = dict(chunk.metadata_json or {})
        metadata.update(
            {
                "deleted_by": payload.get("deleted_by") or event.created_by,
                "deleted_event_id": event.event_id,
                "source_deleted": True,
            }
        )
        chunk.metadata_json = metadata
        chunk.is_deleted = True
        db.session.add(chunk)
    return chunks


def sales_order_reservation_items(payload):
    items = []
    for line in payload.get("items") or []:
        product_id = line.get("product_id")
        remaining = int(line.get("quantity") or 0)
        if not product_id or remaining <= 0:
            continue
        stocks = (
            Stock.query
            .filter(Stock.product_id == product_id, Stock.is_deleted == False, Stock.quantity > 0)
            .order_by(Stock.quantity.desc(), Stock.id.asc())
            .all()
        )
        available = sum(int(stock.quantity or 0) for stock in stocks)
        if available < remaining:
            raise ValueError(f"商品 {product_id} 库存不足，无法预留")
        for stock in stocks:
            if remaining <= 0:
                break
            quantity = min(int(stock.quantity or 0), remaining)
            if quantity <= 0:
                continue
            items.append({"product_id": int(product_id), "warehouse_id": stock.warehouse_id, "quantity": quantity})
            remaining -= quantity
    return items


def reserve_sales_order_stock(event):
    payload = event.payload or {}
    order_id = payload.get("order_id")
    if not order_id:
        return []
    items = sales_order_reservation_items(payload)
    if not items:
        return []
    return InventoryApplicationService().reserve_stock(
        "sales_order",
        order_id,
        items,
        f"sales-order:{order_id}:confirmed",
        created_by=payload.get("seller_id") or event.created_by,
        reason=f"销售订单确认预留 - {payload.get('order_no') or order_id}",
        write_legacy_log=False,
    )


def sales_order_releasable_reservation_items(order_id):
    if not order_id:
        return []

    movements = (
        StockMovement.query
        .filter(
            StockMovement.source_type == "sales_order",
            StockMovement.source_id == str(order_id),
            StockMovement.direction.in_(
                [
                    StockMovement.DIRECTION_RESERVE,
                    StockMovement.DIRECTION_RELEASE,
                    StockMovement.DIRECTION_DEDUCT,
                ]
            ),
            StockMovement.is_deleted == False,
        )
        .order_by(StockMovement.id.asc())
        .all()
    )
    net_by_stock = {}
    for movement in movements:
        key = (movement.product_id, movement.warehouse_id)
        net_by_stock.setdefault(key, 0)
        if movement.direction == StockMovement.DIRECTION_RESERVE:
            net_by_stock[key] += int(movement.quantity or 0)
        elif movement.direction in (StockMovement.DIRECTION_RELEASE, StockMovement.DIRECTION_DEDUCT):
            net_by_stock[key] -= int(movement.quantity or 0)

    return [
        {"product_id": product_id, "warehouse_id": warehouse_id, "quantity": quantity}
        for (product_id, warehouse_id), quantity in net_by_stock.items()
        if quantity > 0
    ]


def release_sales_order_stock(event):
    payload = event.payload or {}
    order_id = payload.get("order_id") or event.aggregate_id
    if not order_id:
        return []

    items = sales_order_releasable_reservation_items(order_id)
    if not items:
        return []

    return InventoryApplicationService().release_stock(
        "sales_order",
        order_id,
        items,
        f"sales-order:{order_id}:cancelled",
        created_by=payload.get("seller_id") or event.created_by,
        reason=f"销售订单取消释放预留 - {payload.get('order_no') or order_id}",
        write_legacy_log=False,
    )


def notify_sales_order_confirmed(event):
    payload = event.payload or {}
    seller_id = payload.get("seller_id") or event.created_by
    order_id = payload.get("order_id")
    order_no = payload.get("order_no") or order_id
    if not seller_id or not order_id:
        return None
    existing = Notification.query.filter_by(
        related_type="order",
        related_id=order_id,
        title=f"销售订单已确认 - {order_no}",
        is_deleted=False,
    ).first()
    if existing:
        return existing
    notification = Notification(
        user_id=int(seller_id),
        title=f"销售订单已确认 - {order_no}",
        content=f"订单 {order_no} 已确认，后续可进入履约、出库与应收协同。",
        type=Notification.TYPE_SUCCESS,
        category=Notification.CATEGORY_ORDER,
        related_type="order",
        related_id=int(order_id),
    )
    db.session.add(notification)
    return notification


def notify_sales_order_cancelled(event):
    payload = event.payload or {}
    seller_id = payload.get("seller_id") or event.created_by
    order_id = payload.get("order_id") or event.aggregate_id
    order_no = payload.get("order_no") or order_id
    if not seller_id or not order_id:
        return None

    title = f"销售订单已取消 - {order_no}"
    existing = Notification.query.filter_by(
        related_type="order",
        related_id=_safe_int(order_id),
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    notification = Notification(
        user_id=int(seller_id),
        title=title,
        content=f"订单 {order_no} 已取消，系统将释放仍未出库的预留库存并保留事件审计记录。",
        type=Notification.TYPE_WARNING,
        category=Notification.CATEGORY_ORDER,
        related_type="order",
        related_id=_safe_int(order_id),
    )
    db.session.add(notification)
    return notification


def create_sales_order_receivable(event):
    payload = event.payload or {}
    order_id = payload.get("order_id")
    if not order_id:
        return None

    existing = Receivable.query.filter_by(order_id=order_id, is_deleted=False).first()
    if existing:
        return existing

    ok, result = FinanceService.create_receivable(order_id)
    if ok:
        return result

    existing = Receivable.query.filter_by(order_id=order_id, is_deleted=False).first()
    if existing:
        return existing
    raise ValueError(result)


def _finance_notification_user_id(payload, event, *, receivable_id=None, payment_id=None):
    user_id = _safe_int(event.created_by) or _safe_int(payload.get("created_by")) or _safe_int(payload.get("operator_id"))
    if user_id:
        return user_id

    if payment_id:
        payment = db.session.get(PaymentRecord, payment_id)
        if payment and payment.operator_id:
            return payment.operator_id
        if payment and payment.receivable:
            receivable_id = payment.receivable_id

    if receivable_id:
        receivable = db.session.get(Receivable, receivable_id)
        order = receivable.order if receivable else None
        if order and order.seller_id:
            return order.seller_id
    return None


def notify_receivable_created(event):
    payload = event.payload or {}
    receivable_id = _safe_int(payload.get("receivable_id")) or _safe_int(event.aggregate_id)
    if not receivable_id:
        return None

    user_id = _finance_notification_user_id(payload, event, receivable_id=receivable_id)
    if not user_id:
        return None

    receivable_no = payload.get("receivable_no") or receivable_id
    order_no = payload.get("order_no") or payload.get("order_id") or "未关联订单"
    total_amount = float(payload.get("total_amount") or 0)
    due_date = payload.get("due_date") or "未设置"
    title = f"应收账款已生成 - {receivable_no}"
    existing = Notification.query.filter_by(
        related_type="receivable",
        related_id=receivable_id,
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    notification = Notification(
        user_id=int(user_id),
        title=title,
        content=(
            f"订单 {order_no} 已生成应收账款 {receivable_no}，金额 {total_amount:.2f}，"
            f"到期日 {due_date}。请跟进客户回款计划。"
        ),
        type=Notification.TYPE_INFO,
        category=Notification.CATEGORY_ORDER,
        related_type="receivable",
        related_id=receivable_id,
    )
    db.session.add(notification)
    return notification


def notify_payment_recorded(event):
    payload = event.payload or {}
    payment_id = _safe_int(payload.get("payment_id")) or _safe_int(event.aggregate_id)
    if not payment_id:
        return None

    user_id = _finance_notification_user_id(payload, event, payment_id=payment_id)
    if not user_id:
        return None

    payment_no = payload.get("payment_no") or payment_id
    receivable_no = payload.get("receivable_no") or payload.get("receivable_id") or "应收账款"
    amount = float(payload.get("amount") or 0)
    unpaid_amount = float(payload.get("unpaid_amount") or 0)
    receivable_status = payload.get("receivable_status") or "unknown"
    title = f"收款已记录 - {payment_no}"
    existing = Notification.query.filter_by(
        related_type="payment",
        related_id=payment_id,
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    notification = Notification(
        user_id=int(user_id),
        title=title,
        content=(
            f"收款 {payment_no} 已记录，关联 {receivable_no}，本次收款 {amount:.2f}，"
            f"剩余未收 {unpaid_amount:.2f}，应收状态 {receivable_status}。"
        ),
        type=Notification.TYPE_SUCCESS,
        category=Notification.CATEGORY_ORDER,
        related_type="payment",
        related_id=payment_id,
    )
    db.session.add(notification)
    return notification


def notify_inventory_movement(event):
    payload = event.payload or {}
    movement_id = _safe_int(payload.get("stock_movement_id")) or _safe_int(event.aggregate_id)
    if not movement_id:
        return None

    user_id = _safe_int(payload.get("created_by")) or _safe_int(event.created_by)
    if not user_id:
        movement = db.session.get(StockMovement, movement_id)
        if movement and movement.created_by:
            user_id = movement.created_by
    if not user_id:
        return None

    labels = {
        "InventoryReserved": ("库存已预留", Notification.TYPE_INFO),
        "InventoryReleased": ("库存预留已释放", Notification.TYPE_WARNING),
        "InventoryDeducted": ("库存已扣减", Notification.TYPE_SUCCESS),
    }
    label, notification_type = labels.get(event.event_type, ("库存已变动", Notification.TYPE_INFO))
    product_id = payload.get("product_id") or "未知商品"
    warehouse_id = payload.get("warehouse_id") or "未知仓库"
    quantity = int(payload.get("quantity") or 0)
    source_type = payload.get("source_type") or event.aggregate_type or "source"
    source_id = payload.get("source_id") or event.aggregate_id
    title = f"{label} - {source_type} #{source_id}"
    existing = Notification.query.filter_by(
        related_type="stock_movement",
        related_id=movement_id,
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    notification = Notification(
        user_id=int(user_id),
        title=title,
        content=(
            f"{label}：商品 {product_id}，仓库 {warehouse_id}，数量 {quantity}。\n"
            f"来源：{source_type} #{source_id}\n"
            f"可用库存：{payload.get('before_available_qty')} -> {payload.get('after_available_qty')}\n"
            f"锁定库存：{payload.get('before_locked_qty')} -> {payload.get('after_locked_qty')}\n"
            f"原因：{payload.get('reason') or '未填写'}"
        ),
        type=notification_type,
        category=Notification.CATEGORY_STOCK,
        related_type="stock_movement",
        related_id=movement_id,
    )
    db.session.add(notification)
    return notification


def receive_purchase_goods_stock(event):
    payload = event.payload or {}
    purchase_order_id = payload.get("purchase_order_id") or event.aggregate_id
    if not purchase_order_id:
        return []

    movements = []
    po_no = payload.get("po_no") or purchase_order_id
    received_by = payload.get("received_by") or event.created_by
    default_warehouse_id = payload.get("warehouse_id")

    for index, line in enumerate(payload.get("received_lines") or []):
        product_id = line.get("product_id")
        warehouse_id = line.get("warehouse_id") or default_warehouse_id
        quantity = int(line.get("receive_qty") or line.get("quantity") or 0)
        if not product_id or not warehouse_id or quantity <= 0:
            continue

        item_id = line.get("item_id") or f"line-{index}"
        received_qty = line.get("received_qty") or quantity
        idempotency_key = f"purchase-order:{purchase_order_id}:item:{item_id}:received:{received_qty}"
        movements.extend(
            InventoryApplicationService().receive_stock(
                "purchase_order",
                purchase_order_id,
                [{"product_id": product_id, "warehouse_id": warehouse_id, "quantity": quantity}],
                idempotency_key,
                created_by=received_by,
                reason=f"采购入库 - {po_no}",
                legacy_transaction_code=po_no,
            )
        )
    return movements


def notify_purchase_order_created(event):
    payload = event.payload or {}
    purchase_order_id = _safe_int(payload.get("purchase_order_id")) or _safe_int(event.aggregate_id)
    created_by = _safe_int(payload.get("created_by")) or _safe_int(event.created_by)
    if not purchase_order_id or not created_by:
        return None

    po_no = payload.get("po_no") or purchase_order_id
    title = f"采购单已创建 - {po_no}"
    existing = Notification.query.filter_by(
        related_type="purchase_order",
        related_id=purchase_order_id,
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    item_count = len(payload.get("items") or [])
    total_amount = float(payload.get("total_amount") or 0)
    warehouse_id = payload.get("warehouse_id") or "待定"
    expected_date = payload.get("expected_date") or "未维护"
    notification = Notification(
        user_id=int(created_by),
        title=title,
        content=(
            f"采购单 {po_no} 已创建为草稿，金额 {total_amount:.2f}，共 {item_count} 条明细。\n"
            f"目标仓库：{warehouse_id}\n"
            f"预计到货：{expected_date}\n"
            f"下一步：提交审批并确认供应商、预算和到货窗口。"
        ),
        type=Notification.TYPE_INFO,
        category=Notification.CATEGORY_APPROVAL,
        related_type="purchase_order",
        related_id=purchase_order_id,
    )
    db.session.add(notification)
    return notification


def notify_purchase_order_approved(event):
    payload = event.payload or {}
    purchase_order_id = payload.get("purchase_order_id") or event.aggregate_id
    approved_by = payload.get("approved_by") or event.created_by
    if not purchase_order_id or not approved_by:
        return None

    po_no = payload.get("po_no") or purchase_order_id
    title = f"采购单已批准 - {po_no}"
    existing = Notification.query.filter_by(
        related_type="purchase_order",
        related_id=_safe_int(purchase_order_id),
        title=title,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    item_count = len(payload.get("items") or [])
    total_amount = float(payload.get("total_amount") or 0)
    warehouse_id = payload.get("warehouse_id")
    notification = Notification(
        user_id=int(approved_by),
        title=title,
        content=(
            f"采购单 {po_no} 已审批通过，金额 {total_amount:.2f}，"
            f"共 {item_count} 条明细。请协调供应商确认交期、仓库 {warehouse_id or '待定'} 收货和质检窗口。"
        ),
        type=Notification.TYPE_SUCCESS,
        category=Notification.CATEGORY_APPROVAL,
        related_type="purchase_order",
        related_id=_safe_int(purchase_order_id),
    )
    db.session.add(notification)
    return notification


def create_replenishment_suggestion_for_stock_alert(event):
    payload = event.payload or {}
    product_id = _safe_int(payload.get("product_id"))
    if not product_id:
        return None

    existing = ReplenishmentSuggestion.query.filter_by(
        product_id=product_id,
        status=ReplenishmentSuggestion.STATUS_PENDING,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    product = db.session.get(Product, product_id)
    if not product or not product.supplier_id:
        return None

    suggestion = ReplenishmentSuggestion(
        product_id=product.id,
        supplier_id=product.supplier_id,
        current_qty=int(payload.get("current_qty") or 0),
        suggested_qty=int(payload.get("suggested_qty") or product.min_stock or 10),
        safety_stock=int(payload.get("min_qty") or product.min_stock or 10),
        status=ReplenishmentSuggestion.STATUS_PENDING,
    )
    db.session.add(suggestion)
    return suggestion


def dispatch_report_requested(event):
    payload = event.payload or {}
    job_id = payload.get("job_id") or event.aggregate_id
    if not job_id:
        return None

    job = BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()
    if not job or job.job_type != "report.generate":
        return None
    if job.status == BackgroundJob.STATUS_SUCCESS:
        return job
    if job.status == BackgroundJob.STATUS_RUNNING:
        return job
    if job.status == BackgroundJob.STATUS_PENDING and job.celery_task_id:
        return job

    report_type = payload.get("report_type") or (job.payload or {}).get("report_type")
    params = payload.get("params") if "params" in payload else (job.payload or {}).get("params")
    user_id = payload.get("requested_by") or job.created_by
    if not report_type:
        return job

    from flask import current_app

    if current_app.config.get("CELERY_TASK_ALWAYS_EAGER", False):
        from app.platform.jobs.reports import generate_report_job

        generate_report_job(job.job_id, report_type, params=params, user_id=user_id, celery_task_id=f"event-{event.event_id}")
        return BackgroundJob.query.filter_by(job_id=job_id, is_deleted=False).first()

    from app.platform.jobs.tasks.reports import generate_report_task

    async_result = generate_report_task.apply_async(
        kwargs={"job_id": job.job_id, "report_type": report_type, "params": params, "user_id": user_id},
        queue=job.queue or payload.get("queue") or "reports",
    )
    job.celery_task_id = async_result.id
    db.session.add(job)
    return job


def notify_quality_inspection_result(event):
    payload = event.payload or {}
    is_failed = event.event_type == "QualityInspectionFailed"
    result_label = "未通过" if is_failed else "通过"
    title = (payload.get("title") or event.aggregate_id or "质量检验任务").strip()
    notification_title = f"质量检验{result_label} - {title}"
    related_id = _safe_int(payload.get("notification_id")) or _safe_int(event.aggregate_id)

    user_id = _safe_int(event.created_by)
    if not user_id and related_id:
        source_notification = db.session.get(Notification, related_id)
        if source_notification:
            user_id = source_notification.user_id
    if not user_id:
        return None

    existing_query = Notification.query.filter_by(
        related_type="quality_inspection_result",
        title=notification_title,
        is_deleted=False,
    )
    if related_id is not None:
        existing_query = existing_query.filter(Notification.related_id == related_id)
    existing = existing_query.first()
    if existing:
        return existing

    owner = payload.get("owner") or "质量工程师"
    priority = payload.get("priority") or ("P0" if is_failed else "P2")
    sla = payload.get("sla") or "1d"
    evidence = payload.get("evidence") or "质量检验结果已同步。"
    action = payload.get("action") or ("请冻结批次并发起整改闭环。" if is_failed else "请推进放行、入库或归档。")
    decision = payload.get("decision") or ("隔离复核" if is_failed else "放行")
    path = payload.get("path") or "/app/quality"
    queue_item_id = payload.get("queue_item_id") or event.aggregate_id

    notification = Notification(
        user_id=user_id,
        title=notification_title,
        content=(
            f"[{owner}/{priority}/{sla}] 质检结果：{result_label}\n"
            f"对象：{queue_item_id}\n"
            f"依据：{evidence}\n"
            f"使用决策：{decision}\n"
            f"处理动作：{action}\n"
            f"来源：{path}"
        ),
        type=Notification.TYPE_ALERT if is_failed else Notification.TYPE_SUCCESS,
        category=Notification.CATEGORY_APPROVAL,
        related_type="quality_inspection_result",
        related_id=related_id,
    )
    db.session.add(notification)
    return notification


def notify_workflow_started(event):
    payload = event.payload or {}
    assignee_id = _safe_int(payload.get("assignee_id"))
    task_id = _safe_int(payload.get("workflow_task_id"))
    instance_id = _safe_int(payload.get("workflow_instance_id"))
    if not assignee_id or not (task_id or instance_id):
        return None

    related_type = "workflow_task" if task_id else "workflow_instance"
    related_id = task_id or instance_id
    task_title = payload.get("task_title") or _workflow_business_text(payload)
    title = _limited_notification_title("新的工作流待办", task_title)
    existing = _find_notification(related_type, related_id, title)
    if existing:
        return existing

    notification = Notification(
        user_id=assignee_id,
        title=title,
        content=(
            f"待办任务已分配给你。\n"
            f"流程：{_workflow_business_text(payload)}\n"
            f"节点：{payload.get('node_key') or 'approval'}\n"
            f"状态：{payload.get('task_status') or 'pending'}"
        ),
        type=Notification.TYPE_INFO,
        category=Notification.CATEGORY_APPROVAL,
        related_type=related_type,
        related_id=related_id,
    )
    db.session.add(notification)
    return notification


def notify_workflow_task_outcome(event):
    payload = event.payload or {}
    task_id = _safe_int(payload.get("workflow_task_id")) or _safe_int(event.aggregate_id)
    if not task_id:
        return None

    applicant_id = _workflow_applicant_id(payload)
    user_id = applicant_id or _safe_int(payload.get("assignee_id")) or _safe_int(payload.get("action_by")) or _safe_int(event.created_by)
    if not user_id:
        return None

    is_rejected = event.event_type == "WorkflowTaskRejected"
    result_label = "已驳回" if is_rejected else "已批准"
    task_title = payload.get("task_title") or _workflow_business_text(payload)
    title = _limited_notification_title(f"工作流{result_label}", task_title)
    existing = _find_notification("workflow_task", task_id, title)
    if existing:
        return existing

    comment = payload.get("comment") or "无"
    action_by = payload.get("action_by") or event.created_by or "未知"
    notification = Notification(
        user_id=int(user_id),
        title=title,
        content=(
            f"流程任务{result_label}。\n"
            f"流程：{_workflow_business_text(payload)}\n"
            f"处理人：{action_by}\n"
            f"意见：{comment}\n"
            f"实例状态：{payload.get('instance_status') or 'unknown'}"
        ),
        type=Notification.TYPE_ALERT if is_rejected else Notification.TYPE_SUCCESS,
        category=Notification.CATEGORY_APPROVAL,
        related_type="workflow_task",
        related_id=task_id,
    )
    db.session.add(notification)
    return notification


DEFAULT_EVENT_HANDLERS = {
    "SalesOrderCreated": [project_reporting_event],
    "SalesOrderConfirmed": [reserve_sales_order_stock, create_sales_order_receivable, notify_sales_order_confirmed, project_reporting_event],
    "SalesOrderCancelled": [release_sales_order_stock, notify_sales_order_cancelled, project_reporting_event],
    "PurchaseOrderCreated": [notify_purchase_order_created, project_reporting_event],
    "PurchaseOrderApproved": [notify_purchase_order_approved, project_reporting_event],
    "PurchaseGoodsReceived": [receive_purchase_goods_stock, project_reporting_event],
    "StockBelowSafetyLine": [create_replenishment_suggestion_for_stock_alert, project_reporting_event],
    "ReportRequested": [dispatch_report_requested, project_reporting_event],
    "QualityInspectionPassed": [notify_quality_inspection_result, project_reporting_event],
    "QualityInspectionFailed": [notify_quality_inspection_result, project_reporting_event],
    "ReceivableCreated": [notify_receivable_created, project_reporting_event],
    "PaymentRecorded": [notify_payment_recorded, project_reporting_event],
    "InventoryReserved": [notify_inventory_movement, project_reporting_event],
    "InventoryReleased": [notify_inventory_movement, project_reporting_event],
    "InventoryDeducted": [notify_inventory_movement, project_reporting_event],
    "WorkflowStarted": [notify_workflow_started, project_reporting_event],
    "WorkflowTaskApproved": [notify_workflow_task_outcome, project_reporting_event],
    "WorkflowTaskRejected": [notify_workflow_task_outcome, project_reporting_event],
    "FileUploaded": [index_uploaded_file_chunks, project_reporting_event],
    "FileDeleted": [mark_file_chunks_deleted, project_reporting_event],
}


default_handler_registry = EventHandlerRegistry(DEFAULT_EVENT_HANDLERS)


def register_default_handlers(bus):
    return default_handler_registry.apply_to_bus(bus)
