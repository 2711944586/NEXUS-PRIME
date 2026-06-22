"""add document chunks for AI RAG

Revision ID: a6b7c8d9e012
Revises: f5a6b7c8d901
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e012"
down_revision = "f5a6b7c8d901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", "chunk_index", name="uq_document_chunk_source_index"),
    )
    op.create_index(op.f("ix_document_chunks_created_at"), "document_chunks", ["created_at"], unique=False)
    op.create_index(op.f("ix_document_chunks_is_deleted"), "document_chunks", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_document_chunks_tenant_id"), "document_chunks", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_source_type"), "document_chunks", ["source_type"], unique=False)
    op.create_index(op.f("ix_document_chunks_source_id"), "document_chunks", ["source_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_content_hash"), "document_chunks", ["content_hash"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_document_chunks_content_hash"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_source_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_source_type"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_tenant_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_is_deleted"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_created_at"), table_name="document_chunks")
    op.drop_table("document_chunks")
