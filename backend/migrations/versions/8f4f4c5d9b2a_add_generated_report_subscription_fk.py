"""Add generated report subscription foreign key

Revision ID: 8f4f4c5d9b2a
Revises: 65cf96d20fca
Create Date: 2026-05-26 15:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8f4f4c5d9b2a'
down_revision = '65cf96d20fca'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subscription_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_generated_reports_subscription_id_report_subscriptions',
            'report_subscriptions',
            ['subscription_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.drop_constraint('fk_generated_reports_subscription_id_report_subscriptions', type_='foreignkey')
        batch_op.drop_column('subscription_id')
