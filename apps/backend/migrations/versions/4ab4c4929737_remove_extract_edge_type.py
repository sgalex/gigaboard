"""remove_extract_edge_type

Revision ID: 4ab4c4929737
Revises: 067b032e50b4
Create Date: 2026-02-03 18:05:01.520060

Migration: Remove EXTRACT edge type
- Update all EXTRACT edges to TRANSFORMATION (SourceNode now inherits ContentNode)
- Remove EXTRACT from EdgeType enum
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ab4c4929737'
down_revision = '067b032e50b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Update all existing EXTRACT edges to TRANSFORMATION
    # Since SourceNode now inherits ContentNode, EXTRACT is replaced by TRANSFORMATION
    op.execute("""
        UPDATE edges 
        SET edge_type = 'TRANSFORMATION' 
        WHERE edge_type = 'EXTRACT'
    """)
    
    # Step 2: Alter enum type to remove EXTRACT
    # PostgreSQL requires recreating the enum
    op.execute("ALTER TYPE edgetype RENAME TO edgetype_old")
    op.execute("""
        CREATE TYPE edgetype AS ENUM (
            'TRANSFORMATION',
            'VISUALIZATION',
            'COMMENT',
            'DRILL_DOWN',
            'REFERENCE'
        )
    """)
    op.execute("""
        ALTER TABLE edges 
        ALTER COLUMN edge_type TYPE edgetype 
        USING edge_type::text::edgetype
    """)
    op.execute("DROP TYPE edgetype_old")


def downgrade() -> None:
    # Recreate old enum with EXTRACT
    op.execute("ALTER TYPE edgetype RENAME TO edgetype_old")
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
    op.execute("""
        ALTER TABLE edges 
        ALTER COLUMN edge_type TYPE edgetype 
        USING edge_type::text::edgetype
    """)
    op.execute("DROP TYPE edgetype_old")
    
    # Note: Cannot restore original EXTRACT edges as we don't track which were EXTRACT
    # All remain as TRANSFORMATION

