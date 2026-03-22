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
import copy
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.llm_router import LLMRouter, LLMCallParams, LLMMessage
from app.services.context_execution_service import ContextExecutionService
from app.services.executors.python_executor import PythonExecutor
from .config import TimeoutConfig
from .context_metrics import summarize_context_estimates
from .context_selection import select_context_for_step
from .execution_policy import ExecutionPolicy, resolve_execution_policy
from .runtime_overrides import (
    load_user_multi_agent_overrides,
    ma_bool,
    ma_int,
    ma_str,
    reset_ma_overrides_token,
    set_ma_overrides_token,
)
from .message_bus import AgentMessageBus
from .message_types import MessageType, AgentMessage
from .schemas.agent_payload import AgentPayload, Plan, PlanStep, ToolResult
from .tabular_tool_contract import enrich_task_for_tabular_tools
from .agents.quality_gate import aggregate_agent_results_for_validation

logger = logging.getLogger(__name__)

# Retry / replan limits
MAX_REPLAN_ATTEMPTS = 3
MAX_RETRY_ATTEMPTS = 1
MAX_VALIDATION_ITERATIONS = 3

# Step-revise planning (см. docs/PLANNING_DECOMPOSITION_STRATEGY.md)
MAX_EXPAND_PER_STEP = 3
MAX_REVISE_REMAINING_PER_SESSION = 25  # типичный план: 9 discovery + research + structurizer + reporter → до 12 revises
MAX_STEPS_EXECUTED = 50

# Tool loop на шаг (readTableList / readTableData …): дефолт и нижняя граница (старое env=3 поднимается до этого).
TOOL_LOOP_MAX_ROUNDS_PER_STEP = 15

# Кэш результатов тулов на время запроса (семантически одинаковые readTableList/readTableData).
MAX_TOOL_RESULT_CACHE_ENTRIES = 128


