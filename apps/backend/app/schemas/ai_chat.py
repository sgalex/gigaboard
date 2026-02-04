"""
Pydantic schemas для AI Chat endpoints.

См. docs/AI_ASSISTANT.md и docs/API.md
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from ..models.chat_message import MessageRole


class AIChatRequest(BaseModel):
    """Запрос к AI Assistant"""
    message: str = Field(..., description="Сообщение от пользователя", min_length=1, max_length=10000)
    session_id: Optional[UUID] = Field(None, description="ID сессии чата (опционально)")
    context: Optional[Dict[str, Any]] = Field(None, description="Дополнительный контекст (выбранные ноды и т.д.)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Какие тренды видны в данных о продажах?",
                    "context": {
                        "selected_nodes": ["node_uuid_1", "node_uuid_2"]
                    }
                }
            ]
        }
    }


class SuggestedAction(BaseModel):
    """Предлагаемое действие от AI"""
    action: str = Field(..., description="Тип действия: create_widget, create_datanode, transform_data и т.д.")
    description: str = Field(..., description="Описание действия для пользователя")
    params: Optional[Dict[str, Any]] = Field(None, description="Параметры для выполнения действия")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "action": "create_widget",
                    "description": "Создать столбчатую диаграмму продаж по регионам",
                    "params": {
                        "type": "bar_chart",
                        "data_node_id": "uuid",
                        "config": {"x": "region", "y": "sales"}
                    }
                }
            ]
        }
    }


class AIChatResponse(BaseModel):
    """Ответ от AI Assistant"""
    response: str = Field(..., description="Текстовый ответ от AI")
    session_id: UUID = Field(..., description="ID сессии чата")
    suggested_actions: Optional[List[SuggestedAction]] = Field(None, description="Предложенные действия")
    context_used: Optional[Dict[str, Any]] = Field(None, description="Использованный контекст")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "Я вижу рост продаж в регионе 'Запад' на 25% по сравнению с предыдущим кварталом...",
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "suggested_actions": [
                        {
                            "action": "create_widget",
                            "description": "Создать график тренда для региона 'Запад'",
                            "params": {"type": "line_chart"}
                        }
                    ]
                }
            ]
        }
    }


class ChatMessageSchema(BaseModel):
    """Схема для одного сообщения в истории"""
    id: UUID
    board_id: UUID
    user_id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    context: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[SuggestedAction]] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    """Ответ с историей чата"""
    messages: List[ChatMessageSchema] = Field(..., description="Список сообщений")
    session_id: Optional[UUID] = Field(None, description="ID сессии (null если нет истории)")
    total_messages: int = Field(..., description="Общее количество сообщений в сессии")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "role": "user",
                            "content": "Проанализируй продажи",
                            "created_at": "2026-01-27T10:00:00Z"
                        }
                    ],
                    "session_id": "660e8400-e29b-41d4-a716-446655440000",
                    "total_messages": 5
                }
            ]
        }
    }
