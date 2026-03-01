"""
Orchestrator V2 — единый координатор Multi-Agent системы.

**Ключевые изменения** по сравнению с V1:
- Единый путь (Engine упразднён, вся логика здесь)
- Агенты инициализируются внутри Orchestrator (перенесено из Engine)
- Нулевой маппинг: ``agent_results: list[dict]`` передаётся
  агентам как есть, каждый агент сам берёт нужные секции
- QualityGateAgent для pipeline-level validation
- Возвращает ``AgentPayload`` (а не raw dict)
- Поддержка adaptive planning и retry/replan

См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.executors.python_executor import PythonExecutor
from .config import TimeoutConfig
from .message_bus import AgentMessageBus
from .message_types import MessageType, AgentMessage
from .schemas.agent_payload import AgentPayload, Plan, PlanStep

logger = logging.getLogger(__name__)

# Retry / replan limits
MAX_REPLAN_ATTEMPTS = 3
MAX_RETRY_ATTEMPTS = 1
MAX_VALIDATION_ITERATIONS = 3


class Orchestrator:
    """
    V2 Orchestrator — единый путь выполнения Multi-Agent запросов.

    Жизненный цикл::

        orchestrator = Orchestrator(
            gigachat_api_key="...",
            enable_agents=["planner", "discovery", "research", ...],
        )
        await orchestrator.initialize()   # Redis → GigaChat → Agents
        result = await orchestrator.process_request(...)
        await orchestrator.shutdown()

    При инициализации создаёт инстансы всех включённых агентов, подписывает
    их на MessageBus (``start_listening``). ``process_request()`` вызывает
    агентов напрямую через ``agent.process_task()`` — все агенты in-process.
    """

    def __init__(
        self,
        gigachat_api_key: Optional[str] = None,
        enable_agents: Optional[List[str]] = None,
        adaptive_planning: bool = True,
    ):
        self.gigachat_api_key = gigachat_api_key or os.getenv("GIGACHAT_API_KEY")
        self.enable_agents = enable_agents or [
            "planner", "discovery", "research", "structurizer",
            "analyst", "transform_codex", "widget_codex", "reporter", "validator",
        ]
        self.adaptive_planning = adaptive_planning

        self.gigachat: Optional[GigaChatService] = None
        self.message_bus: Optional[AgentMessageBus] = None
        self.agents: Dict[str, Any] = {}
        self.is_initialized = False

        self._logger = logging.getLogger(f"{__name__}.Orchestrator")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Инициализирует Redis → GigaChat → MessageBus → агенты."""
        if self.is_initialized:
            self._logger.warning("Orchestrator already initialized")
            return

        self._logger.info("🚀 Initializing Orchestrator V2...")

        try:
            # 1. Redis
            await init_redis()
            self._logger.info("✅ Redis initialized")

            # 2. GigaChat
            if not self.gigachat_api_key:
                raise ValueError("GIGACHAT_API_KEY not provided")
            self.gigachat = GigaChatService(api_key=self.gigachat_api_key)
            self._logger.info("✅ GigaChat initialized")

            # 3. MessageBus
            self.message_bus = AgentMessageBus()
            await self.message_bus.connect()
            self._logger.info("✅ MessageBus connected")
            
            # 3.5. PythonExecutor для ValidatorAgent
            self.executor = PythonExecutor()
            self._logger.info("✅ PythonExecutor initialized")

            # 4. Агенты
            await self._initialize_agents()
            self._logger.info(f"✅ {len(self.agents)} agents initialized")

            self.is_initialized = True
            self._logger.info("✅ Orchestrator V2 ready")

        except Exception as e:
            self._logger.error(f"❌ Orchestrator init failed: {e}", exc_info=True)
            await self.shutdown()
            raise RuntimeError(f"Orchestrator initialization failed: {e}")

    async def _initialize_agents(self) -> None:
        """Создаёт и запускает агентов на основе ``self.enable_agents``."""
        # Lazy imports — агенты могут ещё не существовать на ранних фазах
        agent_registry: Dict[str, Any] = {}

        # --- V2 core agents ---
        try:
            from .agents.planner import PlannerAgent
            agent_registry["planner"] = lambda: PlannerAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("PlannerAgent not available")

        try:
            from .agents.discovery import DiscoveryAgent
            agent_registry["discovery"] = lambda: DiscoveryAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except Exception as e:
            self._logger.warning(f"DiscoveryAgent not available: {type(e).__name__}: {e}")

        try:
            from .agents.research import ResearchAgent
            agent_registry["research"] = lambda: ResearchAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except Exception as e:
            self._logger.warning(f"ResearchAgent not available: {type(e).__name__}: {e}")

        try:
            from .agents.structurizer import StructurizerAgent
            agent_registry["structurizer"] = lambda: StructurizerAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("StructurizerAgent not available")

        try:
            from .agents.analyst import AnalystAgent
            agent_registry["analyst"] = lambda: AnalystAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("AnalystAgent not available")

        try:
            from .agents.transform_codex import TransformCodexAgent
            agent_registry["transform_codex"] = lambda: TransformCodexAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("TransformCodexAgent not available")

        try:
            from .agents.widget_codex import WidgetCodexAgent
            agent_registry["widget_codex"] = lambda: WidgetCodexAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("WidgetCodexAgent not available")

        try:
            from .agents.reporter import ReporterAgent
            agent_registry["reporter"] = lambda: ReporterAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat,
            )
        except ImportError:
            self._logger.debug("ReporterAgent not available")

        try:
            from .agents.quality_gate import QualityGateAgent
            agent_registry["validator"] = lambda: QualityGateAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat,
                executor=self.executor,
            )
        except ImportError:
            self._logger.debug("QualityGateAgent not available")

        # Создаём только запрошенные агенты
        self._logger.info(f"  📋 Registry keys: {list(agent_registry.keys())}")
        self._logger.info(f"  📋 Enable agents: {self.enable_agents}")
        for name in self.enable_agents:
            factory = agent_registry.get(name)
            if factory:
                try:
                    self.agents[name] = factory()
                    await self.agents[name].start_listening()
                    self._logger.info(f"  ✅ {name} agent listening")
                except Exception as e:
                    self._logger.warning(f"  ⚠️ Failed to init {name}: {e}")
            else:
                self._logger.warning(f"  ⚠️ Agent '{name}' not found in registry, skipping")

    async def shutdown(self) -> None:
        """Останавливает Orchestrator и освобождает ресурсы."""
        self._logger.info("🛑 Shutting down Orchestrator V2...")
        try:
            if self.message_bus:
                await self.message_bus.disconnect()
                self._logger.info("✅ MessageBus disconnected")
            await close_redis()
            self._logger.info("✅ Redis closed")
        except Exception as e:
            self._logger.error(f"⚠️ Error during shutdown: {e}", exc_info=True)
        self.is_initialized = False
        self._logger.info("✅ Orchestrator V2 shutdown complete")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_request(
        self,
        user_request: str,
        board_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        skip_validation: bool = False,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Обрабатывает пользовательский запрос через Multi-Agent pipeline.

        Цикл выполнения::

            PlannerAgent → [execute steps] → ValidatorAgent
                                             ├── valid   → return
                                             └── invalid → replan (до MAX)

        Нулевой маппинг: ``agent_results`` передаётся агентам как есть.
        Каждый агент сам берёт нужные секции из ``AgentPayload``.

        Args:
            user_request: Текст запроса пользователя
            board_id: ID доски
            user_id: ID пользователя
            session_id: ID сессии (если None — создаётся)
            context: Дополнительный контекст (selected_node_ids, content_nodes_data, etc.)
            skip_validation: Пропустить ValidatorAgent

        Returns:
            Dict с результатом:
            - status: "success" | "error"
            - session_id: ID сессии
            - plan: План выполнения
            - results: dict[str, AgentPayload serialized]
            - execution_time: Время в секундах
        """
        if not self.is_initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

        session_id = session_id or f"session_{uuid4().hex[:12]}"
        start_time = datetime.now()

        self._logger.info(f"🎬 [{session_id}] Processing: {user_request[:120]}...")

        try:
            # См. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md — один мутабельный pipeline_context
            pipeline_context: Dict[str, Any] = {
                "session_id": session_id,
                "board_id": board_id,
                "user_id": user_id,
                "user_request": user_request,
                **(context or {}),
                "agent_results": [],  # append-only, последний ключ (Изменение #2)
            }

            # ============================================================
            # STEP 1: PlannerAgent — создание плана
            # ============================================================
            self._logger.info(f"📋 [{session_id}] Step 1: Planning...")

            plan_payload = await self._execute_agent(
                "planner",
                task={
                    "type": "create_plan",
                    "user_request": user_request,
                    "board_context": pipeline_context.get("board_context", {}),
                    "selected_node_ids": pipeline_context.get("selected_node_ids", []),
                },
                context=pipeline_context,
            )
            # Записываем результат планнера в хронологию
            pipeline_context["agent_results"].append(
                plan_payload.model_dump() if isinstance(plan_payload, AgentPayload) else plan_payload
            )

            # Извлекаем план
            plan = self._extract_plan(plan_payload)
            if not plan or not plan.get("steps"):
                return self._error_result(
                    session_id, start_time,
                    "Planner Agent не смог создать план выполнения",
                )

            steps = plan.get("steps", [])
            self._logger.info(f"✅ [{session_id}] Plan: {len(steps)} steps")

            # ============================================================
            # STEP 2 & 3: Execution + Validation Loop
            # Master loop для поддержки replanning после валидации
            # ============================================================
            raw_results: Dict[str, Any] = {"plan": plan}
            replan_count = 0
            
            # Индекс начала результатов текущего плана в agent_results.
            # При replan сдвигаем, чтобы _validate_results агрегировала
            # только результаты текущего цикла, а не старые сломанные code_blocks.
            current_plan_results_start = len(pipeline_context.get("agent_results", []))
            # FIX: Записываем в pipeline_context, чтобы reporter и другие агенты
            # могли читать только результаты текущего плана (без стейла прошлых replan).
            pipeline_context["current_plan_results_start"] = current_plan_results_start
            
            # Master execution loop - продолжается пока не выполнится успешно или не кончатся попытки
            while replan_count <= MAX_REPLAN_ATTEMPTS:
                step_index = 0

                # ============================================================
                # STEP 2: Последовательное выполнение шагов (zero mapping)
                # ============================================================
                while step_index < len(steps):
                    step = steps[step_index]
                    agent_name = step.get("agent", "unknown")
                    task_data = step.get("task", {})
                    step_id = step.get("step_id", str(step_index + 1))

                    self._logger.info(
                        f"⚙️ [{session_id}] Step {step_index + 1}/{len(steps)}: "
                        f"{agent_name} — {task_data.get('type', task_data.get('description', 'N/A'))}"
                    )

                    # Проверяем наличие агента; если имя неизвестное —
                    # пытаемся вывести реальный agent из описания задачи
                    if agent_name not in self.agents:
                        resolved = self._resolve_agent_name(agent_name, task_data)
                        if resolved:
                            self._logger.info(
                                f"🔀 Resolved unknown agent '{agent_name}' → '{resolved}'"
                            )
                            agent_name = resolved
                        else:
                            self._logger.warning(f"⚠️ Agent '{agent_name}' not enabled, skipping")
                            step_index += 1
                            continue

                    # Изменение #6: QualityGate получает execution_context (полные DataFrame)
                    if agent_name == "validator" and execution_context:
                        agent_ctx = {**pipeline_context, **execution_context}
                    else:
                        agent_ctx = pipeline_context

                    # Выполняем с retry
                    step_payload = await self._execute_with_retry(
                        agent_name, task_data, agent_ctx,
                    )

                    # Проверяем качество результата агента
                    # Если данные некорректные или парсинг провалился → попытка replan
                    if step_payload.status == "error" and replan_count < MAX_REPLAN_ATTEMPTS:
                        self._logger.warning(
                            f"⚠️ [{session_id}] {agent_name} failed with error: {step_payload.error}"
                        )
                        
                        # FIX: Сохраняем ошибочный результат в agent_results ПЕРЕД replan,
                        # чтобы агенты в новом плане видели, что пошло не так.
                        # Ранее `continue` пропускал append → ошибка терялась из общего контекста.
                        error_result_dict = (
                            step_payload.model_dump()
                            if isinstance(step_payload, AgentPayload)
                            else step_payload
                        )
                        pipeline_context["agent_results"].append(error_result_dict)
                        
                        # FIX: Инжектируем ошибку в pipeline_context,
                        # чтобы codex мог прочитать previous_error напрямую из context.
                        pipeline_context["previous_error"] = step_payload.error
                        pipeline_context["error_retry"] = True
                        pipeline_context["failed_agent"] = agent_name
                        
                        # FIX: Инжектируем previous_code из последнего code_block,
                        # чтобы Codex видел какой код не сработал и мог исправить именно его.
                        failed_code = self._extract_last_code(pipeline_context.get("agent_results", []))
                        if failed_code:
                            pipeline_context["previous_code"] = failed_code
                            self._logger.info(
                                f"📎 [{session_id}] Injected previous_code ({len(failed_code)} chars) for Codex replan"
                            )
                        
                        # Попытка replanning для исправления ошибки
                        replan_count += 1
                        self._logger.info(
                            f"🔄 [{session_id}] Replanning after agent error "
                            f"({replan_count}/{MAX_REPLAN_ATTEMPTS}): {step_payload.error}"
                        )
                        
                        new_plan = await self._replan(
                            plan, 
                            pipeline_context, 
                            {
                                "last_error": step_payload.error,
                                "failed_agent": agent_name,
                            }
                        )
                        
                        if new_plan and new_plan.get("steps"):
                            plan = new_plan
                            steps = plan["steps"]
                            raw_results["plan"] = plan
                            raw_results[f"replan_{replan_count}"] = {
                                "after_step": step_index + 1,
                                "reason": f"Agent {agent_name} error: {step_payload.error}",
                                "type": "error_recovery",
                            }
                            # Новый план выполняется с начала
                            current_plan_results_start = len(pipeline_context.get("agent_results", []))
                            pipeline_context["current_plan_results_start"] = current_plan_results_start
                            step_index = 0
                            continue
                        else:
                            self._logger.warning(f"⚠️ [{session_id}] Replanning failed, continuing with error")
                            # Ошибочный результат уже в agent_results (append выше).
                            # Сохраняем в raw_results и Redis, затем переходим к следующему шагу.
                            if agent_name in raw_results:
                                run_num = 2
                                while f"{agent_name}_{run_num}" in raw_results:
                                    run_num += 1
                                raw_results[f"{agent_name}_{run_num}"] = error_result_dict
                            else:
                                raw_results[agent_name] = error_result_dict
                            step_index += 1
                            continue

                    # Изменение #2: append в agent_results (chronological list)
                    result_dict = step_payload.model_dump() if isinstance(step_payload, AgentPayload) else step_payload
                    pipeline_context["agent_results"].append(result_dict)

                    # raw_results: append-only для обратной совместимости (return format)
                    if agent_name in raw_results:
                        run_num = 2
                        while f"{agent_name}_{run_num}" in raw_results:
                            run_num += 1
                        raw_results[f"{agent_name}_{run_num}"] = result_dict
                    else:
                        raw_results[agent_name] = result_dict

                    # Сохраняем в Redis для межагентного доступа
                    if self.message_bus:
                        try:
                            await self.message_bus.store_session_result(
                                session_id=session_id,
                                agent_name=agent_name,
                                result=result_dict,
                            )
                        except Exception as e:
                            self._logger.warning(f"⚠️ Failed to store result in Redis: {e}")

                    if step_payload.status == "error":
                        self._logger.warning(f"⚠️ [{session_id}] {agent_name} returned error: {step_payload.error}")

                    self._logger.info(f"✅ [{session_id}] {agent_name} done (status={step_payload.status})")

                    # Adaptive planning: проверяем необходимость replan
                    # Adaptive replanning: intelligently decide when to replan
                    # ВАЖНО: Делаем replan ТОЛЬКО в критических случаях:
                    # - Есть suggested_steps от ValidatorAgent (ошибки валидации)
                    # - Discovery нашёл дополнительные источники данных
                    # - Structurizer извлёк неожиданную структуру
                    # НЕ делаем replan для simple успешных шагов (analyst → reporter в discussion mode)
                    should_check_replan = False
                    
                    # Проверяем есть ли suggested_steps от валидатора (ошибки validation/execution)
                    if pipeline_context.get("suggested_steps") or pipeline_context.get("validation_issues"):
                        should_check_replan = True
                    
                    # Discovery нашёл источники - может понадобиться research/structurizer
                    if step.get("agent") == "discovery" and step_payload.sources:
                        should_check_replan = True
                    
                    # Structurizer извлёк таблицы - может понадобиться дополнительный анализ
                    if step.get("agent") == "structurizer" and step_payload.tables:
                        should_check_replan = True
                    
                    if (
                        self.adaptive_planning
                        and should_check_replan
                        and step_payload.status == "success"
                        and replan_count < MAX_REPLAN_ATTEMPTS
                        and step_index < len(steps) - 1
                    ):
                        replan_decision = await self._should_replan(
                            plan, step, step_index, step_payload, pipeline_context,
                        )
                        if replan_decision.get("replan"):
                            replan_count += 1
                            self._logger.info(
                                f"🔄 [{session_id}] Replanning ({replan_count}/{MAX_REPLAN_ATTEMPTS}): "
                                f"{replan_decision.get('reason', 'N/A')}"
                            )
                            new_plan = await self._replan(plan, pipeline_context)
                            if new_plan and new_plan.get("steps"):
                                plan = new_plan
                                steps = plan["steps"]
                                raw_results["plan"] = plan
                                raw_results[f"replan_{replan_count}"] = {
                                    "after_step": step_index + 1,
                                    "reason": replan_decision.get("reason"),
                                    "type": "adaptive",
                                }
                                # Новый план выполняется с начала,
                                # agent_results сохранены для контекста агентов
                                current_plan_results_start = len(pipeline_context.get("agent_results", []))
                                pipeline_context["current_plan_results_start"] = current_plan_results_start
                                step_index = 0
                                continue

                    step_index += 1

                # ============================================================
                # STEP 3: ValidatorAgent — валидация результатов
                # ============================================================
                if not skip_validation and "validator" in self.agents:
                    self._logger.info(f"🔍 [{session_id}] Validating results...")
                    # Изменение #6: QualityGate получает execution_context (полные DataFrame)
                    validation_payload = await self._validate_results(
                        user_request, pipeline_context, execution_context,
                        current_plan_results_start=current_plan_results_start,
                    )
                    # Записываем результат валидации в хронологию
                    val_result_dict = (
                        validation_payload.model_dump()
                        if isinstance(validation_payload, AgentPayload)
                        else validation_payload
                    )
                    pipeline_context["agent_results"].append(val_result_dict)
                    raw_results["validator"] = val_result_dict
                    
                    # Проверяем результат валидации
                    if validation_payload.validation:
                        val_result = validation_payload.validation
                        
                        if not val_result.valid:
                            self._logger.warning(
                                f"⚠️ [{session_id}] Validation failed: {val_result.message}"
                            )
                            
                            # Если есть suggested_replan и не превышен лимит → replan
                            if val_result.suggested_replan and replan_count < MAX_REPLAN_ATTEMPTS:
                                replan_count += 1
                                self._logger.info(
                                    f"🔄 [{session_id}] Replanning after validation failure "
                                    f"({replan_count}/{MAX_REPLAN_ATTEMPTS}): {val_result.suggested_replan.reason}"
                                )
                                
                                # Создаём новый план на основе рекомендаций валидатора
                                replan_context = {
                                    "validation_failed": True,
                                    "validation_message": val_result.message,
                                    "validation_issues": [
                                        issue.model_dump() if hasattr(issue, 'model_dump') else issue 
                                        for issue in (val_result.issues or [])
                                    ],
                                    "suggested_steps": [
                                        step.model_dump() if hasattr(step, 'model_dump') else step
                                        for step in (val_result.suggested_replan.additional_steps or [])
                                    ],
                                }
                                
                                # FIX GAP 4: Транслируем error_details из suggested_replan
                                # в pipeline_context, чтобы codex мог прочитать при retry.
                                # QualityGate кладёт error_details в task каждого suggested step,
                                # но PlannerAgent (LLM) может их потерять при генерации нового плана.
                                # Дублируем в context как fallback.
                                for step_data in replan_context.get("suggested_steps", []):
                                    task_data = step_data.get("task", {}) if isinstance(step_data, dict) else {}
                                    ed = task_data.get("error_details")
                                    if ed:
                                        pipeline_context["previous_error"] = ed.get("error", "")
                                        pipeline_context["error_retry"] = True
                                        self._logger.info(
                                            f"📎 [{session_id}] Injected error_details into pipeline_context: "
                                            f"{ed.get('error', '')[:100]}"
                                        )
                                        break
                                
                                # FIX: Инжектируем previous_code из последнего code_block,
                                # чтобы Codex при replan видел неудачный код и мог исправить.
                                failed_code = self._extract_last_code(pipeline_context.get("agent_results", []))
                                if failed_code:
                                    pipeline_context["previous_code"] = failed_code
                                    self._logger.info(
                                        f"📎 [{session_id}] Injected previous_code ({len(failed_code)} chars) for validation replan"
                                    )
                                
                                new_plan = await self._replan(plan, pipeline_context, replan_context)
                                
                                if new_plan and new_plan.get("steps"):
                                    # Выполняем новый план
                                    plan = new_plan
                                    steps = plan["steps"]
                                    raw_results[f"replan_{replan_count}"] = {
                                        "reason": val_result.suggested_replan.reason,
                                        "type": "validation_recovery",
                                        "validation_issues": val_result.issues,
                                    }
                                    raw_results["plan"] = plan
                                    
                                    # Изменение #2: agent_results является append-only,
                                    # история сохраняется для контекста агентов
                                    
                                    self._logger.info(
                                        f"🔄 [{session_id}] Re-executing with new plan: "
                                        f"{len(steps)} steps, agent_results has {len(pipeline_context['agent_results'])} entries"
                                    )
                                    
                                    current_plan_results_start = len(pipeline_context.get("agent_results", []))
                                    pipeline_context["current_plan_results_start"] = current_plan_results_start
                                    step_index = 0
                                    # Продолжаем цикл while с начала нового плана
                                    continue
                                else:
                                    self._logger.warning(f"⚠️ [{session_id}] Validation-based replanning failed")
                                    # Replanning провалился → завершаем с текущими результатами
                                    break
                            else:
                                # FIX: Валидация не прошла, но нет suggested_replan
                                # или лимит replan исчерпан → завершаем с текущими результатами.
                                # БЕЗ этого break цикл while бесконечно повторяет
                                # execute → validate → fail → execute → ...
                                self._logger.warning(
                                    f"⚠️ [{session_id}] Validation failed without replan suggestion "
                                    f"(replan_count={replan_count}/{MAX_REPLAN_ATTEMPTS}), "
                                    f"finishing with current results"
                                )
                                break
                        else:
                            self._logger.info(f"✅ [{session_id}] Validation passed")
                            # Валидация прошла → завершаем успешно
                            break
                    else:
                        self._logger.info(f"✅ [{session_id}] Validation passed")
                        # Валидация прошла → завершаем успешно
                        break
                else:
                    # Валидация не запускалась → завершаем
                    break

            # ============================================================
            # Cleanup & Return (после выхода из master loop)
            # ============================================================
            # Добавляем replan metadata в plan для прозрачности
            # Это позволяет тестам и клиентам видеть историю перепланирования
            plan["replan_count"] = replan_count
            if replan_count > 0:
                plan["replan_history"] = [
                    v for k, v in raw_results.items()
                    if k.startswith("replan_") and isinstance(v, dict)
                ]
                plan["agent_results_at_replan"] = len(
                    pipeline_context.get("agent_results", [])
                )

            # Очищаем Redis session
            if self.message_bus:
                try:
                    await self.message_bus.clear_session_results(session_id)
                except Exception:
                    pass

            execution_time = (datetime.now() - start_time).total_seconds()
            self._logger.info(
                f"✅ [{session_id}] Completed in {execution_time:.2f}s "
                f"(replans: {replan_count})"
            )

            return {
                "status": "success",
                "session_id": session_id,
                "plan": plan,
                "results": raw_results,
                "execution_time": execution_time,
            }

        except Exception as e:
            self._logger.error(f"❌ [{session_id}] Failed: {e}", exc_info=True)
            return self._error_result(session_id, start_time, str(e))

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """Возвращает агента по имени."""
        return self.agents.get(agent_name)

    @staticmethod
    def _extract_last_code(agent_results: List[Dict[str, Any]]) -> Optional[str]:
        """
        Извлекает код из последнего успешного code_block в agent_results.
        Используется для инжекции previous_code при replan,
        чтобы Codex видел неудачный код и мог его исправить.
        """
        # Итерируем с конца — берём последний code_block
        for result in reversed(agent_results):
            if not isinstance(result, dict):
                continue
            code_blocks = result.get("code_blocks", [])
            for cb in reversed(code_blocks):
                if isinstance(cb, dict) and cb.get("code", "").strip():
                    return cb["code"]
        return None

    def list_agents(self) -> List[str]:
        """Список активных агентов."""
        return list(self.agents.keys())

    @property
    def ready(self) -> bool:
        """Orchestrator готов к работе."""
        return (
            self.is_initialized
            and self.gigachat is not None
            and self.message_bus is not None
        )

    # ------------------------------------------------------------------
    # Internal: agent name resolution
    # ------------------------------------------------------------------

    def _resolve_agent_name(
        self, unknown_name: str, task_data: Dict[str, Any]
    ) -> Optional[str]:
        """Попытка вывести реальное имя агента, если LLM вернул невалидное.

        GigaChat иногда ставит step_id или произвольное имя в поле agent.
        Эвристика: ищем ключевые слова в description/type задачи.
        """
        desc = (
            task_data.get("description", "")
            + " "
            + task_data.get("type", "")
        ).lower()

        # Карта ключевых слов → реальный agent
        keyword_map = [
            (["transform", "код", "code", "fix", "исправ", "ошибк", "error",
              "python", "pandas", "трансформ"], "transform_codex"),
            (["виджет", "widget", "визуализ", "chart", "echarts", "график"],
             "widget_codex"),
            (["анализ", "analys", "insight", "finding"], "analyst"),
            (["structur", "структур", "extract", "извлеч"], "structurizer"),
            (["report", "отчёт", "отчет", "итог", "summary"], "reporter"),
        ]

        for keywords, agent in keyword_map:
            if agent in self.agents and any(kw in desc for kw in keywords):
                return agent

        return None

    # ------------------------------------------------------------------
    # Internal: step execution
    # ------------------------------------------------------------------

    async def _execute_agent(
        self,
        agent_name: str,
        task: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AgentPayload:
        """Вызывает ``agent.process_task()`` с таймаутом. Возвращает AgentPayload."""
        agent = self.agents.get(agent_name)
        if not agent:
            return AgentPayload.make_error(
                agent=agent_name,
                error_message=f"Agent '{agent_name}' not available",
            )

        timeout = TimeoutConfig.get_timeout(MessageType.TASK_REQUEST, agent_name)

        try:
            result = await asyncio.wait_for(
                agent.process_task(task=task, context=context),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self._logger.error(f"⏱️ {agent_name} timeout after {timeout}s")
            return AgentPayload.make_error(
                agent=agent_name,
                error_message=f"Agent '{agent_name}' timeout ({timeout}s)",
                suggestions=["Попробуйте упростить запрос"],
            )
        except Exception as e:
            self._logger.error(f"❌ {agent_name} error: {e}", exc_info=True)
            return AgentPayload.make_error(
                agent=agent_name,
                error_message=str(e),
            )

        # Если агент вернул dict (V1 legacy) — оборачиваем в AgentPayload
        if isinstance(result, dict):
            return self._wrap_legacy_result(agent_name, result)

        return result

    async def _execute_with_retry(
        self,
        agent_name: str,
        task: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AgentPayload:
        """Выполняет шаг с retry (MAX_RETRY_ATTEMPTS).

        При ошибке инжектирует информацию об ошибке в context,
        чтобы агент мог учесть её при повторной генерации.
        """
        last_result: Optional[AgentPayload] = None

        for attempt in range(MAX_RETRY_ATTEMPTS + 1):
            result = await self._execute_agent(agent_name, task, context)
            last_result = result

            if result.status != "error":
                # Очищаем retry-контекст при успехе
                context.pop("_retry_attempt", None)
                return result

            if attempt < MAX_RETRY_ATTEMPTS:
                self._logger.warning(
                    f"🔁 Retrying {agent_name} (attempt {attempt + 2}/{MAX_RETRY_ATTEMPTS + 1}): "
                    f"{result.error}"
                )
                # FIX: Инжектируем ошибку в context, чтобы агент видел причину провала
                # и мог скорректировать генерацию (например, codex исправит SyntaxError).
                # Используем ключи previous_error/error_retry, которые codex уже читает.
                context["previous_error"] = result.error
                context["error_retry"] = True
                context["_retry_attempt"] = attempt + 2
                # Если агент вернул code_blocks — сохраняем неудачный код
                if result.code_blocks:
                    last_code = result.code_blocks[-1]
                    code_text = last_code.code if hasattr(last_code, "code") else (last_code.get("code", "") if isinstance(last_code, dict) else "")
                    if code_text:
                        context["previous_code"] = code_text
            else:
                self._logger.warning(
                    f"❌ All retries exhausted for {agent_name}: {result.error}"
                )
                # Очищаем retry-контекст
                context.pop("_retry_attempt", None)

        return last_result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal: plan extraction & replanning
    # ------------------------------------------------------------------

    def _extract_plan(self, payload: AgentPayload) -> Optional[Dict[str, Any]]:
        """Извлекает план из AgentPayload PlannerAgent.

        Поддерживает как V2 формат (``payload.plan``), так и V1 legacy
        (``plan`` в dict-результате).
        """
        # V2: AgentPayload.plan
        if isinstance(payload, AgentPayload) and payload.plan:
            return payload.plan.model_dump()

        # V1 legacy: dict с ключом "plan"
        if isinstance(payload, AgentPayload) and payload.metadata:
            legacy = payload.metadata.get("legacy_result", {})
            if isinstance(legacy, dict):
                plan = legacy.get("plan", legacy)
                if "steps" in plan:
                    return plan

        # Fallback: весь payload.model_dump() если есть status=success
        if isinstance(payload, AgentPayload) and payload.status == "success":
            dumped = payload.model_dump()
            if "plan" in dumped and dumped["plan"] and "steps" in dumped["plan"]:
                return dumped["plan"]

        # Ещё один fallback для V1: payload мог быть dict напрямую
        if isinstance(payload, dict):
            if "plan" in payload:
                plan = payload["plan"]
                if isinstance(plan, dict) and "steps" in plan:
                    return plan
            if "steps" in payload:
                return payload

        self._logger.warning("⚠️ Could not extract plan from Planner result")
        return None

    async def _should_replan(
        self,
        current_plan: Dict[str, Any],
        step: Dict[str, Any],
        step_index: int,
        step_result: AgentPayload,
        pipeline_context: Dict[str, Any],
    ) -> Dict[str, bool]:
        """Определяет, нужно ли пересматривать план после успешного шага.
        
        Включает расширенный контекст: результат текущего шага и
        накопленные результаты (agent_results) для информированного решения.
        См. docs/ADAPTIVE_PLANNING.md
        """
        if not self.gigachat:
            return {"replan": False}

        try:
            remaining_steps = current_plan.get("steps", [])[step_index + 1:]
            
            # Сериализуем накопленные результаты (agent_results) для контекста
            accumulated_summary = []
            for r in pipeline_context.get("agent_results", []):
                if isinstance(r, dict):
                    accumulated_summary.append(
                        f"  - {r.get('agent', '?')}: status={r.get('status')}, "
                        f"findings={len(r.get('findings', []))}, "
                        f"tables={len(r.get('tables', []))}, "
                        f"code_blocks={len(r.get('code_blocks', []))}"
                    )
            accumulated_text = "\n".join(accumulated_summary) if accumulated_summary else "  (пока нет)"

            # Описываем результат текущего шага
            step_output_parts = []
            if step_result.findings:
                step_output_parts.append(f"findings: {len(step_result.findings)}")
            if step_result.tables:
                step_output_parts.append(f"tables: {len(step_result.tables)}")
            if step_result.sources:
                step_output_parts.append(f"sources: {len(step_result.sources)}")
            if step_result.code_blocks:
                step_output_parts.append(f"code_blocks: {len(step_result.code_blocks)}")
            step_output = ", ".join(step_output_parts) if step_output_parts else "no output data"

            # Описываем оставшиеся шаги
            remaining_agents = [s.get("agent", "?") for s in remaining_steps]

            prompt = (
                f"Ты - AI планировщик. Анализируй, нужно ли пересмотреть план.\n\n"
                f"ТЕКУЩИЙ ШАГ #{step_index + 1}:\n"
                f"  Агент: {step.get('agent')}\n"
                f"  Статус: {step_result.status}\n"
                f"  Результат: {step_output}\n\n"
                f"НАКОПЛЕННЫЕ РЕЗУЛЬТАТЫ АГЕНТОВ:\n{accumulated_text}\n\n"
                f"ОСТАВШИЕСЯ ШАГИ ({len(remaining_steps)}):\n"
                f"  Агенты: {', '.join(remaining_agents) if remaining_agents else 'нет'}\n\n"
                f"Нужно ли пересмотреть план? Учитывай:\n"
                f"- Агент нашёл неожиданные данные → план может измениться\n"
                f"- Агент нашёл новые источники → нужны дополнительные шаги\n"
                f"- Оставшиеся шаги уже не актуальны\n\n"
                f"Ответь JSON: {{\"replan\": true/false, \"reason\": \"...\"}}"
            )

            response = await self.gigachat.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self._logger.debug(f"Replan analysis failed: {e}")

        return {"replan": False}

    async def _replan(
        self,
        current_plan: Dict[str, Any],
        pipeline_context: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Вызывает PlannerAgent для перепланирования."""
        if "planner" not in self.agents:
            return None

        try:
            # Изменение #2: сериализуем agent_results для контекста планировщика
            serialized_results = []
            for r in pipeline_context.get("agent_results", []):
                if isinstance(r, dict):
                    serialized_results.append({
                        "status": r.get("status"),
                        "agent": r.get("agent"),
                        "findings_count": len(r.get("findings", [])),
                        "tables_count": len(r.get("tables", [])),
                        "code_blocks_count": len(r.get("code_blocks", [])),
                        "sources_count": len(r.get("sources", [])),
                        "has_narrative": r.get("narrative") is not None,
                    })

            # Извлекаем suggested_steps из extra_context если есть
            suggested_steps = (extra_context or {}).get("suggested_steps", [])
            validation_issues = (extra_context or {}).get("validation_issues", [])
            
            replan_payload = await self._execute_agent(
                "planner",
                task={
                    "type": "replan",
                    "original_plan": current_plan,
                    "current_results": serialized_results,
                    "reason": (extra_context or {}).get("last_error", "Adaptive replanning"),
                    "failed_step": (extra_context or {}).get("failed_agent"),
                    "suggested_steps": suggested_steps,
                    "validation_issues": validation_issues,
                },
                context=pipeline_context,
            )
            return self._extract_plan(replan_payload)
        except Exception as e:
            self._logger.warning(f"⚠️ Replanning failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal: validation
    # ------------------------------------------------------------------

    async def _validate_results(
        self,
        user_request: str,
        pipeline_context: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None,
        current_plan_results_start: int = 0,
    ) -> AgentPayload:
        """Вызывает ValidatorAgent для валидации результатов.
        
        Args:
            current_plan_results_start: индекс в agent_results,
                с которого начинаются результаты текущего плана.
                Используется чтобы не агрегировать старые сломанные
                code_blocks из предыдущих replan-циклов.
        """
        # Агрегируем только результаты текущего плана,
        # а не ВСЕ agent_results (включая сломанные code_blocks из прошлых replan)
        all_results = pipeline_context.get("agent_results", [])
        current_results = all_results[current_plan_results_start:]
        
        aggregated_payload = AgentPayload.success(agent="orchestrator")
        for result in current_results:
            if isinstance(result, dict) and result.get("status") != "error":
                temp = AgentPayload(**result) if "agent" in result else None
                if temp:
                    aggregated_payload.merge_from(temp)

        # Изменение #6: QualityGate получает execution_context (полные DataFrame)
        if execution_context:
            validation_ctx = {**pipeline_context, **execution_context}
        else:
            validation_ctx = pipeline_context

        return await self._execute_agent(
            "validator",
            task={
                "type": "validate",
                "user_request": user_request,
                "aggregated_payload": aggregated_payload.model_dump(),
            },
            context=validation_ctx,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_legacy_result(agent_name: str, result: Dict[str, Any]) -> AgentPayload:
        """Оборачивает V1 dict-результат в AgentPayload для совместимости."""
        status = result.get("status", "success")
        if status == "error":
            return AgentPayload.make_error(
                agent=agent_name,
                error_message=result.get("error", "Unknown error"),
                suggestions=result.get("suggestions"),
            )
        return AgentPayload.success(
            agent=agent_name,
            metadata={"legacy_result": result},
        )

    @staticmethod
    def _error_result(
        session_id: str,
        start_time: datetime,
        error: str,
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "session_id": session_id,
            "error": error,
            "execution_time": (datetime.now() - start_time).total_seconds(),
        }


