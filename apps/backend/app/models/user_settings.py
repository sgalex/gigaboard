from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.core import Base


class UserSecret(Base):
    """
    Хранилище пользовательских секретов (API-ключи и т.п.).

    На уровне модели мы храним только зашифрованное значение и минимальные метаданные.
    Детали шифрования инкапсулируются в сервисном слое.
    """

    __tablename__ = "user_secrets"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Тип секрета, напр.: "external_llm_api_key"
    type = Column(String(100), nullable=False, index=True)
    # Опциональный идентификатор провайдера/сервиса (напр. "openai", "deepseek")
    provider = Column(String(100), nullable=True)
    # Зашифрованное значение секрета (формат и способ шифрования определяются в сервисе)
    encrypted_value = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="secrets")

    def __repr__(self) -> str:
        return f"<UserSecret(id={self.id}, user_id={self.user_id}, type={self.type})>"


class UserAISettings(Base):
    """
    Персональные AI/LLM-настройки пользователя.

    Эти настройки задают дефолтный провайдер и модель для Multi-Agent системы.
    """

    __tablename__ = "user_ai_settings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # "gigachat" | "external_openai_compat"
    provider = Column(String(50), nullable=False, default="gigachat")

    # GigaChat: модель, scope и опционально пользовательский API-ключ
    gigachat_model = Column(String(100), nullable=True)
    gigachat_scope = Column(String(100), nullable=True)
    gigachat_api_key_secret_id = Column(
        PGUUID(as_uuid=True), ForeignKey("user_secrets.id"), nullable=True
    )

    # Внешний OpenAI-совместимый провайдер
    external_base_url = Column(String(255), nullable=True)
    external_default_model = Column(String(255), nullable=True)
    external_timeout_seconds = Column(Integer, nullable=True)
    external_api_key_secret_id = Column(
        PGUUID(as_uuid=True), ForeignKey("user_secrets.id"), nullable=True
    )

    # Общие параметры генерации (temperature: 0.0–1.0)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)

    # Произвольные пользовательские предпочтения (язык, стиль и т.п.)
    preferred_style = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="ai_settings")
    external_api_key_secret = relationship(
        "UserSecret",
        foreign_keys=[external_api_key_secret_id],
    )

    def __repr__(self) -> str:
        return f"<UserAISettings(user_id={self.user_id}, provider={self.provider})>"


class LLMConfig(Base):
    """
    Один LLM-пресет: имя, провайдер, реквизиты (ключи, base URL, модель и т.д.).
    Администратор создаёт/редактирует пресеты; модель по умолчанию и привязки агентов
    задаются в system_llm_settings и agent_llm_override. См. docs/LLM_CONFIGURATION_CONCEPT.md.
    """

    __tablename__ = "llm_config"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False, default="gigachat")
    sort_order = Column(Integer, nullable=False, default=0)

    gigachat_model = Column(String(100), nullable=True)
    gigachat_scope = Column(String(100), nullable=True)
    gigachat_api_key_encrypted = Column(String, nullable=True)

    external_base_url = Column(String(255), nullable=True)
    external_default_model = Column(String(255), nullable=True)
    external_timeout_seconds = Column(Integer, nullable=True)
    external_api_key_encrypted = Column(String, nullable=True)

    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<LLMConfig(id={self.id}, name={self.name!r}, provider={self.provider})>"


class AgentLLMOverride(Base):
    """
    Привязка агента к LLM-пресету. Если для agent_key есть запись — агент использует
    указанный пресет; иначе используется default из system_llm_settings.
    """

    __tablename__ = "agent_llm_override"

    agent_key = Column(String(80), primary_key=True)
    llm_config_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("llm_config.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    llm_config = relationship("LLMConfig", backref="agent_overrides")

    def __repr__(self) -> str:
        return f"<AgentLLMOverride(agent_key={self.agent_key!r}, llm_config_id={self.llm_config_id})>"


class SystemLLMSettings(Base):
    """
    Системные настройки LLM (одна запись на инстанс).
    Хранит только ссылку на пресет по умолчанию. Привязки агентов — в agent_llm_override.
    Редактирует только администратор. См. docs/ADMIN_AND_SYSTEM_LLM.md, LLM_CONFIGURATION_CONCEPT.md.
    """

    __tablename__ = "system_llm_settings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    default_llm_config_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("llm_config.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    default_llm_config = relationship("LLMConfig", foreign_keys=[default_llm_config_id])

    def __repr__(self) -> str:
        return f"<SystemLLMSettings(default_llm_config_id={self.default_llm_config_id})>"

