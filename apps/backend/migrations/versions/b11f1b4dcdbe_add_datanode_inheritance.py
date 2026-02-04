"""add_datanode_inheritance

Revision ID: b11f1b4dcdbe
Revises: 007
Create Date: 2026-01-26 19:24:47.133493

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b11f1b4dcdbe'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add joined table inheritance for DataNode subtypes."""
    
    # 1. Add data_node_type discriminator column to data_nodes
    op.add_column('data_nodes', sa.Column('data_node_type', sa.String(20), nullable=True))
    
    # 2. Set default value for existing records based on source_mode
    op.execute("""
        UPDATE data_nodes 
        SET data_node_type = COALESCE(source_mode, 'text')
        WHERE data_node_type IS NULL
    """)
    
    # 3. Make data_node_type NOT NULL
    op.alter_column('data_nodes', 'data_node_type', nullable=False)
    
    # 4. Create data_nodes_text table
    op.create_table(
        'data_nodes_text',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['data_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 5. Create data_nodes_file table
    op.create_table(
        'data_nodes_file',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['data_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 6. Create data_nodes_api table
    op.create_table(
        'data_nodes_api',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_url', sa.String(1000), nullable=True),
        sa.Column('api_method', sa.String(10), nullable=True),
        sa.Column('api_headers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('api_params', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('api_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['data_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 7. Migrate existing data to appropriate child tables
    # Migrate text nodes
    op.execute("""
        INSERT INTO data_nodes_text (id, text_content, query)
        SELECT id, NULL, query
        FROM data_nodes
        WHERE data_node_type = 'text'
    """)
    
    # Migrate file nodes
    op.execute("""
        INSERT INTO data_nodes_file (id, file_name, file_path, file_type, file_size)
        SELECT id, NULL, NULL, file_type, NULL
        FROM data_nodes
        WHERE data_node_type = 'file'
    """)
    
    # Migrate API nodes
    op.execute("""
        INSERT INTO data_nodes_api (id, api_url, api_method, api_headers, api_params, api_config)
        SELECT id, NULL, NULL, NULL, NULL, api_config
        FROM data_nodes
        WHERE data_node_type = 'api'
    """)
    
    # 8. Drop old columns from data_nodes (they're now in child tables)
    op.drop_column('data_nodes', 'query')
    op.drop_column('data_nodes', 'api_config')
    op.drop_column('data_nodes', 'source_mode')
    op.drop_column('data_nodes', 'file_type')


def downgrade() -> None:
    """Reverse the inheritance migration."""
    
    # 1. Add back the removed columns
    op.add_column('data_nodes', sa.Column('query', sa.Text(), nullable=True))
    op.add_column('data_nodes', sa.Column('api_config', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('data_nodes', sa.Column('source_mode', sa.String(20), nullable=True))
    op.add_column('data_nodes', sa.Column('file_type', sa.String(20), nullable=True))
    
    # 2. Restore data from child tables
    op.execute("""
        UPDATE data_nodes dn
        SET query = dnt.query
        FROM data_nodes_text dnt
        WHERE dn.id = dnt.id
    """)
    
    op.execute("""
        UPDATE data_nodes dn
        SET file_type = dnf.file_type
        FROM data_nodes_file dnf
        WHERE dn.id = dnf.id
    """)
    
    op.execute("""
        UPDATE data_nodes dn
        SET api_config = dna.api_config
        FROM data_nodes_api dna
        WHERE dn.id = dna.id
    """)
    
    op.execute("""
        UPDATE data_nodes
        SET source_mode = data_node_type
    """)
    
    # 3. Drop child tables
    op.drop_table('data_nodes_api')
    op.drop_table('data_nodes_file')
    op.drop_table('data_nodes_text')
    
    # 4. Drop discriminator column
    op.drop_column('data_nodes', 'data_node_type')

