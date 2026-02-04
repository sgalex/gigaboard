"""Add projects, boards, and widgets tables.

Revision ID: 002
Revises: 001
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create projects, boards, and widgets tables."""
    
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create boards table
    op.create_table(
        'boards',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create widgets table
    op.create_table(
        'widgets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('x', sa.Integer, nullable=False, default=0),
        sa.Column('y', sa.Integer, nullable=False, default=0),
        sa.Column('width', sa.Integer, nullable=False, default=300),
        sa.Column('height', sa.Integer, nullable=False, default=200),
        sa.Column('config', sa.JSON, nullable=False, default={}),
        sa.Column('data', sa.JSON, nullable=False, default={}),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes
    op.create_index('idx_projects_user_id', 'projects', ['user_id'])
    op.create_index('idx_boards_project_id', 'boards', ['project_id'])
    op.create_index('idx_boards_user_id', 'boards', ['user_id'])
    op.create_index('idx_widgets_board_id', 'widgets', ['board_id'])


def downgrade() -> None:
    """Drop projects, boards, and widgets tables."""
    
    # Drop indexes
    op.drop_index('idx_widgets_board_id', 'widgets')
    op.drop_index('idx_boards_user_id', 'boards')
    op.drop_index('idx_boards_project_id', 'boards')
    op.drop_index('idx_projects_user_id', 'projects')
    
    # Drop tables (in reverse order due to FK constraints)
    op.drop_table('widgets')
    op.drop_table('boards')
    op.drop_table('projects')
