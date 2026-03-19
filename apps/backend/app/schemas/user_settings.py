from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class LLMProvider(str, Enum):
    GIGACHAT = "gigachat"
    EXTERNAL_OPENAI_COMPAT = "external_openai_compat"


class ExternalOpenAISettings(BaseModel):
    base_url: HttpUrl | str = Field(
        default="https://api.openai.com/v1",
        description="Базовый URL OpenAI-совместимого API",
    )
    default_model: str = Field(
        default="gpt-4.1-mini",
        description="Имя модели по умолчанию (например, gpt-4.1, deepseek-chat, groq/llama-3)",
        min_length=1,
        max_length=255,
    )
    timeout_seconds: Optional[int] = Field(
        default=60,
        ge=1,
        le=600,
        description="Таймаут запросов к внешнему LLM",
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Креативность ответов модели",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=32768,
        description="Максимальное количество токенов в ответе",
    )


class UserAISettingsResponse(BaseModel):
    user_id: UUID
    provider: LLMProvider

    # GigaChat
    gigachat_model: Optional[str] = None
    gigachat_scope: Optional[str] = None
    has_gigachat_api_key: bool = False

    # Внешний провайдер
    external_base_url: Optional[str] = None
    external_default_model: Optional[str] = None
    external_timeout_seconds: Optional[int] = None

    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # Флаг наличия сохранённого внешнего API-ключа
    has_external_api_key: bool = False

    # Произвольные пользовательские предпочтения (язык, стиль и т.п.)
    preferred_style: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class UserAISettingsUpdate(BaseModel):
    provider: LLMProvider = Field(
        default=LLMProvider.GIGACHAT,
        description='Выбранный провайдер LLM: "gigachat" или "external_openai_compat"',
    )

    # GigaChat
    gigachat_model: Optional[str] = Field(
        default=None,
        description="Имя модели GigaChat (GigaChat, GigaChat-Pro, GigaChat-Max и т.д.)",
        max_length=100,
    )
    gigachat_scope: Optional[str] = Field(
        default=None,
        description="Scope доступа GigaChat (GIGACHAT_API_PERS, GIGACHAT_API_CORP и т.п.)",
        max_length=100,
    )
    gigachat_api_key: Optional[str] = Field(
        default=None,
        description="API-ключ GigaChat (write-only). Пусто = использовать системный ключ.",
        min_length=1,
        max_length=4096,
    )

    # Внешний провайдер
    external_base_url: Optional[str] = Field(
        default=None,
        description="Базовый URL OpenAI-совместимого API",
        max_length=255,
    )
    external_default_model: Optional[str] = Field(
        default=None,
        description="Имя модели по умолчанию",
        max_length=255,
    )
    external_timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=600,
        description="Таймаут запросов к внешнему LLM",
    )

    # Новый/обновлённый внешний API-ключ (write-only)
    external_api_key: Optional[str] = Field(
        default=None,
        description="API-ключ внешнего OpenAI-совместимого провайдера. Не возвращается в ответе.",
        min_length=1,
        max_length=4096,
    )

    # Общие параметры генерации
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Креативность ответов модели",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=32768,
        description="Максимальное количество токенов в ответе",
    )

    preferred_style: Optional[dict[str, Any]] = Field(
        default=None,
        description="Дополнительные пользовательские предпочтения (язык, тон, формат ответов и т.п.)",
    )


class UserAISettingsTestRequest(BaseModel):
    """
    Запрос для тестирования подключения к выбранному провайдеру.

    Можно переопределить часть настроек профиля (например, попробовать новый ключ или модель),
    не сохраняя их сразу.
    """

    provider: Optional[LLMProvider] = None
    gigachat_api_key: Optional[str] = None
    gigachat_model: Optional[str] = None
    gigachat_scope: Optional[str] = None
    external_base_url: Optional[str] = None
    external_default_model: Optional[str] = None
    external_timeout_seconds: Optional[int] = None
    external_api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class GigaChatModelInfo(BaseModel):
    """Один элемент списка доступных моделей GigaChat."""

    id: str
    name: str
    description: Optional[str] = None


class UserAISettingsTestResponse(BaseModel):
    ok: bool
    provider: LLMProvider
    message: str
    details: Optional[dict[str, Any]] = None


# --- Модели LLM и системные настройки (только для администратора) ---
# См. docs/LLM_CONFIGURATION_CONCEPT.md


class LLMConfigResponse(BaseModel):
    """Одна настроенная модель LLM (без раскрытия ключей)."""

    id: UUID
    name: str
    provider: LLMProvider
    sort_order: int = 0
    gigachat_model: Optional[str] = None
    gigachat_scope: Optional[str] = None
    has_gigachat_api_key: bool = False
    external_base_url: Optional[str] = None
    external_default_model: Optional[str] = None
    external_timeout_seconds: Optional[int] = None
    has_external_api_key: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    class Config:
        from_attributes = True


class LLMConfigCreate(BaseModel):
    """Создание модели LLM."""

    name: str = Field(..., min_length=1, max_length=100)
    provider: LLMProvider = LLMProvider.GIGACHAT
    sort_order: int = 0
    gigachat_model: Optional[str] = None
    gigachat_scope: Optional[str] = None
    gigachat_api_key: Optional[str] = None
    external_base_url: Optional[str] = None
    external_default_model: Optional[str] = None
    external_timeout_seconds: Optional[int] = None
    external_api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class LLMConfigUpdate(BaseModel):
    """Обновление модели LLM (все поля опциональны)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider: Optional[LLMProvider] = None
    sort_order: Optional[int] = None
    gigachat_model: Optional[str] = None
    gigachat_scope: Optional[str] = None
    gigachat_api_key: Optional[str] = None
    external_base_url: Optional[str] = None
    external_default_model: Optional[str] = None
    external_timeout_seconds: Optional[int] = None
    external_api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class SystemLLMSettingsResponse(BaseModel):
    """Системные настройки: модель по умолчанию и списки для UI."""

    default_llm_config_id: Optional[UUID] = None
    configs: list[LLMConfigResponse] = Field(default_factory=list)
    agent_overrides: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Список {agent_key, llm_config_id}",
    )

    class Config:
        from_attributes = True


class SystemLLMSettingsUpdate(BaseModel):
    """Обновление только модели по умолчанию."""

    default_llm_config_id: Optional[UUID] = None


class AgentLLMOverrideItem(BaseModel):
    """Одна привязка агент → модель."""

    agent_key: str
    llm_config_id: UUID


class AgentLLMOverridesSet(BaseModel):
    """Установить привязки (полная замена). Пустой llm_config_id = снять привязку не передаём."""

    overrides: list[AgentLLMOverrideItem] = Field(default_factory=list)


class SystemLLMPlaygroundRunRequest(BaseModel):
    """Запрос на запуск мультиагента в Playground."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    chat_history: list[dict[str, str]] | None = Field(
        default=None,
        description="История сообщений чата для контекста (role, content).",
    )

