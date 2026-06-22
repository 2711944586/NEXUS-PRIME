from __future__ import annotations

import re
from dataclasses import dataclass

from app.extensions import db
from app.domains.ai.infrastructure.vector_repository import DocumentChunkRepository
from app.models.ai import DocumentChunk
from app.models.content import Attachment
from app.platform.policy import policy


@dataclass(frozen=True)
class RagSource:
    chunk_id: int
    source_type: str
    source_id: str
    title: str | None
    snippet: str
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "snippet": self.snippet,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RagResult:
    sources: list[RagSource]

    @property
    def has_sources(self) -> bool:
        return bool(self.sources)

    def to_dicts(self) -> list[dict]:
        return [source.to_dict() for source in self.sources]


class RagAnswerService:
    def __init__(self, repository: DocumentChunkRepository | None = None):
        self.repository = repository or DocumentChunkRepository()

    def retrieve(self, question: str, user, *, tenant_id: str = "default", limit: int = 4) -> RagResult:
        if not (question or "").strip() or not user:
            return RagResult([])

        candidates = self._candidate_chunks(question, tenant_id=tenant_id, limit=max(limit * 4, 12))
        sources: list[RagSource] = []
        for chunk in candidates:
            if not self._can_read_chunk(user, chunk):
                continue
            sources.append(self._source_from_chunk(chunk))
            if len(sources) >= limit:
                break
        return RagResult(sources)

    def context_message(self, result: RagResult) -> str | None:
        if not result.has_sources:
            return None
        lines = [
            "以下是用户有权限访问的企业文档片段。回答文档问题时只能基于这些片段，不要编造未出现的内容。",
        ]
        for index, source in enumerate(result.sources, 1):
            title = source.title or f"{source.source_type}:{source.source_id}"
            lines.append(f"[文档{index}] {title}\n{source.snippet}")
        return "\n\n".join(lines)

    def compose_local_answer(self, question: str, result: RagResult, *, base_answer: str | None = None) -> str:
        if not result.has_sources:
            return base_answer or ""

        lines = [
            "【文档检索回答】",
            f"我在你有权限访问的资料中找到 {len(result.sources)} 条相关片段：",
        ]
        for index, source in enumerate(result.sources, 1):
            title = source.title or f"{source.source_type}:{source.source_id}"
            lines.append(f"{index}. {title}：{source.snippet}")
        lines.extend(
            [
                "",
                "【使用边界】",
                "以上内容只来自已授权文档片段；如果需要执行采购、库存、付款或删除等关键动作，仍需人工确认并走正式业务流程。",
            ]
        )
        if base_answer:
            lines.extend(["", "【经营分析补充】", base_answer])
        return "\n".join(lines)

    def _candidate_chunks(self, question: str, *, tenant_id: str, limit: int) -> list[DocumentChunk]:
        seen: set[int] = set()
        candidates: list[DocumentChunk] = []
        for term in search_terms(question):
            for chunk in self.repository.search_text(term, tenant_id=tenant_id, limit=limit):
                if chunk.id in seen:
                    continue
                seen.add(chunk.id)
                candidates.append(chunk)
                if len(candidates) >= limit:
                    return candidates
        return candidates

    def _can_read_chunk(self, user, chunk: DocumentChunk) -> bool:
        if chunk.source_type == "attachment":
            attachment_id = _safe_int(chunk.source_id)
            attachment = db.session.get(Attachment, attachment_id) if attachment_id else None
            if not attachment or attachment.is_deleted:
                return False
            return policy.can(user, "ai.tool.search_documents", resource=attachment).allowed
        return policy.can(user, "ai.tool.search_documents", context={"admin_only": True}).allowed

    def _source_from_chunk(self, chunk: DocumentChunk) -> RagSource:
        metadata = dict(chunk.metadata_json or {})
        return RagSource(
            chunk_id=chunk.id,
            source_type=chunk.source_type,
            source_id=str(chunk.source_id),
            title=chunk.title,
            snippet=trim_snippet(chunk.content),
            metadata={
                "filename": metadata.get("filename"),
                "mimetype": metadata.get("mimetype"),
                "storage_provider": metadata.get("storage_provider"),
                "chunk_index": chunk.chunk_index,
            },
        )


def search_terms(question: str) -> list[str]:
    cleaned = (question or "").strip()
    if not cleaned:
        return []

    terms: list[str] = [cleaned]
    terms.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{1,}", cleaned))
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
        terms.append(segment)
        if len(segment) > 6:
            for size in (6, 4, 2):
                for start in range(0, len(segment) - size + 1):
                    terms.append(segment[start : start + size])
        elif len(segment) > 2:
            for size in (4, 2):
                if len(segment) >= size:
                    for start in range(0, len(segment) - size + 1):
                        terms.append(segment[start : start + size])

    unique: list[str] = []
    for term in terms:
        normalized = term.strip()
        if len(normalized) < 2 or normalized in unique:
            continue
        unique.append(normalized)
    return unique[:32]


def trim_snippet(content: str, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", (content or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