def _canonical_json_for_tool_cache(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            str(k): _canonical_json_for_tool_cache(v)
            for k, v in sorted(obj.items(), key=lambda x: str(x[0]))
        }
    if isinstance(obj, list):
        return [_canonical_json_for_tool_cache(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _tool_request_cache_key(canonical_tool_name: str, arguments: Dict[str, Any]) -> str:
    norm = _canonical_json_for_tool_cache(arguments)
    payload = json.dumps(
        {"tool": canonical_tool_name, "arguments": norm},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tool_cache_digest_line(canonical_tool_name: str, arguments: Dict[str, Any]) -> str:
    if canonical_tool_name == "readTableListFromContentNodes":
        nids = arguments.get("nodeIds") or []
        return f"readTableListFromContentNodes: nodeIds={nids[:6]}{'…' if len(nids) > 6 else ''}"
    if canonical_tool_name == "readTableData":
        jd = arguments.get("jsonDecl") if isinstance(arguments.get("jsonDecl"), dict) else arguments
        if not isinstance(jd, dict):
            jd = {}
        cid = jd.get("contentNodeId") or jd.get("content_node_id")
        tid = jd.get("table_id") or jd.get("tableId")
        off = jd.get("offset", 0)
        lim = jd.get("limit", 50)
        return (
            f"readTableData: contentNodeId={cid}, table_id={tid}, offset={off}, limit={lim}"
        )
    return f"{canonical_tool_name}: (cached)"


def _trim_tool_result_cache(cache: Dict[str, Any]) -> None:
    while len(cache) > MAX_TOOL_RESULT_CACHE_ENTRIES:
        cache.pop(next(iter(cache)))


def _store_tool_result_in_pipeline_cache(
    pipeline_context: Dict[str, Any],
    *,
    cache_key: str,
    canonical_tool_name: str,
    arguments: Dict[str, Any],
    result_dump: Dict[str, Any],
) -> None:
    if not result_dump.get("success"):
        return
    cache = pipeline_context.setdefault("_tool_result_cache", {})
    cache[cache_key] = copy.deepcopy(result_dump)
    _trim_tool_result_cache(cache)
    seen = pipeline_context.setdefault("_tool_cache_digest_seen_keys", set())
    if cache_key in seen:
        return
    seen.add(cache_key)
    line = _tool_cache_digest_line(canonical_tool_name, arguments)
    pipeline_context.setdefault("tool_request_cache_digest_lines", []).append(line)


def _infer_table_id_from_recent_list_tool_results(
    pipeline_context: Dict[str, Any],
    content_node_id: str,
) -> Optional[str]:
    """
    Если LLM вызвал readTableData без table_id, подставляем id таблицы из последнего
    успешного readTableListFromContentNodes для той же content node (частая ошибка агентов).
    """
    cid = str(content_node_id or "").strip()
    if not cid:
        return None

    def _from_data(data: Dict[str, Any]) -> Optional[str]:
        rows: List[Dict[str, Any]] = []
        for row in data.get("tables", []) or []:
            if isinstance(row, dict):
                rows.append(row)
        matching = [r for r in rows if str(r.get("content_node_id")) == cid]
        if len(matching) == 1:
            tid = matching[0].get("table_id")
            return str(tid) if tid else None
        if len(matching) > 1:
            tid = matching[0].get("table_id")
            if tid:
                logger.debug(
                    "Inferring table_id: multiple tables for node %s, using first %s",
                    cid,
                    tid,
                )
                return str(tid)
        for node in data.get("nodes", []) or []:
            if not isinstance(node, dict):
                continue
            if str(node.get("content_node_id")) != cid:
                continue
            ntables = [t for t in (node.get("tables") or []) if isinstance(t, dict)]
            if not ntables:
                continue
            tid = ntables[0].get("table_id")
            if tid:
                if len(ntables) > 1:
                    logger.debug(
                        "Inferring table_id from nodes[]: %s (first of %d)",
                        tid,
                        len(ntables),
                    )
                return str(tid)
        return None

    def _scan_group(results: Optional[List[Any]]) -> Optional[str]:
        if not isinstance(results, list):
            return None
        for r in reversed(results):
            if not isinstance(r, dict) or not r.get("success"):
                continue
            if r.get("tool_name") not in (
                "readTableListFromContentNodes",
                "readTableListFromContentNode",
            ):
                continue
            data = r.get("data")
            if not isinstance(data, dict):
                continue
            got = _from_data(data)
            if got:
                logger.debug(
                    "Inferred readTableData table_id=%s from prior list tool for node %s",
                    got,
                    cid,
                )
                return got
        return None

    got = _scan_group(pipeline_context.get("last_tool_results"))
    if got:
        return got
    full = pipeline_context.get("tool_results")
    if isinstance(full, list) and full:
        return _scan_group(full)
    return None


def _normalize_read_table_data_json_decl(
    json_decl: Dict[str, Any],
    *,
    default_content_node_id: str,
    pipeline_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Алиасы полей и fallback table_id из последнего readTableList (см. трейсы transform_codex)."""
    out = dict(json_decl)
    if default_content_node_id and not (
        out.get("contentNodeId")
        or out.get("content_node_id")
        or out.get("nodeId")
    ):
        out["contentNodeId"] = default_content_node_id
    if out.get("tableId") and not out.get("table_id"):
        out["table_id"] = out["tableId"]
    if not (out.get("table_id") or out.get("tableId")):
        for key in ("table_name", "tableName", "name", "table"):
            v = out.get(key)
            if v is not None and str(v).strip():
                out["table_id"] = str(v).strip()
                break
    cid = str(
        out.get("contentNodeId")
        or out.get("content_node_id")
        or out.get("nodeId")
        or ""
    ).strip()
    if not (out.get("table_id") or out.get("tableId")):
        inferred = _infer_table_id_from_recent_list_tool_results(
            pipeline_context,
            cid,
        )
        if inferred:
            out["table_id"] = inferred
    if out.get("tableId") and not out.get("table_id"):
        out["table_id"] = out["tableId"]
    return out


def _truncate_trace_tool_payload(obj: Any, max_list_items: int) -> Any:
    """Урезает вложенные списки в дампе ответа тула для JSONL-трейса."""
    if max_list_items <= 0:
        return obj
    if isinstance(obj, dict):
        return {
            str(k): _truncate_trace_tool_payload(v, max_list_items)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        if len(obj) > max_list_items:
            prefix = [
                _truncate_trace_tool_payload(x, max_list_items)
                for x in obj[:max_list_items]
            ]
            prefix.append(
                {
                    "_trace_note": (
                        f"list truncated: {len(obj)} items total, "
                        f"showing first {max_list_items}"
                    )
                }
            )
            return prefix
        return [_truncate_trace_tool_payload(x, max_list_items) for x in obj]
    return obj


def _tool_result_trace_details(result_dump: Dict[str, Any]) -> Dict[str, Any]:
    """Поля `details` для события `tool_result`: полный ответ тула с лимитами размера."""
    max_items = ma_int("MULTI_AGENT_TRACE_TOOL_DATA_MAX_LIST_ITEMS", 200)
    max_chars = ma_int("MULTI_AGENT_TRACE_TOOL_DATA_MAX_CHARS", 200_000)
    payload = _truncate_trace_tool_payload(result_dump, max_items)
    detail: Dict[str, Any] = {
        "result": payload,
        "result_truncated": False,
    }
    try:
        js = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        err_payload = {
            "_trace_serialization_error": True,
            "repr": repr(result_dump)[:8000],
        }
        detail["result"] = err_payload
        js = json.dumps(err_payload, ensure_ascii=False, default=str)
    char_len = len(js)
    detail["result_char_len"] = char_len
    if max_chars > 0 and char_len > max_chars:
        detail["result"] = None
        detail["result_truncated"] = True
        detail["result_json_head"] = js[:max_chars]
        detail["result_json_omitted_chars"] = char_len - max_chars
    return detail


def _trim_analyst_tool_requests_for_round(
    agent_name: str,
    payload: AgentPayload,
) -> AgentPayload:
    """
    У Analyst часто приходит 2–3 одинаковых readTableData за раунд и повтор тех же
    запросов 15+ раз. Дедуп по (tool_name, arguments) и лимит за раунд (env) режут петлю.
    """
    if agent_name != "analyst" or not payload.tool_requests:
        return payload
    max_req = ma_int("MULTI_AGENT_ANALYST_MAX_TOOL_REQUESTS_PER_ROUND", 2)
    reqs = list(payload.tool_requests)
    seen: set[str] = set()
    deduped: List[Any] = []
    for r in reqs:
        d = r.model_dump()
        sig = (d.get("tool_name") or "") + json.dumps(
            d.get("arguments") or {},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(r)
    trimmed = deduped[:max_req] if len(deduped) > max_req else deduped
    if len(trimmed) == len(reqs):
        return payload
    logger.info(
        "Analyst tool_requests trimmed: %d -> %d (dedupe+cap, max=%d)",
        len(reqs),
        len(trimmed),
        max_req,
    )
    return payload.model_copy(update={"tool_requests": trimmed})


class MultiAgentTraceLogger:
    """Append-only JSONL trace logger for end-to-end orchestrator runs."""

    _lock = asyncio.Lock()

    @classmethod
    def is_enabled(cls) -> bool:
        return ma_bool("MULTI_AGENT_TRACE_ENABLED", True)

    @classmethod
    def _trace_dir(cls) -> Path:
        custom = ma_str("MULTI_AGENT_TRACE_DIR", "").strip()
        if custom:
            return Path(custom)
        # .../apps/backend/app/services/multi_agent/orchestrator.py -> .../apps/backend
        backend_root = Path(__file__).resolve().parents[3]
        return backend_root / "logs" / "multi_agent_traces"

    @classmethod
    async def write_trace(cls, trace_data: Dict[str, Any]) -> Optional[Path]:
        if not cls.is_enabled():
            return None
        try:
            trace_dir = cls._trace_dir()
            trace_dir.mkdir(parents=True, exist_ok=True)
            file_path = trace_dir / f"orchestrator_trace_{datetime.now().strftime('%Y%m%d')}.jsonl"
            line = json.dumps(trace_data, ensure_ascii=False)
            async with cls._lock:
                # Synchronous append under lock: simple and deterministic.
                with file_path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            return file_path
        except Exception:
            logger.exception("Failed to write multi-agent trace")
            return None


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
        llm_router: Optional[LLMRouter] = None,
        db_session_factory: Any = None,
    ):
        self.gigachat_api_key = gigachat_api_key
        self.enable_agents = enable_agents or [
            "planner", "discovery", "research", "structurizer",
            "analyst", "transform_codex", "widget_codex", "context_filter", "reporter", "validator",
        ]
        self.adaptive_planning = adaptive_planning
        self._db_session_factory = db_session_factory

        self.gigachat: Optional[GigaChatService] = None
        self.llm_router: Optional[LLMRouter] = llm_router
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

            # 2. LLM — только из моделей в панели администратора (GigaChat одна из настроенных моделей)
            self.gigachat = GigaChatService(api_key=self.gigachat_api_key) if self.gigachat_api_key else None

            # 2.1 LLMRouter (если не был передан извне)
            if self.llm_router is None:
                self.llm_router = LLMRouter(
                    gigachat_service=self.gigachat,
                    db_session_factory=self._db_session_factory,
                )

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
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("PlannerAgent not available")

        try:
            from .agents.discovery import DiscoveryAgent
            agent_registry["discovery"] = lambda: DiscoveryAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except Exception as e:
            self._logger.warning(f"DiscoveryAgent not available: {type(e).__name__}: {e}")

        try:
            from .agents.research import ResearchAgent
            agent_registry["research"] = lambda: ResearchAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except Exception as e:
            self._logger.warning(f"ResearchAgent not available: {type(e).__name__}: {e}")

        try:
            from .agents.structurizer import StructurizerAgent
            agent_registry["structurizer"] = lambda: StructurizerAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("StructurizerAgent not available")

        try:
            from .agents.analyst import AnalystAgent
            agent_registry["analyst"] = lambda: AnalystAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("AnalystAgent not available")

        try:
            from .agents.transform_codex import TransformCodexAgent
            agent_registry["transform_codex"] = lambda: TransformCodexAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("TransformCodexAgent not available")

        try:
            from .agents.widget_codex import WidgetCodexAgent
            agent_registry["widget_codex"] = lambda: WidgetCodexAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("WidgetCodexAgent not available")

        try:
            from .agents.context_filter import ContextFilterAgent
            agent_registry["context_filter"] = lambda: ContextFilterAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("ContextFilterAgent not available")

        try:
            from .agents.reporter import ReporterAgent
            agent_registry["reporter"] = lambda: ReporterAgent(
                message_bus=self.message_bus, gigachat_service=self.gigachat, llm_router=self.llm_router,
            )
        except ImportError:
            self._logger.debug("ReporterAgent not available")

        try:
            from .agents.quality_gate import QualityGateAgent
            agent_registry["validator"] = lambda: QualityGateAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat,
                executor=self.executor,
                llm_router=self.llm_router,
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
        run_started_perf = time.perf_counter()
        trace_events: List[Dict[str, Any]] = []
        trace_status = "unknown"
        trace_error: Optional[str] = None
        trace_file_path: Optional[str] = None
        time_to_first_result_ms: Optional[int] = None
        planner_error_streak = 0
        max_planner_error_streak = 0
        last_context_compaction_level = "full"
        last_fallback_reason: Optional[str] = None
        agent_runtime_options_map: Dict[str, Dict[str, Any]] = {}
        overall_t0 = time.perf_counter()

        def _safe_len(value: Any) -> int:
            return len(value) if isinstance(value, (list, dict, tuple, set)) else 0

        def _agent_title(agent_name: str) -> str:
            titles = {
                "planner": "Planner",
                "discovery": "Discovery",
                "research": "Research",
                "structurizer": "Structurizer",
                "analyst": "Analyst",
                "transform_codex": "Transform Codex",
                "widget_codex": "Widget Codex",
                "reporter": "Reporter",
                "validator": "Validator",
            }
            return titles.get(agent_name, agent_name)

        def _task_title(task: Any) -> str:
            if not isinstance(task, dict):
                return "Выполнение шага"
            summary = str(task.get("summary") or "").strip()
            if summary:
                return summary[:240]
            task_type = str(task.get("type") or "").strip()
            description = str(task.get("description") or "").strip()
            query = str(task.get("query") or "").strip()
            if description:
                return description[:240]
            if query:
                return query[:240]
            if task_type:
                return task_type
            return "Выполнение шага"

        progress_callback = (context or {}).get("_progress_callback")
        enable_plan_progress = bool((context or {}).get("_enable_plan_progress", False))

        async def _emit_progress(
            *,
            agent_name: str,
            task: Optional[Dict[str, Any]] = None,
            phase: str = "execution",
            step_index: Optional[int] = None,
            total_steps: Optional[int] = None,
        ) -> None:
            if not callable(progress_callback):
                return
            progress_payload: Dict[str, Any] = {
                "agent": agent_name,
                "agent_label": _agent_title(agent_name),
                "task": _task_title(task or {}),
                "phase": phase,
            }
            if step_index is not None:
                progress_payload["step_index"] = step_index
            if total_steps is not None:
                progress_payload["total_steps"] = total_steps
            try:
                maybe_awaitable = progress_callback(progress_payload)
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
            except Exception:
                self._logger.debug("Progress callback failed", exc_info=True)

        def _plan_tasks_from_steps(plan_steps: Any) -> List[str]:
            if not isinstance(plan_steps, list):
                return []
            tasks: List[str] = []
            for step in plan_steps:
                if not isinstance(step, dict):
                    continue
                task = step.get("task")
                title = _task_title(task)
                if title:
                    tasks.append(title)
            return tasks

        async def _emit_plan_update(
            *,
            plan_steps: Any,
            completed_count: int = 0,
            source: str = "plan",
        ) -> None:
            if not enable_plan_progress or not callable(progress_callback):
                return
            try:
                maybe_awaitable = progress_callback(
                    {
                        "event": "plan_update",
                        "phase": "planning",
                        "source": source,
                        "steps": _plan_tasks_from_steps(plan_steps),
                        "completed_count": max(0, int(completed_count)),
                    }
                )
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
            except Exception:
                self._logger.debug("Plan update callback failed", exc_info=True)

        def _log_trace(
            *,
            event: str,
            phase: str,
            agent: Optional[str] = None,
            step_id: Optional[str] = None,
            step_index: Optional[int] = None,
            duration_ms: Optional[int] = None,
            status: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            error: Optional[str] = None,
        ) -> None:
            trace_events.append({
                "ts": datetime.utcnow().isoformat() + "Z",
                "event": event,
                "phase": phase,
                "agent": agent,
                "step_id": step_id,
                "step_index": step_index,
                "duration_ms": duration_ms,
                "status": status,
                "error": error,
                "details": details or {},
            })

        async def _run_agent_traced(
            *,
            agent_name: str,
            task: Dict[str, Any],
            agent_context: Dict[str, Any],
            phase: str,
            step_id: Optional[str] = None,
            step_index: Optional[int] = None,
            use_retry: bool = False,
        ) -> AgentPayload:
            nonlocal time_to_first_result_ms, planner_error_streak, max_planner_error_streak
            nonlocal last_context_compaction_level, last_fallback_reason
            task_type = task.get("type") if isinstance(task, dict) else None
            runtime_options = agent_runtime_options_map.get(agent_name)
            policy: ExecutionPolicy = resolve_execution_policy(
                agent_name,
                task_type,
                runtime_options=runtime_options,
            )
            initial_compaction = policy.context_ladder[0] if policy.context_ladder else "full"
            effective_context = select_context_for_step(
                agent_name,
                agent_context,
                task_type=task_type,
                compaction_level=initial_compaction,
                runtime_options=runtime_options,
            )
            original_results_count = len(agent_context.get("agent_results", [])) if isinstance(agent_context.get("agent_results"), list) else 0
            effective_results_count = len(effective_context.get("agent_results", [])) if isinstance(effective_context.get("agent_results"), list) else 0
            original_chat_count = len(agent_context.get("chat_history", [])) if isinstance(agent_context.get("chat_history"), list) else 0
            effective_chat_count = len(effective_context.get("chat_history", [])) if isinstance(effective_context.get("chat_history"), list) else 0
            context_estimates = summarize_context_estimates(effective_context)
            if context_estimates["context_total_chars"] >= ma_int(
                "MULTI_AGENT_CONTEXT_WARN_CHARS", 250000
            ):
                self._logger.warning(
                    "⚠️ [%s] Large agent context before %s: ~%d chars "
                    "(agent_results=%d, chat_history=%d)",
                    session_id,
                    agent_name,
                    context_estimates["context_total_chars"],
                    context_estimates["agent_results_count"],
                    context_estimates["chat_history_count"],
                )
            _log_trace(
                event="agent_call_start",
                phase=phase,
                agent=agent_name,
                step_id=step_id,
                step_index=step_index,
                details={
                    "task_type": task_type,
                    "context_estimates": context_estimates,
                    "context_selection": {
                        "applied_for": effective_context.get("_context_selection_applied_for"),
                        "selection_task_type": effective_context.get("_context_selection_task_type"),
                        "budget_items": effective_context.get("_context_selection_budget_items"),
                        "budget_chars": effective_context.get("_context_selection_budget_chars"),
                        "compaction_level": initial_compaction,
                        "agent_results_before": original_results_count,
                        "agent_results_after": effective_results_count,
                        "chat_history_before": original_chat_count,
                        "chat_history_after": effective_chat_count,
                    },
                    "execution_policy": {
                        "timeout_sec": policy.timeout_sec,
                        "max_retries": policy.max_retries,
                        "context_ladder": policy.context_ladder,
                    },
                },
            )
            t0 = time.perf_counter()
            if use_retry:
                def _context_factory(compaction_level: str) -> Dict[str, Any]:
                    nonlocal last_context_compaction_level
                    last_context_compaction_level = compaction_level
                    return select_context_for_step(
                        agent_name,
                        agent_context,
                        task_type=task_type,
                        compaction_level=compaction_level,
                        runtime_options=runtime_options,
                    )

                def _on_retry(attempt: int, reason: str, compaction_level: str) -> None:
                    nonlocal planner_error_streak, max_planner_error_streak, last_fallback_reason
                    last_fallback_reason = reason
                    if agent_name == "planner":
                        planner_error_streak += 1
                        max_planner_error_streak = max(max_planner_error_streak, planner_error_streak)
                    _log_trace(
                        event="agent_retry",
                        phase=phase,
                        agent=agent_name,
                        step_id=step_id,
                        step_index=step_index,
                        status="retrying",
                        details={
                            "attempt": attempt,
                            "reason": reason,
                            "compaction_level": compaction_level,
                            "task_type": task_type,
                        },
                    )

                payload = await self._execute_with_retry(
                    agent_name,
                    task,
                    effective_context,
                    max_retries=policy.max_retries,
                    timeout_override=policy.timeout_sec,
                    context_ladder=policy.context_ladder,
                    context_factory=_context_factory,
                    on_retry=_on_retry,
                )
            else:
                payload = await self._execute_agent(
                    agent_name,
                    task,
                    effective_context,
                    timeout_override=policy.timeout_sec,
                )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if time_to_first_result_ms is None and payload.status != "error":
                time_to_first_result_ms = int((time.perf_counter() - overall_t0) * 1000)
            if payload.status != "error" and agent_name == "planner":
                planner_error_streak = 0
            _log_trace(
                event="agent_call_end",
                phase=phase,
                agent=agent_name,
                step_id=step_id,
                step_index=step_index,
                duration_ms=elapsed_ms,
                status=payload.status,
                error=payload.error if payload.status == "error" else None,
                details={
                    "findings": len(payload.findings or []),
                    "tables": len(payload.tables or []),
                    "sources": len(payload.sources or []),
                    "code_blocks": len(payload.code_blocks or []),
                    "context_compaction_level": last_context_compaction_level,
                    "fallback_reason": last_fallback_reason,
                },
            )
            return payload

        async def _run_step_with_tools(
            *,
            agent_name: str,
            task: Dict[str, Any],
            agent_context: Dict[str, Any],
            phase: str,
            step_id: str,
            step_index: int,
            use_retry: bool = True,
        ) -> AgentPayload:
            payload = await _run_agent_traced(
                agent_name=agent_name,
                task=task,
                agent_context=agent_context,
                phase=phase,
                step_id=step_id,
                step_index=step_index,
                use_retry=use_retry,
            )
            tools_enabled = bool(pipeline_context.get("tools_enabled"))
            enabled_agents = set(pipeline_context.get("tools_enabled_agents", []))
            if not tools_enabled or agent_name not in enabled_agents:
                return payload
            payload = _trim_analyst_tool_requests_for_round(agent_name, payload)
            _log_trace(
                event="tool_loop_probe",
                phase=phase,
                agent=agent_name,
                step_id=step_id,
                step_index=step_index,
                details={
                    "has_tool_requests": bool(payload.tool_requests),
                    "tool_requests_count": len(payload.tool_requests or []),
                    "tool_requests": [req.tool_name for req in (payload.tool_requests or [])],
                },
            )
            max_rounds = max(
                1,
                int(
                    pipeline_context.get(
                        "tools_max_rounds_per_step",
                        TOOL_LOOP_MAX_ROUNDS_PER_STEP,
                    )
                ),
            )
            rounds = 0
            while isinstance(payload, AgentPayload) and payload.tool_requests:
                if rounds >= max_rounds:
                    return AgentPayload.make_error(
                        agent=agent_name,
                        error_message=(
                            f"Tool loop limit reached ({max_rounds}) for agent '{agent_name}'"
                        ),
                    )
                rounds += 1
                tool_results: List[ToolResult] = []
                _log_trace(
                    event="tool_loop_start",
                    phase=phase,
                    agent=agent_name,
                    step_id=step_id,
                    step_index=step_index,
                    details={
                        "round": rounds,
                        "tool_requests": [req.tool_name for req in payload.tool_requests],
                    },
                )
                for req in payload.tool_requests:
                    req_dump = req.model_dump()
                    _log_trace(
                        event="tool_request",
                        phase=phase,
                        agent=agent_name,
                        step_id=step_id,
                        step_index=step_index,
                        details={
                            "round": rounds,
                            "request_id": req.request_id,
                            "tool_name": req.tool_name,
                            "reason": req.reason,
                            "arguments": req_dump.get("arguments", {}),
                        },
                    )
                    result = await self._execute_orchestrator_tool_request(
                        request=req_dump,
                        pipeline_context=pipeline_context,
                    )
                    tool_results.append(result)
                    result_dump = result.model_dump()
                    tr_detail = _tool_result_trace_details(result_dump)
                    _log_trace(
                        event="tool_result",
                        phase=phase,
                        agent=agent_name,
                        step_id=step_id,
                        step_index=step_index,
                        status="success" if result.success else "error",
                        error=result.error,
                        details={
                            "round": rounds,
                            "request_id": result.request_id,
                            "tool_name": result.tool_name,
                            "success": bool(result.success),
                            "data_keys": sorted(list((result_dump.get("data") or {}).keys()))
                            if isinstance(result_dump.get("data"), dict)
                            else [],
                            **tr_detail,
                        },
                    )
                if not tool_results:
                    break
                tool_results_dump = [r.model_dump() for r in tool_results]
                pipeline_context.setdefault("tool_results", []).extend(tool_results_dump)
                pipeline_context["last_tool_results"] = tool_results_dump
                pipeline_context["tool_last_agent"] = agent_name
                _log_trace(
                    event="tool_loop_results",
                    phase=phase,
                    agent=agent_name,
                    step_id=step_id,
                    step_index=step_index,
                    details={
                        "round": rounds,
                        "results_count": len(tool_results_dump),
                        "success_count": len([r for r in tool_results_dump if r.get("success")]),
                    },
                )
                payload = await _run_agent_traced(
                    agent_name=agent_name,
                    task=task,
                    agent_context=agent_context,
                    phase=phase,
                    step_id=step_id,
                    step_index=step_index,
                    use_retry=False,
                )
                payload = _trim_analyst_tool_requests_for_round(agent_name, payload)
            return payload

        self._logger.info(f"🎬 [{session_id}] Processing: {user_request[:120]}...")
        _log_trace(
            event="run_start",
            phase="orchestrator",
            status="started",
            details={
                "board_id": board_id,
                "user_id": str(user_id) if user_id else None,
                "session_id": session_id,
                "skip_validation": skip_validation,
                "adaptive_planning": self.adaptive_planning,
                "request_preview": user_request[:300],
                "context_keys": sorted(list((context or {}).keys())),
                "selected_node_ids_count": _safe_len((context or {}).get("selected_node_ids")),
                "content_nodes_data_count": _safe_len((context or {}).get("content_nodes_data")),
                "chat_history_count": _safe_len((context or {}).get("chat_history")),
                "input_data_preview_tables": _safe_len((context or {}).get("input_data_preview")),
                "catalog_data_preview_tables": _safe_len((context or {}).get("catalog_data_preview")),
                "incoming_context_estimates": summarize_context_estimates(context or {}),
            },
        )

        overrides = await load_user_multi_agent_overrides(
            self._db_session_factory, user_id
        )
        ma_token = None
        if overrides:
            ma_token = set_ma_overrides_token(overrides)

        try:
            # См. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md — один мутабельный pipeline_context
            context_no_callbacks = dict(context or {})
            context_no_callbacks.pop("_progress_callback", None)
            context_no_callbacks.pop("_enable_plan_progress", None)
            pipeline_context: Dict[str, Any] = {
                "session_id": session_id,
                "board_id": board_id,
                "user_id": user_id,
                "user_request": user_request,
                **context_no_callbacks,
                "agent_results": [],  # append-only, последний ключ (Изменение #2)
            }
            self._init_pipeline_memory(pipeline_context)
            tools_enabled = ma_bool("MULTI_AGENT_ENABLE_TOOLS", False)
            tools_agents_raw = ma_str(
                "MULTI_AGENT_TOOL_ENABLED_AGENTS",
                "transform_codex,analyst,structurizer,widget_codex",
            ).strip()
            tools_agents = [
                item.strip() for item in tools_agents_raw.split(",") if item.strip()
            ]
            pipeline_context["tools_enabled"] = tools_enabled
            pipeline_context["tools_enabled_agents"] = tools_agents
            _tool_rounds_raw = ma_int(
                "MULTI_AGENT_TOOL_MAX_ROUNDS_PER_STEP",
                TOOL_LOOP_MAX_ROUNDS_PER_STEP,
            )
            _tool_rounds = max(TOOL_LOOP_MAX_ROUNDS_PER_STEP, _tool_rounds_raw)
            if _tool_rounds_raw < TOOL_LOOP_MAX_ROUNDS_PER_STEP:
                self._logger.info(
                    "MULTI_AGENT_TOOL_MAX_ROUNDS_PER_STEP=%s is below minimum %s; using %s",
                    _tool_rounds_raw,
                    TOOL_LOOP_MAX_ROUNDS_PER_STEP,
                    _tool_rounds,
                )
            pipeline_context["tools_max_rounds_per_step"] = _tool_rounds
            pipeline_context["tool_results"] = []
            pipeline_context["_tool_result_cache"] = {}
            pipeline_context["tool_request_cache_digest_lines"] = []
            pipeline_context["_tool_cache_digest_seen_keys"] = set()
            pipeline_context["force_tool_data_access"] = (
                tools_enabled and ma_bool("MULTI_AGENT_FORCE_TOOL_DATA_ACCESS", True)
            )
            pipeline_context["_trace_event"] = _log_trace
            if self.llm_router:
                try:
                    agent_runtime_options_map = await self.llm_router.get_agent_runtime_options_map()
                except Exception as e:
                    self._logger.warning("Failed to load agent runtime options: %s", e)
                    agent_runtime_options_map = {}
            pipeline_context["_agent_runtime_options_map"] = agent_runtime_options_map

            _ctrl = (context or {}).get("controller") or ""
            suggestions_fast = _ctrl in ("transform_suggestions", "widget_suggestions")
            pipeline_context["suggestions_fast_path"] = suggestions_fast
            assistant_simple_qa = self._is_simple_assistant_qa(pipeline_context)
            pipeline_context["assistant_simple_qa"] = assistant_simple_qa
            disable_heavy_decomposition = (
                suggestions_fast or assistant_simple_qa
            )
            _log_trace(
                event="pipeline_context_built",
                phase="setup",
                details={
                    "suggestions_fast_path": suggestions_fast,
                    "assistant_simple_qa": assistant_simple_qa,
                    "force_tool_data_access": bool(
                        pipeline_context.get("force_tool_data_access")
                    ),
                    "disable_heavy_decomposition": disable_heavy_decomposition,
                    "context_estimates": summarize_context_estimates(pipeline_context),
                },
            )

            # ============================================================
            # STEP 1: PlannerAgent — создание плана (или фиксированный путь для UI-подсказок)
            # ============================================================
            if suggestions_fast:
                # Избегаем structurizer/transform_codex и лишних OAuth — только analyst → reporter.
                # См. controller.transform_suggestions / widget_suggestions.
                self._logger.info(
                    f"📋 [{session_id}] Suggestions fast path ({_ctrl}): analyst → reporter"
                )
                plan = {
                    "plan_id": str(uuid4()),
                    "user_request": user_request,
                    "steps": [
                        {
                            "step_id": "1",
                            "agent": "analyst",
                            "task": {"description": user_request[:4000]},
                            "depends_on": [],
                        },
                        {
                            "step_id": "2",
                            "agent": "reporter",
                            "task": {
                                "description": "Кратко сформулируй итог по рекомендациям аналитика.",
                                "widget_type": "text",
                            },
                            "depends_on": ["1"],
                        },
                    ],
                    "replan_count": 0,
                }
            else:
                self._logger.info(f"📋 [{session_id}] Step 1: Planning...")
                await _emit_progress(
                    agent_name="planner",
                    task={
                        "type": "create_plan",
                        "description": "Формирую план выполнения запроса",
                    },
                    phase="planning",
                    step_index=1,
                )

                plan_payload = await _run_agent_traced(
                    agent_name="planner",
                    task={
                        "type": "create_plan",
                        "user_request": user_request,
                        "board_context": pipeline_context.get("board_context", {}),
                        "selected_node_ids": pipeline_context.get("selected_node_ids", []),
                    },
                    agent_context=pipeline_context,
                    phase="planning",
                )
                pipeline_context["agent_results"].append(
                    plan_payload.model_dump() if isinstance(plan_payload, AgentPayload) else plan_payload
                )
                if isinstance(plan_payload, AgentPayload):
                    self._update_pipeline_memory(
                        pipeline_context,
                        agent_name="planner",
                        payload=plan_payload,
                    )

                plan = self._extract_plan(plan_payload)
                if not plan or not plan.get("steps"):
                    error_message = "Planner Agent не смог создать план выполнения"
                    trace_status = "error"
                    trace_error = error_message
                    _log_trace(
                        event="run_finish",
                        phase="orchestrator",
                        status="error",
                        error=error_message,
                    )
                    return self._error_result(
                        session_id, start_time,
                        error_message,
                    )

            steps = plan.get("steps", [])
            _plan_agents = [s.get("agent") if isinstance(s, dict) else "?" for s in steps]
            self._logger.info(f"✅ [{session_id}] Plan: {len(steps)} steps → {_plan_agents}")
            await _emit_plan_update(
                plan_steps=steps,
                completed_count=0,
                source="initial_plan",
            )
            _log_trace(
                event="plan_created",
                phase="planning",
                status="success",
                details={"steps_count": len(steps), "agents": _plan_agents},
            )

            # ============================================================
            # STEP 2 & 3: Execution + Validation Loop
            # Master loop для поддержки replanning после валидации
            # ============================================================
            raw_results: Dict[str, Any] = {"plan": plan}
            replan_count = 0
            validation_recovery_count = 0

            # Индекс начала результатов текущего плана в agent_results.
            current_plan_results_start = len(pipeline_context.get("agent_results", []))
            pipeline_context["current_plan_results_start"] = current_plan_results_start

            # Пошаговая декомпозиция и пересмотр остатка плана (основной режим, см. docs/PLANNING_DECOMPOSITION_STRATEGY.md)
            steps = [dict(s) if isinstance(s, dict) else (s.model_dump() if hasattr(s, "model_dump") else s) for s in steps]
            for j, s in enumerate(steps):
                s["step_id"] = str(j + 1)
                s["_status"] = "pending"
            revise_count = 0
            steps_executed = 0
            expand_count: Dict[str, int] = {}
            ended_due_to_limits = False
            quality_gate_failed = False
            quality_gate_message: Optional[str] = None
            quality_gate_issues_count = 0
            validator_error_count = 0
            validator_timeout_count = 0
            validator_parse_fallback_count = 0
            validator_missing_validation_field_count = 0

            while True:
                pending_idxs = [i for i, s in enumerate(steps) if s.get("_status") == "pending"]
                if not pending_idxs:
                    break
                if steps_executed >= MAX_STEPS_EXECUTED or revise_count >= MAX_REVISE_REMAINING_PER_SESSION:
                    self._logger.warning(
                        f"⚠️ [{session_id}] Step-revise limits reached (steps_executed={steps_executed}, revise_count={revise_count})"
                    )
                    _log_trace(
                        event="limits_reached",
                        phase="execution",
                        status="warning",
                        details={
                            "steps_executed": steps_executed,
                            "revise_count": revise_count,
                            "max_steps_executed": MAX_STEPS_EXECUTED,
                            "max_revise_remaining": MAX_REVISE_REMAINING_PER_SESSION,
                        },
                    )
                    ended_due_to_limits = True
                    break
                i = pending_idxs[0]
                S = steps[i]
                step_id = str(S.get("step_id", i + 1))
                step_for_planner = {k: v for k, v in S.items() if k != "_status"}

                # Проверка атомарности (для suggestions_fast_path не вызываем planner)
                atomic = True
                sub_steps: List[Any] = []
                _agent_expand = S.get("agent", "")
                _is_widget_ctx = (
                    pipeline_context.get("mode") == "widget"
                    or pipeline_context.get("controller") == "widget"
                )
                # widget/transformation context: не декомпозируем analyst и codex шаги —
                # expand_step плодит sub-analyst'ов, раздувая контекст до таймаута
                # (widget_codex никогда не вызывается, т.к. перед ним вечная очередь analyst).
                _skip_expand_widget_codex = _agent_expand == "widget_codex" and _is_widget_ctx
                _is_transform_ctx = (
                    pipeline_context.get("mode") == "transformation"
                    or pipeline_context.get("controller") == "transformation"
                )
                _skip_expand_transform_codex = (
                    _agent_expand == "transform_codex" and _is_transform_ctx
                )
                _skip_expand_analyst_in_codex_pipeline = (
                    _agent_expand == "analyst"
                    and (_is_widget_ctx or _is_transform_ctx)
                )
                _skip_expand = (
                    _skip_expand_widget_codex
                    or _skip_expand_transform_codex
                    or _skip_expand_analyst_in_codex_pipeline
                )
                if not disable_heavy_decomposition and not _skip_expand:
                    expand_payload = await _run_agent_traced(
                        agent_name="planner",
                        task={"type": "expand_step", "step": step_for_planner},
                        agent_context=pipeline_context,
                        phase="expand_step",
                        step_id=step_id,
                        step_index=i,
                    )
                    if expand_payload.status == "success" and getattr(expand_payload, "metadata", None):
                        exp_result = expand_payload.metadata.get("expand_step_result", {})
                        atomic = exp_result.get("atomic", True)
                        sub_steps = exp_result.get("sub_steps") or []
                elif _skip_expand:
                    self._logger.debug(
                        f"[{session_id}] skip expand_step for {_agent_expand} (codex pipeline)"
                    )
                if not atomic and sub_steps and expand_count.get(step_id, 0) < MAX_EXPAND_PER_STEP:
                    _log_trace(
                        event="step_expanded",
                        phase="expand_step",
                        step_id=step_id,
                        step_index=i,
                        status="success",
                        details={"sub_steps_count": len(sub_steps)},
                    )
                    expand_count[step_id] = expand_count.get(step_id, 0) + 1
                    new_subs = []
                    for j, sub in enumerate(sub_steps):
                        d = dict(sub)
                        d["_status"] = "pending"
                        d["step_id"] = str(i + 1 + j)
                        new_subs.append(d)
                    steps = steps[:i] + new_subs + steps[i + 1:]
                    for idx, s in enumerate(steps):
                        s["step_id"] = str(idx + 1)
                    continue

                # Выполнение шага
                agent_name = S.get("agent", "unknown")
                task_data = S.get("task", {})
                if isinstance(task_data, dict):
                    task_data = enrich_task_for_tabular_tools(
                        agent_name,
                        dict(task_data),
                        pipeline_context,
                    )
                else:
                    task_data = {}
                if agent_name == "validator":
                    # Валидатор выполняется отдельной финальной фазой ниже.
                    # Не запускаем его как обычный execute_step, чтобы не дублировать
                    # проверку и не загрязнять agent_results промежуточной валидацией.
                    self._logger.info(
                        f"⏭️ [{session_id}] Skipping validator step in plan; final validation phase will run"
                    )
                    _log_trace(
                        event="step_skipped",
                        phase="execute_step",
                        agent=agent_name,
                        step_id=step_id,
                        step_index=i,
                        status="skipped",
                        details={"reason": "validator_runs_in_final_phase"},
                    )
                    S["_status"] = "done"
                    steps_executed += 1
                    continue
                if agent_name == "context_filter":
                    _log_trace(
                        event="agent_call_start",
                        phase="execute_step",
                        agent="context_filter",
                        step_id=step_id,
                        step_index=i,
                        details={"task_type": task_data.get("type"), "llm_generation": True},
                    )
                    _cf_t0 = time.perf_counter()
                    step_payload = await self._execute_context_filter_step(
                        task_data=task_data,
                        pipeline_context=pipeline_context,
                    )
                    _log_trace(
                        event="agent_call_end",
                        phase="execute_step",
                        agent="context_filter",
                        step_id=step_id,
                        step_index=i,
                        duration_ms=int((time.perf_counter() - _cf_t0) * 1000),
                        status=step_payload.status,
                        error=step_payload.error if step_payload.status == "error" else None,
                        details={
                            "findings": len(step_payload.findings or []),
                            "tables": len(step_payload.tables or []),
                            "sources": len(step_payload.sources or []),
                            "code_blocks": len(step_payload.code_blocks or []),
                        },
                    )
                    result_dict = step_payload.model_dump()
                    pipeline_context["agent_results"].append(result_dict)
                    self._update_pipeline_memory(
                        pipeline_context,
                        agent_name=agent_name,
                        payload=step_payload,
                    )
                    if agent_name in raw_results:
                        run_num = 2
                        while f"{agent_name}_{run_num}" in raw_results:
                            run_num += 1
                        raw_results[f"{agent_name}_{run_num}"] = result_dict
                    else:
                        raw_results[agent_name] = result_dict
                    S["_status"] = "done"
                    steps_executed += 1
                    continue
                if agent_name not in self.agents:
                    resolved = self._resolve_agent_name(agent_name, task_data)
                    if resolved:
                        agent_name = resolved
                    else:
                        self._logger.warning(f"⚠️ Agent '{agent_name}' not enabled, marking step done")
                        S["_status"] = "done"
                        steps_executed += 1
                        continue

                # Fast QA path guard: if compact input tables already exist, skip heavy structurizer.
                if agent_name == "structurizer" and self._should_skip_structurizer_for_assistant(
                    pipeline_context, task_data
                ):
                    self._logger.info(
                        "⏭️ [%s] Skipping structurizer in assistant QA fast-path (input_data_preview available)",
                        session_id,
                    )
                    _log_trace(
                        event="step_skipped",
                        phase="execute_step",
                        agent=agent_name,
                        step_id=step_id,
                        step_index=i,
                        status="skipped",
                        details={"reason": "assistant_fast_path_skip_structurizer"},
                    )
                    S["_status"] = "done"
                    steps_executed += 1
                    continue

                agent_ctx = {**pipeline_context, **execution_context} if agent_name == "validator" and execution_context else pipeline_context
                await _emit_progress(
                    agent_name=agent_name,
                    task=task_data if isinstance(task_data, dict) else {},
                    phase="execution",
                    step_index=i + 1,
                    total_steps=len(steps),
                )
                step_payload = await _run_step_with_tools(
                    agent_name=agent_name,
                    task=task_data,
                    agent_context=agent_ctx,
                    phase="execute_step",
                    step_id=step_id,
                    step_index=i,
                    use_retry=True,
                )

                result_dict = step_payload.model_dump() if isinstance(step_payload, AgentPayload) else step_payload
                pipeline_context["agent_results"].append(result_dict)
                if isinstance(step_payload, AgentPayload):
                    self._update_pipeline_memory(
                        pipeline_context,
                        agent_name=agent_name,
                        payload=step_payload,
                    )
                if agent_name in raw_results:
                    run_num = 2
                    while f"{agent_name}_{run_num}" in raw_results:
                        run_num += 1
                    raw_results[f"{agent_name}_{run_num}"] = result_dict
                else:
                    raw_results[agent_name] = result_dict
                S["_status"] = "done"
                steps_executed += 1

                if step_payload.status == "error":
                    pipeline_context["previous_error"] = step_payload.error
                    pipeline_context["failed_agent"] = agent_name

                suboptimal_reason = self._is_step_result_suboptimal(agent_name, step_payload)
                if suboptimal_reason:
                    pipeline_context["last_step_suboptimal"] = suboptimal_reason
                    pipeline_context["failed_agent"] = agent_name

                # Пересмотр остатка (только по критериям: ошибка, suboptimal, analyst)
                completed = [s for s in steps if s.get("_status") == "done"]
                remaining = [s for s in steps if s.get("_status") == "pending"]
                if not remaining:
                    break
                steps_executed = len(completed)
                if (
                    not disable_heavy_decomposition
                    and self._should_revise_remaining(
                        agent_name,
                        step_payload,
                        suboptimal_reason,
                        steps_executed,
                        pipeline_context=pipeline_context,
                        remaining_steps=remaining,
                        completed_steps=completed,
                    )
                ):
                    completed_summary = [{"agent": s.get("agent"), "task": s.get("task")} for s in completed]
                    remaining_clean = [{k: v for k, v in s.items() if k != "_status"} for s in remaining]
                    results_summary = self._serialize_results_for_planner(
                        pipeline_context.get("agent_results", []),
                        max_items=20,
                        include_last_narrative=True,
                    )
                    rev_task = {
                        "type": "revise_remaining",
                        "user_request": pipeline_context.get("user_request", ""),
                        "completed_steps": completed_summary,
                        "remaining_steps": remaining_clean,
                        "results_summary": results_summary,
                    }
                    if step_payload.status == "error":
                        rev_task["last_error"] = step_payload.error
                        rev_task["failed_agent"] = agent_name
                    if suboptimal_reason:
                        rev_task["last_step_suboptimal"] = True
                        rev_task["suboptimal_reason"] = suboptimal_reason
                        rev_task["failed_agent"] = agent_name
                    _log_trace(
                        event="revise_remaining_requested",
                        phase="revise_remaining",
                        agent="planner",
                        step_id=step_id,
                        step_index=i,
                        details={
                            "remaining_before": len(remaining_clean),
                            "completed_count": len(completed_summary),
                            "reason_error": step_payload.error if step_payload.status == "error" else None,
                            "reason_suboptimal": suboptimal_reason,
                        },
                    )
                    rev_payload = await _run_agent_traced(
                        agent_name="planner",
                        task=rev_task,
                        agent_context=pipeline_context,
                        phase="revise_remaining",
                        step_id=step_id,
                        step_index=i,
                        use_retry=True,
                    )
                    if rev_payload.status == "success" and getattr(rev_payload, "metadata", None):
                        new_remaining = rev_payload.metadata.get("remaining_steps", remaining_clean)
                        new_agents = [s.get("agent") for s in new_remaining if s.get("agent")]
                        self._logger.info(
                            f"[{session_id}] revise_remaining returned {len(new_remaining)} steps: {new_agents}"
                        )
                        # Дополнительная защита от зацикливания:
                        # прогоняем remaining_steps через нормализацию Planner,
                        # чтобы убрать дубликаты discovery/research/structurizer
                        # и привести зависимости к "чистому" виду.
                        planner_agent = self.agents.get("planner")
                        if planner_agent and hasattr(planner_agent, "_normalize_plan_steps"):
                            try:
                                tmp_plan = {"steps": new_remaining}
                                tmp_plan = planner_agent._normalize_plan_steps(tmp_plan)  # type: ignore[attr-defined]
                                new_remaining = tmp_plan.get("steps", new_remaining) or new_remaining
                                new_agents = [s.get("agent") for s in new_remaining if s.get("agent")]
                                self._logger.info(
                                    f"[{session_id}] normalized remaining_steps via Planner: "
                                    f"{len(new_remaining)} steps: {new_agents}"
                                )
                            except Exception as norm_err:
                                self._logger.warning(
                                    f"[{session_id}] Failed to normalize remaining_steps via Planner: {norm_err}"
                                )
                        # Защита: не допускать удаления критических агентов
                        _critical_agents = ["structurizer", "reporter", "widget_codex", "transform_codex"]
                        _had = {a: any(s.get("agent") == a for s in remaining_clean) for a in _critical_agents}
                        _has = {a: any(s.get("agent") == a for s in new_remaining) for a in _critical_agents}
                        _dropped = [a for a in _critical_agents if _had[a] and not _has[a]]
                        if _dropped:
                            new_remaining = remaining_clean
                            self._logger.warning(
                                f"[{session_id}] revise_remaining dropped {_dropped}; keeping original remaining ({len(remaining_clean)} steps)"
                            )
                        _log_trace(
                            event="revise_remaining_applied",
                            phase="revise_remaining",
                            agent="planner",
                            step_id=step_id,
                            step_index=i,
                            status="success",
                            details={
                                "remaining_after": len(new_remaining),
                                "dropped_critical_agents": _dropped,
                            },
                        )
                    else:
                        new_remaining = remaining_clean
                        _log_trace(
                            event="revise_remaining_skipped",
                            phase="revise_remaining",
                            agent="planner",
                            step_id=step_id,
                            step_index=i,
                            status="warning",
                            details={"reason": "planner_returned_no_metadata"},
                        )
                    # Повторный codex guard: если revise_remaining потерял widget_codex/transform_codex
                    planner_agent = self.agents.get("planner")
                    if planner_agent:
                        _tmp = {"steps": new_remaining}
                        if hasattr(planner_agent, "_ensure_widget_codex_in_plan"):
                            _tmp = planner_agent._ensure_widget_codex_in_plan(_tmp, pipeline_context, pipeline_context.get("user_request", ""))
                        if hasattr(planner_agent, "_ensure_transform_codex_in_plan"):
                            _tmp = planner_agent._ensure_transform_codex_in_plan(_tmp, pipeline_context, pipeline_context.get("user_request", ""))
                        new_remaining = _tmp.get("steps", new_remaining)
                    # Ограничиваем число оставшихся шагов и нормализуем step_id (см. PLANNING_DECOMPOSITION_STRATEGY.md)
                    if len(new_remaining) > MAX_STEPS_EXECUTED - len(completed):
                        new_remaining = new_remaining[: MAX_STEPS_EXECUTED - len(completed)]
                    base_id = len(completed) + 1
                    new_remaining_with_status = []
                    for j, s in enumerate(new_remaining):
                        step_copy = dict(s)
                        step_copy["step_id"] = str(base_id + j)
                        step_copy["_status"] = "pending"
                        new_remaining_with_status.append(step_copy)
                    steps = completed + new_remaining_with_status
                    revise_count += 1
                    await _emit_plan_update(
                        plan_steps=steps,
                        completed_count=len(completed),
                        source="revise_remaining",
                    )
                else:
                    self._logger.debug(
                        f"[{session_id}] skip revise_remaining (step {steps_executed}: {agent_name}, ok)"
                    )

            plan["steps"] = [{k: v for k, v in s.items() if k != "_status"} for s in steps]
            raw_results["plan"] = plan
            step_index = len(steps)

            # Master execution loop — один проход для валидации (шаги уже выполнены в цикле выше)
            while replan_count <= MAX_REPLAN_ATTEMPTS:
                # ============================================================
                # STEP 2: цикл по шагам уже выполнен выше; здесь только проверка step_index
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

                    # Planner is a control-flow agent and must not appear as executable plan step.
                    # Defensive guard: skip malformed planner steps to avoid "Unknown task type: None".
                    if agent_name == "planner":
                        self._logger.warning(
                            f"⚠️ [{session_id}] Skipping malformed planner execution step "
                            f"(step_id={step_id}, task_type={task_data.get('type') if isinstance(task_data, dict) else None})"
                        )
                        _log_trace(
                            event="step_skipped",
                            phase="execute_step",
                            agent="planner",
                            step_id=step_id,
                            step_index=step_index,
                            status="warning",
                            details={"reason": "planner_cannot_be_execution_step"},
                        )
                        step_index += 1
                        continue

                    # Изменение #6: QualityGate получает execution_context (полные DataFrame)
                    if agent_name == "validator" and execution_context:
                        agent_ctx = {**pipeline_context, **execution_context}
                    else:
                        agent_ctx = pipeline_context

                    # Выполняем с retry
                    step_task_type = task_data.get("type") if isinstance(task_data, dict) else None
                    step_runtime_options = agent_runtime_options_map.get(agent_name)
                    step_policy = resolve_execution_policy(
                        agent_name,
                        step_task_type,
                        runtime_options=step_runtime_options,
                    )
                    def _step_on_retry(attempt: int, reason: str, compaction_level: str) -> None:
                        nonlocal planner_error_streak, max_planner_error_streak
                        nonlocal last_context_compaction_level, last_fallback_reason
                        last_context_compaction_level = compaction_level
                        last_fallback_reason = reason
                        if agent_name == "planner":
                            planner_error_streak += 1
                            max_planner_error_streak = max(
                                max_planner_error_streak,
                                planner_error_streak,
                            )
                        _log_trace(
                            event="agent_retry",
                            phase="execution",
                            agent=agent_name,
                            step_id=step_id,
                            step_index=step_index,
                            status="retrying",
                            details={
                                "attempt": attempt,
                                "reason": reason,
                                "compaction_level": compaction_level,
                                "task_type": step_task_type,
                            },
                        )
                    step_payload = await self._execute_with_retry(
                        agent_name,
                        task_data,
                        agent_ctx,
                        max_retries=step_policy.max_retries,
                        timeout_override=step_policy.timeout_sec,
                        context_ladder=step_policy.context_ladder,
                        context_factory=lambda lvl: select_context_for_step(
                            agent_name,
                            agent_ctx,
                            task_type=step_task_type,
                            compaction_level=lvl,
                            runtime_options=step_runtime_options,
                        ),
                        on_retry=_step_on_retry,
                    )
                    if step_payload.status != "error" and agent_name == "planner":
                        planner_error_streak = 0

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
                            await _emit_plan_update(
                                plan_steps=steps,
                                completed_count=0,
                                source="replan_after_error",
                            )
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
                    if isinstance(step_payload, AgentPayload):
                        self._update_pipeline_memory(
                            pipeline_context,
                            agent_name=agent_name,
                            payload=step_payload,
                        )

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
                                await _emit_plan_update(
                                    plan_steps=steps,
                                    completed_count=0,
                                    source="adaptive_replan",
                                )
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
                    # Валидатор должен работать как gate над финальным отчётом.
                    # Если reporter ещё не выполнялся (или выполнение оборвалось по лимитам),
                    # валидация только запутает пользователя, поэтому пропускаем её.
                    reporter_executed = any(
                        isinstance(r, dict) and r.get("agent") == "reporter"
                        for r in pipeline_context.get("agent_results", [])
                    )
                    if not reporter_executed:
                        if ended_due_to_limits:
                            self._logger.warning(
                                f"⚠️ [{session_id}] Skipping validation: reporter not executed and step limits reached"
                            )
                        else:
                            self._logger.info(
                                f"ℹ️ [{session_id}] Skipping validation: reporter not executed yet"
                            )
                        break

                    self._logger.info(f"🔍 [{session_id}] Validating results...")
                    await _emit_progress(
                        agent_name="validator",
                        task={"type": "run_quality_gate", "description": "Проверяю качество итогового ответа"},
                        phase="validation",
                    )
                    # Изменение #6: QualityGate получает execution_context (полные DataFrame)
                    _log_trace(
                        event="agent_call_start",
                        phase="validation",
                        agent="validator",
                        details={"task_type": "validate"},
                    )
                    _val_t0 = time.perf_counter()
                    validation_payload = await self._validate_results(
                        user_request,
                        pipeline_context,
                        execution_context,
                        current_plan_results_start=current_plan_results_start,
                    )
                    _log_trace(
                        event="agent_call_end",
                        phase="validation",
                        agent="validator",
                        duration_ms=int((time.perf_counter() - _val_t0) * 1000),
                        status=validation_payload.status,
                        error=validation_payload.error if validation_payload.status == "error" else None,
                        details={
                            "findings": len(validation_payload.findings or []),
                            "tables": len(validation_payload.tables or []),
                            "sources": len(validation_payload.sources or []),
                            "code_blocks": len(validation_payload.code_blocks or []),
                        },
                    )
                    # Записываем результат валидации в хронологию
                    val_result_dict = (
                        validation_payload.model_dump()
                        if isinstance(validation_payload, AgentPayload)
                        else validation_payload
                    )
                    pipeline_context["agent_results"].append(val_result_dict)
                    raw_results["validator"] = val_result_dict
                    self._update_pipeline_memory(
                        pipeline_context,
                        agent_name="validator",
                        note=f"Validator status: {validation_payload.status}",
                    )

                    # Fail-closed: ошибка ValidatorAgent не должна трактоваться как pass.
                    if validation_payload.status == "error":
                        validator_error_message = (
                            validation_payload.error
                            or "Validator returned status=error without details"
                        )
                        validator_error_count += 1
                        if "timeout" in validator_error_message.lower():
                            validator_timeout_count += 1

                        self._logger.warning(
                            f"⚠️ [{session_id}] Validator execution error: {validator_error_message}. "
                            "Finishing with current results."
                        )
                        quality_gate_failed = True
                        quality_gate_message = f"Validator execution error: {validator_error_message}"
                        quality_gate_issues_count = 0
                        _log_trace(
                            event="validation_failed",
                            phase="validation",
                            agent="validator",
                            status="failed",
                            details={
                                "message": quality_gate_message,
                                "issues_count": 0,
                                "reason": "validator_error",
                                "validator_status": validation_payload.status,
                            },
                        )
                        break
                    
                    # Проверяем результат валидации
                    if validation_payload.validation:
                        val_result = validation_payload.validation
                        if (
                            isinstance(val_result.message, str)
                            and "Parse error" in val_result.message
                        ):
                            validator_parse_fallback_count += 1
                        
                        if not val_result.valid:
                            # Targeted recovery: if validator provided a replan and attempts remain,
                            # do not finish immediately — run planner.replan with validator hints.
                            if (
                                val_result.suggested_replan
                                and validation_recovery_count
                                < ma_int("MULTI_AGENT_MAX_VALIDATION_RECOVERY", 2)
                                and replan_count < MAX_REPLAN_ATTEMPTS
                            ):
                                sr = val_result.suggested_replan
                                suggested_steps = []
                                for step in sr.additional_steps or []:
                                    suggested_steps.append(
                                        {
                                            "agent": step.agent,
                                            "description": step.task.get("description", ""),
                                        }
                                    )
                                validation_issues = [
                                    {
                                        "severity": issue.severity,
                                        "message": issue.text,
                                    }
                                    for issue in (val_result.issues or [])
                                ]
                                validation_recovery_count += 1
                                replan_count += 1
                                self._logger.info(
                                    f"🔄 [{session_id}] Replanning after validation failure "
                                    f"({replan_count}/{MAX_REPLAN_ATTEMPTS}, "
                                    f"validation_recovery {validation_recovery_count}/"
                                    f"{ma_int('MULTI_AGENT_MAX_VALIDATION_RECOVERY', 2)}): {sr.reason}"
                                )
                                new_plan = await self._replan(
                                    plan,
                                    pipeline_context,
                                    {
                                        "last_error": val_result.message or "Validation failed",
                                        "failed_agent": "validator",
                                        "suggested_steps": suggested_steps,
                                        "validation_issues": validation_issues,
                                    },
                                )
                                if new_plan and new_plan.get("steps"):
                                    plan = new_plan
                                    steps = plan["steps"]
                                    await _emit_plan_update(
                                        plan_steps=steps,
                                        completed_count=0,
                                        source="validation_replan",
                                    )
                                    raw_results["plan"] = plan
                                    raw_results[f"replan_{replan_count}"] = {
                                        "after_step": step_index + 1,
                                        "reason": val_result.message or "Validation failed",
                                        "type": "validation_recovery",
                                    }
                                    current_plan_results_start = len(
                                        pipeline_context.get("agent_results", [])
                                    )
                                    pipeline_context["current_plan_results_start"] = (
                                        current_plan_results_start
                                    )
                                    step_index = 0
                                    continue
                            self._logger.warning(
                                f"⚠️ [{session_id}] Validation failed: {val_result.message}. Finishing with current results."
                            )
                            quality_gate_failed = True
                            quality_gate_message = val_result.message
                            quality_gate_issues_count = len(val_result.issues or [])
                            _log_trace(
                                event="validation_failed",
                                phase="validation",
                                agent="validator",
                                status="failed",
                                details={
                                    "message": val_result.message,
                                    "issues_count": len(val_result.issues or []),
                                    "reason": "validation_invalid",
                                },
                            )
                            break
                        else:
                            self._logger.info(f"✅ [{session_id}] Validation passed")
                            _log_trace(
                                event="validation_passed",
                                phase="validation",
                                agent="validator",
                                status="success",
                            )
                            # Валидация прошла → завершаем успешно
                            break
                    else:
                        # Fail-closed: payload без поля validation — это ошибка контракта.
                        validator_missing_validation_field_count += 1
                        self._logger.warning(
                            f"⚠️ [{session_id}] Validator returned payload without validation field. "
                            "Finishing with failed_quality_gate."
                        )
                        quality_gate_failed = True
                        quality_gate_message = "Validator payload missing validation field"
                        quality_gate_issues_count = 0
                        _log_trace(
                            event="validation_failed",
                            phase="validation",
                            agent="validator",
                            status="failed",
                            details={
                                "message": quality_gate_message,
                                "issues_count": 0,
                                "reason": "missing_validation_field",
                            },
                        )
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
            final_status = "failed_quality_gate" if quality_gate_failed else "success"
            trace_status = final_status
            _log_trace(
                event="run_finish",
                phase="orchestrator",
                status=final_status,
                details={
                    "execution_time_sec": execution_time,
                    "time_to_first_result_ms": time_to_first_result_ms,
                    "replan_count": replan_count,
                    "agent_results_count": len(pipeline_context.get("agent_results", [])),
                    "quality_gate_failed": quality_gate_failed,
                    "quality_gate_message": quality_gate_message,
                    "quality_gate_issues_count": quality_gate_issues_count,
                    "planner_error_streak_max": max_planner_error_streak,
                    "context_compaction_level": last_context_compaction_level,
                    "fallback_reason": last_fallback_reason,
                    "pipeline_memory_keys": sorted(
                        list((pipeline_context.get("pipeline_memory") or {}).keys())
                    ) if isinstance(pipeline_context.get("pipeline_memory"), dict) else [],
                    "validator_error_count": validator_error_count,
                    "validator_timeout_count": validator_timeout_count,
                    "validator_parse_fallback_count": validator_parse_fallback_count,
                    "validator_missing_validation_field_count": validator_missing_validation_field_count,
                },
            )

            return {
                "status": final_status,
                "session_id": session_id,
                "plan": plan,
                "results": raw_results,
                "execution_time": execution_time,
                "time_to_first_result_ms": time_to_first_result_ms,
                "quality_gate_failed": quality_gate_failed,
                "quality_gate_message": quality_gate_message,
                "quality_gate_issues_count": quality_gate_issues_count,
                "planner_error_streak_max": max_planner_error_streak,
                "context_compaction_level": last_context_compaction_level,
                "fallback_reason": last_fallback_reason,
                "validator_error_count": validator_error_count,
                "validator_timeout_count": validator_timeout_count,
                "validator_parse_fallback_count": validator_parse_fallback_count,
                "validator_missing_validation_field_count": validator_missing_validation_field_count,
            }

        except Exception as e:
            self._logger.error(f"❌ [{session_id}] Failed: {e}", exc_info=True)
            trace_status = "error"
            trace_error = str(e)
            _log_trace(
                event="run_finish",
                phase="orchestrator",
                status="error",
                error=str(e),
            )
            return self._error_result(session_id, start_time, str(e))
        finally:
            if MultiAgentTraceLogger.is_enabled():
                if trace_status == "unknown":
                    trace_status = "error"
                    trace_error = trace_error or "Orchestrator finished without terminal status"
                    if not any(ev.get("event") == "run_finish" for ev in trace_events):
                        _log_trace(
                            event="run_finish",
                            phase="orchestrator",
                            status="error",
                            error=trace_error,
                        )

                aggregate: Dict[str, Dict[str, Any]] = {}
                for ev in trace_events:
                    if ev.get("event") != "agent_call_end":
                        continue
                    agent_name = ev.get("agent") or "unknown"
                    item = aggregate.setdefault(agent_name, {"calls": 0, "total_ms": 0, "errors": 0})
                    item["calls"] += 1
                    item["total_ms"] += int(ev.get("duration_ms") or 0)
                    if ev.get("status") == "error":
                        item["errors"] += 1

                trace_payload = {
                    "trace_version": 1,
                    "session_id": session_id,
                    "board_id": board_id,
                    "user_id": str(user_id) if user_id else None,
                    "request_preview": user_request[:500],
                    "started_at": start_time.isoformat(),
                    "finished_at": datetime.now().isoformat(),
                    "total_duration_ms": int((time.perf_counter() - run_started_perf) * 1000),
                    "status": trace_status,
                    "error": trace_error,
                    "events_count": len(trace_events),
                    "agent_metrics": aggregate,
                    "events": trace_events,
                }
                file_path = await MultiAgentTraceLogger.write_trace(trace_payload)
                trace_file_path = str(file_path) if file_path else None
                if trace_file_path:
                    self._logger.info("🧾 [%s] Trace saved: %s", session_id, trace_file_path)
            if ma_token is not None:
                reset_ma_overrides_token(ma_token)

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

    @staticmethod
    def _init_pipeline_memory(context: Dict[str, Any]) -> None:
        if not isinstance(context.get("pipeline_memory"), dict):
            context["pipeline_memory"] = {
                "goal": "",
                "constraints": [],
                "decisions": [],
                "open_questions": [],
                "evidence": [],
            }

    @staticmethod
    def _append_memory_items(target: List[str], value: Any, *, limit: int = 8) -> None:
        if value is None:
            return
        items = value if isinstance(value, list) else [value]
        for raw in items:
            text = str(raw).strip()
            if not text:
                continue
            if text in target:
                continue
            target.append(text)
            if len(target) > limit:
                del target[0 : len(target) - limit]

    @classmethod
    def _update_pipeline_memory(
        cls,
        pipeline_context: Dict[str, Any],
        *,
        agent_name: str,
        payload: Optional[AgentPayload] = None,
        note: Optional[str] = None,
    ) -> None:
        cls._init_pipeline_memory(pipeline_context)
        memory = pipeline_context["pipeline_memory"]
        if not isinstance(memory, dict):
            return

        if not memory.get("goal"):
            memory["goal"] = str(
                pipeline_context.get("original_user_request")
                or pipeline_context.get("user_request", "")
            )[:300]

        if note:
            cls._append_memory_items(memory.setdefault("decisions", []), note)

        if not payload:
            return

        if agent_name == "planner" and payload.plan:
            plan_steps = payload.plan.steps or []
            summary = f"Planner produced {len(plan_steps)} steps"
            cls._append_memory_items(memory.setdefault("decisions", []), summary)
            return

        if agent_name == "analyst":
            findings = payload.findings or []
            evidence = []
            for f in findings[:3]:
                text = f.text if hasattr(f, "text") else (f.get("text") if isinstance(f, dict) else "")
                if text:
                    evidence.append(text[:220])
            cls._append_memory_items(memory.setdefault("evidence", []), evidence, limit=10)

        if agent_name == "reporter":
            nar = payload.narrative.text if getattr(payload, "narrative", None) else ""
            if nar:
                cls._append_memory_items(memory.setdefault("decisions", []), f"Reporter summary: {nar[:220]}")

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

    async def _execute_context_filter_step(
        self,
        *,
        task_data: Dict[str, Any],
        pipeline_context: Dict[str, Any],
    ) -> AgentPayload:
        """
        LLM-assisted context filtering step used by Planner as `context_filter`.
        Flow:
        1) ContextFilterAgent builds filter JSON declaration from text task.
        2) Filter is applied to context (working set refresh).
        3) Active filter state is updated and filtered pipeline is recomputed.
        """
        board_context = dict(pipeline_context.get("board_context", {}) or {})
        if not isinstance(board_context, dict):
            return AgentPayload.make_error(
                agent="context_filter",
                error_message="board_context is not available",
            )
        if not board_context.get("content_nodes_data") and pipeline_context.get("content_nodes_data"):
            # Runtime fallback: orchestrator context may have prepared tables at top-level.
            board_context["content_nodes_data"] = pipeline_context.get("content_nodes_data", [])

        db = pipeline_context.get("db")
        board_id_raw = pipeline_context.get("board_id")
        board_uuid = None
        if board_id_raw and board_context.get("scope", "board") == "board":
            try:
                board_uuid = UUID(str(board_id_raw))
            except Exception:
                board_uuid = None

        try:
            user_request_for_filter = (
                task_data.get("user_request")
                or pipeline_context.get("original_user_request")
                or pipeline_context.get("user_request", "")
            )

            llm_filter_expression = task_data.get("filter_expression")
            llm_reason = ""
            llm_required_tables = task_data.get("required_tables", [])
            llm_allow_auto_filter = bool(task_data.get("allow_auto_filter", True))

            if "context_filter" in self.agents:
                llm_task = {
                    "type": "build_filter_expression",
                    "description": task_data.get("description", ""),
                    "user_request": user_request_for_filter,
                    "required_tables": llm_required_tables,
                    "allow_auto_filter": llm_allow_auto_filter,
                }
                runtime_options_map = pipeline_context.get("_agent_runtime_options_map")
                cf_runtime_options = (
                    runtime_options_map.get("context_filter")
                    if isinstance(runtime_options_map, dict)
                    else None
                )
                cf_policy = resolve_execution_policy(
                    "context_filter",
                    "build_filter_expression",
                    runtime_options=cf_runtime_options,
                )
                llm_payload = await self._execute_with_retry(
                    "context_filter",
                    llm_task,
                    pipeline_context,
                    max_retries=cf_policy.max_retries,
                    timeout_override=cf_policy.timeout_sec,
                    context_ladder=cf_policy.context_ladder,
                    context_factory=lambda lvl: select_context_for_step(
                        "context_filter",
                        pipeline_context,
                        task_type="build_filter_expression",
                        compaction_level=lvl,
                        runtime_options=cf_runtime_options,
                    ),
                )
                if llm_payload.status == "success":
                    llm_meta = llm_payload.metadata or {}
                    if llm_meta.get("filter_expression") is not None:
                        llm_filter_expression = llm_meta.get("filter_expression")
                    llm_required_tables = llm_meta.get("required_tables", llm_required_tables) or []
                    llm_allow_auto_filter = bool(llm_meta.get("allow_auto_filter", llm_allow_auto_filter))
                    llm_reason = str(llm_meta.get("reason", "") or "")
                else:
                    self._logger.warning(
                        "context_filter LLM generation failed, fallback to deterministic filter planning: %s",
                        llm_payload.error,
                    )

            self._logger.info(
                "🔎 context_filter input: %s",
                json.dumps(
                    {
                        "user_request": user_request_for_filter,
                        "llm_filter_expression": llm_filter_expression,
                        "llm_required_tables": llm_required_tables,
                        "llm_allow_auto_filter": llm_allow_auto_filter,
                        "board_scope": board_context.get("scope", "board"),
                        "source_board_ids": board_context.get("source_board_ids", []),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

            prepared = await ContextExecutionService().prepare_board_context(
                board_context=board_context,
                db=db,
                board_id=board_uuid,
                source_board_ids=board_context.get("source_board_ids", []),
                selected_node_ids=pipeline_context.get("selected_node_ids", []),
                required_tables=llm_required_tables,
                user_message=user_request_for_filter,
                filter_expression=llm_filter_expression,
                allow_auto_filter=llm_allow_auto_filter,
            )
            prepared_nodes = prepared.get("prepared_nodes_data", []) or []
            catalog_nodes = prepared.get("catalog_nodes_data", []) or []
            context_used = prepared.get("context_used", {}) or {}
            self._logger.info(
                "🔎 context_filter output: %s",
                json.dumps(
                    {
                        "filtering_mode": context_used.get("filtering_mode"),
                        "resolved_source_board_ids": context_used.get("resolved_source_board_ids", []),
                        "tables": context_used.get("tables", []),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

            applied_filter = context_used.get("filters") or llm_filter_expression
            if isinstance(applied_filter, dict):
                pipeline_context["_orchestrator_applied_filter_expression"] = applied_filter
            filtered_node_count = None
            if db is not None and isinstance(applied_filter, dict):
                try:
                    from app.services.filter_state_service import FilterStateService
                    from app.routes.filters import _compute_filtered_pipeline

                    user_id_str = str(pipeline_context.get("user_id") or "")
                    scope = str(board_context.get("scope", "board") or "board")
                    recompute_mode: Optional[str] = None
                    recomputed_nodes: List[Dict[str, Any]] = []

                    if board_uuid is not None:
                        # Board scope: recompute full board pipeline from source.
                        FilterStateService.add_filter_json_object(
                            scope="board",
                            target_id=str(board_uuid),
                            user_id=user_id_str,
                            filter_json=applied_filter,
                        )
                        filtered_nodes = await _compute_filtered_pipeline(
                            db,
                            board_uuid,
                            applied_filter,
                            user_id_str,
                        )
                        pipeline_context["_raw_filtered_pipeline_result"] = filtered_nodes
                        recomputed_nodes = self._normalize_filtered_nodes_data(filtered_nodes)
                        recompute_mode = "board_pipeline"
                    else:
                        # Dashboard scope: recompute each source board pipeline from source,
                        # then keep only nodes present in current assistant working set.
                        target_node_ids = self._extract_real_content_node_ids(prepared_nodes)
                        source_board_ids = self._parse_board_ids(
                            board_context.get("source_board_ids", [])
                        )
                        if not source_board_ids:
                            source_board_ids = await self._infer_board_ids_for_nodes(
                                db=db,
                                node_ids=target_node_ids,
                            )

                        dashboard_id = board_context.get("dashboard_id") or board_id_raw
                        if dashboard_id:
                            FilterStateService.add_filter_json_object(
                                scope="dashboard",
                                target_id=str(dashboard_id),
                                user_id=user_id_str,
                                filter_json=applied_filter,
                            )

                        combined_nodes: Dict[str, Dict[str, Any]] = {}
                        for bid in source_board_ids:
                            board_result = await _compute_filtered_pipeline(
                                db,
                                bid,
                                applied_filter,
                                user_id_str,
                            )
                            combined_nodes.update(board_result)

                        pipeline_context["_raw_filtered_pipeline_result"] = combined_nodes
                        normalized = self._normalize_filtered_nodes_data(combined_nodes)
                        if target_node_ids:
                            recomputed_nodes = [
                                n for n in normalized
                                if str(n.get("id", "")) in target_node_ids
                            ]
                        else:
                            recomputed_nodes = normalized
                        recompute_mode = "dashboard_pipeline"

                    if recomputed_nodes:
                        filtered_node_count = len(recomputed_nodes)
                        pipeline_context["filtered_content_nodes_data"] = recomputed_nodes
                        prepared_nodes = recomputed_nodes
                        context_used["tables"] = self._build_context_table_stats_from_nodes(
                            recomputed_nodes,
                            base_stats=context_used.get("tables", []),
                        )
                        context_used["pipeline_recompute_mode"] = recompute_mode
                        self._log_filtered_nodes_snapshot(
                            label=f"context_filter:{recompute_mode}",
                            nodes=recomputed_nodes,
                        )
                except Exception:
                    self._logger.exception("Failed to persist/recompute context filter state")

            # Refresh runtime context for next steps.
            pipeline_context["content_nodes_data"] = prepared_nodes
            pipeline_context["selected_content_nodes_data"] = prepared_nodes
            pipeline_context["input_data_preview"] = self._build_input_data_preview(prepared_nodes)
            pipeline_context["catalog_data_preview"] = self._build_input_data_preview(
                catalog_nodes,
                sample_rows_limit=1,
            )
            board_context["content_nodes_data"] = prepared_nodes
            board_context["selected_nodes_data"] = prepared_nodes
            pipeline_context["board_context"] = board_context

            return AgentPayload.success(
                agent="context_filter",
                narrative={"text": "Context filter applied", "format": "plain"},
                metadata={
                    "context_used": context_used,
                    "working_set_tables": len(pipeline_context["input_data_preview"]),
                    "catalog_tables": len(pipeline_context["catalog_data_preview"]),
                    "filter_applied_for_answer": bool(context_used.get("filter_applied_for_answer")),
                    "auto_filter_planned": bool(context_used.get("auto_filter_planned")),
                    "filters": context_used.get("filters"),
                    "proposed_filters": context_used.get("proposed_filters"),
                    "llm_filter_expression": llm_filter_expression,
                    "llm_filter_reason": llm_reason,
                    "llm_required_tables": llm_required_tables,
                    "filtered_node_count": filtered_node_count,
                },
            )
        except Exception as e:
            self._logger.exception("context_filter step failed: %s", e)
            return AgentPayload.make_error(
                agent="context_filter",
                error_message=str(e),
            )

    @staticmethod
    def _build_input_data_preview(
        prepared_nodes_data: List[Dict[str, Any]],
        *,
        sample_rows_limit: int = 8,
    ) -> Dict[str, Dict[str, Any]]:
        """Build compact table preview for agent context (orchestrator runtime update)."""
        preview: Dict[str, Dict[str, Any]] = {}
        max_tables = 32

        for node in prepared_nodes_data:
            node_name = str(node.get("name") or node.get("id") or "node")
            node_id = str(node.get("id") or node_name)
            tables = node.get("tables", []) or []
            for table in tables:
                if len(preview) >= max_tables:
                    return preview
                table_name = str(table.get("name", "table"))
                table_key = f"{node_id}:{table_name}"
                columns = table.get("columns", []) or []
                sample_rows = table.get("sample_rows", []) or []
                preview[table_key] = {
                    "node_id": node_id,
                    "node_name": node_name,
                    "table_name": table_name,
                    "columns": columns,
                    "row_count": int(table.get("row_count", len(sample_rows))),
                    "sample_rows": sample_rows[:sample_rows_limit],
                }

        return preview

    @staticmethod
    def _normalize_filtered_nodes_data(
        filtered_nodes: Any,
    ) -> List[Dict[str, Any]]:
        """Normalize _compute_filtered_pipeline output to content_nodes_data format."""
        if isinstance(filtered_nodes, dict):
            items = filtered_nodes.items()
        elif isinstance(filtered_nodes, list):
            items = []
            for idx, entry in enumerate(filtered_nodes):
                if isinstance(entry, dict):
                    node_id = str(entry.get("id") or entry.get("node_id") or f"node_{idx}")
                    items.append((node_id, entry))
        else:
            return []

        normalized: List[Dict[str, Any]] = []
        for node_id, entry in items:
            if not isinstance(entry, dict):
                continue
            out_tables: List[Dict[str, Any]] = []
            for table in entry.get("tables", []) or []:
                if not isinstance(table, dict):
                    continue
                rows = table.get("rows", []) or []
                sample_rows = table.get("sample_rows", []) or rows[:8]
                out_tables.append(
                    {
                        "name": table.get("name", "table"),
                        "columns": table.get("columns", []) or [],
                        "row_count": int(table.get("row_count", len(rows))),
                        "sample_rows": sample_rows[:8],
                    }
                )
            normalized.append(
                {
                    "id": str(entry.get("id") or node_id),
                    "name": entry.get("name") or f"content_node-{node_id}",
                    "node_type": entry.get("node_type", "content"),
                    "text": entry.get("text", ""),
                    "tables": out_tables,
                }
            )
        return normalized

    @staticmethod
    def _build_context_table_stats_from_nodes(
        prepared_nodes: List[Dict[str, Any]],
        *,
        base_stats: Any = None,
    ) -> List[Dict[str, Any]]:
        """Build context_used.tables from normalized nodes preserving known before-counts."""
        before_map: Dict[tuple[str, str], int] = {}
        if isinstance(base_stats, list):
            for s in base_stats:
                if not isinstance(s, dict):
                    continue
                nid = str(s.get("node_id") or "")
                tname = str(s.get("table_name") or "")
                if not nid or not tname:
                    continue
                try:
                    before_map[(nid, tname)] = int(s.get("row_count_before", 0))
                except Exception:
                    continue

        out: List[Dict[str, Any]] = []
        for node in prepared_nodes:
            node_id = str(node.get("id") or "")
            node_name = str(node.get("name") or node_id)
            for table in node.get("tables", []) or []:
                table_name = str(table.get("name", "table"))
                sample_rows = table.get("sample_rows", []) or []
                after_count = int(table.get("row_count", len(sample_rows)))
                before_count = before_map.get((node_id, table_name), after_count)
                out.append(
                    {
                        "node_id": node_id,
                        "node_name": node_name,
                        "table_name": table_name,
                        "row_count_before": before_count,
                        "row_count_after": after_count,
                        "row_count_after_is_sample": False,
                    }
                )
        return out

    @staticmethod
    def _extract_real_content_node_ids(prepared_nodes: List[Dict[str, Any]]) -> set[str]:
        out: set[str] = set()
        for node in prepared_nodes or []:
            raw_id = str(node.get("id", "")).strip()
            if not raw_id or ":" in raw_id:
                continue
            try:
                out.add(str(UUID(raw_id)))
            except Exception:
                continue
        return out

    @staticmethod
    def _parse_board_ids(raw_ids: Any) -> list[UUID]:
        out: list[UUID] = []
        seen: set[str] = set()
        for raw in raw_ids if isinstance(raw_ids, list) else []:
            try:
                bid = UUID(str(raw))
            except Exception:
                continue
            key = str(bid)
            if key in seen:
                continue
            seen.add(key)
            out.append(bid)
        return out

    @staticmethod
    async def _infer_board_ids_for_nodes(
        *,
        db: Any,
        node_ids: set[str],
    ) -> list[UUID]:
        if not node_ids:
            return []
        from sqlalchemy import select
        from app.models.content_node import ContentNode

        uuids: list[UUID] = []
        for nid in node_ids:
            try:
                uuids.append(UUID(nid))
            except Exception:
                continue
        if not uuids:
            return []

        result = await db.execute(
            select(ContentNode.board_id).where(ContentNode.id.in_(uuids))
        )
        out: list[UUID] = []
        seen: set[str] = set()
        for (bid,) in result.all():
            if not bid:
                continue
            key = str(bid)
            if key in seen:
                continue
            seen.add(key)
            out.append(bid)
        return out

    def _log_filtered_nodes_snapshot(
        self,
        *,
        label: str,
        nodes: List[Dict[str, Any]],
    ) -> None:
        """
        Emit compact but detailed diagnostics for filtered node tables.
        """
        try:
            payload: list[dict[str, Any]] = []
            for node in (nodes or [])[:20]:
                node_entry = {
                    "node_id": str(node.get("id", "")),
                    "node_name": str(node.get("name", "")),
                    "tables": [],
                }
                for table in (node.get("tables", []) or [])[:10]:
                    sample_rows = table.get("sample_rows", []) or []
                    compact_rows = []
                    for row in sample_rows[:3]:
                        if isinstance(row, dict):
                            compact_rows.append({str(k): v for k, v in list(row.items())[:8]})
                    node_entry["tables"].append({
                        "table_name": str(table.get("name", "table")),
                        "row_count": int(table.get("row_count", len(sample_rows))),
                        "sample_rows": compact_rows,
                    })
                payload.append(node_entry)
            self._logger.info("🔎 FILTERED NODES SNAPSHOT %s: %s", label, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            self._logger.exception("Failed to emit filtered nodes snapshot for %s", label)

    @staticmethod
    def _merge_filter_parts(parts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        clean = [p for p in parts if isinstance(p, dict) and p]
        if not clean:
            return None
        if len(clean) == 1:
            return clean[0]
        return {"type": "and", "conditions": clean}

    def _resolve_effective_filter_for_tools(
        self,
        pipeline_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Собирает FilterExpression для readTableData: UI (board/dashboard) + fallback из чата."""
        from app.services.filter_state_service import FilterStateService

        parts: List[Dict[str, Any]] = []
        board_id = pipeline_context.get("board_id")
        user_id = str(pipeline_context.get("user_id") or "")
        bc = pipeline_context.get("board_context") or {}
        if board_id and user_id:
            af = FilterStateService.get_active_filters(
                scope="board",
                target_id=str(board_id),
                user_id=user_id,
            )
            f = af.get("filters")
            if isinstance(f, dict) and f:
                parts.append(f)
        dash = bc.get("dashboard_id") or pipeline_context.get("dashboard_id")
        if dash and user_id:
            af = FilterStateService.get_active_filters(
                scope="dashboard",
                target_id=str(dash),
                user_id=user_id,
            )
            f = af.get("filters")
            if isinstance(f, dict) and f:
                parts.append(f)
        merged = self._merge_filter_parts(parts)
        if merged is not None:
            return merged
        fallback = pipeline_context.get("_orchestrator_applied_filter_expression")
        if isinstance(fallback, dict) and fallback:
            return fallback
        return None

    @staticmethod
    def _tables_from_raw_pipeline_result(
        raw: Optional[Dict[str, Any]],
        content_node_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        if not isinstance(raw, dict) or not raw:
            return None
        entry = raw.get(str(content_node_id))
        if not isinstance(entry, dict):
            return None
        tables = entry.get("tables")
        if not isinstance(tables, list) or not tables:
            return None
        return [t for t in tables if isinstance(t, dict)]

    def _merge_filtered_pipeline_into_raw_cache(
        self,
        pipeline_context: Dict[str, Any],
        fragment: Dict[str, Dict[str, Any]],
    ) -> None:
        """Обновляет _raw_filtered_pipeline_result свежим фрагментом (по node_id)."""
        if not fragment:
            return
        existing = pipeline_context.get("_raw_filtered_pipeline_result")
        if isinstance(existing, dict):
            existing.update(fragment)
        else:
            pipeline_context["_raw_filtered_pipeline_result"] = dict(fragment)

    async def _compute_filtered_pipeline_tables_for_node(
        self,
        *,
        content_node_id: str,
        pipeline_context: Dict[str, Any],
    ) -> Optional[List[Dict[str, Any]]]:
        """Таблицы ContentNode после полной pandas-цепочки на бэке (как compute-filtered / readTableData).

        Использует тот же эффективный фильтр, что ``_resolve_effective_filter_for_tools`` (board/dashboard + чат).
        ``filters=None`` допустим — пересчёт без кросс-фильтра, но с исполнением цепочки upstream.

        Возвращает ``None``, если пересчёт недоступен (нет сессии, выключен путь, нет board).
        Возвращает список таблиц (возможно пустой), если пересчёт выполнен.
        """
        if not self._db_session_factory:
            return None
        if not ma_bool("MULTI_AGENT_TOOLS_USE_FILTERED_PIPELINE", True):
            return None

        from app.routes.filters import _compute_filtered_pipeline

        eff = self._resolve_effective_filter_for_tools(pipeline_context)
        user_id_str = str(pipeline_context.get("user_id") or "")
        board_id_raw = pipeline_context.get("board_id")
        bc = pipeline_context.get("board_context") or {}
        board_uuid: Optional[UUID] = None
        if board_id_raw and bc.get("scope", "board") == "board":
            try:
                board_uuid = UUID(str(board_id_raw))
            except Exception:
                board_uuid = None

        try:
            async with self._db_session_factory() as session:
                if board_uuid is not None:
                    result = await _compute_filtered_pipeline(
                        session,
                        board_uuid,
                        eff,
                        user_id_str,
                    )
                    self._merge_filtered_pipeline_into_raw_cache(pipeline_context, result)
                    entry = result.get(str(content_node_id))
                    if isinstance(entry, dict):
                        tables = entry.get("tables")
                        if isinstance(tables, list):
                            return [t for t in tables if isinstance(t, dict)]
                    return []

                prepared = pipeline_context.get("content_nodes_data", []) or []
                node_ids_for_infer: set[str] = set(
                    self._extract_real_content_node_ids(prepared)
                )
                if content_node_id:
                    try:
                        node_ids_for_infer.add(str(UUID(str(content_node_id))))
                    except Exception:
                        pass
                source_board_ids = self._parse_board_ids(bc.get("source_board_ids", []))
                if not source_board_ids:
                    infer_set = node_ids_for_infer or {str(content_node_id)}
                    source_board_ids = await self._infer_board_ids_for_nodes(
                        db=session,
                        node_ids=infer_set,
                    )
                if not source_board_ids:
                    return None

                combined: Dict[str, Dict[str, Any]] = {}
                for bid in source_board_ids:
                    board_result = await _compute_filtered_pipeline(
                        session,
                        bid,
                        eff,
                        user_id_str,
                    )
                    combined.update(board_result)
                self._merge_filtered_pipeline_into_raw_cache(pipeline_context, combined)
                entry = combined.get(str(content_node_id))
                if isinstance(entry, dict):
                    tables = entry.get("tables")
                    if isinstance(tables, list):
                        return [t for t in tables if isinstance(t, dict)]
                return []
        except Exception:
            logger.exception(
                "compute_filtered_pipeline_tables_for_node failed node=%s",
                content_node_id,
            )
            return None

    async def _ensure_filtered_pipeline_raw_cache(
        self,
        pipeline_context: Dict[str, Any],
    ) -> None:
        """Ленивый пересчёт _compute_filtered_pipeline для тулов (если сырой кэш ещё пуст)."""
        if not ma_bool("MULTI_AGENT_TOOLS_USE_FILTERED_PIPELINE", True):
            return
        if pipeline_context.get("_raw_filtered_pipeline_result"):
            return
        if not self._db_session_factory:
            return
        eff = self._resolve_effective_filter_for_tools(pipeline_context)
        user_id_str = str(pipeline_context.get("user_id") or "")
        board_id_raw = pipeline_context.get("board_id")
        bc = pipeline_context.get("board_context") or {}
        board_uuid: Optional[UUID] = None
        if board_id_raw and bc.get("scope", "board") == "board":
            try:
                board_uuid = UUID(str(board_id_raw))
            except Exception:
                board_uuid = None
        from app.routes.filters import _compute_filtered_pipeline

        try:
            async with self._db_session_factory() as session:
                if board_uuid is not None:
                    result = await _compute_filtered_pipeline(
                        session,
                        board_uuid,
                        eff,
                        user_id_str,
                    )
                    pipeline_context["_raw_filtered_pipeline_result"] = result
                else:
                    prepared = pipeline_context.get("content_nodes_data", []) or []
                    target_ids = self._extract_real_content_node_ids(prepared)
                    source_board_ids = self._parse_board_ids(
                        bc.get("source_board_ids", [])
                    )
                    if not source_board_ids:
                        source_board_ids = await self._infer_board_ids_for_nodes(
                            db=session,
                            node_ids=target_ids,
                        )
                    if not source_board_ids:
                        # Нет доски для пересчёта — оставляем кэш пустым (fallback на content в БД).
                        return
                    combined: Dict[str, Dict[str, Any]] = {}
                    for bid in source_board_ids:
                        board_result = await _compute_filtered_pipeline(
                            session,
                            bid,
                            eff,
                            user_id_str,
                        )
                        combined.update(board_result)
                    pipeline_context["_raw_filtered_pipeline_result"] = combined
        except Exception:
            logger.exception("Lazy filtered pipeline for multi-agent tools failed")

    # ------------------------------------------------------------------
    # Internal: orchestrator tools
    # ------------------------------------------------------------------

    async def _execute_orchestrator_tool_request(
        self,
        *,
        request: Dict[str, Any],
        pipeline_context: Dict[str, Any],
    ) -> ToolResult:
        tool_name = str(request.get("tool_name") or "").strip()
        request_id = str(request.get("request_id") or str(uuid4()))
        arguments = request.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        context_content_node_ids: List[str] = []
        for raw_ids in (
            pipeline_context.get("selected_node_ids"),
            pipeline_context.get("content_node_ids"),
            pipeline_context.get("contentNodeIds"),
        ):
            if not isinstance(raw_ids, list):
                continue
            for item in raw_ids:
                text = str(item or "").strip()
                if text and text not in context_content_node_ids:
                    context_content_node_ids.append(text)
        default_content_node_id = str(
            pipeline_context.get("content_node_id")
            or (context_content_node_ids[0] if context_content_node_ids else "")
            or ""
        ).strip()
        default_node_ids: List[str] = []
        for item in context_content_node_ids:
            if item and item not in default_node_ids:
                default_node_ids.append(item)
        if default_content_node_id and default_content_node_id not in default_node_ids:
            default_node_ids.insert(0, default_content_node_id)
        try:
            if tool_name in {"readTableListFromContentNodes", "readTableListFromContentNode"}:
                node_ids_raw = (
                    arguments.get("nodeIds")
                    or arguments.get("contentNodeIds")
                )
                if not isinstance(node_ids_raw, list):
                    node_ids_raw = []
                normalized_node_ids: List[str] = []
                for item in node_ids_raw:
                    text = str(item or "").strip()
                    if text and text not in normalized_node_ids:
                        normalized_node_ids.append(text)
                legacy_single = str(
                    arguments.get("contentNodeId")
                    or arguments.get("content_node_id")
                    or arguments.get("nodeId")
                    or ""
                ).strip()
                if legacy_single and legacy_single not in normalized_node_ids:
                    normalized_node_ids.append(legacy_single)
                if not normalized_node_ids and default_node_ids:
                    normalized_node_ids = list(default_node_ids)
                if normalized_node_ids:
                    arguments["nodeIds"] = normalized_node_ids
                    # Keep legacy field for compatibility in downstream logs/prompts.
                    if not arguments.get("contentNodeId"):
                        arguments["contentNodeId"] = normalized_node_ids[0]
            if tool_name == "readTableData":
                json_decl = arguments.get("jsonDecl", arguments)
                if isinstance(json_decl, str):
                    try:
                        json_decl = json.loads(json_decl)
                    except Exception:
                        json_decl = {}
                if not isinstance(json_decl, dict):
                    json_decl = {}
                json_decl = _normalize_read_table_data_json_decl(
                    json_decl,
                    default_content_node_id=default_content_node_id,
                    pipeline_context=pipeline_context,
                )
                if "jsonDecl" in arguments:
                    arguments["jsonDecl"] = json_decl
                else:
                    arguments = json_decl

            cache_key: Optional[str] = None
            canonical_for_cache = ""
            if tool_name in {
                "readTableListFromContentNodes",
                "readTableListFromContentNode",
                "readTableData",
            }:
                canonical_for_cache = (
                    "readTableListFromContentNodes"
                    if tool_name
                    in ("readTableListFromContentNodes", "readTableListFromContentNode")
                    else "readTableData"
                )
                cache_key = _tool_request_cache_key(canonical_for_cache, arguments)
                cache = pipeline_context.get("_tool_result_cache")
                if isinstance(cache, dict) and cache_key in cache:
                    entry = copy.deepcopy(cache[cache_key])
                    entry["request_id"] = request_id
                    self._logger.info(
                        "Tool result cache hit: %s (key=%s…)",
                        canonical_for_cache,
                        cache_key[:16],
                    )
                    tr_fn = pipeline_context.get("_trace_event")
                    if callable(tr_fn):
                        try:
                            tr_fn(
                                event="tool_cache_hit",
                                phase="execute_step",
                                details={
                                    "tool_name": canonical_for_cache,
                                    "cache_key_prefix": cache_key[:16],
                                },
                            )
                        except Exception:
                            pass
                    return ToolResult.model_validate(entry)

            if tool_name in {"readTableListFromContentNodes", "readTableListFromContentNode"}:
                data = await self._tool_read_table_list_from_content_node(
                    arguments=arguments,
                    pipeline_context=pipeline_context,
                )
                res = ToolResult(
                    request_id=request_id,
                    tool_name="readTableListFromContentNodes",
                    success=True,
                    data=data,
                )
                if cache_key and canonical_for_cache:
                    _store_tool_result_in_pipeline_cache(
                        pipeline_context,
                        cache_key=cache_key,
                        canonical_tool_name=canonical_for_cache,
                        arguments=arguments,
                        result_dump=res.model_dump(),
                    )
                return res
            if tool_name == "readTableData":
                data = await self._tool_read_table_data(
                    arguments=arguments,
                    pipeline_context=pipeline_context,
                )
                res = ToolResult(
                    request_id=request_id,
                    tool_name=tool_name,
                    success=True,
                    data=data,
                )
                if cache_key and canonical_for_cache:
                    _store_tool_result_in_pipeline_cache(
                        pipeline_context,
                        cache_key=cache_key,
                        canonical_tool_name=canonical_for_cache,
                        arguments=arguments,
                        result_dump=res.model_dump(),
                    )
                return res
            return ToolResult(
                request_id=request_id,
                tool_name=tool_name or "unknown",
                success=False,
                error=f"Unsupported tool: {tool_name}",
            )
        except Exception as e:
            self._logger.warning("Tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                request_id=request_id,
                tool_name=tool_name or "unknown",
                success=False,
                error=str(e),
            )

    def _content_node_display_from_pipeline_lists(
        self,
        content_node_id: str,
        pipeline_context: Dict[str, Any],
    ) -> Optional[tuple[str, str]]:
        """Имя и текстовое описание ноды из снимков контекста (без запроса к БД)."""
        cid = str(content_node_id)
        lists_to_scan: List[Any] = []
        for key in (
            "content_nodes_data",
            "filtered_content_nodes_data",
            "selected_content_nodes_data",
        ):
            v = pipeline_context.get(key)
            if isinstance(v, list):
                lists_to_scan.append(v)
        bc = pipeline_context.get("board_context")
        if isinstance(bc, dict):
            for key in ("content_nodes_data", "selected_nodes_data"):
                v = bc.get(key)
                if isinstance(v, list):
                    lists_to_scan.append(v)
        for nodes in lists_to_scan:
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                nid = str(node.get("id") or node.get("node_id") or "")
                if nid != cid:
                    continue
                meta = node.get("metadata") or node.get("node_metadata") or {}
                name_from_meta = ""
                if isinstance(meta, dict):
                    name_from_meta = str(meta.get("name") or "").strip()
                name = (
                    name_from_meta
                    or node.get("name")
                    or node.get("node_name")
                    or ""
                )
                name = str(name).strip()
                if not name:
                    name = f"content_node-{cid}"
                desc = str(
                    node.get("text")
                    or node.get("description")
                    or ""
                )
                return (name, desc)
        return None

    async def _resolve_content_node_display_info(
        self,
        *,
        content_node_id: str,
        pipeline_context: Dict[str, Any],
    ) -> tuple[str, str]:
        """Имя ноды и описание (текст summary); контекст пайплайна, иначе БД."""
        cached = self._content_node_display_from_pipeline_lists(
            content_node_id, pipeline_context
        )
        if cached is not None:
            return cached
        ctx_board = pipeline_context.get("board_id")
        fallback = (f"content_node-{content_node_id}", "")
        if self._db_session_factory:
            try:
                from app.services.content_node_service import ContentNodeService

                async with self._db_session_factory() as session:
                    node = await ContentNodeService.get_content_node(
                        session,
                        UUID(str(content_node_id)),
                    )
                    if node:
                        if ctx_board and str(node.board_id) != str(ctx_board):
                            return fallback
                        nm = node.node_metadata or {}
                        name = str(nm.get("name", "") or "").strip() if nm else ""
                        if not name:
                            name = f"Node {node.id}"
                        text = ""
                        if isinstance(node.content, dict):
                            text = str(node.content.get("text") or "")
                        return (name, text)
            except Exception as e:
                self._logger.debug(
                    "content_node display info DB fallback for %s: %s",
                    content_node_id,
                    e,
                )
        return fallback

    async def _tool_read_table_list_from_content_node(
        self,
        *,
        arguments: Dict[str, Any],
        pipeline_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        node_ids_raw = (
            arguments.get("nodeIds")
            or arguments.get("contentNodeIds")
            or []
        )
        if not isinstance(node_ids_raw, list):
            node_ids_raw = []
        normalized_node_ids: List[str] = []
        for item in node_ids_raw:
            text = str(item or "").strip()
            if text and text not in normalized_node_ids:
                normalized_node_ids.append(text)
        legacy_single = str(
            arguments.get("contentNodeId")
            or arguments.get("content_node_id")
            or arguments.get("nodeId")
            or ""
        ).strip()
        if legacy_single and legacy_single not in normalized_node_ids:
            normalized_node_ids.append(legacy_single)
        if not normalized_node_ids:
            raise ValueError("nodeIds is required")

        out_tables: List[Dict[str, Any]] = []
        nodes_payload: List[Dict[str, Any]] = []
        for node_id in normalized_node_ids:
            cn_name, cn_desc = await self._resolve_content_node_display_info(
                content_node_id=str(node_id),
                pipeline_context=pipeline_context,
            )
            tables = await self._load_content_node_tables(
                content_node_id=str(node_id),
                pipeline_context=pipeline_context,
            )
            node_tables: List[Dict[str, Any]] = []
            for idx, table in enumerate(tables):
                if not isinstance(table, dict):
                    continue
                table_name = str(table.get("name", f"table_{idx + 1}"))
                table_id = str(table.get("id") or table_name)
                columns_raw = table.get("columns", []) or []
                columns: List[Dict[str, Any]] = []
                for col in columns_raw:
                    if isinstance(col, dict):
                        columns.append(
                            {
                                "name": str(col.get("name", "")),
                                "type": str(col.get("type", "string")),
                            }
                        )
                    else:
                        columns.append({"name": str(col), "type": "string"})
                row_count = int(
                    table.get(
                        "row_count",
                        len(table.get("rows", []) or table.get("sample_rows", []) or []),
                    )
                )
                table_item = {
                    "content_node_id": str(node_id),
                    "content_node_name": cn_name,
                    "content_node_description": cn_desc,
                    "table_id": table_id,
                    "table_name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                }
                out_tables.append(table_item)
                node_tables.append(
                    {
                        "content_node_name": cn_name,
                        "content_node_description": cn_desc,
                        "table_id": table_id,
                        "table_name": table_name,
                        "columns": columns,
                        "row_count": row_count,
                    }
                )
            nodes_payload.append(
                {
                    "content_node_id": str(node_id),
                    "content_node_name": cn_name,
                    "content_node_description": cn_desc,
                    "tables": node_tables,
                    "tables_count": len(node_tables),
                }
            )
        return {
            "content_node_id": normalized_node_ids[0],
            "content_node_ids": normalized_node_ids,
            "nodes": nodes_payload,
            "tables": out_tables,
            "tables_count": len(out_tables),
        }

    async def _tool_read_table_data(
        self,
        *,
        arguments: Dict[str, Any],
        pipeline_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        json_decl = arguments.get("jsonDecl", arguments)
        if isinstance(json_decl, str):
            try:
                json_decl = json.loads(json_decl)
            except Exception:
                raise ValueError("jsonDecl must be valid JSON object")
        if not isinstance(json_decl, dict):
            raise ValueError("jsonDecl must be object")

        content_node_id = (
            json_decl.get("contentNodeId")
            or json_decl.get("content_node_id")
            or json_decl.get("nodeId")
        )
        table_id = json_decl.get("table_id") or json_decl.get("tableId")
        if not content_node_id:
            raise ValueError("jsonDecl.contentNodeId is required")
        if not table_id:
            raise ValueError(
                "jsonDecl.table_id is required (legacy alias: tableId)"
            )

        offset = max(0, int(json_decl.get("offset", 0) or 0))
        requested_limit = int(json_decl.get("limit", 50) or 50)
        max_limit = max(1, ma_int("MULTI_AGENT_TOOL_READ_TABLE_DATA_MAX_LIMIT", 200))
        limit = min(max(1, requested_limit), max_limit)

        tables = await self._load_content_node_tables(
            content_node_id=str(content_node_id),
            pipeline_context=pipeline_context,
        )
        target: Optional[Dict[str, Any]] = None
        for table in tables:
            if not isinstance(table, dict):
                continue
            t_name = str(table.get("name", ""))
            t_id = str(table.get("id") or t_name)
            if str(table_id) in (t_id, t_name):
                target = table
                break
        if not target:
            raise ValueError(
                f"Table '{table_id}' not found in content node {content_node_id}"
            )

        rows = target.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        row_count_meta = int(
            target.get("row_count", len(rows) if rows else 0)
        )
        # Снимок отфильтрованного пайплайна часто даёт row_count/columns без materialized rows —
        # тогда readTableData возвращал 0 строк при ненулевом row_count (см. трейсы: «таблицы пусты»).
        if not rows and row_count_meta > 0:
            hydrated = await self._hydrate_table_rows_from_content_db(
                content_node_id=str(content_node_id),
                table_id=str(table_id),
                pipeline_context=pipeline_context,
            )
            if isinstance(hydrated, list) and hydrated:
                rows = hydrated
                self._logger.info(
                    "readTableData: hydrated %d row(s) for node=%s table=%s "
                    "(snapshot had metadata only; filtered pipeline or content fallback)",
                    len(rows),
                    content_node_id,
                    table_id,
                )
        row_count = int(target.get("row_count", len(rows)))
        if rows:
            row_count = max(row_count, len(rows))
        sliced_rows = rows[offset : offset + limit]
        columns_raw = target.get("columns", []) or []
        columns: List[Dict[str, Any]] = []
        for col in columns_raw:
            if isinstance(col, dict):
                columns.append(
                    {
                        "name": str(col.get("name", "")),
                        "type": str(col.get("type", "string")),
                    }
                )
            else:
                columns.append({"name": str(col), "type": "string"})
        return {
            "content_node_id": str(content_node_id),
            "table_id": str(target.get("id") or target.get("name") or table_id),
            "table_name": str(target.get("name") or table_id),
            "row_count": row_count,
            "offset": offset,
            "limit": limit,
            "returned_rows": len(sliced_rows),
            "columns": columns,
            "rows": sliced_rows,
        }

    async def _hydrate_table_rows_from_content_db(
        self,
        *,
        content_node_id: str,
        table_id: str,
        pipeline_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Строки при пустом ``rows`` в снимке: сначала полная цепочка на бэке (как compute-filtered), затем content в БД.

        Прямое чтение ``node.content`` без пересчёта обходит кросс-фильтр и upstream-трансформации;
        поэтому при включённом ``MULTI_AGENT_TOOLS_USE_FILTERED_PIPELINE`` сначала вызывается
        ``_compute_filtered_pipeline`` с тем же эффективным фильтром, что у readTableData.
        """
        pipeline_tables = await self._compute_filtered_pipeline_tables_for_node(
            content_node_id=content_node_id,
            pipeline_context=pipeline_context,
        )
        if pipeline_tables is not None:
            tid = str(table_id)
            for t in pipeline_tables:
                if not isinstance(t, dict):
                    continue
                t_name = str(t.get("name", ""))
                t_id = str(t.get("id") or t_name)
                if tid in (t_id, t_name):
                    r = t.get("rows", [])
                    return (
                        [x for x in r if isinstance(x, dict)]
                        if isinstance(r, list)
                        else []
                    )
            return []

        if not self._db_session_factory:
            return []
        try:
            from uuid import UUID as _UUID

            from app.services.content_node_service import ContentNodeService

            async with self._db_session_factory() as session:
                node = await ContentNodeService.get_content_node(
                    session,
                    _UUID(str(content_node_id)),
                )
                if not node or not isinstance(node.content, dict):
                    return []
                ctx_board = pipeline_context.get("board_id")
                if ctx_board and str(node.board_id) != str(ctx_board):
                    return []
                tables = node.content.get("tables", [])
                if not isinstance(tables, list):
                    return []
                tid = str(table_id)
                for t in tables:
                    if not isinstance(t, dict):
                        continue
                    t_name = str(t.get("name", ""))
                    t_id = str(t.get("id") or t_name)
                    if tid in (t_id, t_name):
                        r = t.get("rows", [])
                        return [x for x in r if isinstance(x, dict)] if isinstance(r, list) else []
        except Exception as e:
            logger.debug(
                "hydrate_table_rows_from_content_db failed node=%s table=%s: %s",
                content_node_id,
                table_id,
                e,
            )
        return []

    async def _load_content_node_tables(
        self,
        *,
        content_node_id: str,
        pipeline_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Таблицы ноды: сначала снимок отфильтрованного пайплайна (как на доске), иначе БД."""
        raw = pipeline_context.get("_raw_filtered_pipeline_result")
        tbl = self._tables_from_raw_pipeline_result(raw, content_node_id)
        if tbl:
            return tbl
        await self._ensure_filtered_pipeline_raw_cache(pipeline_context)
        raw = pipeline_context.get("_raw_filtered_pipeline_result")
        tbl = self._tables_from_raw_pipeline_result(raw, content_node_id)
        if tbl:
            return tbl

        # Primary path: DB lookup to return full table rows (без активного фильтра).
        if self._db_session_factory:
            try:
                from app.services.content_node_service import ContentNodeService

                async with self._db_session_factory() as session:
                    node = await ContentNodeService.get_content_node(
                        session,
                        UUID(str(content_node_id)),
                    )
                    if node and isinstance(node.content, dict):
                        ctx_board = pipeline_context.get("board_id")
                        if ctx_board and str(node.board_id) != str(ctx_board):
                            raise ValueError(
                                f"ContentNode {content_node_id} does not belong to board {ctx_board}"
                            )
                        tables = node.content.get("tables", [])
                        if isinstance(tables, list):
                            return [t for t in tables if isinstance(t, dict)]
            except Exception as e:
                self._logger.debug(
                    "DB table load fallback for node %s: %s",
                    content_node_id,
                    e,
                )

        # Fallback path: context nodes (may be sampled).
        for node in pipeline_context.get("content_nodes_data", []) or []:
            node_id = str(node.get("id") or node.get("node_id") or "")
            if node_id != str(content_node_id):
                continue
            tables = node.get("tables", []) or []
            return [t for t in tables if isinstance(t, dict)]
        return []

    # ------------------------------------------------------------------
    # Internal: step execution
    # ------------------------------------------------------------------

    async def _execute_agent(
        self,
        agent_name: str,
        task: Dict[str, Any],
        context: Dict[str, Any],
        timeout_override: Optional[int] = None,
    ) -> AgentPayload:
        """Вызывает ``agent.process_task()`` с таймаутом. Возвращает AgentPayload."""
        agent = self.agents.get(agent_name)
        if not agent:
            return AgentPayload.make_error(
                agent=agent_name,
                error_message=f"Agent '{agent_name}' not available",
            )

        timeout = timeout_override or TimeoutConfig.get_timeout(MessageType.TASK_REQUEST, agent_name)

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
        *,
        max_retries: Optional[int] = None,
        timeout_override: Optional[int] = None,
        context_ladder: Optional[List[str]] = None,
        context_factory: Optional[Callable[[str], Dict[str, Any]]] = None,
        on_retry: Optional[Callable[[int, str, str], None]] = None,
    ) -> AgentPayload:
        """Выполняет шаг с retry (MAX_RETRY_ATTEMPTS).

        При ошибке инжектирует информацию об ошибке в context,
        чтобы агент мог учесть её при повторной генерации.
        """
        retries = MAX_RETRY_ATTEMPTS if max_retries is None else max_retries
        last_result: Optional[AgentPayload] = None
        ladder = context_ladder or ["full"]

        for attempt in range(retries + 1):
            compaction_level = ladder[min(attempt, len(ladder) - 1)]
            effective_context = context_factory(compaction_level) if context_factory else context
            result = await self._execute_agent(
                agent_name,
                task,
                effective_context,
                timeout_override=timeout_override,
            )
            last_result = result

            if result.status != "error":
                # Очищаем retry-контекст при успехе
                effective_context.pop("_retry_attempt", None)
                return result

            if attempt < retries:
                self._logger.warning(
                    f"🔁 Retrying {agent_name} (attempt {attempt + 2}/{retries + 1}): "
                    f"{result.error}"
                )
                if on_retry:
                    try:
                        on_retry(attempt + 2, result.error or "unknown_error", compaction_level)
                    except Exception:
                        pass
                # FIX: Инжектируем ошибку в context, чтобы агент видел причину провала
                # и мог скорректировать генерацию (например, codex исправит SyntaxError).
                # Используем ключи previous_error/error_retry, которые codex уже читает.
                effective_context["previous_error"] = result.error
                effective_context["error_retry"] = True
                effective_context["_retry_attempt"] = attempt + 2
                # Если агент вернул code_blocks — сохраняем неудачный код
                if result.code_blocks:
                    last_code = result.code_blocks[-1]
                    code_text = last_code.code if hasattr(last_code, "code") else (last_code.get("code", "") if isinstance(last_code, dict) else "")
                    if code_text:
                        effective_context["previous_code"] = code_text
            else:
                self._logger.warning(
                    f"❌ All retries exhausted for {agent_name}: {result.error}"
                )
                # Очищаем retry-контекст
                effective_context.pop("_retry_attempt", None)

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
        if not self.gigachat and not self.llm_router:
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

            user_id = pipeline_context.get("user_id")
            if self.llm_router and user_id:
                uid = UUID(str(user_id)) if isinstance(user_id, str) else user_id
                try:
                    response = await self.llm_router.chat_completion(
                        user_id=uid,
                        params=LLMCallParams(
                            messages=[LLMMessage(role="user", content=prompt)],
                            temperature=0.3,
                            max_tokens=300,
                        ),
                        agent_key="planner",
                    )
                except RuntimeError:
                    self._logger.debug("LLM not configured for replan decision")
                    return {"replan": False}
            elif self.gigachat:
                response = await self.gigachat.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300,
                )
            else:
                self._logger.debug("No LLM available for replan decision")
                return {"replan": False}

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self._logger.debug(f"Replan analysis failed: {e}")

        return {"replan": False}

    @staticmethod
    def _is_step_result_suboptimal(agent_name: str, step_payload: AgentPayload) -> Optional[str]:
        """
        Определяет «мягкий» провал: статус success, но результат бесполезен.
        Возвращает причину для revise_remaining или None.
        """
        if step_payload.status != "success":
            return None
        if agent_name == "structurizer":
            tables = getattr(step_payload, "tables", None) or []
            if len(tables) == 0:
                nar = getattr(step_payload, "narrative", None)
                text = (nar.text if hasattr(nar, "text") else (nar.get("text", "") if isinstance(nar, dict) else "")) or ""
                if "error" in text.lower() or "parse error" in text.lower() or "json" in text.lower():
                    return "Structurizer вернул пустые таблицы (ошибка парсинга в narrative)"
                return "Structurizer вернул пустые таблицы"
        if agent_name == "discovery":
            sources = getattr(step_payload, "sources", None) or []
            if len(sources) == 0:
                return "Discovery не нашёл источников"
        return None

    @staticmethod
    def _should_revise_remaining(
        agent_name: str,
        step_payload: AgentPayload,
        suboptimal_reason: Optional[str],
        steps_executed: int,
        *,
        pipeline_context: Optional[Dict[str, Any]] = None,
        remaining_steps: Optional[List[Dict[str, Any]]] = None,
        completed_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Критерии вызова revise_remaining (см. docs/PLANNING_DECOMPOSITION_STRATEGY.md).
        Вызываем не после каждого шага, а при ошибке, suboptimal или после analyst.
        """
        if step_payload.status == "error":
            return True
        if suboptimal_reason:
            return True
        if agent_name == "analyst":
            ctx = pipeline_context or {}
            rem = remaining_steps or []
            comp = completed_steps or []
            is_widget = ctx.get("mode") == "widget" or ctx.get("controller") == "widget"
            is_transformation = (
                ctx.get("mode") == "transformation"
                or ctx.get("controller") == "transformation"
            )
            # Виджет / трансформация: analyst → codex → … Revise после каждого analyst
            # при «хвосте только analyst» ломает план (дубли KPI / лишние LLM).
            if step_payload.status == "success" and (is_widget or is_transformation):
                rem_agents = {s.get("agent") for s in rem if isinstance(s, dict)}
                comp_agents = {s.get("agent") for s in comp if isinstance(s, dict)}
                if is_widget and (
                    "widget_codex" in rem_agents
                    and "research" not in comp_agents
                    and "discovery" not in comp_agents
                ):
                    return False
                if is_transformation and (
                    "transform_codex" in rem_agents
                    and "research" not in comp_agents
                    and "discovery" not in comp_agents
                ):
                    return False
                if rem and all(
                    (s.get("agent") == "analyst") for s in rem if isinstance(s, dict)
                ):
                    return False
            return True
        return False

    @staticmethod
    def _user_expects_table_or_report(user_request: str) -> bool:
        """Проверяет, ожидает ли пользователь таблицу или итоговый вывод (для защиты revise_remaining)."""
        if not user_request or not isinstance(user_request, str):
            return False
        req_lower = user_request.lower()
        return (
            "таблиц" in req_lower
            or "вывод" in req_lower
            or "сравни" in req_lower
            or "сравнен" in req_lower
            or "итог" in req_lower
            or "отчет" in req_lower
            or "отчёт" in req_lower
        )

    @staticmethod
    def _is_simple_assistant_qa(pipeline_context: Dict[str, Any]) -> bool:
        """
        Heuristic for short factual/analytical Q&A in assistant mode.
        In this mode we avoid expensive expand/revise loops.
        """
        if (pipeline_context.get("controller") or "") != "ai_assistant":
            return False
        if (pipeline_context.get("mode") or "") not in ("assistant", ""):
            return False
        if not pipeline_context.get("input_data_preview"):
            return False

        req = str(pipeline_context.get("original_user_request") or pipeline_context.get("user_request") or "").strip().lower()
        if not req:
            return False

        heavy_kw = (
            "трансформ", "transform", "код", "code", "python", "виджет", "widget",
            "график", "chart", "визуализ", "выгрузи", "export", "файл", "csv", "json",
            "исслед", "research", "discovery", "структур", "structur", "extract",
        )
        if any(k in req for k in heavy_kw):
            return False

        # Short single-turn business questions are typical fast-path candidates.
        return len(req) <= 220

    @staticmethod
    def _should_skip_structurizer_for_assistant(
        pipeline_context: Dict[str, Any],
        task_data: Dict[str, Any],
    ) -> bool:
        """Skip structurizer when assistant already has structured input preview."""
        if not Orchestrator._is_simple_assistant_qa(pipeline_context):
            return False
        if not pipeline_context.get("input_data_preview"):
            return False

        # Allow structurizer only if explicitly requested in task.
        text = (
            str(task_data.get("type", "")) + " " + str(task_data.get("description", ""))
        ).lower()
        explicit_structurizer_need = any(
            kw in text for kw in ("force_structurizer", "parse raw", "raw html", "raw markdown")
        )
        return not explicit_structurizer_need

    @staticmethod
    def _serialize_results_for_planner(
        agent_results: List[Dict[str, Any]],
        max_items: int = 20,
        include_last_narrative: bool = True,
        max_narrative_len: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Сжатое представление agent_results для Planner (revise_remaining, replan)."""
        serialized = []
        for r in agent_results[-max_items:] if len(agent_results) > max_items else agent_results:
            if not isinstance(r, dict):
                continue
            entry = {
                "status": r.get("status"),
                "agent": r.get("agent"),
                "findings_count": len(r.get("findings", [])),
                "tables_count": len(r.get("tables", [])),
                "code_blocks_count": len(r.get("code_blocks", [])),
                "sources_count": len(r.get("sources", [])),
                "has_narrative": r.get("narrative") is not None,
            }
            if include_last_narrative and serialized and r.get("agent") == "analyst":
                nar = r.get("narrative")
                if isinstance(nar, dict) and nar.get("text"):
                    entry["narrative_preview"] = nar["text"][:max_narrative_len]
                elif isinstance(nar, str):
                    entry["narrative_preview"] = nar[:max_narrative_len]
            serialized.append(entry)
        return serialized

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
            serialized_results = self._serialize_results_for_planner(
                pipeline_context.get("agent_results", []),
                max_items=30,
                include_last_narrative=True,
            )

            # Извлекаем suggested_steps из extra_context если есть
            suggested_steps = (extra_context or {}).get("suggested_steps", [])
            validation_issues = (extra_context or {}).get("validation_issues", [])

            replan_task = {
                "type": "replan",
                "original_plan": current_plan,
                "current_results": serialized_results,
                "reason": (extra_context or {}).get("last_error", "Adaptive replanning"),
                "failed_step": (extra_context or {}).get("failed_agent"),
                "suggested_steps": suggested_steps,
                "validation_issues": validation_issues,
            }
            runtime_options_map = pipeline_context.get("_agent_runtime_options_map")
            planner_runtime_options = (
                runtime_options_map.get("planner")
                if isinstance(runtime_options_map, dict)
                else None
            )
            planner_policy = resolve_execution_policy(
                "planner",
                "replan",
                runtime_options=planner_runtime_options,
            )
            initial_compaction = (
                planner_policy.context_ladder[0] if planner_policy.context_ladder else "full"
            )
            replan_context = select_context_for_step(
                "planner",
                pipeline_context,
                task_type="replan",
                compaction_level=initial_compaction,
                runtime_options=planner_runtime_options,
            )
            replan_payload = await self._execute_with_retry(
                "planner",
                replan_task,
                replan_context,
                max_retries=planner_policy.max_retries,
                timeout_override=planner_policy.timeout_sec,
                context_ladder=planner_policy.context_ladder,
                context_factory=lambda lvl: select_context_for_step(
                    "planner",
                    pipeline_context,
                    task_type="replan",
                    compaction_level=lvl,
                    runtime_options=planner_runtime_options,
                ),
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
        # Агрегируем только результаты текущего плана
        all_results = pipeline_context.get("agent_results", [])
        current_results = all_results[current_plan_results_start:]
        current_results_copy = copy.deepcopy(current_results)

        # Валидатор ожидает результаты по агентам (discovery, research, reporter, ...),
        # чтобы _summarize включал narrative каждого агента. merge_from не копирует narrative,
        # поэтому один merged payload приводит к тому, что LLM не видит текст ответа.
        # Не используем «последний ключ agent побеждает»: при нескольких analyst в срезе
        # берём запись с max len(findings). См. aggregate_agent_results_for_validation.
        aggregated_result = aggregate_agent_results_for_validation(current_results)

        if execution_context:
            validation_ctx = {**pipeline_context, **execution_context}
        else:
            validation_ctx = pipeline_context
        runtime_options_map = pipeline_context.get("_agent_runtime_options_map")
        validator_runtime_options = (
            runtime_options_map.get("validator")
            if isinstance(runtime_options_map, dict)
            else None
        )
        validation_ctx = select_context_for_step(
            "validator",
            validation_ctx,
            task_type="validate",
            compaction_level="full",
            runtime_options=validator_runtime_options,
        )

        # IMPORTANT:
        # For assistant flows user_request may be enriched with board context
        # ("... N widgets ..."), which can bias expected-outcome detection.
        # Prefer original raw user prompt for Validator intent classification.
        validation_user_request = (
            pipeline_context.get("original_user_request")
            if isinstance(pipeline_context.get("original_user_request"), str)
            else user_request
        )

        validator_policy = resolve_execution_policy(
            "validator",
            "validate",
            runtime_options=validator_runtime_options,
        )
        validation_task = {
            "type": "validate",
            "user_request": validation_user_request,
            "aggregated_result": aggregated_result,
            "validation_agent_results_slice": current_results_copy,
        }
        return await self._execute_with_retry(
            "validator",
            task=validation_task,
            context=validation_ctx,
            max_retries=validator_policy.max_retries,
            timeout_override=validator_policy.timeout_sec,
            context_ladder=validator_policy.context_ladder,
            context_factory=lambda lvl: select_context_for_step(
                "validator",
                validation_ctx,
                task_type="validate",
                compaction_level=lvl,
                runtime_options=validator_runtime_options,
            ),
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


