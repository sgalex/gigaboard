"""
MultiAgentOrchestrator - центральный координатор Multi-Agent системы.

Отвечает за:
- Приём запросов от AIService
- Создание и управление сессиями
- Декомпозицию задач через Planner Agent
- Маршрутизацию задач к агентам через Message Bus
- Агрегацию результатов
- Валидацию через CriticAgent
- Возврат финального ответа
"""
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentSessionStatus
from .session import AgentSessionManager
from .message_bus import AgentMessageBus
from .message_types import MessageType, AgentMessage
from .exceptions import MessageBusError
from .agents.critic import CriticAgent, determine_expected_outcome, ExpectedOutcome

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    Orchestrator для координации Multi-Agent обработки запросов.
    
    Workflow:
    1. Создать AgentSession
    2. Отправить запрос Planner Agent для декомпозиции
    3. Получить план задач
    4. Последовательно/параллельно отправлять задачи агентам
    5. Собрать результаты
    6. Агрегировать финальный ответ
    7. Валидировать через CriticAgent
    8. Обновить сессию (или перепланировать)
    """
    
    # Константы для CriticAgent
    MAX_CRITIC_ITERATIONS = 5  # Максимум итераций перепланирования
    CRITIC_TIMEOUT = 30        # Timeout для CriticAgent (секунды)
    CONFIDENCE_THRESHOLD = 0.7 # Ниже этого — считаем invalid
    
    def __init__(self, db: AsyncSession, message_bus: AgentMessageBus):
        """
        Args:
            db: SQLAlchemy async session
            message_bus: AgentMessageBus instance для общения с агентами
        """
        self.db = db
        self.message_bus = message_bus
        self.session_manager = AgentSessionManager(db)
        self._critic_agent: Optional[CriticAgent] = None
        self.current_session_id: Optional[UUID] = None  # Для доступа к последней сессии
    
    async def process_user_request(
        self,
        user_id: UUID,
        board_id: UUID,
        user_message: str,
        chat_session_id: Optional[str] = None,
        selected_node_ids: Optional[List[UUID]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Обработать запрос пользователя через Multi-Agent систему.
        
        Args:
            user_id: ID пользователя
            board_id: ID доски
            user_message: Сообщение пользователя
            chat_session_id: ID чат-сессии (для связи с ChatMessage)
            selected_node_ids: Выбранные ноды (контекст)
            
        Yields:
            str: Streaming chunks ответа
        """
        session = None
        
        try:
            # 1. Создать сессию
            session = await self.session_manager.create_session(
                user_id=user_id,
                board_id=board_id,
                user_message=user_message,
                chat_session_id=chat_session_id,
                selected_node_ids=selected_node_ids,
            )
            
            # Сохраняем session_id для доступа извне (например, из PromptExtractor)
            self.current_session_id = session.id
            
            logger.info(f"🤖 Starting Multi-Agent processing for session {session.id}")
            yield f"🔄 Начинаю обработку запроса...\n\n"
            
            # 2. Определить, нужна ли Multi-Agent обработка
            # Пока используем простую эвристику: если запрос длинный или содержит keywords
            needs_multi_agent = await self._needs_multi_agent_processing(user_message)
            
            if not needs_multi_agent:
                # Простой запрос - отвечаем напрямую без декомпозиции
                logger.info(f"💬 Simple request, skipping Multi-Agent")
                await self.session_manager.update_status(session.id, AgentSessionStatus.COMPLETED)
                yield "✅ Это простой запрос, обрабатываю напрямую.\n\n"
                return
            
            # 3. Отправить запрос Planner Agent для декомпозиции
            await self.session_manager.update_status(session.id, AgentSessionStatus.PLANNING)
            yield "🧠 Planner Agent анализирует запрос и создаёт план...\n\n"
            
            plan = await self._request_plan(session.id, user_message, board_id, selected_node_ids)
            
            if not plan or "steps" not in plan:
                logger.warning(f"⚠️ Planner Agent returned empty plan")
                await self.session_manager.fail_session(
                    session.id,
                    "Planner Agent не смог создать план выполнения"
                )
                yield "❌ Не удалось создать план выполнения.\n\n"
                return
            
            await self.session_manager.update_plan(session.id, plan)
            
            steps = plan.get("steps", [])
            yield f"📋 План создан: {len(steps)} шагов\n\n"
            
            # Отправляем детали каждого шага плана
            for i, step in enumerate(steps, 1):
                agent_name = step.get("agent", "unknown")
                task_desc = step.get("task", {}).get("description", "No description")
                task_type = step.get("task", {}).get("type", "unknown")
                dependencies = step.get("dependencies", [])
                
                yield f"   {i}. [{agent_name.upper()}] {task_desc}\n"
                yield f"      Тип: {task_type}\n"
                if dependencies:
                    yield f"      Зависимости: {', '.join(dependencies)}\n"
                yield "\n"
            
            # 4. Выполнить задачи
            await self.session_manager.update_status(session.id, AgentSessionStatus.PROCESSING)
            
            all_results = []
            # Накапливаем previous_results для передачи между агентами
            previous_results: Dict[str, Any] = {}
            
            for i, step in enumerate(steps):
                agent_name = step.get("agent", "unknown")
                task_desc = step.get("task", {}).get("description", "unknown")
                task_type = step.get("task", {}).get("type", "unknown")
                
                yield f"⚙️ Шаг {i+1}/{len(steps)}: {task_desc} (Agent: {agent_name})\n"
                
                # Замеряем время выполнения
                start_time = time.time()
                result = await self._execute_task(session.id, i, step, previous_results)
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                all_results.append(result)
                
                # Сохраняем результат для следующих шагов
                if result.get("status") == "completed" and result.get("result"):
                    agent_result = result.get("result")
                    previous_results[agent_name] = agent_result
                    logger.info(f"📦 Saved result for {agent_name}: keys={list(agent_result.keys() if isinstance(agent_result, dict) else [])}")
                    
                    # Обогащаем результат метаинформацией для Redis
                    enriched_result = {
                        **agent_result,
                        "_meta": {
                            "agent_name": agent_name,
                            "task_type": task_type,
                            "task_description": task_desc,
                            "step_index": i,
                            "total_steps": len(steps),
                            "execution_time_ms": execution_time_ms,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "status": result.get("status")
                        }
                    }
                    
                    # Сохраняем в Redis для доступа другим агентам
                    await self.message_bus.store_session_result(
                        session_id=str(session.id),
                        agent_name=agent_name,
                        result=enriched_result
                    )
                
                await self.session_manager.update_results(session.id, i, result)
                
                if result.get("status") == "completed":
                    yield f"✅ Задача {i+1} выполнена\n\n"
                else:
                    yield f"⚠️ Задача {i+1} завершена с предупреждениями\n\n"
            
            # 5. Агрегировать результаты
            await self.session_manager.update_status(session.id, AgentSessionStatus.AGGREGATING)
            yield "🔗 Собираю результаты...\n\n"
            
            final_response = await self._aggregate_results(user_message, all_results)
            
            # 6. Валидация через CriticAgent
            expected_outcome = determine_expected_outcome(user_message)
            
            # Собираем результаты в формате для CriticAgent
            critic_results = {
                result.get("agent", f"agent_{i}"): result.get("result", {})
                for i, result in enumerate(all_results)
                if result.get("status") == "completed"
            }
            
            validation_result = await self._validate_with_critic(
                user_message=user_message,
                aggregated_result=critic_results,
                expected_outcome=expected_outcome,
                iteration=1
            )
            
            if not validation_result.get("valid", True):
                confidence = validation_result.get("confidence", 0)
                issues = validation_result.get("issues", [])
                
                yield f"🔍 Валидация результата: confidence={confidence:.0%}\n"
                
                if issues:
                    for issue in issues[:3]:  # Показываем до 3 проблем
                        severity = issue.get("severity", "info")
                        message = issue.get("message", "Unknown issue")
                        yield f"   ⚠️ [{severity}] {message}\n"
                    yield "\n"
                
                # Если есть рекомендации по перепланированию — можно расширить
                # Пока просто предупреждаем пользователя
                recommendations = validation_result.get("recommendations", [])
                if recommendations:
                    yield "💡 Рекомендации:\n"
                    for rec in recommendations[:2]:
                        desc = rec.get("description", str(rec))
                        yield f"   • {desc}\n"
                    yield "\n"
            else:
                yield "✅ Валидация пройдена\n\n"
            
            # 7. Завершить сессию
            await self.session_manager.complete_session(session.id, final_response)
            
            # Очищаем результаты сессии из Redis (они уже агрегированы)
            await self.message_bus.clear_session_results(str(session.id))
            
            yield "✅ Обработка завершена!\n\n"
            yield final_response
            
            logger.info(f"✅ Multi-Agent processing completed for session {session.id}")
            
        except Exception as e:
            logger.error(f"❌ Error in Multi-Agent processing: {e}", exc_info=True)
            
            if session:
                await self.session_manager.fail_session(
                    session.id,
                    f"Internal error: {str(e)}"
                )
            
            yield f"❌ Ошибка при обработке: {str(e)}\n\n"
    
    async def _needs_multi_agent_processing(self, user_message: str) -> bool:
        """
        Определить, нужна ли Multi-Agent обработка.
        
        Пока простая эвристика:
        - Длинные сообщения (> 100 символов)
        - Содержат keywords: "создай", "трансформируй", "визуализируй", "найди данные"
        
        TODO: В будущем использовать LLM classifier
        """
        keywords = [
            "создай", "сгенерируй", "построй",
            "трансформируй", "преобразуй", "обработай",
            "визуализируй", "построй график", "покажи",
            "найди", "найди данные", "загрузи данные", "получи данные", "поиск",
            "проанализируй", "рассчитай", "вычисли",
        ]
        
        message_lower = user_message.lower()
        
        # Проверка keywords
        has_keyword = any(keyword in message_lower for keyword in keywords)
        
        # Проверка длины
        is_long = len(user_message) > 100
        
        return has_keyword or is_long
    
    async def _request_plan(
        self,
        session_id: UUID,
        user_message: str,
        board_id: UUID,
        selected_node_ids: Optional[List[UUID]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Запросить план выполнения у Planner Agent.
        
        Args:
            session_id: ID сессии
            user_message: Сообщение пользователя
            board_id: ID доски
            selected_node_ids: Выбранные ноды
            
        Returns:
            Dict с планом или None
        """
        try:
            # Отправить запрос Planner Agent
            from uuid import uuid4 as gen_uuid
            
            message = AgentMessage(
                message_id=str(gen_uuid()),
                message_type=MessageType.TASK_REQUEST,
                sender="orchestrator",
                receiver="planner",
                session_id=str(session_id),
                board_id=str(board_id),
                payload={
                    "task": {
                        "type": "create_plan",
                        "user_request": user_message,
                    },
                    "context": {
                        "session_id": str(session_id),
                        "board_id": str(board_id),
                        "selected_node_ids": [str(nid) for nid in selected_node_ids] if selected_node_ids else [],
                    }
                }
            )
            
            # Отправляем запрос Planner Agent через Message Bus
            logger.info("📤 Sending plan request to Planner Agent")
            
            try:
                response = await self.message_bus.request_response(
                    message=message,
                    timeout=self._get_agent_timeout("planner", "create_plan")
                )
                
                logger.info(f"📥 Received response from Planner Agent: type={type(response)}")
                if response:
                    logger.info(f"   Response has payload: {hasattr(response, 'payload')}")
                    if hasattr(response, 'payload'):
                        logger.info(f"   Payload type: {type(response.payload)}")
                        logger.info(f"   Payload keys: {response.payload.keys() if isinstance(response.payload, dict) else 'N/A'}")
                
                if response and response.payload.get("status") == "success":
                    # План находится в payload.result.plan (двойная вложенность из-за BaseAgent wrapper)
                    result = response.payload.get("result", {})
                    plan = result.get("plan")
                    if plan:
                        logger.info(f"✅ Received plan with {len(plan.get('steps', []))} steps")
                        return plan
                    else:
                        logger.error("❌ No plan in result")
                        return None
                else:
                    error_msg = response.payload.get("error", "Unknown error") if response else "No response"
                    logger.error(f"❌ Planner Agent failed: {error_msg}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.error("⏱️ Planner Agent timeout")
                return None
            except MessageBusError as e:
                logger.error(f"❌ Message bus error: {e}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error requesting plan from Planner Agent: {e}")
            return None
    
    async def _execute_task(
        self,
        session_id: UUID,
        task_index: int,
        task: Dict[str, Any],
        previous_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Выполнить одну задачу через соответствующего агента.
        
        Args:
            session_id: ID сессии
            task_index: Индекс задачи
            task: Описание задачи из плана
            previous_results: Результаты предыдущих шагов (по имени агента)
            
        Returns:
            Dict с результатом
        """
        try:
            agent_name = task.get("agent", "unknown")
            task_data = task.get("task", {})
            
            # Отправить задачу агенту
            from uuid import uuid4 as gen_uuid
            
            message = AgentMessage(
                message_id=str(gen_uuid()),
                message_type=MessageType.TASK_REQUEST,
                sender="orchestrator",
                receiver=agent_name,
                session_id=str(session_id),
                board_id="unknown",  # TODO: Pass board_id through context
                payload={
                    "task": task_data,
                    "context": {
                        "session_id": str(session_id),
                        "task_index": task_index,
                        "previous_results": previous_results or {},
                    }
                }
            )
            
            # Отправляем задачу агенту через Message Bus
            logger.info(f"📤 Sending task {task_index} to {agent_name} agent")
            logger.info(f"📦 previous_results keys: {list((previous_results or {}).keys())}")
            
            try:
                timeout = self._get_agent_timeout(agent_name, task_data.get("type", "default"))
                
                response = await self.message_bus.request_response(
                    message=message,
                    timeout=timeout
                )
                
                if response and response.payload.get("status") == "success":
                    result = response.payload.get("result", {})
                    logger.info(f"✅ Task {task_index} completed by {agent_name}")
                    return {
                        "status": "completed",
                        "agent": agent_name,
                        "result": result
                    }
                else:
                    error_msg = response.payload.get("error", "Unknown error") if response else "No response"
                    logger.error(f"❌ Task {task_index} failed: {error_msg}")
                    return {
                        "status": "error",
                        "agent": agent_name,
                        "error": error_msg
                    }
                    
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Task {task_index} timeout for agent {agent_name}")
                return {
                    "status": "error",
                    "agent": agent_name,
                    "error": f"Agent {agent_name} timeout"
                }
            except MessageBusError as e:
                logger.error(f"❌ Message bus error for task {task_index}: {e}")
                return {
                    "status": "error",
                    "agent": agent_name,
                    "error": str(e)
                }
            
        except Exception as e:
            logger.error(f"❌ Error executing task {task_index}: {e}")
            return {
                "status": "failed",
                "error": str(e),
            }
    
    def _get_agent_timeout(self, agent_name: str, task_type: str) -> int:
        """
        Получить timeout для агента в зависимости от типа задачи.
        
        Args:
            agent_name: Имя агента
            task_type: Тип задачи
            
        Returns:
            int: Timeout в секундах
        """
        # Разные агенты требуют разного времени
        timeouts = {
            "planner": 30,
            "researcher": 120,
            "analyst": 60,
            "transformation": 90,
            "reporter": 60,
            "developer": 180,
            "executor": 300,
            "form_generator": 30,
            "data_discovery": 120,
        }
        
        return timeouts.get(agent_name, 60)  # Default 60 секунд
    
    async def _aggregate_results(
        self,
        user_message: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """
        Агрегировать результаты всех задач в финальный ответ.
        
        Args:
            user_message: Исходный запрос пользователя
            results: Результаты от агентов
            
        Returns:
            str: Финальный ответ пользователю
        """
        # Пока простая агрегация - объединение всех результатов
        # TODO: В будущем использовать LLM для генерации связного ответа
        
        response_parts = []
        
        for i, result in enumerate(results):
            status = result.get("status", "unknown")
            agent = result.get("agent", "unknown")
            
            if status == "completed":
                result_data = result.get("result", {})
                
                # Извлекаем детальный результат в зависимости от агента
                if isinstance(result_data, dict):
                    # Если есть message - используем его
                    if "message" in result_data:
                        message = result_data["message"]
                    # Для researcher - показываем информацию о данных
                    elif "content_type" in result_data:
                        content_type = result_data.get("content_type", "unknown")
                        row_count = result_data.get("statistics", {}).get("row_count", 0)
                        message = f"Получены данные типа '{content_type}' ({row_count} строк)"
                        if "note" in result_data:
                            message += f"\nNote: {result_data['note']}"
                    # Для analyst - показываем инсайты
                    elif "insights" in result_data:
                        insights = result_data.get("insights", [])
                        if insights:
                            # Insights могут быть dict или str (fallback)
                            insight_texts = []
                            for ins in insights[:3]:
                                if isinstance(ins, dict):
                                    insight_texts.append(f"- {ins.get('title', 'N/A')}")
                                else:
                                    insight_texts.append(f"- {str(ins)}")
                            message = f"Найдено {len(insights)} инсайтов:\n" + "\n".join(insight_texts)
                        else:
                            message = "Анализ выполнен"
                    # Для reporter - показываем информацию о визуализации
                    elif "widget_type" in result_data:
                        widget_type = result_data.get("widget_type", "unknown")
                        description = result_data.get("description", "")
                        message = f"Создана визуализация типа '{widget_type}': {description}"
                    else:
                        # Дефолтное сообщение
                        message = "Задача выполнена"
                else:
                    message = str(result_data) if result_data else "Задача выполнена"
                
                response_parts.append(f"**{agent.capitalize()}**: {message}")
            else:
                error = result.get("error", "Unknown error")
                response_parts.append(f"**{agent.capitalize()}**: ⚠️ {error}")
        
        final_response = "\n\n".join(response_parts)
        
        return final_response
    
    async def _validate_with_critic(
        self,
        user_message: str,
        aggregated_result: Dict[str, Any],
        expected_outcome: str,
        iteration: int = 1
    ) -> Dict[str, Any]:
        """
        Валидирует результаты через CriticAgent.
        
        Args:
            user_message: Исходный запрос пользователя
            aggregated_result: Результаты от всех агентов
            expected_outcome: Ожидаемый тип результата
            iteration: Номер итерации валидации
            
        Returns:
            Dict с результатом валидации:
            {
                "valid": bool,
                "confidence": float,
                "issues": [...],
                "recommendations": [...],
                "suggested_replan": {...}  # если valid=false
            }
        """
        try:
            # Lazy инициализация CriticAgent
            if self._critic_agent is None:
                from app.services.gigachat_service import GigaChatService
                gigachat = GigaChatService()
                self._critic_agent = CriticAgent(
                    message_bus=None,  # Standalone режим, без Message Bus
                    gigachat_service=gigachat
                )
            
            logger.info(
                f"🔍 Validating with CriticAgent: expected={expected_outcome}, "
                f"iteration={iteration}/{self.MAX_CRITIC_ITERATIONS}"
            )
            
            result = await asyncio.wait_for(
                self._critic_agent.validate(
                    user_message=user_message,
                    aggregated_result=aggregated_result,
                    expected_outcome=expected_outcome,
                    iteration=iteration,
                    max_iterations=self.MAX_CRITIC_ITERATIONS
                ),
                timeout=self.CRITIC_TIMEOUT
            )
            
            logger.info(f"📋 CriticAgent result: valid={result.get('valid')}, confidence={result.get('confidence', 0):.2f}")
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ CriticAgent timeout after {self.CRITIC_TIMEOUT}s")
            return {
                "valid": True,  # Default to valid on timeout
                "confidence": 0.5,
                "message": "Validation skipped due to timeout"
            }
        except Exception as e:
            logger.error(f"❌ CriticAgent error: {e}", exc_info=True)
            return {
                "valid": True,  # Default to valid on error
                "confidence": 0.5,
                "message": f"Validation error: {str(e)}"
            }
