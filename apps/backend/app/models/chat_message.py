"""
ChatMessage model для хранения истории диалога с AI Assistant.

См. docs/AI_ASSISTANT.md
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from ..core import Base


class MessageRole(str, enum.Enum):
    """Роль отправителя сообщения"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(Base):
    """
    История сообщений AI чата в контексте доски.
    
    Attributes:
        id: UUID сообщения
        board_id: UUID доски
        user_id: UUID пользователя
        session_id: UUID сессии чата (для группировки диалогов)
        role: Роль отправителя (user/assistant/system)
        content: Текст сообщения
        context: Контекст на момент сообщения (выбранные ноды и т.д.)
        suggested_actions: Предложенные AI действия (JSON)
        created_at: Время создания
    """
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    role = Column(SQLEnum(MessageRole), nullable=False, default=MessageRole.USER)
    content = Column(Text, nullable=False)
    
    # Контекст на момент сообщения (выбранные ноды, фильтры и т.д.)
    context = Column(JSONB, nullable=True)
    
    # Предложенные действия от AI (для assistant messages)
    suggested_actions = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    board = relationship("Board", backref="chat_messages")
    user = relationship("User", backref="chat_messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role}, board_id={self.board_id})>"
