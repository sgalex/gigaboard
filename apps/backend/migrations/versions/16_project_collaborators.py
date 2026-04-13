"""project_collaborators table for shared project access

Revision ID: 16_proj_collab
Revises: 15_user_ai_ma
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "16_proj_collab"
down_revision: Union[str, None] = "15_user_ai_ma"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "project_collaborators" not in insp.get_table_names():
        op.create_table(
            "project_collaborators",
            sa.Column("project_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("project_id", "user_id"),
            sa.UniqueConstraint("project_id", "user_id", name="uq_project_collaborator"),
        )
    ix = "ix_project_collaborators_user_id"
    existing_ix = {i["name"] for i in insp.get_indexes("project_collaborators")} if "project_collaborators" in insp.get_table_names() else set()
    if ix not in existing_ix and "project_collaborators" in insp.get_table_names():
        op.create_index(
            ix,
            "project_collaborators",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_project_collaborators_user_id", table_name="project_collaborators")
    op.drop_table("project_collaborators")
