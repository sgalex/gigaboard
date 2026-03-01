"""add board thumbnail_url

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-01

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'boards',
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('boards', 'thumbnail_url')
