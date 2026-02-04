"""Add base nodes table with joined table inheritance

Revision ID: 007
Revises: 006
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate to joined table inheritance structure:
    1. Create base nodes table
    2. Migrate existing data
    3. Modify child tables to reference nodes table
    """
    
    # 1. Create base nodes table
    op.create_table(
        'nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('board_id', sa.UUID(), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False),
        sa.Column('x', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('y', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['board_id'], ['boards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_nodes_board_id', 'nodes', ['board_id'])
    op.create_index('ix_nodes_node_type', 'nodes', ['node_type'])
    
    # 2. Migrate data from data_nodes to nodes table
    op.execute("""
        INSERT INTO nodes (id, board_id, node_type, x, y, width, height, created_at, updated_at)
        SELECT id, board_id, 'data_node', x, y, NULL, NULL, created_at, updated_at
        FROM data_nodes
    """)
    
    # 3. Migrate data from widget_nodes to nodes table
    op.execute("""
        INSERT INTO nodes (id, board_id, node_type, x, y, width, height, created_at, updated_at)
        SELECT id, board_id, 'widget_node', x, y, width, height, created_at, updated_at
        FROM widget_nodes
    """)
    
    # 4. Migrate data from comment_nodes to nodes table
    op.execute("""
        INSERT INTO nodes (id, board_id, node_type, x, y, width, height, created_at, updated_at)
        SELECT id, board_id, 'comment_node', x, y, width, height, created_at, updated_at
        FROM comment_nodes
    """)
    
    # 5. Drop old columns and constraints from child tables
    # DataNodes
    op.drop_constraint('data_nodes_board_id_fkey', 'data_nodes', type_='foreignkey')
    op.drop_column('data_nodes', 'board_id')
    op.drop_column('data_nodes', 'x')
    op.drop_column('data_nodes', 'y')
    op.drop_column('data_nodes', 'created_at')
    op.drop_column('data_nodes', 'updated_at')
    
    # Add foreign key to nodes table
    op.create_foreign_key(
        'data_nodes_id_fkey',
        'data_nodes', 'nodes',
        ['id'], ['id'],
        ondelete='CASCADE'
    )
    
    # WidgetNodes
    op.drop_constraint('widget_nodes_board_id_fkey', 'widget_nodes', type_='foreignkey')
    op.drop_column('widget_nodes', 'board_id')
    op.drop_column('widget_nodes', 'x')
    op.drop_column('widget_nodes', 'y')
    op.drop_column('widget_nodes', 'width')
    op.drop_column('widget_nodes', 'height')
    op.drop_column('widget_nodes', 'created_at')
    op.drop_column('widget_nodes', 'updated_at')
    
    op.create_foreign_key(
        'widget_nodes_id_fkey',
        'widget_nodes', 'nodes',
        ['id'], ['id'],
        ondelete='CASCADE'
    )
    
    # CommentNodes
    op.drop_constraint('comment_nodes_board_id_fkey', 'comment_nodes', type_='foreignkey')
    op.drop_column('comment_nodes', 'board_id')
    op.drop_column('comment_nodes', 'x')
    op.drop_column('comment_nodes', 'y')
    op.drop_column('comment_nodes', 'width')
    op.drop_column('comment_nodes', 'height')
    op.drop_column('comment_nodes', 'created_at')
    op.drop_column('comment_nodes', 'updated_at')
    
    op.create_foreign_key(
        'comment_nodes_id_fkey',
        'comment_nodes', 'nodes',
        ['id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Revert to separate tables structure."""
    
    # 1. Add back columns to child tables
    # DataNodes
    op.drop_constraint('data_nodes_id_fkey', 'data_nodes', type_='foreignkey')
    op.add_column('data_nodes', sa.Column('board_id', sa.UUID(), nullable=True))
    op.add_column('data_nodes', sa.Column('x', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('data_nodes', sa.Column('y', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('data_nodes', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('data_nodes', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # WidgetNodes
    op.drop_constraint('widget_nodes_id_fkey', 'widget_nodes', type_='foreignkey')
    op.add_column('widget_nodes', sa.Column('board_id', sa.UUID(), nullable=True))
    op.add_column('widget_nodes', sa.Column('x', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('widget_nodes', sa.Column('y', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('widget_nodes', sa.Column('width', sa.Integer(), nullable=False, server_default='400'))
    op.add_column('widget_nodes', sa.Column('height', sa.Integer(), nullable=False, server_default='300'))
    op.add_column('widget_nodes', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('widget_nodes', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # CommentNodes
    op.drop_constraint('comment_nodes_id_fkey', 'comment_nodes', type_='foreignkey')
    op.add_column('comment_nodes', sa.Column('board_id', sa.UUID(), nullable=True))
    op.add_column('comment_nodes', sa.Column('x', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('comment_nodes', sa.Column('y', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('comment_nodes', sa.Column('width', sa.Integer(), nullable=False, server_default='300'))
    op.add_column('comment_nodes', sa.Column('height', sa.Integer(), nullable=False, server_default='150'))
    op.add_column('comment_nodes', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('comment_nodes', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # 2. Copy data back from nodes table
    op.execute("""
        UPDATE data_nodes
        SET board_id = nodes.board_id,
            x = nodes.x,
            y = nodes.y,
            created_at = nodes.created_at,
            updated_at = nodes.updated_at
        FROM nodes
        WHERE data_nodes.id = nodes.id
    """)
    
    op.execute("""
        UPDATE widget_nodes
        SET board_id = nodes.board_id,
            x = nodes.x,
            y = nodes.y,
            width = nodes.width,
            height = nodes.height,
            created_at = nodes.created_at,
            updated_at = nodes.updated_at
        FROM nodes
        WHERE widget_nodes.id = nodes.id
    """)
    
    op.execute("""
        UPDATE comment_nodes
        SET board_id = nodes.board_id,
            x = nodes.x,
            y = nodes.y,
            width = nodes.width,
            height = nodes.height,
            created_at = nodes.created_at,
            updated_at = nodes.updated_at
        FROM nodes
        WHERE comment_nodes.id = nodes.id
    """)
    
    # 3. Make columns non-nullable
    op.alter_column('data_nodes', 'board_id', nullable=False)
    op.alter_column('data_nodes', 'created_at', nullable=False)
    op.alter_column('data_nodes', 'updated_at', nullable=False)
    
    op.alter_column('widget_nodes', 'board_id', nullable=False)
    op.alter_column('widget_nodes', 'created_at', nullable=False)
    op.alter_column('widget_nodes', 'updated_at', nullable=False)
    
    op.alter_column('comment_nodes', 'board_id', nullable=False)
    op.alter_column('comment_nodes', 'created_at', nullable=False)
    op.alter_column('comment_nodes', 'updated_at', nullable=False)
    
    # 4. Re-create foreign keys
    op.create_foreign_key(
        'data_nodes_board_id_fkey',
        'data_nodes', 'boards',
        ['board_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'widget_nodes_board_id_fkey',
        'widget_nodes', 'boards',
        ['board_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'comment_nodes_board_id_fkey',
        'comment_nodes', 'boards',
        ['board_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 5. Drop nodes table
    op.drop_index('ix_nodes_node_type', table_name='nodes')
    op.drop_index('ix_nodes_board_id', table_name='nodes')
    op.drop_table('nodes')
