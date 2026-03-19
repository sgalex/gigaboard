"""system_llm_settings

Revision ID: 12_sys_llm
Revises: 11_user_role
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "12_sys_llm"
down_revision: Union[str, None] = "11_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_llm_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="gigachat"),
        sa.Column("gigachat_model", sa.String(100), nullable=True),
        sa.Column("gigachat_scope", sa.String(100), nullable=True),
        sa.Column("gigachat_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("external_base_url", sa.String(255), nullable=True),
        sa.Column("external_default_model", sa.String(255), nullable=True),
        sa.Column("external_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("external_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("system_llm_settings")
