"""Add stock balances and movements

Revision ID: d3e4f5a6b789
Revises: c2d3e4f5a678
Create Date: 2026-06-20 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b789'
down_revision = 'c2d3e4f5a678'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stock_balances',
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('available_qty', sa.Integer(), nullable=False),
        sa.Column('locked_qty', sa.Integer(), nullable=False),
        sa.Column('damaged_qty', sa.Integer(), nullable=False),
        sa.Column('in_transit_qty', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['biz_products.id']),
        sa.ForeignKeyConstraint(['warehouse_id'], ['stock_warehouses.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'product_id', 'warehouse_id', name='uq_stock_balance_tenant_product_warehouse'),
    )
    with op.batch_alter_table('stock_balances', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_balances_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_stock_balances_is_deleted'), ['is_deleted'], unique=False)

    op.create_table(
        'stock_movements',
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('before_available_qty', sa.Integer(), nullable=False),
        sa.Column('after_available_qty', sa.Integer(), nullable=False),
        sa.Column('before_locked_qty', sa.Integer(), nullable=False),
        sa.Column('after_locked_qty', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=128), nullable=False),
        sa.Column('source_id', sa.String(length=128), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['auth_users.id']),
        sa.ForeignKeyConstraint(['product_id'], ['biz_products.id']),
        sa.ForeignKeyConstraint(['warehouse_id'], ['stock_warehouses.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_stock_movements_idempotency_key'),
    )
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_movements_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_stock_movements_direction'), ['direction'], unique=False)
        batch_op.create_index(batch_op.f('ix_stock_movements_is_deleted'), ['is_deleted'], unique=False)


def downgrade():
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stock_movements_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_stock_movements_direction'))
        batch_op.drop_index(batch_op.f('ix_stock_movements_created_at'))
    op.drop_table('stock_movements')

    with op.batch_alter_table('stock_balances', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stock_balances_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_stock_balances_created_at'))
    op.drop_table('stock_balances')
