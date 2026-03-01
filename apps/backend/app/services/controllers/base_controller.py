"""
BaseController — базовый класс для Satellite Controllers (V2).

Инкапсулирует общую логику:
- Вызов Orchestrator.process_request()
- Формирование ControllerResult
- Обработка ошибок
- Логирование

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.1
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..multi_agent.schemas.agent_payload import (
    AgentPayload,
    CodeBlock,
    Finding,
    Narrative,
    PayloadContentTable,
    ValidationResult,
)


@dataclass
class ControllerResult:
    """Универсальный результат контроллера для route-handler'а.

    Все контроллеры возвращают этот объект. Route-handler конвертирует
    его в HTTP ответ (JSON). Поля заполняются селективно — контроллер
    решает, что именно нужно вернуть.
    """

    status: str = "success"  # "success" | "error"
    error: Optional[str] = None

    # ── Narrative / text ────────────────────────────────────────────
    narrative: Optional[str] = None
    narrative_format: str = "markdown"  # "markdown" | "html" | "plain"

    # ── Code (transformation / widget) ───────────────────────────────
    code: Optional[str] = None
    code_language: Optional[str] = None  # "python" | "html"
    code_description: Optional[str] = None

    # ── Preview data (after execution) ──────────────────────────────
    preview_data: Optional[Dict[str, Any]] = None

    # ── Widget-specific ─────────────────────────────────────────────
    widget_name: Optional[str] = None
    widget_type: Optional[str] = None
    widget_code: Optional[str] = None  # Full HTML for widget

    # ── Suggestions ─────────────────────────────────────────────────
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    # ── Validation ──────────────────────────────────────────────────
    validation: Optional[Dict[str, Any]] = None

    # ── Meta ────────────────────────────────────────────────────────
    session_id: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None  # "transformation" | "discussion" | "widget"
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в dict для JSON-сериализации (пропускает None)."""
        d: Dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if v is not None and v != [] and v != {}:
                d[k] = v
        d["status"] = self.status  # always include
        return d


class BaseController:
    """
    Базовый класс Satellite Controller (V2).

    Контроллер:
    1. Получает запрос от route-handler'а (user_message + context)
    2. Вызывает ``orchestrator.process_request()``
    3. Извлекает нужные секции из результата (code_blocks, narrative, etc.)
    4. Возвращает ``ControllerResult``

    Наследники реализуют ``process_request()`` и helpers.
    """

    controller_name: str = "base"

    def __init__(self, orchestrator: Any):
        """
        Args:
            orchestrator: Инициализированный Orchestrator V2 instance.
        """
        self.orchestrator = orchestrator
        self.logger = logging.getLogger(
            f"controller.{self.controller_name}"
        )

    # ── Main interface (override in subclasses) ──────────────────────
    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Обрабатывает пользовательский запрос.

        Args:
            user_message: Текст запроса
            context: Контекст (board_id, user_id, input_data, chat_history, etc.)

        Returns:
            ControllerResult с данными для route-handler'а.
        """
        raise NotImplementedError("Subclasses must implement process_request()")

    # ══════════════════════════════════════════════════════════════════
    #  Helpers: вызов Orchestrator
    # ══════════════════════════════════════════════════════════════════

    async def _call_orchestrator(
        self,
        user_request: str,
        board_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        skip_validation: bool = False,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Вызывает Orchestrator.process_request() с обработкой ошибок."""
        try:
            result = await self.orchestrator.process_request(
                user_request=user_request,
                board_id=board_id,
                user_id=user_id,
                session_id=session_id,
                context=context,
                skip_validation=skip_validation,
                execution_context=execution_context,
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Orchestrator call failed: {e}", exc_info=True
            )
            return {"status": "error", "error": str(e)}

    def _error_result(
        self,
        message: str,
        execution_time_ms: int = 0,
    ) -> ControllerResult:
        """Формирует ControllerResult с ошибкой."""
        return ControllerResult(
            status="error",
            error=message,
            execution_time_ms=execution_time_ms,
        )

    # ══════════════════════════════════════════════════════════════════
    #  Helpers: извлечение секций из AgentPayload / Orchestrator result
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_code_blocks(
        results: Dict[str, Any],
        purpose: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает code_blocks из результатов агентов.

        Args:
            results: dict[agent_name → serialized AgentPayload]
            purpose: Фильтр по purpose ("transformation" | "widget")

        Returns:
            Список code_block dicts.
        """
        blocks: List[Dict[str, Any]] = []
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            for cb in payload.get("code_blocks", []):
                if isinstance(cb, dict):
                    if purpose is None or cb.get("purpose") == purpose:
                        blocks.append(cb)
        return blocks

    @staticmethod
    def _extract_narrative(results: Dict[str, Any]) -> Optional[str]:
        """Извлекает последний (самый поздний) narrative из результатов.

        Fallback: если ни один агент не оставил narrative.text, но есть
        findings — строит краткий текст из них, чтобы пользователь
        получил осмысленный ответ вместо заглушки.
        """
        text: Optional[str] = None
        all_findings: list[Dict[str, Any]] = []
        seen_finding_texts: set[str] = set()
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            nar = payload.get("narrative")
            if isinstance(nar, dict) and nar.get("text"):
                text = nar["text"]
            elif isinstance(nar, str) and nar:
                text = nar
            # Collect findings for fallback (dedup by text)
            for f in payload.get("findings", []):
                if isinstance(f, dict) and f.get("text"):
                    ft = f["text"]
                    if ft not in seen_finding_texts:
                        seen_finding_texts.add(ft)
                        all_findings.append(f)

        # Fallback: build narrative from findings if no agent provided one
        if not text and all_findings:
            parts = [f"- {f['text']}" for f in all_findings[:10]]
            text = "## Результаты анализа\n\n" + "\n".join(parts)

        return text

    @staticmethod
    def _extract_findings(
        results: Dict[str, Any],
        finding_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Извлекает findings из результатов агентов.

        При replan один агент может выполняться несколько раз
        (analyst, analyst_2, ...). Дедуплицируем по тексту finding.
        """
        findings: List[Dict[str, Any]] = []
        seen_texts: set[str] = set()
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            for f in payload.get("findings", []):
                if isinstance(f, dict):
                    if finding_type is None or f.get("type") == finding_type:
                        text = f.get("text", "")
                        if text and text not in seen_texts:
                            seen_texts.add(text)
                            findings.append(f)
                        elif not text:
                            findings.append(f)
        return findings

    @staticmethod
    def _extract_tables(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлекает tables из результатов агентов.

        Дедуплицирует по имени таблицы (при replan один агент
        может выполняться несколько раз: structurizer, structurizer_2, ...).
        """
        tables: List[Dict[str, Any]] = []
        seen_names: set[str] = set()
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            for t in payload.get("tables", []):
                if isinstance(t, dict):
                    name = t.get("name", "")
                    if name and name in seen_names:
                        continue  # дубль таблицы
                    if name:
                        seen_names.add(name)
                    tables.append(t)
        return tables

    @staticmethod
    def _extract_validation(
        results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Извлекает validation из результатов (от ValidatorAgent)."""
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            v = payload.get("validation")
            if isinstance(v, dict):
                return v
        return None
