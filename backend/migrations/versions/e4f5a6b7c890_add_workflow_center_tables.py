"""add workflow center tables

Revision ID: e4f5a6b7c890
Revises: d3e4f5a6b789
Create Date: 2026-06-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e4f5a6b7c890"
down_revision = "d3e4f5a6b789"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("process_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("process_key", name="uq_workflow_definition_process_key"),
    )
    op.create_index(op.f("ix_workflow_definitions_created_at"), "workflow_definitions", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_definitions_is_active"), "workflow_definitions", ["is_active"], unique=False)
    op.create_index(op.f("ix_workflow_definitions_is_deleted"), "workflow_definitions", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_workflow_definitions_process_key"), "workflow_definitions", ["process_key"], unique=False)

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("definition_id", sa.Integer(), nullable=False),
        sa.Column("business_type", sa.String(length=128), nullable=False),
        sa.Column("business_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_node_key", sa.String(length=128), nullable=True),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["applicant_id"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_instances_applicant_id"), "workflow_instances", ["applicant_id"], unique=False)
    op.create_index(op.f("ix_workflow_instances_business_id"), "workflow_instances", ["business_id"], unique=False)
    op.create_index(op.f("ix_workflow_instances_business_type"), "workflow_instances", ["business_type"], unique=False)
    op.create_index(op.f("ix_workflow_instances_created_at"), "workflow_instances", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_instances_definition_id"), "workflow_instances", ["definition_id"], unique=False)
    op.create_index(op.f("ix_workflow_instances_is_deleted"), "workflow_instances", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_workflow_instances_status"), "workflow_instances", ["status"], unique=False)

    op.create_table(
        "workflow_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=False),
        sa.Column("action_by", sa.Integer(), nullable=True),
        sa.Column("action_at", sa.DateTime(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["action_by"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["workflow_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_tasks_assignee_id"), "workflow_tasks", ["assignee_id"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_created_at"), "workflow_tasks", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_instance_id"), "workflow_tasks", ["instance_id"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_is_deleted"), "workflow_tasks", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_status"), "workflow_tasks", ["status"], unique=False)

    op.create_table(
        "workflow_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["workflow_instances.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["workflow_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_logs_action"), "workflow_logs", ["action"], unique=False)
    op.create_index(op.f("ix_workflow_logs_created_at"), "workflow_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_logs_instance_id"), "workflow_logs", ["instance_id"], unique=False)
    op.create_index(op.f("ix_workflow_logs_is_deleted"), "workflow_logs", ["is_deleted"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_workflow_logs_is_deleted"), table_name="workflow_logs")
    op.drop_index(op.f("ix_workflow_logs_instance_id"), table_name="workflow_logs")
    op.drop_index(op.f("ix_workflow_logs_created_at"), table_name="workflow_logs")
    op.drop_index(op.f("ix_workflow_logs_action"), table_name="workflow_logs")
    op.drop_table("workflow_logs")

    op.drop_index(op.f("ix_workflow_tasks_status"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_is_deleted"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_instance_id"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_created_at"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_assignee_id"), table_name="workflow_tasks")
    op.drop_table("workflow_tasks")

    op.drop_index(op.f("ix_workflow_instances_status"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_is_deleted"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_definition_id"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_created_at"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_business_type"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_business_id"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_applicant_id"), table_name="workflow_instances")
    op.drop_table("workflow_instances")

    op.drop_index(op.f("ix_workflow_definitions_process_key"), table_name="workflow_definitions")
    op.drop_index(op.f("ix_workflow_definitions_is_deleted"), table_name="workflow_definitions")
    op.drop_index(op.f("ix_workflow_definitions_is_active"), table_name="workflow_definitions")
    op.drop_index(op.f("ix_workflow_definitions_created_at"), table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
