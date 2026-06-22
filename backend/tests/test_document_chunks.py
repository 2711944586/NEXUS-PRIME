from app import create_app
from app.extensions import db
from app.models.ai import DocumentChunk
from app.domains.ai.infrastructure.vector_repository import ChunkInput, DocumentChunkRepository, content_hash


def test_document_chunk_repository_upserts_and_searches_text():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        repo = DocumentChunkRepository()
        chunk = repo.upsert_chunk(
            ChunkInput(
                source_type="attachment",
                source_id="42",
                chunk_index=0,
                title="采购制度",
                content="供应商质检报告必须进入 RAG 检索。",
                embedding=[0.1, 0.2, 0.3],
                embedding_model="test-embedding",
                metadata={"filename": "policy.txt"},
            )
        )
        db.session.commit()

        assert chunk.id is not None
        assert chunk.content_hash == content_hash("供应商质检报告必须进入 RAG 检索。")
        assert chunk.embedding == [0.1, 0.2, 0.3]
        assert chunk.metadata_json["filename"] == "policy.txt"

        results = repo.search_text("质检报告")

        assert [item.id for item in results] == [chunk.id]
        db.session.remove()
        db.drop_all()


def test_document_chunk_repository_reuses_source_index_key():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        repo = DocumentChunkRepository()
        repo.upsert_chunk(ChunkInput(source_type="article", source_id="7", chunk_index=1, content="旧内容"))
        db.session.commit()

        updated = repo.upsert_chunk(
            ChunkInput(source_type="article", source_id="7", chunk_index=1, content="新内容", title="更新")
        )
        db.session.commit()

        assert DocumentChunk.query.count() == 1
        assert updated.content == "新内容"
        assert updated.title == "更新"
        db.session.remove()
        db.drop_all()


def test_document_chunk_repository_rejects_empty_content():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        repo = DocumentChunkRepository()
        try:
            repo.upsert_chunk(ChunkInput(source_type="attachment", source_id="1", chunk_index=0, content=" "))
        except ValueError as exc:
            assert "content" in str(exc)
        else:
            raise AssertionError("empty chunk content should be rejected")
        finally:
            db.session.remove()
            db.drop_all()
