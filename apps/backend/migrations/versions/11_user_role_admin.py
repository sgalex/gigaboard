"""user role admin

Revision ID: 11_user_role
Revises: 10_gc_secret
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "11_user_role"
down_revision: Union[str, None] = "10_gc_secret"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
