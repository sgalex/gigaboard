"""
MultiAgentEngine - фасад для управления мультиагентной системой.

Предоставляет единый интерфейс для:
- Инициализации всех ресурсов (Redis, GigaChat, MessageBus)
- Создания и управления агентами
- Выполнения пользовательских запросов
- Получения результатов

Используется AI Assistant'ом для работы с мультиагентной системой.
"""
import json
import logging
import os
import re
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from .message_bus import AgentMessageBus
from .message_types import MessageType, AgentMessage
from .agents.planner import PlannerAgent
from .agents.search import SearchAgent
from .agents.analyst import AnalystAgent
from .agents.reporter import ReporterAgent
from .agents.researcher import ResearcherAgent
from .agents.transformation import TransformationAgent
from .agents.widget_suggestions import WidgetSuggestionAgent


logger = logging.getLogger(__name__)

# Константы для управления retry и replan
MAX_REPLAN_ATTEMPTS = 2  # Максимум попыток перепланирования
MAX_RETRY_ATTEMPTS = 1    # Максимум попыток повтора шага


class MultiAgentEngine:
    """
    Движок мультиагентной системы.
    
    Примеры использования:
        # Инициализация
        engine = MultiAgentEngine()
        await engine.initialize()
        
        # Обработка запроса
        result = await engine.process_request(
            user_request="Найди статистику продаж за 2025 год",
            board_id="board_123",
            user_id="user_456",
            context={"selected_node_ids": ["node_1"]}
        )
        
        # Завершение
        await engine.shutdown()
    """
    
    def __init__(
        self,
        gigachat_api_key: Optional[str] = None,
        enable_agents: Optional[List[str]] = None,
        adaptive_planning: bool = True
    ):
        """
        Args:
            gigachat_api_key: API ключ GigaChat (если None, берется из env)
            enable_agents: Список агентов для активации (если None, все)
            adaptive_planning: Если True, план корректируется после каждого шага на основе результатов
        """
        self.gigachat_api_key = gigachat_api_key or os.getenv("GIGACHAT_API_KEY")
        self.enable_agents = enable_agents or [
            "planner", "search", "analyst", "reporter", "researcher", "transformation"
        ]
        self.adaptive_planning = adaptive_planning
        
        self.gigachat: Optional[GigaChatService] = None
        self.message_bus: Optional[AgentMessageBus] = None
        self.agents: Dict[str, Any] = {}
        self.is_initialized = False
        
        self.logger = logging.getLogger(f"{__name__}.MultiAgentEngine")
        
    async def initialize(self) -> None:
        """
        Инициализирует все ресурсы мультиагентной системы.
        
        Raises:
            RuntimeError: Если инициализация не удалась
        """
        if self.is_initialized:
            self.logger.warning("Engine already initialized")
            return
        
        self.logger.info("🚀 Initializing MultiAgentEngine...")
        
        try:
            # 1. Redis
            await init_redis()
            self.logger.info("✅ Redis initialized")
            
            # 2. GigaChat
            if not self.gigachat_api_key:
                raise ValueError("GIGACHAT_API_KEY not provided and not in environment")
            
            self.gigachat = GigaChatService(api_key=self.gigachat_api_key)
            self.logger.info("✅ GigaChat initialized")
            
            # 3. Message Bus
            self.message_bus = AgentMessageBus()
            await self.message_bus.connect()
            self.logger.info("✅ Message Bus connected")
            
            # 4. Агенты
            await self._initialize_agents()
            self.logger.info(f"✅ {len(self.agents)} agents initialized")
            
            self.is_initialized = True
            self.logger.info("✅ MultiAgentEngine ready")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize engine: {e}", exc_info=True)
            await self.shutdown()
            raise RuntimeError(f"Engine initialization failed: {e}")
    
    async def _initialize_agents(self) -> None:
        """Создает и запускает всех агентов."""
        
        # Planner (обязательный)
        if "planner" in self.enable_agents:
            self.agents["planner"] = PlannerAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Search
        if "search" in self.enable_agents:
            self.agents["search"] = SearchAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Analyst
        if "analyst" in self.enable_agents:
            self.agents["analyst"] = AnalystAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Reporter
        if "reporter" in self.enable_agents:
            self.agents["reporter"] = ReporterAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Researcher
        if "researcher" in self.enable_agents:
            self.agents["researcher"] = ResearcherAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Transformation
        if "transformation" in self.enable_agents:
            self.agents["transformation"] = TransformationAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Suggestions (for Widget AI)
        if "suggestions" in self.enable_agents:
            self.agents["suggestions"] = WidgetSuggestionAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        
        # Запускаем подписки агентов на MessageBus
        for agent_name, agent in self.agents.items():
            await agent.start_listening()
            self.logger.info(f"✅ {agent_name} agent listening")
    
    async def _should_replan_after_step(
        self,
        current_plan: Dict[str, Any],
        step: Dict[str, Any],
        step_index: int,
        step_result: Dict[str, Any],
        all_results: Dict[str, Any],
        full_context: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Определяет, нужно ли пересматривать план после успешного выполнения шага.
        
        Анализирует результаты через GigaChat для принятия решения о replanning.
        """
        try:
            # Формируем краткое описание результата (чтобы не перегружать контекст)
            result_summary = {
                "status": step_result.get("status"),
                "agent": step.get("agent"),
                "data_keys": list(step_result.get("data", {}).keys()) if isinstance(step_result.get("data"), dict) else []
            }
            
            # Формируем prompt для анализа
            prompt = f"""Ты - AI планировщик, анализирующий результаты выполнения шагов в data pipeline.

ТЕКУЩАЯ СИТУАЦИЯ:
Только что успешно выполнен шаг #{step_index + 1}: {step.get('description', 'N/A')}
Агент: {step.get('agent', 'N/A')}
Статус: {step_result.get('status', 'N/A')}

ОБЩИЙ КОНТЕКСТ:
Всего шагов в плане: {len(current_plan.get('steps', []))}
Выполнено шагов: {step_index + 1}
Накопленные результаты: {len(all_results)} результатов

ОСТАВШИЕСЯ ШАГИ:
{json.dumps([s.get('description', 'N/A') for s in current_plan.get('steps', [])[step_index + 1:]], ensure_ascii=False, indent=2)}

ТВОЯ ЗАДАЧА:
Определи, нужно ли ПОЛНОСТЬЮ ПЕРЕСМОТРЕТЬ план (replan) на основе новых результатов.

КРИТЕРИИ ДЛЯ REPLAN:
1. Результат содержит СУЩЕСТВЕННО НОВУЮ информацию, которая меняет стратегию
2. Обнаружены НОВЫЕ источники данных, требующие изменения подхода
3. Текущий план НЕ ОПТИМАЛЕН для достижения цели с учётом новых знаний
4. Нужно изменить ПОСЛЕДОВАТЕЛЬНОСТЬ шагов или их логику
5. Результат показывает, что некоторые шаги можно ПРОПУСТИТЬ или ОБЪЕДИНИТЬ

НЕ НУЖЕН REPLAN если:
- План работает как ожидалось
- Результаты предсказуемы и не меняют стратегию
- Оставшиеся шаги корректны и достаточны

Верни JSON:
{{
    "replan": true/false,
    "reason": "Краткое объяснение решения",
    "key_insights": "Ключевые находки из результата"
}}
"""
            
            response = await self.gigachat.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            # Парсим ответ
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group())
                return decision
            else:
                # По умолчанию не делаем replan
                return {"replan": False, "reason": "No clear need for replanning"}
                
        except Exception as e:
            self.logger.error(f"Failed to analyze replan need: {e}")
            # В случае ошибки не делаем replan
            return {"replan": False, "reason": f"Analysis error: {str(e)}"}
    
    async def _optimize_plan_after_step(
        self,
        current_plan: Dict[str, Any],
        step: Dict[str, Any],
        step_index: int,
        step_result: Dict[str, Any],
        all_results: Dict[str, Any],
        full_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Анализирует результат успешного шага и предлагает оптимизацию плана.
        
        Returns:
            - should_update: bool - нужно ли обновлять план
            - updated_plan: Dict - новый план (если should_update=True)
            - changes: str - описание изменений
        """
        if not self.adaptive_planning:
            return {"should_update": False}
        
        self.logger.info(f"🔍 Analyzing step {step_index} results for plan optimization...")
        
        try:
            # Формируем prompt для PlannerAgent
            optimization_prompt = f"""
Анализируй результаты выполненного шага и определи, нужна ли корректировка плана.

ТЕКУЩИЙ ПЛАН:
{json.dumps(current_plan, indent=2, ensure_ascii=False)}

ВЫПОЛНЕННЫЙ ШАГ #{step_index}:
Agent: {step.get('agent')}
Task: {step.get('task', {}).get('type')}

РЕЗУЛЬТАТ:
{json.dumps(step_result, indent=2, ensure_ascii=False)}

ПРОАНАЛИЗИРУЙ:
1. Содержат ли результаты новую информацию, влияющую на следующие шаги?
2. Нужно ли добавить новые шаги для обработки обнаруженных данных?
3. Можно ли пропустить/упростить последующие шаги?
4. Нужно ли изменить параметры следующих шагов?

Если корректировка НЕ НУЖНА, верни:
{{
  "optimize": false,
  "reason": "План актуален"
}}

Если корректировка НУЖНА, верни:
{{
  "optimize": true,
  "reason": "Описание причины",
  "changes": [
    {{"action": "add_step", "after_step": 2, "step": {{...}}}},
    {{"action": "modify_step", "step_id": 3, "changes": {{...}}}},
    {{"action": "remove_step", "step_id": 4}}
  ]
}}
"""
            
            # Вызываем GigaChat напрямую для анализа
            messages = [
                {"role": "system", "content": "Ты планировщик workflow. Анализируй результаты и предлагай оптимизации."},
                {"role": "user", "content": optimization_prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3  # Низкая температура для консервативных решений
            )
            
            # Парсим ответ
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                optimization_data = json.loads(json_match.group())
                
                if optimization_data.get("optimize"):
                    self.logger.info(f"📊 Optimization suggested: {optimization_data.get('reason')}")
                    
                    # Применяем изменения к плану
                    updated_plan = self._apply_plan_changes(
                        current_plan,
                        optimization_data.get("changes", [])
                    )
                    
                    return {
                        "should_update": True,
                        "updated_plan": updated_plan,
                        "changes": optimization_data.get("reason"),
                        "optimization_data": optimization_data
                    }
                else:
                    self.logger.info(f"✅ Plan is optimal: {optimization_data.get('reason')}")
                    return {
                        "should_update": False,
                        "reason": optimization_data.get("reason")
                    }
            else:
                self.logger.warning("Could not parse optimization response")
                return {"should_update": False}
                
        except Exception as e:
            self.logger.error(f"❌ Error during plan optimization: {e}", exc_info=True)
            return {"should_update": False}
    
    def _apply_plan_changes(
        self,
        current_plan: Dict[str, Any],
        changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Применяет изменения к плану.
        
        Поддерживает действия:
        - add_step: добавить новый шаг
        - modify_step: изменить существующий шаг
        - remove_step: удалить шаг
        """
        updated_plan = current_plan.copy()
        steps = list(updated_plan.get("steps", []))
        
        for change in changes:
            action = change.get("action")
            
            if action == "add_step":
                after_step = change.get("after_step", len(steps))
                new_step = change.get("step", {})
                steps.insert(after_step, new_step)
                self.logger.info(f"➕ Added step after position {after_step}")
                
            elif action == "modify_step":
                step_id = change.get("step_id")
                modifications = change.get("changes", {})
                for i, step in enumerate(steps):
                    if step.get("step_id") == step_id:
                        steps[i].update(modifications)
                        self.logger.info(f"✏️ Modified step {step_id}")
                        break
                        
            elif action == "remove_step":
                step_id = change.get("step_id")
                steps = [s for s in steps if s.get("step_id") != step_id]
                self.logger.info(f"➖ Removed step {step_id}")
        
        updated_plan["steps"] = steps
        return updated_plan
    
    async def _handle_step_error(
        self,
        step: Dict[str, Any],
        step_index: int,
        error: Exception,
        step_result: Dict[str, Any],
        full_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обрабатывает ошибку шага и принимает решение о дальнейших действиях.
        
        Вызывает PlannerAgent._evaluate_result для анализа ошибки.
        
        Returns:
            - decision: "continue", "retry", "replan", "abort"
            - message: пояснение решения
        """
        self.logger.info(f"🔍 Evaluating error in step {step_index}...")
        
        try:
            # Вызываем PlannerAgent для оценки ошибки
            evaluation = await self.agents["planner"].process_task(
                task={
                    "type": "evaluate_result",
                    "step_result": step_result,
                    "step_id": step.get("step_id", step_index)
                },
                context=full_context
            )
            
            if evaluation.get("status") == "success":
                decision = evaluation.get("decision", "abort")
                message = evaluation.get("message", "Unknown error")
                
                self.logger.info(f"📊 Decision: {decision} - {message}")
                
                return {
                    "decision": decision,
                    "message": message,
                    "evaluation": evaluation
                }
            else:
                # Если оценка не удалась, используем fallback
                self.logger.warning("⚠️ Evaluation failed, using fallback decision")
                return {
                    "decision": "abort",
                    "message": "Could not evaluate error"
                }
                
        except Exception as eval_error:
            self.logger.error(f"❌ Error during evaluation: {eval_error}", exc_info=True)
            return {
                "decision": "abort",
                "message": f"Evaluation failed: {eval_error}"
            }
    
    async def process_request(
        self,
        user_request: str,
        board_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает пользовательский запрос через мультиагентную систему.
        
        Args:
            user_request: Текст запроса пользователя
            board_id: ID доски
            user_id: ID пользователя (опционально)
            session_id: ID сессии (если None, создается новый)
            context: Дополнительный контекст (selected_nodes, board_context, etc.)
        
        Returns:
            Результат выполнения с полями:
            - status: "success" | "error"
            - session_id: ID сессии
            - plan: План выполнения от Planner
            - results: Результаты от всех агентов
            - execution_time: Время выполнения в секундах
            - error: Описание ошибки (если status="error")
        """
        if not self.is_initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        session_id = session_id or f"session_{uuid4().hex[:12]}"
        start_time = datetime.now()
        
        self.logger.info(f"🎬 Processing request in session {session_id}")
        self.logger.info(f"📝 User request: {user_request}")
        
        try:
            # Формируем контекст
            full_context = {
                "session_id": session_id,
                "board_id": board_id,
                "user_id": user_id,
                **(context or {})
            }
            
            # ========== STEP 1: Planner создает план ==========
            self.logger.info("📋 Step 1: Creating execution plan...")
            
            plan_result = await self.agents["planner"].process_task(
                task={
                    "type": "create_plan",
                    "user_request": user_request,
                    "board_context": full_context.get("board_context", {}),
                    "selected_node_ids": full_context.get("selected_node_ids", [])
                },
                context=full_context
            )
            
            if plan_result.get("status") != "success":
                return {
                    "status": "error",
                    "session_id": session_id,
                    "error": f"Planning failed: {plan_result}",
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Извлекаем план из результата (может быть в plan или прямо в корне)
            plan = plan_result.get("plan", plan_result)
            steps = plan.get("steps", [])
            
            self.logger.info(f"✅ Plan created with {len(steps)} steps")
            
            # ========== STEP 2: Выполняем план последовательно ==========
            results = {
                "plan": plan_result
            }
            
            replan_count = 0
            step_index = 0
            
            while step_index < len(steps):
                i = step_index + 1
                step = steps[step_index]
                agent_name = step.get("agent")
                task = step.get("task", {})
                depends_on = step.get("depends_on", [])
                retry_count = 0
                
                self.logger.info(f"🔄 Step {i}/{len(steps)}: {agent_name} - {task.get('type')}")
                
                # Проверяем наличие агента
                if agent_name not in self.agents:
                    self.logger.warning(f"⚠️ Agent '{agent_name}' not enabled, skipping step {i}")
                    step_index += 1
                    continue
                
                # Формируем контекст с результатами предыдущих шагов
                step_context = full_context.copy()
                step_context["previous_results"] = {}
                
                # Добавляем зависимые результаты (по step_id)
                for dep_step_id in depends_on:
                    dep_key = f"step_{dep_step_id}"
                    if dep_key in results:
                        step_context["previous_results"][dep_step_id] = results[dep_key]
                
                # Добавляем все предыдущие результаты агентов по именам
                # ВАЖНО: Проверяем и step_X и agent_name
                for key, value in results.items():
                    if key.startswith("step_"):
                        # Извлекаем имя агента из результата
                        agent_result_name = value.get("agent")
                        if agent_result_name:
                            step_context["previous_results"][agent_result_name] = value
                    elif key in ["search", "analyst", "researcher", "reporter", "transformation"]:
                        step_context["previous_results"][key] = value
                
                # Если это ResearcherAgent и есть результаты SearchAgent, автоматически передаём URLs
                if agent_name == "researcher" and task.get("type") == "fetch_urls":
                    if "search" in step_context["previous_results"]:
                        search_result = step_context["previous_results"]["search"]
                        if search_result.get("status") == "success":
                            # URLs будут извлечены ResearcherAgent из previous_results
                            self.logger.info(f"🔗 ResearcherAgent will fetch URLs from SearchAgent results")
                
                # Если это AnalystAgent и есть результаты, обогащаем task
                if agent_name == "analyst":
                    # Приоритет: ResearcherAgent > SearchAgent
                    data_source = None
                    
                    # Сначала проверяем ResearcherAgent (полное содержимое страниц)
                    if "researcher" in step_context["previous_results"]:
                        researcher_result = step_context["previous_results"]["researcher"]
                        if researcher_result.get("status") == "success" and researcher_result.get("pages"):
                            data_source = "researcher"
                            if "data_summary" not in task:
                                # Создаём summary из загруженных страниц
                                pages = researcher_result.get("pages", [])
                                summary_parts = [f"- {p.get('title', 'N/A')}: {p.get('content', '')[:200]}..." for p in pages[:3]]
                                task["data_summary"] = "\n".join(summary_parts)
                            if "data" not in task:
                                task["data"] = {
                                    "pages": researcher_result.get("pages", []),
                                    "pages_fetched": researcher_result.get("pages_fetched", 0),
                                    "source": "web_pages"
                                }
                            self.logger.info(f"📥 AnalystAgent will analyze {researcher_result.get('pages_fetched', 0)} fetched pages")
                    
                    # Если ResearcherAgent не сработал, fallback на SearchAgent (только snippets)
                    elif "search" in step_context["previous_results"]:
                        search_result = step_context["previous_results"]["search"]
                        if search_result.get("status") == "success":
                            data_source = "search"
                            # SearchAgent возвращает данные напрямую в корне
                            if "data_summary" not in task and search_result.get("summary"):
                                task["data_summary"] = search_result["summary"]
                            # Передаём всю структуру результата как data
                            if "data" not in task:
                                task["data"] = {
                                    "query": search_result.get("query"),
                                    "results": search_result.get("results", []),
                                    "summary": search_result.get("summary", ""),
                                    "sources": search_result.get("sources", []),
                                    "result_count": search_result.get("result_count", 0)
                                }
                            self.logger.info(f"📥 AnalystAgent will analyze SearchAgent results (snippets only)")
                
                # Выполняем задачу (с возможностью retry)
                step_success = False
                
                while not step_success and retry_count <= MAX_RETRY_ATTEMPTS:
                    try:
                        result = await self.agents[agent_name].process_task(
                            task=task,
                            context=step_context
                        )
                        
                        # Проверяем статус результата
                        if result.get("status") in ["success", "partial_success"]:
                            # Сохраняем результат
                            results[f"step_{step.get('step_id')}"] = result
                            results[agent_name] = result  # Также по имени агента для удобства
                            
                            self.logger.info(f"✅ Step {i} completed: {result.get('status', 'N/A')}")
                            
                            # ========== ADAPTIVE PLANNING: Пересматриваем план на основе новых результатов ==========
                            if self.adaptive_planning and replan_count < MAX_REPLAN_ATTEMPTS:
                                should_replan = await self._should_replan_after_step(
                                    current_plan=plan,
                                    step=step,
                                    step_index=i,
                                    step_result=result,
                                    all_results=results,
                                    full_context=full_context
                                )
                                
                                # Логируем решение GigaChat
                                self.logger.info(f"🤖 GigaChat replan decision: {should_replan.get('replan')}")
                                self.logger.info(f"   Reason: {should_replan.get('reason')}")
                                
                                if should_replan.get("replan"):
                                    replan_count += 1
                                    self.logger.info(f"🔄 Replanning based on step {i} results (attempt {replan_count}/{MAX_REPLAN_ATTEMPTS})...")
                                    
                                    # Вызываем полноценный replan с контекстом всех результатов
                                    replan_result = await self.agents["planner"].process_task(
                                        task={
                                            "type": "replan",
                                            "original_plan": plan,
                                            "current_results": results,
                                            "completed_steps": i,
                                            "reason": should_replan.get("reason", "Adapting to new information")
                                        },
                                        context=full_context
                                    )
                                    
                                    if replan_result.get("status") == "success":
                                        new_plan = replan_result.get("plan", {})
                                        new_steps = new_plan.get("steps", [])
                                        
                                        self.logger.info(f"✅ Plan updated: {len(steps)} → {len(new_steps)} steps")
                                        plan = new_plan
                                        steps = new_steps
                                        
                                        # Сохраняем информацию о replanning
                                        results[f"replan_{replan_count}"] = {
                                            "after_step": i,
                                            "old_steps_count": len(steps),
                                            "new_steps_count": len(new_steps),
                                            "reason": should_replan.get("reason"),
                                            "changes": replan_result.get("changes", "Plan updated based on results")
                                        }
                                    else:
                                        self.logger.warning(f"⚠️ Replanning failed: {replan_result}")
                            
                            step_success = True
                            step_index += 1  # Переходим к следующему шагу
                            
                        elif result.get("status") == "error":
                            # Агент вернул ошибку - обрабатываем через evaluation
                            raise Exception(result.get("error", "Unknown error from agent"))
                        else:
                            # Неизвестный статус - считаем успехом
                            results[f"step_{step.get('step_id')}"] = result
                            results[agent_name] = result
                            step_success = True
                            step_index += 1
                        
                    except Exception as e:
                        self.logger.error(f"❌ Step {i} failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS + 1}): {e}")
                        
                        # Формируем результат ошибки
                        error_result = {
                            "status": "error",
                            "error": str(e),
                            "agent": agent_name,
                            "step_id": step.get("step_id", i),
                            "attempt": retry_count + 1
                        }
                        
                        # Получаем решение от PlannerAgent
                        decision_result = await self._handle_step_error(
                            step=step,
                            step_index=i,
                            error=e,
                            step_result=error_result,
                            full_context=full_context
                        )
                        
                        decision = decision_result.get("decision", "abort")
                        
                        if decision == "retry" and retry_count < MAX_RETRY_ATTEMPTS:
                            retry_count += 1
                            self.logger.info(f"🔁 Retrying step {i} (attempt {retry_count + 1})...")
                            continue
                            
                        elif decision == "replan" and replan_count < MAX_REPLAN_ATTEMPTS:
                            replan_count += 1
                            self.logger.info(f"🔄 Replanning workflow (attempt {replan_count}/{MAX_REPLAN_ATTEMPTS})...")
                            
                            # Вызываем перепланирование
                            replan_result = await self.agents["planner"].process_task(
                                task={
                                    "type": "replan",
                                    "original_plan": plan,
                                    "current_results": results,
                                    "failed_step": step,
                                    "reason": decision_result.get("message", "Step failed")
                                },
                                context=full_context
                            )
                            
                            if replan_result.get("status") == "success":
                                # Обновляем план
                                new_plan = replan_result.get("plan", {})
                                steps = new_plan.get("steps", [])
                                self.logger.info(f"✅ Plan updated with {len(steps)} steps")
                                
                                # Сохраняем информацию о replanning
                                results[f"replan_{replan_count}"] = replan_result
                                
                                # Начинаем с текущего шага заново
                                step_success = True  # Выходим из retry loop
                                # step_index остаётся прежним - повторим этот шаг с новым планом
                            else:
                                self.logger.error(f"❌ Replanning failed: {replan_result}")
                                decision = "abort"  # Переходим к abort
                        
                        if decision == "abort" or decision == "continue":
                            # Сохраняем ошибку и продолжаем/останавливаем
                            results[f"step_{step.get('step_id')}"] = error_result
                            results[agent_name] = error_result
                            
                            if decision == "abort":
                                self.logger.error(f"🛑 Aborting workflow due to critical error in step {i}")
                                return {
                                    "status": "error",
                                    "session_id": session_id,
                                    "plan": plan,
                                    "results": results,
                                    "error": f"Workflow aborted at step {i}: {str(e)}",
                                    "execution_time": (datetime.now() - start_time).total_seconds(),
                                    "abort_reason": decision_result.get("message")
                                }
                            else:
                                # continue - переходим к следующему шагу
                                self.logger.warning(f"⚠️ Continuing to next step despite error in step {i}")
                                step_success = True
                                step_index += 1
                        
                        # Если ни retry, ни replan, ни abort/continue не сработали
                        if not step_success:
                            self.logger.error(f"❌ All retry attempts exhausted for step {i}")
                            results[f"step_{step.get('step_id')}"] = error_result
                            step_success = True
                            step_index += 1
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(f"✅ Request processed in {execution_time:.2f}s")
            
            return {
                "status": "success",
                "session_id": session_id,
                "plan": plan,  # Возвращаем объект плана, а не plan_result
                "results": results,
                "execution_time": execution_time
            }
            
        except Exception as e:
            self.logger.error(f"❌ Request processing failed: {e}", exc_info=True)
            
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "execution_time": (datetime.now() - start_time).total_seconds()
            }
    
    async def shutdown(self) -> None:
        """Завершает работу движка и освобождает ресурсы."""
        self.logger.info("🛑 Shutting down MultiAgentEngine...")
        
        try:
            # Отключаем агентов (если они подписаны на MessageBus)
            # В текущей реализации агенты не требуют явного shutdown
            
            # Отключаем Message Bus
            if self.message_bus:
                await self.message_bus.disconnect()
                self.logger.info("✅ Message Bus disconnected")
            
            # Закрываем Redis
            await close_redis()
            self.logger.info("✅ Redis closed")
            
            self.is_initialized = False
            self.logger.info("✅ MultiAgentEngine shutdown complete")
            
        except Exception as e:
            self.logger.error(f"⚠️ Error during shutdown: {e}", exc_info=True)
    
    def get_agent(self, agent_name: str) -> Optional[Any]:
        """
        Возвращает агента по имени (для прямого доступа).
        
        Args:
            agent_name: Имя агента (planner, search, analyst, etc.)
        
        Returns:
            Экземпляр агента или None
        """
        return self.agents.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """Возвращает список всех активных агентов."""
        return list(self.agents.keys())
    
    @property
    def ready(self) -> bool:
        """Проверяет готовность движка к работе."""
        return self.is_initialized and self.gigachat is not None and self.message_bus is not None
