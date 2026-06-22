"""add reporting read models

Revision ID: f5a6b7c8d901
Revises: e4f5a6b7c890
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f5a6b7c8d901"
down_revision = "e4f5a6b7c890"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reporting_daily_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("dimension_type", sa.String(length=64), nullable=False),
        sa.Column("dimension_id", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_event_id", sa.String(length=36), nullable=True),
        sa.Column("last_event_type", sa.String(length=128), nullable=True),
        sa.Column("last_projected_at", sa.DateTime(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "metric_date",
            "metric_name",
            "dimension_type",
            "dimension_id",
            name="uq_reporting_daily_metric_key",
        ),
    )
    op.create_index(op.f("ix_reporting_daily_metrics_created_at"), "reporting_daily_metrics", ["created_at"], unique=False)
    op.create_index(op.f("ix_reporting_daily_metrics_is_deleted"), "reporting_daily_metrics", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_reporting_daily_metrics_metric_date"), "reporting_daily_metrics", ["metric_date"], unique=False)
    op.create_index(op.f("ix_reporting_daily_metrics_metric_name"), "reporting_daily_metrics", ["metric_name"], unique=False)

    op.create_table(
        "reporting_projection_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("metrics_count", sa.Integer(), nullable=False),
        sa.Column("projected_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_reporting_projection_states_event_id"),
    )
    op.create_index(op.f("ix_reporting_projection_states_created_at"), "reporting_projection_states", ["created_at"], unique=False)
    op.create_index(op.f("ix_reporting_projection_states_event_id"), "reporting_projection_states", ["event_id"], unique=False)
    op.create_index(op.f("ix_reporting_projection_states_event_type"), "reporting_projection_states", ["event_type"], unique=False)
    op.create_index(op.f("ix_reporting_projection_states_is_deleted"), "reporting_projection_states", ["is_deleted"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_reporting_projection_states_is_deleted"), table_name="reporting_projection_states")
    op.drop_index(op.f("ix_reporting_projection_states_event_type"), table_name="reporting_projection_states")
    op.drop_index(op.f("ix_reporting_projection_states_event_id"), table_name="reporting_projection_states")
    op.drop_index(op.f("ix_reporting_projection_states_created_at"), table_name="reporting_projection_states")
    op.drop_table("reporting_projection_states")

    op.drop_index(op.f("ix_reporting_daily_metrics_metric_name"), table_name="reporting_daily_metrics")
    op.drop_index(op.f("ix_reporting_daily_metrics_metric_date"), table_name="reporting_daily_metrics")
    op.drop_index(op.f("ix_reporting_daily_metrics_is_deleted"), table_name="reporting_daily_metrics")
    op.drop_index(op.f("ix_reporting_daily_metrics_created_at"), table_name="reporting_daily_metrics")
    op.drop_table("reporting_daily_metrics")
