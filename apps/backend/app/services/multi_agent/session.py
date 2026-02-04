"""
AgentSessionManager - управление сессиями Multi-Agent обработки.

Отвечает за CRUD операции и lifecycle management сессий.
"""
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentSession, AgentSessionStatus

logger = logging.getLogger(__name__)


class AgentSessionManager:
    """Manager для работы с AgentSession."""
    
    def __init__(self, db: AsyncSession):
        """
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
    
    async def create_session(
        self,
        user_id: UUID,
        board_id: UUID,
        user_message: str,
        chat_session_id: Optional[str] = None,
        selected_node_ids: Optional[List[UUID]] = None,
        session_metadata: Optional[dict] = None,
    ) -> AgentSession:
        """
        Создать новую сессию обработки.
        
        Args:
            user_id: ID пользователя
            board_id: ID доски
            user_message: Запрос пользователя
            chat_session_id: ID чат-сессии (опционально)
            selected_node_ids: Выбранные ноды (контекст)
            session_metadata: Дополнительные метаданные
            
        Returns:
            AgentSession: Созданная сессия
        """
        session = AgentSession(
            user_id=user_id,
            board_id=board_id,
            user_message=user_message,
            chat_session_id=chat_session_id,
            status=AgentSessionStatus.PENDING,
            selected_node_ids=[str(nid) for nid in selected_node_ids] if selected_node_ids else None,
            session_metadata=session_metadata or {},
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"✅ Created AgentSession {session.id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: UUID) -> Optional[AgentSession]:
        """
        Получить сессию по ID.
        
        Args:
            session_id: ID сессии
            
        Returns:
            AgentSession или None
        """
        result = await self.db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        session_id: UUID,
        status: AgentSessionStatus,
        error_message: Optional[str] = None,
    ) -> Optional[AgentSession]:
        """
        Обновить статус сессии.
        
        Args:
            session_id: ID сессии
            status: Новый статус
            error_message: Сообщение об ошибке (опционально)
            
        Returns:
            AgentSession или None
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"⚠️ Session {session_id} not found")
            return None
        
        session.status = status
        session.updated_at = datetime.utcnow()
        
        if error_message:
            session.error_message = error_message
        
        if status in [AgentSessionStatus.COMPLETED, AgentSessionStatus.FAILED, AgentSessionStatus.CANCELLED]:
            session.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"✅ Updated AgentSession {session_id} status to {status.value}")
        return session
    
    async def update_plan(
        self,
        session_id: UUID,
        plan: dict,
    ) -> Optional[AgentSession]:
        """
        Сохранить план выполнения от Planner Agent.
        
        Args:
            session_id: ID сессии
            plan: План задач (JSON)
            
        Returns:
            AgentSession или None
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.plan = plan
        session.status = AgentSessionStatus.PROCESSING
        session.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"✅ Updated plan for AgentSession {session_id}")
        return session
    
    async def update_results(
        self,
        session_id: UUID,
        task_index: int,
        result: dict,
    ) -> Optional[AgentSession]:
        """
        Добавить результат выполнения задачи.
        
        Args:
            session_id: ID сессии
            task_index: Индекс задачи
            result: Результат от агента
            
        Returns:
            AgentSession или None
        """
        from sqlalchemy.orm.attributes import flag_modified
        
        session = await self.get_session(session_id)
        if not session:
            return None
        
        if session.results is None:
            session.results = {}
        
        session.results[f"task_{task_index}"] = result
        session.current_task_index = task_index + 1
        session.updated_at = datetime.utcnow()
        
        # CRITICAL: Mark JSON field as modified for SQLAlchemy to detect changes
        flag_modified(session, "results")
        
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"✅ Updated results for AgentSession {session_id}, task {task_index}")
        return session
    
    async def complete_session(
        self,
        session_id: UUID,
        final_response: str,
    ) -> Optional[AgentSession]:
        """
        Завершить сессию с финальным ответом.
        
        Args:
            session_id: ID сессии
            final_response: Финальный ответ пользователю
            
        Returns:
            AgentSession или None
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.final_response = final_response
        session.status = AgentSessionStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"✅ Completed AgentSession {session_id}")
        return session
    
    async def fail_session(
        self,
        session_id: UUID,
        error_message: str,
    ) -> Optional[AgentSession]:
        """
        Пометить сессию как failed.
        
        Args:
            session_id: ID сессии
            error_message: Сообщение об ошибке
            
        Returns:
            AgentSession или None
        """
        return await self.update_status(
            session_id=session_id,
            status=AgentSessionStatus.FAILED,
            error_message=error_message,
        )
    
    async def get_user_sessions(
        self,
        user_id: UUID,
        board_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[AgentSession]:
        """
        Получить сессии пользователя.
        
        Args:
            user_id: ID пользователя
            board_id: ID доски (опционально)
            limit: Максимум сессий
            
        Returns:
            List[AgentSession]
        """
        query = select(AgentSession).where(AgentSession.user_id == user_id)
        
        if board_id:
            query = query.where(AgentSession.board_id == board_id)
        
        query = query.order_by(AgentSession.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_active_sessions(self, user_id: UUID) -> List[AgentSession]:
        """
        Получить активные (не завершённые) сессии пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            List[AgentSession]
        """
        result = await self.db.execute(
            select(AgentSession)
            .where(
                and_(
                    AgentSession.user_id == user_id,
                    AgentSession.status.in_([
                        AgentSessionStatus.PENDING,
                        AgentSessionStatus.PLANNING,
                        AgentSessionStatus.PROCESSING,
                        AgentSessionStatus.AGGREGATING,
                    ])
                )
            )
            .order_by(AgentSession.created_at.desc())
        )
        return list(result.scalars().all())
