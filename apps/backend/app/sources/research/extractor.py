"""Research Source Extractor - AI deep research via multi-agent.

Делегирует вызов ResearchController (Orchestrator: discovery → research
→ structurizer → analyst → reporter) и маппит результат в ExtractionResult.
См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
"""
import time
from typing import Any
from uuid import uuid4

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


def _effective_initial_prompt(config: dict[str, Any]) -> str:
    """Текст запроса: initial_prompt или первая user-реплика из conversation_history."""
    raw = (config.get("initial_prompt") or "").strip()
    if raw:
        return raw
    history = config.get("conversation_history")
    if isinstance(history, list):
        for msg in history:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def _controller_tables_to_table_data(tables: list[dict[str, Any]]) -> list[TableData]:
    """Конвертирует tables из ControllerResult (dict) в list[TableData]."""
    out: list[TableData] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        out.append(TableData(
            id=str(t.get("id", uuid4())),
            name=t.get("name", "table"),
            columns=t.get("columns", []),
            rows=t.get("rows", []),
        ))
    return out


class ResearchSource(BaseSource):
    """Поиск с ИИ: обработчик источника через мультиагентную систему (ResearchController)."""

    source_type = "research"
    display_name = "Поиск с ИИ"
    icon = "🔍"
    description = "Поиск данных через AI-агентов"

    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate research source config."""
        errors = []
        if not _effective_initial_prompt(config):
            errors.append("Необходимо указать запрос для исследования")
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()

    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs: Any,
    ) -> ExtractionResult:
        """Execute deep research via ResearchController (Orchestrator)."""
        start_time = time.time()
        try:
            initial_prompt = _effective_initial_prompt(config)
            if not initial_prompt:
                return ExtractionResult.failure(
                    "Не указан запрос для исследования "
                    "(нужен initial_prompt или хотя бы одна реплика пользователя в conversation_history)"
                )
            orchestrator = kwargs.get("orchestrator") or kwargs.get("multi_agent_engine")

            if orchestrator:
                return await self._run_research(orchestrator, initial_prompt, config)
            return ExtractionResult(
                success=True,
                text=f"Исследование по запросу: '{initial_prompt}'\n\n"
                     "Мультиагентная система не доступна. "
                     "Настройте GigaChat API и перезапустите backend.",
                tables=[],
                extraction_time_ms=int((time.time() - start_time) * 1000),
                metadata={"prompt": initial_prompt, "multi_agent_available": False},
            )
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка исследования: {str(e)}")

    async def _run_research(
        self,
        orchestrator: Any,
        prompt: str,
        config: dict[str, Any],
    ) -> ExtractionResult:
        """Запуск исследования через ResearchController; маппинг в ExtractionResult."""
        start_time = time.time()
        try:
            from app.services.controllers import ResearchController

            controller = ResearchController(orchestrator)
            ctx: dict[str, Any] = {}
            if config.get("conversation_history"):
                ctx["chat_history"] = config["conversation_history"]

            result = await controller.process_request(prompt, context=ctx)

            if result.status == "error":
                return ExtractionResult.failure(result.error or "Unknown error")

            tables_data = _controller_tables_to_table_data(result.tables)
            return ExtractionResult(
                success=True,
                text=result.narrative or "",
                tables=tables_data,
                extraction_time_ms=result.execution_time_ms,
                metadata={"sources": result.sources},
            )
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка мультиагента: {str(e)}")
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for research dialog."""
        return {
            "type": "object",
            "properties": {
                "initial_prompt": {
                    "type": "string",
                    "format": "textarea",
                    "title": "Запрос для исследования",
                    "description": "Опишите, какие данные нужно найти",
                },
            },
            "required": ["initial_prompt"],
        }
