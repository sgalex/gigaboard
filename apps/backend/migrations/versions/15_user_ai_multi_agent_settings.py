"""user_ai_settings multi_agent_settings JSON

Revision ID: 15_user_ai_ma
Revises: 14_agent_rt_opts
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "15_user_ai_ma"
down_revision: Union[str, None] = "14_agent_rt_opts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_ai_settings",
        sa.Column("multi_agent_settings", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_ai_settings", "multi_agent_settings")
