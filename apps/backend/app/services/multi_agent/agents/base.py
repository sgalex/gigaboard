"""
Базовый класс для всех агентов Multi-Agent системы.

V2: Все агенты возвращают AgentPayload вместо Dict[str, Any].
См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TypeVar
from datetime import datetime
import json

T = TypeVar("T")

from ..message_bus import AgentMessageBus
from ..message_types import MessageType, AgentMessage
from ..exceptions import MessageBusError, TimeoutError as AgentTimeoutError
from ..schemas.agent_payload import (
    AgentPayload,
    CodeBlock,
    Finding,
    Narrative,
    PayloadContentTable,
    Plan,
    Source,
    ValidationResult,
)


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Базовый класс для всех агентов.
    
    Предоставляет:
    - Подключение к Message Bus
    - Обработка TASK_REQUEST сообщений
    - Логирование и метрики
    - Обработка ошибок
    """
    
    def __init__(
        self,
        agent_name: str,
        message_bus: AgentMessageBus,
        system_prompt: Optional[str] = None
    ):
        """
        Args:
            agent_name: Имя агента (planner, analyst, researcher, etc.)
            message_bus: Экземпляр AgentMessageBus
            system_prompt: System prompt для LLM (опционально)
        """
        self.agent_name = agent_name
        self.message_bus = message_bus
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.task_count = 0
        self.error_count = 0
        
    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Возвращает дефолтный system prompt для агента."""
        pass
    
    @abstractmethod
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentPayload:
        """
        Обрабатывает задачу от Planner или Orchestrator.
        
        Args:
            task: Описание задачи с параметрами
            context: Дополнительный контекст (board_id, user_id, selected_nodes, etc.)
            
        Returns:
            AgentPayload — универсальный формат результата (V2).
        """
        pass
    
    async def start_listening(self):
        """
        Подписывается на канал agent_inbox:{agent_name} и начинает слушать задачи.
        """
        channel = f"agent_inbox:{self.agent_name}"
        self.logger.info(f"🎧 {self.agent_name.upper()} Agent starting to listen on {channel}")
        
        self.logger.info(f"🔔 Subscribing with agent_name='{self.agent_name}' and callback={self._handle_message.__name__}")
        
        await self.message_bus.subscribe(
            agent_name=self.agent_name,
            callback=self._handle_message
        )
        
        self.logger.info(f"✅ {self.agent_name.upper()} Agent subscription complete")
    
    async def _handle_message(self, message: AgentMessage):
        """
        Обрабатывает входящее сообщение от Message Bus.
        """
        self.logger.info(
            f"🔔 _handle_message called: msg_type={message.message_type}, "
            f"sender={message.sender}, receiver={message.receiver}, "
            f"msg_id={message.message_id[:8]}..."
        )
        
        try:
            # Проверяем тип сообщения
            if message.message_type != MessageType.TASK_REQUEST:
                self.logger.warning(
                    f"⚠️  Unexpected message type: {message.message_type}, expected TASK_REQUEST"
                )
                return
            
            self.logger.info(f"✅ Message type is TASK_REQUEST")
            
            # Проверяем, что сообщение адресовано нам
            if message.receiver != self.agent_name:
                self.logger.warning(
                    f"⚠️  Message receiver mismatch: expected '{self.agent_name}', got '{message.receiver}'"
                )
                return
            
            self.logger.info(f"✅ Message is addressed to us ({self.agent_name})")
            
            self.logger.info(
                f"📨 Received task request from {message.sender}: {message.payload.get('task', {}).get('description', 'N/A')}"
            )
            
            # Извлекаем задачу и контекст
            task = message.payload.get("task", {})
            context = message.payload.get("context", {})
            
            # Инкрементируем счетчик
            self.task_count += 1
            
            # Обрабатываем задачу
            start_time = datetime.now()
            result = await self.process_task(task, context)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Сериализуем AgentPayload (V2) в dict для отправки
            result_dict = result.model_dump() if isinstance(result, AgentPayload) else result
            
            # Отправляем результат обратно
            from uuid import uuid4
            
            self.logger.info(
                f"📤 Sending response back to {message.sender} (parent_msg_id: {message.message_id[:8]}...)"
            )
            
            response_message = AgentMessage(
                message_id=str(uuid4()),
                message_type=MessageType.TASK_RESULT,
                sender=self.agent_name,
                receiver=message.sender,  # FIXED: was 'recipient'
                session_id=message.session_id,
                board_id=message.board_id,
                parent_message_id=message.message_id,  # Link to request
                payload={
                    "status": result_dict.get("status", "success"),
                    "result": result_dict,
                    "execution_time": execution_time,
                    "agent": self.agent_name
                }
            )
            
            self.logger.info(
                f"📨 Publishing response: msg_id={response_message.message_id[:8]}..., "
                f"parent={message.message_id[:8]}..."
            )
            
            await self.message_bus.publish(response_message)
            
            self.logger.info(
                f"✅ Task completed in {execution_time:.2f}s, sent response to {message.sender}"
            )
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Error processing task: {str(e)}", exc_info=True)
            
            # Отправляем сообщение об ошибке
            error_message = AgentMessage(
                message_type=MessageType.TASK_RESPONSE,
                sender=self.agent_name,
                recipient=message.sender,
                correlation_id=message.correlation_id,
                payload={
                    "status": "error",
                    "error": str(e),
                    "agent": self.agent_name
                }
            )
            
            await self.message_bus.publish(
                message=error_message,
                target_agent=message.sender
            )
    
    def _validate_task(self, task: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Валидирует наличие обязательных полей в задаче.
        
        Args:
            task: Задача для валидации
            required_fields: Список обязательных полей
            
        Raises:
            ValueError: Если отсутствуют обязательные поля
        """
        missing_fields = [field for field in required_fields if field not in task]
        if missing_fields:
            raise ValueError(
                f"Missing required fields in task: {', '.join(missing_fields)}"
            )
    
    def _format_error_response(
        self,
        error_message: str,
        suggestions: Optional[List[str]] = None
    ) -> AgentPayload:
        """
        Форматирует ответ об ошибке как AgentPayload (V2).
        """
        return AgentPayload.make_error(
            agent=self.agent_name,
            error_message=error_message,
            suggestions=suggestions,
        )
    
    # ------------------------------------------------------------------
    # V2 AgentPayload helpers
    # ------------------------------------------------------------------

    def _success_payload(
        self,
        *,
        narrative: Optional[Narrative] = None,
        narrative_text: Optional[str] = None,
        tables: Optional[List[PayloadContentTable]] = None,
        code_blocks: Optional[List[CodeBlock]] = None,
        sources: Optional[List[Source]] = None,
        findings: Optional[List[Finding]] = None,
        validation: Optional[ValidationResult] = None,
        plan: Optional[Plan] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentPayload:
        """Создать успешный AgentPayload от имени этого агента.

        Shortcuts:
        - ``narrative_text="..."`` — создаст Narrative(text=..., format="markdown")
        """
        if narrative is None and narrative_text is not None:
            narrative = Narrative(text=narrative_text)

        return AgentPayload.success(
            agent=self.agent_name,
            narrative=narrative,
            tables=tables,
            code_blocks=code_blocks,
            sources=sources,
            findings=findings,
            validation=validation,
            plan=plan,
            metadata=metadata,
        )

    def _error_payload(
        self,
        error_message: str,
        suggestions: Optional[List[str]] = None,
    ) -> AgentPayload:
        """Создать AgentPayload с ошибкой от имени этого агента."""
        return AgentPayload.make_error(
            agent=self.agent_name,
            error_message=error_message,
            suggestions=suggestions,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику работы агента.
        """
        return {
            "agent_name": self.agent_name,
            "task_count": self.task_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.task_count, 1)
        }

    # ============================================================
    # GigaChat retry helper — повторный вызов при ошибке парсинга
    # ============================================================

    MAX_GIGACHAT_PARSE_RETRIES = 1  # 1 retry = максимум 2 вызова

    async def _call_gigachat_with_json_retry(
        self,
        messages: List[Dict[str, str]],
        parse_fn: Callable[[Any], T],
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> T:
        """Вызывает GigaChat и парсит ответ; при ошибке парсинга повторяет с уточнением.

        Args:
            messages: Список сообщений для GigaChat (будет мутирован при retry).
            parse_fn: Функция парсинга ответа → результат. Должна бросить исключение
                       (json.JSONDecodeError, ValueError, ...) при невалидном ответе.
            temperature: Температура GigaChat.
            max_tokens: Макс. токенов (если None — не передаётся).
            max_retries: Сколько раз повторить (по умолчанию MAX_GIGACHAT_PARSE_RETRIES).

        Returns:
            Результат parse_fn(response) при успехе.

        Raises:
            Последнее исключение от parse_fn, если все попытки исчерпаны.
        """
        gigachat = getattr(self, "gigachat", None)
        if gigachat is None:
            raise RuntimeError(f"{self.agent_name}: gigachat service not initialized")

        retries = max_retries if max_retries is not None else self.MAX_GIGACHAT_PARSE_RETRIES
        last_error: Optional[Exception] = None

        for attempt in range(1 + retries):
            kwargs: Dict[str, Any] = {"messages": messages, "temperature": temperature}
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            response = await gigachat.chat_completion(**kwargs)

            try:
                return parse_fn(response)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    # Добавляем ответ LLM + описание ошибки и просим исправить
                    raw_text = response if isinstance(response, str) else str(response)
                    # Обрезаем чтобы не раздуть промпт
                    raw_text_short = raw_text[:1500] if len(raw_text) > 1500 else raw_text
                    self.logger.warning(
                        f"⚠️ [{self.agent_name}] Parse error (attempt {attempt + 1}): {e}. Retrying..."
                    )
                    messages.append({"role": "assistant", "content": raw_text_short})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Твой предыдущий ответ содержит синтаксическую ошибку и не может быть распознан: {e}\n"
                            "Пожалуйста, верни исправленный ответ — ТОЛЬКО валидный JSON, без текста вне JSON."
                        ),
                    })
                else:
                    self.logger.error(
                        f"❌ [{self.agent_name}] Parse failed after {attempt + 1} attempt(s): {e}"
                    )

        raise last_error  # type: ignore[misc]

    # ============================================================
    # Context helpers — reading agent_results (chronological list)
    # См. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md
    # ============================================================

    def _last_result(self, context: Optional[Dict[str, Any]], agent_name: str) -> Optional[Dict[str, Any]]:
        """Последний результат указанного агента из хронологии agent_results."""
        if not context:
            return None
        for r in reversed(context.get("agent_results", [])):
            if isinstance(r, dict) and r.get("agent") == agent_name:
                return r
        return None

    def _all_results(self, context: Optional[Dict[str, Any]], agent_name: str) -> List[Dict[str, Any]]:
        """Все результаты указанного агента в хронологическом порядке."""
        if not context:
            return []
        return [
            r for r in context.get("agent_results", [])
            if isinstance(r, dict) and r.get("agent") == agent_name
        ]

    # ============================================================
    # Session Results - доступ к результатам других агентов
    # ============================================================
    
    async def get_agent_result(
        self,
        session_id: str,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить результат другого агента из Redis.
        
        Args:
            session_id: ID сессии
            agent_name: Имя агента, чей результат нужен
            
        Returns:
            Dict с результатом или None
            
        Example:
            # Получить результаты SearchAgent
            search_result = await self.get_agent_result(session_id, "search")
            if search_result:
                urls = [r["url"] for r in search_result.get("results", [])]
        """
        return await self.message_bus.get_session_result(session_id, agent_name)
    
    async def get_all_previous_results(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Получить все результаты агентов для текущей сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Dict[agent_name, result] со всеми результатами
            
        Example:
            results = await self.get_all_previous_results(session_id)
            if "search" in results:
                # Обработать результаты поиска
                pass
        """
        return await self.message_bus.get_all_session_results(session_id)
