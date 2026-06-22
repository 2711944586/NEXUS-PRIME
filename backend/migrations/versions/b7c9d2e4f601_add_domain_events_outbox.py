"""Add domain events outbox

Revision ID: b7c9d2e4f601
Revises: 9c0f1a2b3d4e
Create Date: 2026-06-20 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c9d2e4f601'
down_revision = '9c0f1a2b3d4e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'domain_events',
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('aggregate_type', sa.String(length=128), nullable=False),
        sa.Column('aggregate_id', sa.String(length=128), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('tenant_id', sa.String(length=128), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )
    with op.batch_alter_table('domain_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_domain_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_domain_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_domain_events_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_domain_events_status'), ['status'], unique=False)
        batch_op.create_index('ix_domain_events_status_created_at', ['status', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('domain_events', schema=None) as batch_op:
        batch_op.drop_index('ix_domain_events_status_created_at')
        batch_op.drop_index(batch_op.f('ix_domain_events_status'))
        batch_op.drop_index(batch_op.f('ix_domain_events_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_domain_events_event_type'))
        batch_op.drop_index(batch_op.f('ix_domain_events_created_at'))
    op.drop_table('domain_events')
