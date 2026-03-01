"""add_dashboard_system_tables

Revision ID: 65bcfd971f8b
Revises: 4ab4c4929737
Create Date: 2026-02-26 17:25:17.018015

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = '65bcfd971f8b'
down_revision = '4ab4c4929737'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- project_widgets ---
    op.create_table(
        'project_widgets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('html_code', sa.Text, nullable=True),
        sa.Column('css_code', sa.Text, nullable=True),
        sa.Column('js_code', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('source_widget_node_id', UUID(as_uuid=True), sa.ForeignKey('widget_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_content_node_id', UUID(as_uuid=True), sa.ForeignKey('content_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_board_id', UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='SET NULL'), nullable=True),
        sa.Column('config', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_project_widgets_project_id', 'project_widgets', ['project_id'])

    # --- project_tables ---
    op.create_table(
        'project_tables',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('columns', JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('sample_data', JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('row_count', sa.Integer, server_default=sa.text('0'), nullable=False),
        sa.Column('source_content_node_id', UUID(as_uuid=True), sa.ForeignKey('content_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_board_id', UUID(as_uuid=True), sa.ForeignKey('boards.id', ondelete='SET NULL'), nullable=True),
        sa.Column('table_name_in_node', sa.String(255), nullable=True),
        sa.Column('config', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_project_tables_project_id', 'project_tables', ['project_id'])

    # --- dashboards ---
    op.create_table(
        'dashboards',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('settings', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dashboards_project_id', 'dashboards', ['project_id'])

    # --- dashboard_items ---
    op.create_table(
        'dashboard_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dashboard_id', UUID(as_uuid=True), sa.ForeignKey('dashboards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_type', sa.String(50), nullable=False),
        sa.Column('source_id', UUID(as_uuid=True), nullable=True),
        sa.Column('layout', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('overrides', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('content', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('z_index', sa.Integer, server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dashboard_items_dashboard_id', 'dashboard_items', ['dashboard_id'])

    # --- dashboard_shares ---
    op.create_table(
        'dashboard_shares',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dashboard_id', UUID(as_uuid=True), sa.ForeignKey('dashboards.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('share_type', sa.String(20), server_default=sa.text("'public'"), nullable=False),
        sa.Column('share_token', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('max_views', sa.Integer, nullable=True),
        sa.Column('branding', JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('view_count', sa.Integer, server_default=sa.text('0'), nullable=False),
        sa.Column('allow_download', sa.Boolean, server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dashboard_shares_share_token', 'dashboard_shares', ['share_token'], unique=True)


def downgrade() -> None:
    op.drop_table('dashboard_shares')
    op.drop_table('dashboard_items')
    op.drop_table('dashboards')
    op.drop_table('project_tables')
    op.drop_table('project_widgets')
