"""add user ai settings and secrets

Revision ID: 08a1b2c3d4e5
Revises: cf01a2b3d4e5_add_cross_filter_system
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "08a1b2c3d4e5"
down_revision: Union[str, None] = "cf01a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_secrets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(length=100), nullable=False, index=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("encrypted_value", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "user_ai_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="gigachat"),
        sa.Column("gigachat_model", sa.String(length=100), nullable=True),
        sa.Column("gigachat_scope", sa.String(length=100), nullable=True),
        sa.Column("external_base_url", sa.String(length=255), nullable=True),
        sa.Column("external_default_model", sa.String(length=255), nullable=True),
        sa.Column("external_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "external_api_key_secret_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_secrets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("temperature", sa.Integer(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("preferred_style", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_ai_settings")
    op.drop_table("user_secrets")

