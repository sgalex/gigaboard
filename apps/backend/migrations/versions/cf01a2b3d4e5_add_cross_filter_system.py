"""add_cross_filter_system

Revision ID: cf01a2b3d4e5
Revises: 65bcfd971f8b
Create Date: 2026-02-27 21:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY

# revision identifiers, used by Alembic.
revision = 'cf01a2b3d4e5'
down_revision = '65bcfd971f8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add settings JSONB to boards table
    op.add_column('boards', sa.Column('settings', JSONB, nullable=True))

    # 2. Create dimensions table
    op.create_table(
        'dimensions',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID, sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('dim_type', sa.String(20), nullable=False, server_default='string'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('known_values', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dimensions_project_id', 'dimensions', ['project_id'])
    op.create_unique_constraint('uq_dimension_project_name', 'dimensions', ['project_id', 'name'])

    # 3. Create dimension_column_mappings table
    op.create_table(
        'dimension_column_mappings',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dimension_id', UUID, sa.ForeignKey('dimensions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', UUID, sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('table_name', sa.String(200), nullable=False),
        sa.Column('column_name', sa.String(200), nullable=False),
        sa.Column('mapping_source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('confidence', sa.Float, server_default='1.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dim_mappings_dimension_id', 'dimension_column_mappings', ['dimension_id'])
    op.create_index('ix_dim_mappings_node_id', 'dimension_column_mappings', ['node_id'])
    op.create_index(
        'ix_dim_mappings_composite',
        'dimension_column_mappings',
        ['dimension_id', 'node_id', 'table_name'],
    )
    op.create_unique_constraint(
        'uq_dim_mapping_unique',
        'dimension_column_mappings',
        ['dimension_id', 'node_id', 'table_name', 'column_name'],
    )

    # 4. Create filter_presets table
    op.create_table(
        'filter_presets',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID, sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('filters', JSONB, nullable=False),
        sa.Column('scope', sa.String(50), nullable=False, server_default='project'),
        sa.Column('target_id', UUID, nullable=True),
        sa.Column('is_default', sa.Boolean, server_default='false', nullable=False),
        sa.Column('tags', ARRAY(sa.String), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_filter_presets_project_id', 'filter_presets', ['project_id'])


def downgrade() -> None:
    op.drop_table('filter_presets')
    op.drop_table('dimension_column_mappings')
    op.drop_table('dimensions')
    op.drop_column('boards', 'settings')
