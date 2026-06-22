"""add AI action drafts

Revision ID: a7b8c9d0e123
Revises: a6b7c8d9e012
Create Date: 2026-06-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e123"
down_revision = "a6b7c8d9e012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_action_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("draft_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("source_tool", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result_type", sa.String(length=128), nullable=True),
        sa.Column("result_id", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_by", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["rejected_by"], ["auth_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_action_drafts_created_at"), "ai_action_drafts", ["created_at"], unique=False)
    op.create_index(op.f("ix_ai_action_drafts_is_deleted"), "ai_action_drafts", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_ai_action_drafts_draft_type"), "ai_action_drafts", ["draft_type"], unique=False)
    op.create_index(op.f("ix_ai_action_drafts_status"), "ai_action_drafts", ["status"], unique=False)
    op.create_index(op.f("ix_ai_action_drafts_source_tool"), "ai_action_drafts", ["source_tool"], unique=False)
    op.create_index(op.f("ix_ai_action_drafts_created_by"), "ai_action_drafts", ["created_by"], unique=False)
    op.create_index(
        "ix_ai_action_drafts_type_status_created_at",
        "ai_action_drafts",
        ["draft_type", "status", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_ai_action_drafts_type_status_created_at", table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_created_by"), table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_source_tool"), table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_status"), table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_draft_type"), table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_is_deleted"), table_name="ai_action_drafts")
    op.drop_index(op.f("ix_ai_action_drafts_created_at"), table_name="ai_action_drafts")
    op.drop_table("ai_action_drafts")
