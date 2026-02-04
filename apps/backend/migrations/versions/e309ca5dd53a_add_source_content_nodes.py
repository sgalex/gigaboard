"""add_source_content_nodes

Revision ID: e309ca5dd53a
Revises: a23e270852e3
Create Date: 2026-01-30 23:22:13.143950

Implements Source-Content Node Architecture (FR-14):
- SourceNode: точки входа данных (file, database, api, prompt, stream, manual)
- ContentNode: результаты обработки (text + N tables)
- Explicit data lineage tracking
- Streaming support with accumulation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e309ca5dd53a'
down_revision = 'a23e270852e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create source_nodes and content_nodes tables."""
    
    # 1. Create source_nodes table
    op.create_table(
        'source_nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('board_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('position', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{"x": 0, "y": 0}'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['board_id'], ['boards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['id'], ['nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_source_nodes_board_id', 'source_nodes', ['board_id'])
    op.create_index('ix_source_nodes_source_type', 'source_nodes', ['source_type'])
    
    # 2. Create content_nodes table
    op.create_table(
        'content_nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('board_id', sa.UUID(), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{"text": "", "tables": []}'),
        sa.Column('lineage', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('position', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{"x": 0, "y": 0}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['board_id'], ['boards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['id'], ['nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_content_nodes_board_id', 'content_nodes', ['board_id'])
    
    # 3. Create GIN index for lineage queries (for data lineage tracking)
    op.create_index(
        'ix_content_nodes_lineage_gin',
        'content_nodes',
        ['lineage'],
        postgresql_using='gin'
    )
    
    # 4. Add EXTRACT edge type to support SourceNode → ContentNode connections
    # Note: Assuming edge_type is an enum or string column in edges table
    # This will be handled by updating edge validation in the application code


def downgrade() -> None:
    """Drop source_nodes and content_nodes tables."""
    
    # Drop indexes first
    op.drop_index('ix_content_nodes_lineage_gin', table_name='content_nodes')
    op.drop_index('ix_content_nodes_board_id', table_name='content_nodes')
    op.drop_index('ix_source_nodes_source_type', table_name='source_nodes')
    op.drop_index('ix_source_nodes_board_id', table_name='source_nodes')
    
    # Drop tables
    op.drop_table('content_nodes')
    op.drop_table('source_nodes')
