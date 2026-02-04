"""Add EXTRACT edge type to enum

Revision ID: 006
Revises: 005
Create Date: 2026-01-31

"""
from alembic import op

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add EXTRACT to EdgeType enum."""
    
    # PostgreSQL: need to recreate enum type
    # First, alter column to text
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE VARCHAR(50)")
    
    # Drop old enum type
    op.execute("DROP TYPE IF EXISTS edgetype")
    
    # Create new enum type with EXTRACT added
    op.execute("""
        CREATE TYPE edgetype AS ENUM (
            'EXTRACT',
            'TRANSFORMATION',
            'VISUALIZATION', 
            'COMMENT',
            'DRILL_DOWN',
            'REFERENCE'
        )
    """)
    
    # Alter column back to enum type
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE edgetype USING edge_type::edgetype")


def downgrade() -> None:
    """Remove EXTRACT from EdgeType enum."""
    
    # Alter column to text
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE VARCHAR(50)")
    
    # Drop new enum type
    op.execute("DROP TYPE IF EXISTS edgetype")
    
    # Recreate old enum type without EXTRACT
    op.execute("""
        CREATE TYPE edgetype AS ENUM (
            'TRANSFORMATION',
            'VISUALIZATION', 
            'COMMENT',
            'DRILL_DOWN',
            'REFERENCE'
        )
    """)
    
    # Alter column back to enum
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE edgetype USING edge_type::edgetype")
