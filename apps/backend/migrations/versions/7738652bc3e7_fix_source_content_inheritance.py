"""fix_source_content_inheritance

Revision ID: 7738652bc3e7
Revises: a97be50bb15e
Create Date: 2026-01-31 13:05:29.142066

Fixes Joined Table Inheritance for SourceNode and ContentNode.
Problem: source_nodes and content_nodes tables have their own board_id column,
but in JTI architecture board_id should only be in the parent 'nodes' table.

Solution:
1. Remove board_id from source_nodes table
2. Remove board_id from content_nodes table
3. board_id is inherited from nodes table via id FK
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7738652bc3e7'
down_revision = 'a97be50bb15e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove board_id from source_nodes and content_nodes (inherited from nodes table)."""
    
    # Drop indexes first
    op.drop_index('ix_source_nodes_board_id', table_name='source_nodes')
    op.drop_index('ix_content_nodes_board_id', table_name='content_nodes')
    
    # Drop FK constraints
    op.drop_constraint('source_nodes_board_id_fkey', 'source_nodes', type_='foreignkey')
    op.drop_constraint('content_nodes_board_id_fkey', 'content_nodes', type_='foreignkey')
    
    # Drop board_id columns (inherited from nodes table now)
    op.drop_column('source_nodes', 'board_id')
    op.drop_column('content_nodes', 'board_id')


def downgrade() -> None:
    """Restore board_id to source_nodes and content_nodes."""
    
    # Add board_id columns back
    op.add_column('source_nodes', sa.Column('board_id', sa.UUID(), nullable=False))
    op.add_column('content_nodes', sa.Column('board_id', sa.UUID(), nullable=False))
    
    # Restore FK constraints
    op.create_foreign_key('source_nodes_board_id_fkey', 'source_nodes', 'boards', ['board_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('content_nodes_board_id_fkey', 'content_nodes', 'boards', ['board_id'], ['id'], ondelete='CASCADE')
    
    # Restore indexes
    op.create_index('ix_source_nodes_board_id', 'source_nodes', ['board_id'])
    op.create_index('ix_content_nodes_board_id', 'content_nodes', ['board_id'])
