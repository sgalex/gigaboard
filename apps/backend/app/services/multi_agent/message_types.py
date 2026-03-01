"""
Message types и схемы для Multi-Agent коммуникации.

V2: AgentMessage.to_agent_payload() для десериализации AgentPayload из payload.
См. docs/MULTI_AGENT_V2_CONCEPT.md, docs/MULTI_AGENT_SYSTEM.md
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Типы сообщений в Multi-Agent системе."""
    
    # Основные типы
    USER_REQUEST = "user_request"           # Orchestrator → Planner: запрос пользователя
    TASK_REQUEST = "task_request"           # Planner → Agent: делегирование задачи
    TASK_RESULT = "task_result"             # Agent → Orchestrator/Planner: результат выполнения
    TASK_PROGRESS = "task_progress"         # Agent → UI: прогресс выполнения
    
    # Межагентные запросы
    AGENT_QUERY = "agent_query"             # Agent → Agent: запрос данных
    AGENT_RESPONSE = "agent_response"       # Agent → Agent: ответ на запрос
    
    # Служебные
    ACKNOWLEDGEMENT = "acknowledgement"     # Подтверждение получения
    ERROR = "error"                         # Agent → Orchestrator: ошибка
    
    # UI уведомления
    SUGGESTED_ACTIONS = "suggested_actions" # Agent → UI: предложения действий
    NODE_CREATED = "node_created"           # Agent → UI: создан новый узел
    UI_NOTIFICATION = "ui_notification"     # Orchestrator → UI: уведомление


class AgentMessage(BaseModel):
    """
    Универсальное сообщение для коммуникации между агентами.
    
    Примеры использования см. в docs/MESSAGE_BUS_QUICKSTART.md
    """
    
    # Идентификация
    message_id: str = Field(..., description="Уникальный ID сообщения (UUID)")
    message_type: MessageType = Field(..., description="Тип сообщения")
    parent_message_id: Optional[str] = Field(None, description="ID родительского сообщения (для цепочек)")
    
    # Маршрутизация
    sender: str = Field(..., description="Имя отправителя (agent name или 'orchestrator')")
    receiver: str = Field(..., description="Имя получателя ('broadcast', agent name, или 'orchestrator')")
    
    # Контекст
    session_id: str = Field(..., description="ID сессии пользователя")
    board_id: str = Field(..., description="ID доски")
    
    # Данные
    payload: Dict[str, Any] = Field(default_factory=dict, description="Полезная нагрузка")
    
    # Метаданные
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")
    requires_acknowledgement: bool = Field(default=False, description="Требуется ли ACK")
    timeout_seconds: Optional[int] = Field(None, description="Таймаут ожидания ответа (секунды)")
    
    # Retry логика
    retry_count: int = Field(default=0, description="Количество повторов отправки")
    max_retries: int = Field(default=3, description="Максимальное количество повторов")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "message_id": "123e4567-e89b-12d3-a456-426614174000",
                "message_type": "user_request",
                "parent_message_id": None,
                "sender": "orchestrator",
                "receiver": "broadcast",
                "session_id": "session_123",
                "board_id": "board_456",
                "payload": {
                    "message": "Создай график продаж по регионам",
                    "board_context": {
                        "nodes": [],
                        "edges": []
                    }
                },
                "timestamp": "2026-01-27T10:00:00Z",
                "requires_acknowledgement": False,
                "timeout_seconds": 30,
                "retry_count": 0,
                "max_retries": 3
            }
        }

    # ------------------------------------------------------------------
    # V2: AgentPayload десериализация
    # ------------------------------------------------------------------

    def to_agent_payload(self) -> "AgentPayload":
        """Извлечь AgentPayload из payload TASK_RESULT сообщения.

        Ожидаемая структура payload::

            {
                "status": "success",
                "result": { ... AgentPayload dict ... },
                "execution_time": 1.23,
                "agent": "analyst"
            }

        Если ``result`` содержит поле ``status`` — это AgentPayload dict.
        Иначе оборачивает весь ``result`` в AgentPayload.success() для
        обратной совместимости с V1 агентами.
        """
        from .schemas.agent_payload import AgentPayload as AP

        result = self.payload.get("result", self.payload)

        # V2 формат: result уже содержит AgentPayload fields
        if isinstance(result, dict) and "status" in result and "agent" in result:
            return AP.model_validate(result)

        # V1 fallback: оборачиваем в AgentPayload
        return AP.success(
            agent=self.payload.get("agent", self.sender),
            metadata={"legacy_result": result},
        )


class AcknowledgementMessage(BaseModel):
    """Подтверждение получения сообщения."""
    
    original_message_id: str
    agent_name: str
    received_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = Field(default="received")  # received, processing, completed
