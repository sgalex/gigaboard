"""
GigaBoard Helpers - функции для использования в сгенерированном коде трансформаций.

Этот модуль доступен в Python executor под именем `gb`.
"""
import asyncio
import logging
from typing import List, Any, Optional

# Для вложенных event loops (синхронный вызов из async контекста)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # Если nest_asyncio недоступен, попробуем без него

logger = logging.getLogger("gigaboard_helpers")


class GigaBoardHelpers:
    """Helper класс для AI-резолвинга в трансформациях."""
    
    def __init__(self, resolver_agent, execution_context: Optional[dict] = None):
        """
        Args:
            resolver_agent: Экземпляр ResolverAgent для прямых вызовов
            execution_context: Контекст выполнения (orchestrated, session_id, etc.)
        """
        self.resolver_agent = resolver_agent
        self.context = execution_context or {}
    
    def ai_resolve_batch(
        self,
        values: List[Any],
        task_description: str,
        result_format: str = "string",
        chunk_size: int = 50
    ) -> List[Any]:
        """
        Резолвит список значений через AI.
        
        Args:
            values: Список значений для резолвинга
            task_description: Описание задачи (например, "определи пол по имени")
            result_format: Формат результата ("string", "number", "json")
            chunk_size: Размер чанка для batch обработки
        
        Returns:
            Список результатов в том же порядке, что и входные значения
        
        Example:
            names = df['name'].tolist()
            genders = gb.ai_resolve_batch(
                names,
                "определи пол человека по имени, вернув M или F"
            )
            df['gender'] = genders
        """
        # Ensure values is a list (convert from pandas Series if needed)
        if hasattr(values, 'tolist'):
            values = values.tolist()
        elif not isinstance(values, list):
            values = list(values)
        
        logger.info(f"🔍 ai_resolve_batch called: {len(values)} values, task: '{task_description[:50]}...'")
        
        try:
            # Выбираем способ вызова на основе контекста
            use_message_bus = self._should_use_message_bus(len(values))
            
            if use_message_bus:
                logger.info("📨 Using MessageBus for AI resolve")
                return self._resolve_via_message_bus(
                    values, task_description, result_format, chunk_size
                )
            else:
                logger.info("⚡ Using direct GigaChat call")
                return self._resolve_direct(
                    values, task_description, result_format, chunk_size
                )
            
        except Exception as e:
            logger.error(f"❌ AI resolve failed: {e}", exc_info=True)
            return [None] * len(values)
    
    def ai_resolve_single(self, value: Any, task_description: str) -> Any:
        """Резолвит одно значение через AI (обертка над batch)."""
        results = self.ai_resolve_batch([value], task_description)
        return results[0] if results else None
    
    def _should_use_message_bus(self, batch_size: int) -> bool:
        """
        Определяет способ вызова на основе контекста и размера батча.
        
        Критерии для MessageBus:
        - Большие батчи (>200 значений) - для мониторинга и chunking
        - Orchestrated выполнение - для consistency и retry logic
        - Наличие session_id - для трекинга в UI
        """
        # Проверяем наличие MessageBus у агента
        if not hasattr(self.resolver_agent, 'message_bus') or not self.resolver_agent.message_bus:
            return False
        
        # Большие батчи -> MessageBus (параллельный chunking + мониторинг)
        if batch_size > 200:
            logger.info(f"📊 Large batch ({batch_size} values) - using MessageBus")
            return True
        
        # Orchestrated выполнение -> MessageBus (consistency)
        if self.context.get("orchestrated", False):
            logger.info("🎯 Orchestrated execution - using MessageBus")
            return True
        
        # Есть session для трекинга -> MessageBus
        if self.context.get("session_id"):
            logger.info("🔗 Session tracking enabled - using MessageBus")
            return True
        
        # По умолчанию - прямой вызов (быстро)
        return False
    
    def _resolve_direct(
        self,
        values: List[Any],
        task_description: str,
        result_format: str,
        chunk_size: int
    ) -> List[Any]:
        """Прямой вызов ResolverAgent через GigaChat."""
        task = {
            "type": "resolve_batch",
            "values": values,
            "task_description": task_description,
            "result_format": result_format,
            "chunk_size": chunk_size
        }
        
        # С nest_asyncio можно использовать run_until_complete
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.resolver_agent.process_task(task, context=self.context)
        )
        
        if "error" in result:
            logger.error(f"❌ AI resolve error: {result['error']}")
            return [None] * len(values)
        
        results = result.get("results", [None] * len(values))
        logger.info(f"✅ Direct resolve success: {len(results)} results")
        return results
    
    def _resolve_via_message_bus(
        self,
        values: List[Any],
        task_description: str,
        result_format: str,
        chunk_size: int
    ) -> List[Any]:
        """Вызов через MessageBus для orchestration."""
        # Fallback на прямой вызов если MessageBus недоступен
        if not hasattr(self.resolver_agent, 'message_bus') or not self.resolver_agent.message_bus:
            logger.warning("⚠️ MessageBus not available, falling back to direct call")
            return self._resolve_direct(values, task_description, result_format, chunk_size)
        
        try:
            task = {
                "type": "resolve_batch",
                "values": values,
                "task_description": task_description,
                "result_format": result_format,
                "chunk_size": chunk_size
            }
            
            # Вызов через MessageBus
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.resolver_agent.message_bus.request_response(
                    source=self.context.get("source", "transformation_executor"),
                    target="resolver",
                    task=task,
                    timeout=300
                )
            )
            
            if "error" in result:
                logger.error(f"❌ MessageBus resolve error: {result['error']}")
                return [None] * len(values)
            
            results = result.get("results", [None] * len(values))
            logger.info(f"✅ MessageBus resolve success: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ MessageBus resolve failed: {e}, falling back to direct")
            return self._resolve_direct(values, task_description, result_format, chunk_size)


# Singleton instance
_helpers_instance: Optional[GigaBoardHelpers] = None


def get_helpers() -> GigaBoardHelpers:
    """Получить экземпляр helpers."""
    global _helpers_instance
    if _helpers_instance is None:
        raise RuntimeError("GigaBoardHelpers not initialized. Call init_helpers() first.")
    return _helpers_instance


def init_helpers(execution_context: Optional[dict] = None):
    """
    Инициализировать helpers с ResolverAgent.
    
    Args:
        execution_context: Контекст выполнения для принятия решений:
            - orchestrated: bool - выполнение через PlannerAgent
            - session_id: str - ID сессии для трекинга
            - source: str - источник вызова (user_ui, planner, api)
    """
    global _helpers_instance
    
    # Импортируем и создаем ResolverAgent
    from ..multi_agent.agents.resolver import get_resolver_agent
    resolver_agent = get_resolver_agent()
    
    _helpers_instance = GigaBoardHelpers(resolver_agent, execution_context)
    return _helpers_instance
