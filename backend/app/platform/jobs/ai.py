from __future__ import annotations

from app.extensions import db
from app.domains.ai.infrastructure.embedding_provider import get_embedding_provider
from app.domains.ai.infrastructure.vector_repository import DocumentChunkRepository


def embed_document_chunks(*, source_type: str | None = None, source_id: str | None = None, limit: int = 50) -> dict:
    repository = DocumentChunkRepository()
    provider = get_embedding_provider()
    chunks = repository.pending_embedding_chunks(source_type=source_type, source_id=source_id, limit=limit)
    summary = {"processed": 0, "embedded": 0, "failed": 0, "chunk_ids": []}

    for chunk in chunks:
        summary["processed"] += 1
        try:
            result = provider.embed_text(chunk.content)
            repository.mark_embedding(chunk, embedding=result.embedding, model=result.model)
            summary["embedded"] += 1
            summary["chunk_ids"].append(chunk.id)
        except Exception as exc:
            metadata = dict(chunk.metadata_json or {})
            metadata["embedding_status"] = "failed"
            metadata["embedding_error"] = str(exc)
            chunk.metadata_json = metadata
            db.session.add(chunk)
            summary["failed"] += 1
    db.session.commit()
    return summary
