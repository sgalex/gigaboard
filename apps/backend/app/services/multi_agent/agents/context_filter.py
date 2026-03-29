"""ContextFilterAgent - LLM-based filter expression builder.

Receives a text filtering task and available table schemas, then returns
a strict JSON declaration of FilterExpression for backend application.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService

logger = logging.getLogger(__name__)


CONTEXT_FILTER_SYSTEM_PROMPT = """
Вы — ContextFilterAgent в системе GigaBoard Multi-Agent.

ЗАДАЧА:
1) По текстовому запросу фильтрации определить выражение фильтра (FilterExpression).
2) Вернуть ТОЛЬКО валидный JSON по контракту ниже.

КОНТРАКТ ОТВЕТА (строго JSON-объект):
{
  "filter_expression": <FilterExpression | null>,
  "required_tables": ["table_a", "table_b"],
  "allow_auto_filter": true,
  "reason": "краткое объяснение выбора фильтра"
}

ГДЕ FilterExpression:
- condition:
  {"type":"condition","dim":"brand","op":"contains","value":"Philips"}
- group:
  {"type":"and","conditions":[ ... ]}
  {"type":"or","conditions":[ ... ]}

ПОДДЕРЖИВАЕМЫЕ op:
"==", "!=", ">", "<", ">=", "<=", "in", "not_in", "between", "contains", "starts_with"

ПРАВИЛА:
- Возвращай ТОЛЬКО JSON, без markdown и без текста до/после.
- Используй ТОЛЬКО измерения/колонки, которые присутствуют в переданном INPUT DATA SCHEMA.
- Если фильтр невозможно уверенно построить — верни "filter_expression": null и объясни в "reason".
- Для бренд/товар/категория запросов предпочитай op="contains" для устойчивости к вариациям текста.
- required_tables — краткий список таблиц, которые приоритетно оставить для анализа (по возможности).
"""


class ContextFilterAgent(BaseAgent):
    """LLM agent that builds FilterExpression JSON from text tasks."""

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="context_filter",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router

    def _get_default_system_prompt(self) -> str:
        return CONTEXT_FILTER_SYSTEM_PROMPT

    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        try:
            context = context or {}
            user_request = (
                task.get("user_request")
                or context.get("original_user_request")
                or context.get("user_request")
                or ""
            ).strip()
            description = str(task.get("description", "")).strip()

            input_preview = context.get("input_data_preview") or {}
            catalog_preview = context.get("catalog_data_preview") or {}

            schema_text = self._schema_for_prompt(input_preview, catalog_preview)

            prompt = (
                "Сформируй декларацию фильтра для следующей задачи.\n\n"
                f"USER_REQUEST:\n{user_request or '—'}\n\n"
                f"TASK_DESCRIPTION:\n{description or '—'}\n\n"
                f"INPUT DATA SCHEMA:\n{schema_text}\n\n"
                "Верни JSON строго по контракту system prompt."
            )
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]

            def _parse_response(resp: Any) -> Dict[str, Any]:
                text = resp if isinstance(resp, str) else str(resp)
                m = re.search(r"\{[\s\S]*\}", text)
                if not m:
                    raise ValueError("No JSON object in ContextFilterAgent response")
                data = json.loads(m.group())
                if not isinstance(data, dict):
                    raise ValueError("ContextFilterAgent response must be JSON object")
                # Soft validation of expected keys
                if "allow_auto_filter" not in data:
                    data["allow_auto_filter"] = True
                if "required_tables" not in data or not isinstance(data.get("required_tables"), list):
                    data["required_tables"] = []
                if "reason" not in data:
                    data["reason"] = ""
                if "filter_expression" in data and data["filter_expression"] is not None:
                    cls = data["filter_expression"]
                    if not isinstance(cls, dict) or "type" not in cls:
                        raise ValueError("filter_expression must be object with 'type'")
                return data

            parsed = await self._call_llm_with_json_retry(
                messages=messages,
                parse_fn=_parse_response,
                context=context,
                temperature=0.2,
                max_tokens=1500,
            )

            filter_expression = parsed.get("filter_expression")
            required_tables = parsed.get("required_tables", [])
            allow_auto_filter = bool(parsed.get("allow_auto_filter", True))
            reason = str(parsed.get("reason", ""))
            self.logger.info(
                "🔎 ContextFilterAgent parsed JSON: %s",
                json.dumps(
                    {
                        "filter_expression": filter_expression,
                        "required_tables": required_tables,
                        "allow_auto_filter": allow_auto_filter,
                        "reason": reason,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

            return self._success_payload(
                narrative_text=(
                    "LLM filter declaration generated"
                    if filter_expression
                    else "LLM filter declaration not generated"
                ),
                metadata={
                    "filter_expression": filter_expression,
                    "required_tables": required_tables,
                    "allow_auto_filter": allow_auto_filter,
                    "reason": reason,
                    "generated_by": "context_filter_llm",
                },
            )
        except Exception as e:
            self.logger.error("ContextFilterAgent error: %s", e, exc_info=True)
            return self._error_payload(str(e))

    @staticmethod
    def _schema_for_prompt(
        input_preview: Dict[str, Any],
        catalog_preview: Dict[str, Any],
    ) -> str:
        """Compact schema serialization for prompt."""
        lines: List[str] = []

        def _append_from(preview: Dict[str, Any], title: str) -> None:
            if not isinstance(preview, dict) or not preview:
                return
            lines.append(f"{title}:")
            for key, meta in list(preview.items())[:40]:
                if not isinstance(meta, dict):
                    continue
                table_name = str(meta.get("table_name") or key)
                cols = meta.get("columns") or []
                col_names: List[str] = []
                for c in cols:
                    if isinstance(c, dict):
                        n = c.get("name")
                        if n:
                            col_names.append(str(n))
                    elif c:
                        col_names.append(str(c))
                lines.append(f"- {table_name}: columns={col_names[:30]}")

        _append_from(input_preview, "working_set_tables")
        _append_from(catalog_preview, "catalog_tables")

        if not lines:
            return "No schema available"
        return "\n".join(lines)

