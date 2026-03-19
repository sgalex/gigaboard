"""user_ai_settings gigachat_api_key_secret_id

Revision ID: 10_gc_secret
Revises: 09_temp_float
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "10_gc_secret"
down_revision: Union[str, None] = "09_temp_float"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_ai_settings",
        sa.Column(
            "gigachat_api_key_secret_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_secrets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_ai_settings", "gigachat_api_key_secret_id")
