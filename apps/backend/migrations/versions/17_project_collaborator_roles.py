"""project_collaborators.role: viewer | editor | admin

Revision ID: 17_proj_roles
Revises: 16_proj_collab
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "17_proj_roles"
down_revision: Union[str, None] = "16_proj_collab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("project_collaborators")}
    if "role" not in cols:
        op.add_column(
            "project_collaborators",
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="editor",
            ),
        )


def downgrade() -> None:
    op.drop_column("project_collaborators", "role")
