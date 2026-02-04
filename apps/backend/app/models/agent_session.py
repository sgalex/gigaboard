"""
AgentSession model - отслеживание сессий Multi-Agent обработки.

Каждая сессия представляет один запрос пользователя, который может быть
разбит на несколько задач, обрабатываемых разными агентами.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
import enum

from app.core import Base


class AgentSessionStatus(enum.Enum):
    """Статусы сессии обработки."""
    PENDING = "pending"           # Создана, ожидает обработки
    PLANNING = "planning"         # Planner Agent разбивает на задачи
    PROCESSING = "processing"     # Агенты обрабатывают задачи
    AGGREGATING = "aggregating"   # Orchestrator собирает результаты
    COMPLETED = "completed"       # Успешно завершена
    FAILED = "failed"            # Завершена с ошибкой
    CANCELLED = "cancelled"      # Отменена пользователем


class AgentSession(Base):
    """
    Сессия Multi-Agent обработки запроса пользователя.
    
    Attributes:
        id: UUID сессии
        user_id: UUID пользователя
        board_id: UUID доски (контекст)
        chat_session_id: ID чат-сессии (для связи с ChatMessage)
        user_message: Исходный запрос пользователя
        status: Текущий статус обработки
        plan: JSON с планом задач от Planner Agent
        current_task_index: Индекс текущей обрабатываемой задачи
        results: JSON с результатами от агентов
        final_response: Финальный ответ пользователю
        error_message: Сообщение об ошибке (если status=failed)
        selected_node_ids: JSON список выбранных нод (контекст)
        metadata: Дополнительные метаданные
        created_at: Время создания
        updated_at: Время последнего обновления
        completed_at: Время завершения
    """
    __tablename__ = "agent_sessions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    board_id = Column(PGUUID(as_uuid=True), ForeignKey("boards.id"), nullable=False, index=True)
    chat_session_id = Column(String(255), nullable=True, index=True)  # Для связи с AI chat
    
    # Запрос пользователя
    user_message = Column(Text, nullable=False)
    
    # Статус обработки
    status = Column(
        SQLEnum(AgentSessionStatus, name="agent_session_status"),
        default=AgentSessionStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # План выполнения (от Planner Agent)
    # Пример: {"tasks": [{"type": "query_data", "agent": "analyst", "params": {...}}, ...]}
    plan = Column(JSON, nullable=True)
    
    # Текущая задача (индекс в plan.tasks)
    current_task_index = Column(Integer, default=0, nullable=False)
    
    # Результаты от агентов
    # Пример: {"task_0": {"agent": "analyst", "result": {...}, "status": "completed"}, ...}
    results = Column(JSON, nullable=True)
    
    # Финальный ответ пользователю
    final_response = Column(Text, nullable=True)
    
    # Ошибка (если есть)
    error_message = Column(Text, nullable=True)
    
    # Контекст: выбранные ноды
    selected_node_ids = Column(JSON, nullable=True)  # ["uuid1", "uuid2", ...]
    
    # Дополнительные метаданные (не 'metadata' - зарезервировано в SQLAlchemy)
    # Пример: {"agent_timings": {"planner": 1.2, "analyst": 3.5}, "retry_count": 0}
    session_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="agent_sessions")
    board = relationship("Board", back_populates="agent_sessions")
    
    def __repr__(self):
        return f"<AgentSession(id={self.id}, status={self.status.value}, board_id={self.board_id})>"
    
    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "board_id": str(self.board_id),
            "chat_session_id": self.chat_session_id,
            "user_message": self.user_message,
            "status": self.status.value,
            "plan": self.plan,
            "current_task_index": self.current_task_index,
            "results": self.results,
            "final_response": self.final_response,
            "error_message": self.error_message,
            "selected_node_ids": self.selected_node_ids,
            "session_metadata": self.session_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
