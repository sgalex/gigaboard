"""Update EdgeType enum with new values

Revision ID: 005
Revises: 004
Create Date: 2026-01-24

"""
from alembic import op

# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new EdgeType values and remove old ones."""
    
    # PostgreSQL: need to recreate enum type
    # First, alter column to text
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE VARCHAR(50)")
    
    # Drop old enum type
    op.execute("DROP TYPE IF EXISTS edgetype")
    
    # Create new enum type with new values
    op.execute("""
        CREATE TYPE edgetype AS ENUM (
            'TRANSFORMATION',
            'VISUALIZATION', 
            'COMMENT',
            'DRILL_DOWN',
            'REFERENCE'
        )
    """)
    
    # Update existing edges to new type (if any exist, convert them)
    op.execute("UPDATE edges SET edge_type = 'REFERENCE' WHERE edge_type = 'DATA_FLOW'")
    op.execute("UPDATE edges SET edge_type = 'REFERENCE' WHERE edge_type = 'DEPENDENCY'")
    
    # Alter column back to enum type
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE edgetype USING edge_type::edgetype")


def downgrade() -> None:
    """Revert to old EdgeType values."""
    
    # Alter column to text
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE VARCHAR(50)")
    
    # Drop new enum type
    op.execute("DROP TYPE IF EXISTS edgetype")
    
    # Recreate old enum type
    op.execute("""
        CREATE TYPE edgetype AS ENUM (
            'DATA_FLOW',
            'DEPENDENCY'
        )
    """)
    
    # Convert values back
    op.execute("UPDATE edges SET edge_type = 'DATA_FLOW' WHERE edge_type IN ('TRANSFORMATION', 'VISUALIZATION', 'REFERENCE')")
    op.execute("UPDATE edges SET edge_type = 'DEPENDENCY' WHERE edge_type IN ('COMMENT', 'DRILL_DOWN')")
    
    # Alter column back to enum
    op.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE edgetype USING edge_type::edgetype")
