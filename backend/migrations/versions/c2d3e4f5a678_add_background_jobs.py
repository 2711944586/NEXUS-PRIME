"""Add background jobs

Revision ID: c2d3e4f5a678
Revises: b7c9d2e4f601
Create Date: 2026-06-20 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a678'
down_revision = 'b7c9d2e4f601'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'background_jobs',
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('job_type', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('queue', sa.String(length=64), nullable=False),
        sa.Column('task_name', sa.String(length=128), nullable=True),
        sa.Column('celery_task_id', sa.String(length=128), nullable=True),
        sa.Column('resource_type', sa.String(length=128), nullable=True),
        sa.Column('resource_id', sa.String(length=128), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['auth_users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id'),
    )
    with op.batch_alter_table('background_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_background_jobs_celery_task_id'), ['celery_task_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_jobs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_jobs_created_by'), ['created_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_jobs_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_jobs_job_type'), ['job_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_background_jobs_status'), ['status'], unique=False)
        batch_op.create_index('ix_background_jobs_type_status_created_at', ['job_type', 'status', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('background_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_background_jobs_type_status_created_at')
        batch_op.drop_index(batch_op.f('ix_background_jobs_status'))
        batch_op.drop_index(batch_op.f('ix_background_jobs_job_type'))
        batch_op.drop_index(batch_op.f('ix_background_jobs_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_background_jobs_created_by'))
        batch_op.drop_index(batch_op.f('ix_background_jobs_created_at'))
        batch_op.drop_index(batch_op.f('ix_background_jobs_celery_task_id'))
    op.drop_table('background_jobs')
