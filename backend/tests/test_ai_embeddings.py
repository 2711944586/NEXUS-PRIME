from app import create_app
from app.extensions import db
from app.domains.ai.infrastructure.embedding_provider import LocalHashEmbeddingProvider
from app.domains.ai.infrastructure.vector_repository import ChunkInput, DocumentChunkRepository
from app.models.ai import DocumentChunk
from app.platform.jobs.ai import embed_document_chunks


def test_local_hash_embedding_provider_is_deterministic():
    provider = LocalHashEmbeddingProvider(dimensions=16)

    first = provider.embed_text("供应商质检报告")
    second = provider.embed_text("供应商质检报告")

    assert first.model == "local-hash-v1"
    assert len(first.embedding) == 16
    assert first.embedding == second.embedding
    assert any(value != 0 for value in first.embedding)


def test_embed_document_chunks_marks_pending_chunks_embedded():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        repo = DocumentChunkRepository()
        chunk = repo.upsert_chunk(
            ChunkInput(
                source_type="attachment",
                source_id="42",
                chunk_index=0,
                title="质检报告",
                content="供应商质检报告必须记录批次和整改闭环。",
                metadata={"embedding_status": "pending"},
            )
        )
        db.session.commit()

        summary = embed_document_chunks(source_type="attachment", source_id="42")

        assert summary["processed"] == 1
        assert summary["embedded"] == 1
        assert summary["failed"] == 0
        stored = db.session.get(DocumentChunk, chunk.id)
        assert stored.embedding_model == "local-hash-v1"
        assert len(stored.embedding) == 32
        assert stored.metadata_json["embedding_status"] == "embedded"
        assert stored.metadata_json["embedding_dimensions"] == 32

        repeat = embed_document_chunks(source_type="attachment", source_id="42")
        assert repeat["processed"] == 0

        db.session.remove()
        db.drop_all()
