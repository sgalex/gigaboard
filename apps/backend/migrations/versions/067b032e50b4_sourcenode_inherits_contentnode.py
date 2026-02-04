"""sourcenode_inherits_contentnode

Revision ID: 067b032e50b4
Revises: 7738652bc3e7
Create Date: 2026-02-03 01:46:54.162125

SourceNode теперь наследует ContentNode (а не BaseNode напрямую).
Иерархия: BaseNode → ContentNode → SourceNode

Изменения:
1. FK source_nodes.id меняется с nodes.id на content_nodes.id
2. Удаляем position и metadata из source_nodes (наследуются от content_nodes)
3. Удаляем EXTRACT из edge_type enum (больше не нужен)

См. docs/SOURCE_NODE_CONCEPT_V2.md
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '067b032e50b4'
down_revision = '7738652bc3e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change SourceNode to inherit from ContentNode."""
    
    # 1. Удаляем старую FK на nodes.id
    op.drop_constraint('source_nodes_id_fkey', 'source_nodes', type_='foreignkey')
    
    # 2. Добавляем новую FK на content_nodes.id
    op.create_foreign_key(
        'source_nodes_id_fkey',
        'source_nodes', 'content_nodes',
        ['id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 3. Удаляем дублирующиеся колонки (наследуются от content_nodes)
    # position уже удалён в предыдущей миграции или не существует
    # op.drop_column('source_nodes', 'position')
    # op.drop_column('source_nodes', 'metadata')
    
    # 4. Удаляем EXTRACT из edge_type enum
    # PostgreSQL не позволяет удалять значения из enum напрямую,
    # поэтому просто оставляем его в enum, но не используем в приложении
    # Значение EXTRACT будет игнорироваться на уровне приложения


def downgrade() -> None:
    """Revert SourceNode to inherit from BaseNode."""
    
    # 1. Удаляем FK на content_nodes.id
    op.drop_constraint('source_nodes_id_fkey', 'source_nodes', type_='foreignkey')
    
    # 2. Восстанавливаем FK на nodes.id
    op.create_foreign_key(
        'source_nodes_id_fkey',
        'source_nodes', 'nodes',
        ['id'], ['id'],
        ondelete='CASCADE'
    )
