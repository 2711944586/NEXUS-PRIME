"""AI action drafts and human confirmation workflows."""
from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models.ai import AiActionDraft
from app.models.notification import ReplenishmentSuggestion
from app.models.stock import Warehouse
from app.platform.crud.serializers import serialize_value
from app.platform.policy import policy
from app.services.audit_service import AuditService


def serialize_action_draft(draft: AiActionDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_type": draft.draft_type,
        "status": draft.status,
        "title": draft.title,
        "source_tool": draft.source_tool,
        "payload": draft.payload or {},
        "result_type": draft.result_type,
        "result_id": draft.result_id,
        "note": draft.note,
        "created_by": draft.created_by,
        "confirmed_by": draft.confirmed_by,
        "confirmed_at": serialize_value(draft.confirmed_at),
        "rejected_by": draft.rejected_by,
        "rejected_at": serialize_value(draft.rejected_at),
        "created_at": serialize_value(draft.created_at),
        "updated_at": serialize_value(draft.updated_at),
    }


class AiActionDraftService:
    REPLENISHMENT = "replenishment"

    @staticmethod
    def create_replenishment_draft(lines: list[dict[str, Any]], user, *, source_tool: str, params: dict[str, Any] | None = None) -> AiActionDraft:
        payload = {
            "type": AiActionDraftService.REPLENISHMENT,
            "status": AiActionDraft.STATUS_DRAFT,
            "requires_human_confirmation": True,
            "params": params or {},
            "lines": lines,
        }
        draft = AiActionDraft(
            draft_type=AiActionDraftService.REPLENISHMENT,
            status=AiActionDraft.STATUS_DRAFT,
            title=f"AI 补货建议草稿（{len(lines)} 项）",
            source_tool=source_tool,
            payload=payload,
            created_by=user.id if user else None,
        )
        db.session.add(draft)
        db.session.flush()
        AuditService.record(
            "ai",
            "draft_created",
            user,
            {
                "draft_id": draft.id,
                "draft_type": draft.draft_type,
                "source_tool": source_tool,
                "line_count": len(lines),
            },
        )
        return draft

    @staticmethod
    def get_draft(draft_id: int) -> AiActionDraft | None:
        return AiActionDraft.query.filter_by(id=draft_id, is_deleted=False).first()

    @staticmethod
    def assert_manageable(draft: AiActionDraft, user) -> None:
        if policy.is_admin(user):
            return
        if draft.created_by == getattr(user, "id", None):
            return
        raise PermissionError("权限不足")

    @staticmethod
    def confirm_replenishment_draft(draft_id: int, user, *, note: str | None = None) -> tuple[AiActionDraft, list[ReplenishmentSuggestion]]:
        draft = AiActionDraftService.get_draft(draft_id)
        if not draft:
            raise LookupError("AI 草稿不存在")
        AiActionDraftService.assert_manageable(draft, user)
        if draft.status != AiActionDraft.STATUS_DRAFT:
            raise ValueError("只有草稿状态可以确认")
        if draft.draft_type != AiActionDraftService.REPLENISHMENT:
            raise ValueError("不支持的 AI 草稿类型")

        lines = (draft.payload or {}).get("lines") or []
        suggestions = []
        for line in lines:
            product_id = int(line.get("product_id") or 0)
            warehouse_id = int(line.get("warehouse_id") or 0) or (Warehouse.query.first().id if Warehouse.query.first() else 0)
            suggested_qty = int(line.get("suggested_qty") or 0)
            if product_id <= 0 or warehouse_id <= 0 or suggested_qty <= 0:
                continue
            suggestion = ReplenishmentSuggestion.query.filter_by(
                product_id=product_id,
                warehouse_id=warehouse_id,
                status=ReplenishmentSuggestion.STATUS_PENDING,
                is_deleted=False,
            ).first()
            if not suggestion:
                suggestion = ReplenishmentSuggestion(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    status=ReplenishmentSuggestion.STATUS_PENDING,
                )
                db.session.add(suggestion)
            suggestion.supplier_id = line.get("supplier_id")
            suggestion.current_qty = int(line.get("current_qty") or 0)
            suggestion.suggested_qty = suggested_qty
            suggestion.safety_stock = line.get("min_stock")
            suggestions.append(suggestion)

        if not suggestions:
            raise ValueError("AI 草稿没有可确认的补货明细")
        db.session.flush()
        result_ids = [str(item.id) for item in suggestions]
        draft.mark_confirmed(
            user,
            result_type="replenishment_suggestion",
            result_id=",".join(result_ids),
            note=note,
        )
        AuditService.record(
            "ai",
            "draft_confirmed",
            user,
            {
                "draft_id": draft.id,
                "draft_type": draft.draft_type,
                "result_type": draft.result_type,
                "result_ids": result_ids,
                "line_count": len(suggestions),
            },
        )
        return draft, suggestions

    @staticmethod
    def reject_draft(draft_id: int, user, *, note: str | None = None) -> AiActionDraft:
        draft = AiActionDraftService.get_draft(draft_id)
        if not draft:
            raise LookupError("AI 草稿不存在")
        AiActionDraftService.assert_manageable(draft, user)
        if draft.status != AiActionDraft.STATUS_DRAFT:
            raise ValueError("只有草稿状态可以拒绝")
        draft.mark_rejected(user, note=note)
        AuditService.record(
            "ai",
            "draft_rejected",
            user,
            {
                "draft_id": draft.id,
                "draft_type": draft.draft_type,
                "note": note,
            },
        )
        return draft
