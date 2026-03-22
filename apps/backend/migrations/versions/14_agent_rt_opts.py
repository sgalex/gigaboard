"""add runtime_options to agent_llm_override

Revision ID: 14_agent_rt_opts
Revises: 7f86bdd5743c
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "14_agent_rt_opts"
down_revision: Union[str, None] = "7f86bdd5743c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_llm_override",
        sa.Column("runtime_options", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_llm_override", "runtime_options")
