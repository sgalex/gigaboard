"""remove_legacy_datanode_tables

Revision ID: a97be50bb15e
Revises: e309ca5dd53a
Create Date: 2026-01-31 12:37:49.925169

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a97be50bb15e'
down_revision = 'e309ca5dd53a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Удаление legacy DataNode таблиц.
    
    DataNode заменён на Source-Content Node Architecture.
    См. docs/SOURCE_CONTENT_NODE_CONCEPT.md
    """
    # Удаляем подтипы DataNode (порядок важен из-за FK)
    op.drop_table('data_nodes_api')
    op.drop_table('data_nodes_file')
    op.drop_table('data_nodes_text')
    # Удаляем базовую таблицу DataNode
    op.drop_table('data_nodes')


def downgrade() -> None:
    """Откат невозможен - DataNode полностью удалён из кодовой базы."""
    raise NotImplementedError(
        "Cannot rollback DataNode removal - code has been deleted. "
        "Use backup to restore if needed."
    )
