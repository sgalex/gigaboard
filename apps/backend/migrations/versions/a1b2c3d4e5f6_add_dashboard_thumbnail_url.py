"""add dashboard thumbnail_url

Revision ID: a1b2c3d4e5f6
Revises: cf01a2b3d4e5
Create Date: 2026-03-01

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'cf01a2b3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'dashboards',
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('dashboards', 'thumbnail_url')
