"""Add article comments for collaboration

Revision ID: 9c0f1a2b3d4e
Revises: 8f4f4c5d9b2a
Create Date: 2026-06-01 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9c0f1a2b3d4e'
down_revision = '8f4f4c5d9b2a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cms_article_comments',
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['cms_articles.id']),
        sa.ForeignKeyConstraint(['author_id'], ['auth_users.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['cms_article_comments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cms_article_comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cms_article_comments_article_id'), ['article_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cms_article_comments_author_id'), ['author_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cms_article_comments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_cms_article_comments_is_deleted'), ['is_deleted'], unique=False)


def downgrade():
    with op.batch_alter_table('cms_article_comments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cms_article_comments_is_deleted'))
        batch_op.drop_index(batch_op.f('ix_cms_article_comments_created_at'))
        batch_op.drop_index(batch_op.f('ix_cms_article_comments_author_id'))
        batch_op.drop_index(batch_op.f('ix_cms_article_comments_article_id'))
    op.drop_table('cms_article_comments')
