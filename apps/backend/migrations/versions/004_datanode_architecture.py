"""Add DataNode architecture tables.

Revision ID: 004
Revises: 003
Create Date: 2026-01-24 19:28:32
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create DataNode, WidgetNode, CommentNode tables."""
    
    # Create data_nodes table
    op.create_table(
        'data_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('data_source_type', sa.String(50), nullable=False),
        sa.Column('query', sa.Text, nullable=True),
        sa.Column('api_config', postgresql.JSONB, nullable=True),
        sa.Column('schema', postgresql.JSONB, nullable=True),
        sa.Column('data', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('parameters', postgresql.JSONB, nullable=True),
        sa.Column('x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('y', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_data_nodes_board_id', 'data_nodes', ['board_id'])
    
    # Create widget_nodes table
    op.create_table(
        'widget_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('html_code', sa.Text, nullable=False),
        sa.Column('css_code', sa.Text, nullable=True),
        sa.Column('js_code', sa.Text, nullable=True),
        sa.Column('config', postgresql.JSONB, nullable=True),
        sa.Column('x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('y', sa.Integer, nullable=False, server_default='0'),
        sa.Column('width', sa.Integer, nullable=False, server_default='400'),
        sa.Column('height', sa.Integer, nullable=False, server_default='300'),
        sa.Column('auto_refresh', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('refresh_interval', sa.Integer, nullable=True),
        sa.Column('generated_by', sa.String(50), nullable=True),
        sa.Column('generation_prompt', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_widget_nodes_board_id', 'widget_nodes', ['board_id'])
    
    # Create comment_nodes table
    op.create_table(
        'comment_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('format_type', sa.String(20), nullable=False, server_default='markdown'),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('config', postgresql.JSONB, nullable=True),
        sa.Column('x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('y', sa.Integer, nullable=False, server_default='0'),
        sa.Column('width', sa.Integer, nullable=False, server_default='300'),
        sa.Column('height', sa.Integer, nullable=False, server_default='150'),
        sa.Column('is_resolved', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_comment_nodes_board_id', 'comment_nodes', ['board_id'])
    op.create_index('ix_comment_nodes_author_id', 'comment_nodes', ['author_id'])
    
    # Drop edges table first (has FK to widgets), then widgets table
    op.drop_table('edges')
    op.drop_table('widgets')
    
    # Recreate edges table for new architecture
    op.create_table(
        'edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_node_type', sa.String(50), nullable=False),
        sa.Column('target_node_type', sa.String(50), nullable=False),
        sa.Column('edge_type', sa.String(50), nullable=False),
        sa.Column('label', sa.String(200), nullable=True),
        sa.Column('parameter_mapping', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('transformation_code', sa.Text, nullable=True),
        sa.Column('transformation_params', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('visual_config', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('is_valid', sa.String(10), nullable=False, server_default='true'),
        sa.Column('validation_errors', sa.Text, nullable=True),
    )
    op.create_index('ix_edges_board_id', 'edges', ['board_id'])
    op.create_index('ix_edges_source_node', 'edges', ['source_node_id'])
    op.create_index('ix_edges_target_node', 'edges', ['target_node_id'])


def downgrade() -> None:
    """Restore old Widget architecture."""
    
    # Drop new tables
    op.drop_index('ix_comment_nodes_author_id', 'comment_nodes')
    op.drop_index('ix_comment_nodes_board_id', 'comment_nodes')
    op.drop_table('comment_nodes')
    
    op.drop_index('ix_widget_nodes_board_id', 'widget_nodes')
    op.drop_table('widget_nodes')
    
    op.drop_index('ix_data_nodes_board_id', 'data_nodes')
    op.drop_table('data_nodes')
    
    # Recreate old edges and widgets tables
    op.drop_index('ix_edges_target_node', 'edges')
    op.drop_index('ix_edges_source_node', 'edges')
    op.drop_index('ix_edges_board_id', 'edges')
    op.drop_table('edges')
    
    # Note: This is a destructive downgrade - data will be lost
    # Recreate old widgets table structure
    op.create_table(
        'widgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('y', sa.Integer, nullable=False, server_default='0'),
        sa.Column('width', sa.Integer, nullable=False, server_default='300'),
        sa.Column('height', sa.Integer, nullable=False, server_default='200'),
        sa.Column('config', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Recreate old edges table
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
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('is_valid', sa.String(10), nullable=False, server_default='true'),
        sa.Column('validation_errors', sa.Text, nullable=True),
    )
