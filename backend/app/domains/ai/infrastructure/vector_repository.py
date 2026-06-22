from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import or_

from app.extensions import db
from app.models.ai import DocumentChunk


@dataclass(frozen=True)
class ChunkInput:
    source_type: str
    source_id: str
    chunk_index: int
    content: str
    title: str | None = None
    tenant_id: str = "default"
    embedding: list[float] | None = None
    embedding_model: str | None = None
    metadata: dict | None = None


class DocumentChunkRepository:
    def upsert_chunk(self, chunk: ChunkInput) -> DocumentChunk:
        content = (chunk.content or "").strip()
        if not content:
            raise ValueError("Document chunk content is required")
        row = DocumentChunk.query.filter_by(
            source_type=chunk.source_type,
            source_id=str(chunk.source_id),
            chunk_index=int(chunk.chunk_index),
        ).first()
        if row is None:
            row = DocumentChunk(
                source_type=chunk.source_type,
                source_id=str(chunk.source_id),
                chunk_index=int(chunk.chunk_index),
            )
            db.session.add(row)
        row.tenant_id = chunk.tenant_id or "default"
        row.title = chunk.title
        row.content = content
        row.content_hash = content_hash(content)
        row.embedding = chunk.embedding
        row.embedding_model = chunk.embedding_model
        row.metadata_json = chunk.metadata or {}
        row.is_deleted = False
        return row

    def pending_embedding_chunks(self, *, source_type: str | None = None, source_id: str | None = None, limit: int = 50) -> list[DocumentChunk]:
        query = DocumentChunk.query.filter(DocumentChunk.is_deleted == False)
        if source_type:
            query = query.filter(DocumentChunk.source_type == source_type)
        if source_id is not None:
            query = query.filter(DocumentChunk.source_id == str(source_id))
        query = query.filter(
            or_(
                DocumentChunk.embedding == None,
                DocumentChunk.embedding_model == None,
                DocumentChunk.metadata_json["embedding_status"].as_string() == "pending",
            )
        )
        return query.order_by(DocumentChunk.updated_at.asc(), DocumentChunk.id.asc()).limit(limit).all()

    def mark_embedding(self, chunk: DocumentChunk, *, embedding: list[float], model: str) -> DocumentChunk:
        if not embedding:
            raise ValueError("Embedding vector is required")
        metadata = dict(chunk.metadata_json or {})
        metadata["embedding_status"] = "embedded"
        metadata["embedding_dimensions"] = len(embedding)
        chunk.embedding = embedding
        chunk.embedding_model = model
        chunk.metadata_json = metadata
        db.session.add(chunk)
        return chunk

    def search_text(self, query: str, *, tenant_id: str = "default", limit: int = 5) -> list[DocumentChunk]:
        term = (query or "").strip()
        if not term:
            return []
        like = f"%{term}%"
        return (
            DocumentChunk.query.filter(
                DocumentChunk.is_deleted == False,
                DocumentChunk.tenant_id == tenant_id,
                or_(DocumentChunk.title.ilike(like), DocumentChunk.content.ilike(like)),
            )
            .order_by(DocumentChunk.updated_at.desc())
            .limit(limit)
            .all()
        )


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()
