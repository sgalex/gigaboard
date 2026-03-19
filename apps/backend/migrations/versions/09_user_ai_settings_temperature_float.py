"""user_ai_settings temperature column to float

Revision ID: 09_temp_float
Revises: 08a1b2c3d4e5
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "09_temp_float"
down_revision: Union[str, None] = "08a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_ai_settings",
        "temperature",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="temperature::double precision",
    )


def downgrade() -> None:
    op.alter_column(
        "user_ai_settings",
        "temperature",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="temperature::integer",
    )
