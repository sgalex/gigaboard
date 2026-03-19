"""llm_config presets and agent_llm_override (variant B)

Revision ID: 13_llm_presets
Revises: 12_sys_llm
Create Date: 2026-03-03

См. docs/LLM_CONFIGURATION_CONCEPT.md: перечень пресетов (llm_config), модель по умолчанию
(system_llm_settings.default_llm_config_id), привязки агентов (agent_llm_override).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "13_llm_presets"
down_revision: Union[str, None] = "12_sys_llm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Таблица пресетов LLM
    op.create_table(
        "llm_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="gigachat"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gigachat_model", sa.String(100), nullable=True),
        sa.Column("gigachat_scope", sa.String(100), nullable=True),
        sa.Column("gigachat_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("external_base_url", sa.String(255), nullable=True),
        sa.Column("external_default_model", sa.String(255), nullable=True),
        sa.Column("external_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("external_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Таблица привязок агент → пресет
    op.create_table(
        "agent_llm_override",
        sa.Column("agent_key", sa.String(80), nullable=False),
        sa.Column("llm_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["llm_config_id"], ["llm_config.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_key"),
    )

    # 3. Перенос данных: одна запись system_llm_settings → первый пресет в llm_config
    conn = op.get_bind()
    r = conn.execute(
        sa.text("SELECT id, provider, gigachat_model, gigachat_scope, gigachat_api_key_encrypted, "
                "external_base_url, external_default_model, external_timeout_seconds, external_api_key_encrypted, "
                "temperature, max_tokens, created_at, updated_at FROM system_llm_settings LIMIT 1")
    ).fetchone()
    if r:
        conn.execute(
            sa.text("""
                INSERT INTO llm_config (id, name, provider, sort_order,
                    gigachat_model, gigachat_scope, gigachat_api_key_encrypted,
                    external_base_url, external_default_model, external_timeout_seconds, external_api_key_encrypted,
                    temperature, max_tokens, created_at, updated_at)
                SELECT gen_random_uuid(), 'По умолчанию', provider, 0,
                    gigachat_model, gigachat_scope, gigachat_api_key_encrypted,
                    external_base_url, external_default_model, external_timeout_seconds, external_api_key_encrypted,
                    temperature, max_tokens, created_at, updated_at
                FROM system_llm_settings LIMIT 1
            """)
        )
    else:
        conn.execute(
            sa.text("""
                INSERT INTO llm_config (id, name, provider, sort_order, created_at, updated_at)
                VALUES (gen_random_uuid(), 'По умолчанию', 'gigachat', 0, now(), now())
            """)
        )
        # Если записей не было — создаём одну в старой схеме (provider обязателен)
        conn.execute(
            sa.text("""
                INSERT INTO system_llm_settings (id, provider, created_at, updated_at)
                VALUES (gen_random_uuid(), 'gigachat', now(), now())
            """)
        )

    # 4. Добавить колонку default_llm_config_id в system_llm_settings
    op.add_column(
        "system_llm_settings",
        sa.Column("default_llm_config_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    conn.execute(
        sa.text("""
            UPDATE system_llm_settings SET default_llm_config_id = (SELECT id FROM llm_config ORDER BY created_at DESC LIMIT 1)
        """)
    )
    op.create_foreign_key(
        "fk_system_llm_settings_default_llm_config_id",
        "system_llm_settings",
        "llm_config",
        ["default_llm_config_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Удалить старые колонки из system_llm_settings
    op.drop_column("system_llm_settings", "provider")
    op.drop_column("system_llm_settings", "gigachat_model")
    op.drop_column("system_llm_settings", "gigachat_scope")
    op.drop_column("system_llm_settings", "gigachat_api_key_encrypted")
    op.drop_column("system_llm_settings", "external_base_url")
    op.drop_column("system_llm_settings", "external_default_model")
    op.drop_column("system_llm_settings", "external_timeout_seconds")
    op.drop_column("system_llm_settings", "external_api_key_encrypted")
    op.drop_column("system_llm_settings", "temperature")
    op.drop_column("system_llm_settings", "max_tokens")


def downgrade() -> None:
    # Восстановить колонки в system_llm_settings (значения из default-пресета)
    op.add_column("system_llm_settings", sa.Column("provider", sa.String(50), nullable=True))
    op.add_column("system_llm_settings", sa.Column("gigachat_model", sa.String(100), nullable=True))
    op.add_column("system_llm_settings", sa.Column("gigachat_scope", sa.String(100), nullable=True))
    op.add_column("system_llm_settings", sa.Column("gigachat_api_key_encrypted", sa.String(), nullable=True))
    op.add_column("system_llm_settings", sa.Column("external_base_url", sa.String(255), nullable=True))
    op.add_column("system_llm_settings", sa.Column("external_default_model", sa.String(255), nullable=True))
    op.add_column("system_llm_settings", sa.Column("external_timeout_seconds", sa.Integer(), nullable=True))
    op.add_column("system_llm_settings", sa.Column("external_api_key_encrypted", sa.String(), nullable=True))
    op.add_column("system_llm_settings", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("system_llm_settings", sa.Column("max_tokens", sa.Integer(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE system_llm_settings s SET
                provider = c.provider,
                gigachat_model = c.gigachat_model,
                gigachat_scope = c.gigachat_scope,
                gigachat_api_key_encrypted = c.gigachat_api_key_encrypted,
                external_base_url = c.external_base_url,
                external_default_model = c.external_default_model,
                external_timeout_seconds = c.external_timeout_seconds,
                external_api_key_encrypted = c.external_api_key_encrypted,
                temperature = c.temperature,
                max_tokens = c.max_tokens
            FROM llm_config c
            WHERE s.default_llm_config_id = c.id
        """)
    )
    op.drop_constraint(
        "fk_system_llm_settings_default_llm_config_id",
        "system_llm_settings",
        type_="foreignkey",
    )
    op.drop_column("system_llm_settings", "default_llm_config_id")

    op.drop_table("agent_llm_override")
    op.drop_table("llm_config")
