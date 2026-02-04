"""Add edges table for widget connections

Revision ID: 003
Revises: 002
Create Date: 2026-01-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create edges table."""
    op.create_table(
        'edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_widget_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('widgets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_widget_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('widgets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('edge_type', sa.String(50), nullable=False),
        sa.Column('label', sa.String(200), nullable=True),
        sa.Column('parameter_mapping', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('visual_config', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_valid', sa.String(10), nullable=False, server_default='true'),
        sa.Column('validation_errors', sa.Text(), nullable=True),
    )
    
    # Create indexes for performance
    op.create_index('idx_edges_board_id', 'edges', ['board_id'])
    op.create_index('idx_edges_source_widget', 'edges', ['source_widget_id'])
    op.create_index('idx_edges_target_widget', 'edges', ['target_widget_id'])
    op.create_index('idx_edges_board_source_target', 'edges', ['board_id', 'source_widget_id', 'target_widget_id'])
    op.create_index('idx_edges_edge_type', 'edges', ['edge_type'])


def downgrade() -> None:
    """Drop edges table."""
    op.drop_index('idx_edges_edge_type', table_name='edges')
    op.drop_index('idx_edges_board_source_target', table_name='edges')
    op.drop_index('idx_edges_target_widget', table_name='edges')
    op.drop_index('idx_edges_source_widget', table_name='edges')
    op.drop_index('idx_edges_board_id', table_name='edges')
    op.drop_table('edges')
