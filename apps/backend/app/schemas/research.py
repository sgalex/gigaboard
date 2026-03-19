"""
Pydantic schemas для Research Chat API.

POST /api/v1/research/chat — чат исследования (ResearchSourceDialog).
См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResearchChatMessage(BaseModel):
    """Одно сообщение в истории чата."""
    role: str = Field(..., description="user | assistant")
    content: str = Field(..., description="Текст сообщения")


class ResearchChatRequest(BaseModel):
    """Запрос к Research Chat."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=15000,
        description="Сообщение пользователя (запрос на исследование)",
    )
    session_id: Optional[str] = Field(None, description="ID сессии (если нет — создаётся новая)")
    chat_history: Optional[list[ResearchChatMessage]] = Field(
        default_factory=list,
        description="История сообщений для контекста",
    )


class ResearchSourceRef(BaseModel):
    """Ссылка на источник (URL + title)."""
    url: str = Field(..., description="URL страницы")
    title: str = Field(..., description="Заголовок или домен")


class ResearchChatResponse(BaseModel):
    """Ответ Research Chat: narrative, tables, sources."""
    narrative: str = Field(..., description="Текстовый итог исследования")
    tables: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Извлечённые таблицы (name, columns, rows)",
    )
    sources: list[ResearchSourceRef] = Field(
        default_factory=list,
        description="Источники (URL, title)",
    )
    session_id: str = Field(..., description="ID сессии")
    execution_time_ms: Optional[int] = Field(None, description="Время выполнения, мс")
    plan: Optional[dict[str, Any]] = Field(None, description="План выполнения (опционально)")
