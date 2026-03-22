"""
Widget Codex Agent — генерация HTML/CSS/JS виджетов (визуализаций).

Специализированный агент для создания интерактивных data-виджетов
на основе ECharts и других библиотек визуализации.

Отделён от TransformCodexAgent (трансформации Python/pandas), чтобы сосредоточить
специфичные знания о визуализациях в одном месте.

V2: Возвращает AgentPayload(code_blocks=[CodeBlock(purpose="widget")]).
    См. docs/MULTI_AGENT_V2_CONCEPT.md, docs/ECHARTS_WIDGET_REFERENCE.md
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import CodeBlock, Narrative, ToolRequest, AgentPayload
from app.services.gigachat_service import GigaChatService

logger = logging.getLogger(__name__)


class WidgetCodexAgent(BaseAgent):
    """
    Widget Codex Agent — генератор виджетов (V2).

    Создаёт standalone HTML/CSS/JS виджеты для WidgetNode:
      • ECharts графики (предпочтительно)
      • Chart.js, Plotly, D3 визуализации
      • Метрики, таблицы, custom-виджеты

    Возвращает AgentPayload:
      code_blocks  — [CodeBlock(language="html", purpose="widget")]
      narrative    — краткое описание виджета
      metadata     — {"widget_type": ..., "widget_name": ...}
    """

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="widget_codex",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router

    # ── default prompt ───────────────────────────────────────────────
    def _get_default_system_prompt(self) -> str:
        from app.services.multi_agent.tabular_tool_contract import (
            TOOL_MODE_AGENT_SYSTEM_APPENDIX_RU,
        )

        return (
            "You are WidgetCodexAgent — a data visualization specialist in GigaBoard.\n"
            "You generate interactive HTML/CSS/JS widgets using ECharts and other libraries.\n"
            "Always return valid JSON.\n"
            + TOOL_MODE_AGENT_SYSTEM_APPENDIX_RU
        )

    # ── main entry ───────────────────────────────────────────────────
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Генерирует HTML/CSS/JS виджет.
        V2: Возвращает AgentPayload(code_blocks=[...], narrative=...).
        """
        try:
            return await self._generate_widget(task, context)
        except Exception as e:
            self.logger.error(f"WidgetCodexAgent error: {e}", exc_info=True)
            return self._error_payload(str(e))

    # ══════════════════════════════════════════════════════════════════
    #  WIDGET generation
    # ══════════════════════════════════════════════════════════════════
    async def _generate_widget(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        description = task.get("description", "")
        if not description:
            return self._error_payload("description required for widget")

        # Изменение #2: agent_results — list (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
        agent_results = (context or {}).get("agent_results", [])
        data_summary = self._build_data_summary_for_widget(task, agent_results, context)

        # Контекст пользовательского запроса
        user_request = (context or {}).get("user_request", "")
        analyst_context = self._extract_analyst_context(agent_results)

        # Existing widget code for iterative refinement
        existing_widget_code = (context or {}).get("existing_widget_code")
        chat_history = (context or {}).get("chat_history", [])
        tools_enabled = bool((context or {}).get("tools_enabled")) if context else False
        force_tool_data_access = bool(
            (context or {}).get("force_tool_data_access")
        ) if context else False
        tool_results = (context or {}).get("tool_results", []) if context else []
        tool_request_cache_digest_lines: Optional[List[str]] = None
        if context and isinstance(context.get("tool_request_cache_digest_lines"), list):
            tool_request_cache_digest_lines = context["tool_request_cache_digest_lines"]
        content_node_id = str((context or {}).get("content_node_id") or "").strip()
        selected_node_ids = []
        if context and isinstance(context.get("selected_node_ids"), list):
            selected_node_ids = [
                str(item).strip()
                for item in context.get("selected_node_ids", [])
                if str(item).strip()
            ]
        if not selected_node_ids and context and isinstance(context.get("content_node_ids"), list):
            selected_node_ids = [
                str(item).strip()
                for item in context.get("content_node_ids", [])
                if str(item).strip()
            ]
        if not selected_node_ids and context and isinstance(context.get("contentNodeIds"), list):
            selected_node_ids = [
                str(item).strip()
                for item in context.get("contentNodeIds", [])
                if str(item).strip()
            ]
        if not content_node_id and selected_node_ids:
            content_node_id = selected_node_ids[0]
        node_ids_for_tools: List[str] = []
        for _id in [content_node_id, *selected_node_ids]:
            _text = str(_id or "").strip()
            if _text and _text not in node_ids_for_tools:
                node_ids_for_tools.append(_text)
        keep_tabular = bool((context or {}).get("keep_tabular_context_in_prompt"))
        if (
            tools_enabled
            and force_tool_data_access
            and not keep_tabular
            and not tool_results
            and node_ids_for_tools
        ):
            return AgentPayload.partial(
                agent=self.agent_name,
                tool_requests=[
                    ToolRequest(
                        tool_name="readTableListFromContentNodes",
                        arguments={"nodeIds": node_ids_for_tools},
                        reason="force_tool_data_access: table context is removed from prompt",
                    )
                ],
                narrative=Narrative(
                    text="Запрашиваю таблицы через инструменты перед генерацией виджета."
                ),
                metadata={"tool_mode": "forced_bootstrap"},
            )

        self.logger.info(f"🎨 WidgetCodex: {description[:100]}…")
        if user_request:
            self.logger.info(f"📝 WidgetCodex: user_request='{user_request[:120]}…'")
        self.logger.info(
            f"🔄 WidgetCodex: existing_widget_code={'present (' + str(len(existing_widget_code)) + ' chars)' if existing_widget_code else 'None'}"
        )

        messages = self._build_messages(
            description=description,
            data_summary=data_summary,
            user_request=user_request,
            analyst_context=analyst_context,
            existing_widget_code=existing_widget_code,
            chat_history=chat_history,
            tools_enabled=tools_enabled,
            tool_results=tool_results,
            tool_request_cache_digest_lines=tool_request_cache_digest_lines,
        )

        total_chars = sum(len(m.get("content", "")) for m in messages)
        self.logger.info(
            f"📨 WidgetCodex prompt to LLM ({total_chars} chars, {len(messages)} messages)"
        )

        # ── LLM call with retry on truncation ──
        MAX_TRUNCATION_RETRIES = 1
        parsed = {}
        response = ""
        first_parsed = {}  # Keep metadata from first attempt for retry fallback

        for attempt in range(MAX_TRUNCATION_RETRIES + 1):
            response = await self._call_llm(
                messages, context=context, temperature=0.3, max_tokens=16384
            )

            self.logger.info(
                f"📥 WidgetCodex raw response attempt {attempt + 1} "
                f"({len(response)} chars): {response[:300]}…"
            )

            # Try structured format first, then JSON fallback
            parsed = self._parse_structured_response(response) or {}
            if not parsed:
                parsed = self._parse_json_from_llm(response)
            tool_requests = self._extract_tool_requests(parsed)
            if tool_requests:
                return AgentPayload.partial(
                    agent=self.agent_name,
                    tool_requests=tool_requests,
                    narrative=Narrative(
                        text="Для генерации виджета требуется догрузка табличных данных."
                    ),
                    metadata={"tool_mode": "request"},
                )

            # On retry: merge metadata from first attempt if missing
            if attempt > 0 and first_parsed:
                for key in ("widget_name", "widget_type", "description"):
                    if not parsed.get(key) and first_parsed.get(key):
                        parsed[key] = first_parsed[key]
                # Keep styles/scripts from first attempt if retry only has render_body
                for key in ("styles", "scripts"):
                    if not parsed.get(key) and first_parsed.get(key):
                        parsed[key] = first_parsed[key]

            render_body_candidate = parsed.get("render_body", "")
            if isinstance(render_body_candidate, str):
                render_body_candidate = self._unescape_html_code(render_body_candidate)

            if render_body_candidate and self._is_truncated_code(render_body_candidate):
                self.logger.warning(
                    f"⚠️ WidgetCodex: render_body appears TRUNCATED "
                    f"({len(render_body_candidate)} chars, ends with: "
                    f"...{render_body_candidate[-60:]!r})"
                )
                if attempt < MAX_TRUNCATION_RETRIES:
                    # Save first attempt metadata for merging later
                    if not first_parsed:
                        first_parsed = dict(parsed)
                    # Tell LLM about truncation and ask for full code
                    tail = render_body_candidate[-80:] if len(render_body_candidate) > 80 else render_body_candidate
                    retry_msg = (
                        f"⚠️ Твой render_body обрезан на полуслове! "
                        f"Код заканчивается на:\n...{tail}\n\n"
                        f"Пожалуйста, сгенерируй ПОЛНЫЙ render_body заново.\n"
                        f"Верни ТОЛЬКО секцию ===RENDER_BODY=== с ПОЛНЫМ JS-кодом.\n"
                        f"Код должен быть ЗАВЕРШЁННЫМ — все скобки закрыты, "
                        f"все строки завершены."
                    )
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": retry_msg})
                    self.logger.info(
                        f"🔄 WidgetCodex: retrying due to truncation "
                        f"(attempt {attempt + 2}/{MAX_TRUNCATION_RETRIES + 1})"
                    )
                    continue
                else:
                    self.logger.warning(
                        f"⚠️ WidgetCodex: render_body still truncated after "
                        f"{MAX_TRUNCATION_RETRIES + 1} attempts, proceeding anyway"
                    )
            break  # No truncation or exhausted retries

        self.logger.info(f"📥 Parsed keys: {list(parsed.keys())}")
        self.logger.info(
            f"📥 Parsed widget_name={parsed.get('widget_name')!r}, "
            f"widget_type={parsed.get('widget_type')!r}, "
            f"description={str(parsed.get('description', ''))[:80]!r}"
        )

        widget_name = parsed.get("widget_name") or ""
        widget_type = parsed.get("widget_type", "custom")

        # Smart fallback: if LLM didn't generate a meaningful widget_name,
        # derive a short name from user_request or task description.
        if not widget_name or widget_name.lower() in ("widget", "chart", "visualization", "виджет", "график"):
            widget_name = self._derive_widget_name(user_request, description, data_summary)
            self.logger.info(f"📝 widget_name derived from context: '{widget_name}'")

        # Enforce short name (max ~50 chars, trim at word boundary)
        pre_sanitize = widget_name
        widget_name = self._sanitize_widget_name(widget_name)
        if widget_name != pre_sanitize:
            self.logger.info(f"✂️ widget_name sanitized: {pre_sanitize!r} → {widget_name!r}")
        self.logger.info(f"🏷️ FINAL widget_name={widget_name!r}")

        # ── Scaffold-based assembly (render_body + styles + scripts) ──
        raw_render_body = parsed.get("render_body", "")
        render_body = self._unescape_html_code(raw_render_body)
        custom_styles = parsed.get("styles", "")
        scripts = parsed.get("scripts", "")

        if render_body.strip():
            # Apply auto-fixes
            render_body = self._strip_markdown_from_code(render_body)   # ### artifacts, MD headings
            render_body = self._fix_smart_quotes(render_body)            # "smart" → "straight" quotes
            custom_styles = self._fix_smart_quotes(custom_styles)
            render_body = self._fix_async_render(render_body)            # missing async on render()
            render_body = self._fix_data_redeclaration(render_body)      # const data = ... redecl
            render_body = self._fix_undefined_col_vars(render_body)      # undefined colName vars
            render_body = self._fix_echarts_yaxis_index(render_body)     # missing dual yAxis array
            render_body = self._fix_echarts_missing_axis(render_body)    # bar/line without xAxis
            render_body = self._fix_echarts_onclick_in_series(render_body)  # onclick → .on('click') [ECharts]
            render_body = self._strip_echarts_onclick_from_chartjs(render_body)  # Chart.js ≠ .on('click')
            render_body = self._fix_formatter_multiline_strings(render_body)  # '...\\n...' not raw newline in '
            render_body = self._fix_illegal_js_string_line_terminators(render_body)  # U+2028/U+2029, \\n from JSON
            render_body = self._fix_invalid_formatter(render_body)       # ${} in formatter strings
            render_body = self._normalize_echarts_string_formatters_to_functions(render_body)
            if render_body.startswith("\ufeff"):
                render_body = render_body.lstrip("\ufeff")
            scripts = self._sanitize_scripts_section(scripts)
            scripts = self._ensure_scripts_for_libs(render_body, scripts)
            head_links = self._ensure_head_links_for_libs(
                render_body, scripts, custom_styles,
            )

            widget_code = self._assemble_widget(
                render_body, custom_styles, scripts, head_links,
            )
            widget_code = self._sanitize_srcdoc_inline_script(widget_code)

            # ── Diagnostic: dump suspicious lines after assembly ──
            issues = self._detect_js_string_issues(widget_code)
            if issues:
                self.logger.warning(
                    f"⚠️ JS string issues detected in final widget code:\n"
                    + "\n".join(f"  line {ln}: {desc}" for ln, desc in issues[:10])
                )
            self.logger.info("🧩 Widget assembled from scaffold + render_body")
        else:
            # Fallback: legacy widget_code (full HTML)
            widget_code = self._unescape_html_code(parsed.get("widget_code", ""))

            # Fallback: если widget_code пустой, попробовать извлечь HTML из raw response
            if not widget_code.strip():
                html_match = re.search(
                    r'(<!DOCTYPE\s+html>.*?</html>)', response, re.DOTALL | re.IGNORECASE
                )
                if html_match:
                    widget_code = html_match.group(1)
                    self.logger.info("📎 Extracted HTML from raw response (fallback)")
                else:
                    # Try markdown html block
                    html_block = re.search(r'```html\s*(.*?)\s*```', response, re.DOTALL)
                    if html_block:
                        widget_code = html_block.group(1)
                        self.logger.info("📎 Extracted HTML from markdown block (fallback)")
                    else:
                        # Try <html>...</html> without DOCTYPE
                        html_tag = re.search(r'(<html[^>]*>.*?</html>)', response, re.DOTALL | re.IGNORECASE)
                        if html_tag:
                            widget_code = html_tag.group(1)
                            self.logger.info("📎 Extracted <html> block from response (fallback)")

            if not widget_code.strip():
                self.logger.warning(f"⚠️ Widget code is EMPTY after all fallbacks. Response was: {response[:500]}")

            # Auto-fix: render() без async + fetchContentData → rows.forEach crash
            widget_code = self._fix_async_render(widget_code)
            self.logger.info(
                f"⚠️ Widget generated via legacy widget_code path"
                f" (code_len={len(widget_code)}, syntax_valid={bool(widget_code.strip())})"
            )

        # Widget description — distinct from name, 1-2 sentence summary
        widget_description = (parsed.get("description") or "").strip()
        if not widget_description or widget_description.lower() == widget_name.lower():
            widget_description = widget_name

        block = CodeBlock(
            code=widget_code,
            language="html",
            purpose="widget",
            syntax_valid=bool(widget_code.strip()),
            warnings=[],
            description=widget_name,
        )

        self.logger.info(f"✅ Widget generated: {widget_name} ({widget_type})")
        self.logger.info(f"   description: {widget_description[:100]}")

        return self._success_payload(
            code_blocks=[block],
            narrative_text=widget_description,
            metadata={
                "widget_type": widget_type,
                "widget_name": widget_name,
                "widget_description": widget_description,
            },
        )

    # ══════════════════════════════════════════════════════════════════
    #  Prompt builders
    # ══════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════
    #  Message building (multi-turn chat)
    # ══════════════════════════════════════════════════════════════════

    def _build_messages(
        self,
        description: str,
        data_summary: str,
        user_request: str = "",
        analyst_context: str = "",
        existing_widget_code: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        tools_enabled: bool = False,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        tool_request_cache_digest_lines: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Build LLM messages array.

        For NEW widgets: system + single user prompt.
        For ITERATIVE updates: system + multi-turn chat history (attention pattern).
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": WIDGET_SYSTEM_PROMPT},
        ]

        if existing_widget_code and chat_history:
            messages.extend(
                self._build_iterative_messages(
                    description, data_summary, user_request,
                    analyst_context, existing_widget_code, chat_history,
                    tool_results=tool_results,
                    tool_request_cache_digest_lines=tool_request_cache_digest_lines,
                )
            )
        else:
            prompt = self._build_new_widget_prompt(
                description, data_summary, user_request, analyst_context,
                tools_enabled=tools_enabled, tool_results=tool_results,
                tool_request_cache_digest_lines=tool_request_cache_digest_lines,
            )
            messages.append({"role": "user", "content": prompt})

        return messages

    def _build_iterative_messages(
        self,
        description: str,
        data_summary: str,
        user_request: str,
        analyst_context: str,
        existing_widget_code: str,
        chat_history: List[Dict[str, Any]],
        *,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        tool_request_cache_digest_lines: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Build multi-turn messages for iterative widget refinement.

        Layout (attention-optimal):
          user:      [data context] + first user request
          assistant: first AI response
          ...
          assistant: last AI response + existing render_body JSON  ← code here
          user:      current user request
        """
        import json as _json
        import re as _re

        result: List[Dict[str, str]] = []
        history = list(chat_history)

        # 1. Pop current user request (last user message)
        current_request = ""
        if history and history[-1].get("role") == "user":
            current_request = history.pop()["content"]
        else:
            # Fallback: extract from enriched user_request
            m = _re.search(r'Запрос:\s*(.+?)(?:\n|$)', user_request)
            current_request = m.group(1).strip() if m else description

        # 2. Data context preamble
        data_parts: List[str] = []
        if data_summary:
            data_parts.append(f"ДОСТУПНЫЕ ДАННЫЕ:\n{data_summary}")
        if analyst_context:
            data_parts.append(f"КОНТЕКСТ АНАЛИЗА:\n{analyst_context}")
        data_preamble = "\n\n".join(data_parts) + "\n\n" if data_parts else ""
        digest_lines = tool_request_cache_digest_lines or []
        if digest_lines:
            digest_txt = (
                "УЖЕ ВЫПОЛНЕННЫЕ ЗАПРОСЫ К ДАННЫМ (не дублируй идентичные tool_requests; "
                "данные уже получены — см. TOOL RESULTS ниже):\n"
            )
            for line in digest_lines[-25:]:
                digest_txt += f"  • {line}\n"
            data_preamble = digest_txt + "\n" + data_preamble
        if tool_results:
            rendered: List[str] = []
            for item in tool_results[-4:]:
                if not isinstance(item, dict):
                    continue
                tname = item.get("tool_name", "tool")
                if item.get("success"):
                    rendered.append(
                        f"- {tname}: {json.dumps(item.get('data', {}), ensure_ascii=False, default=str)[:2500]}"
                    )
                else:
                    rendered.append(f"- {tname}: ERROR={item.get('error', 'unknown')}")
            if rendered:
                data_preamble = (
                    "TOOL RESULTS (latest):\n" + "\n".join(rendered) + "\n\n" + data_preamble
                )

        # 3. Extract render_body from existing widget → structured block for assistant msg
        dynamic = self._extract_dynamic_parts(existing_widget_code)
        if dynamic:
            code_parts = [
                f"widget_name: {description[:60] or 'Визуализация'}",
                "widget_type: chart",
                f"description: Обновление виджета — {description[:80]}",
                "",
                "===RENDER_BODY===",
                dynamic["render_body"],
            ]
            if dynamic.get("styles", "").strip():
                code_parts.append("\n===STYLES===")
                code_parts.append(dynamic["styles"])
            if dynamic.get("scripts", "").strip():
                code_parts.append("\n===SCRIPTS===")
                code_parts.append(dynamic["scripts"])
            code_block = "\n".join(code_parts)
        else:
            # Legacy widget — pass full HTML
            code_block = f"```html\n{existing_widget_code}\n```"

        # 4. Process history → multi-turn messages
        if history:
            # Find last assistant message index
            last_assistant_idx: Optional[int] = None
            for i in range(len(history) - 1, -1, -1):
                if history[i].get("role") == "assistant":
                    last_assistant_idx = i
                    break

            first_user_done = False
            for i, msg in enumerate(history):
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "user" and not first_user_done:
                    # First user message: prepend data context
                    result.append({"role": "user", "content": data_preamble + content})
                    first_user_done = True
                elif role == "assistant" and i == last_assistant_idx:
                    # Last assistant message: append existing code
                    result.append({"role": "assistant", "content": content + "\n\n" + code_block})
                else:
                    result.append({"role": role, "content": content})

            # Edge case: history has user messages but no assistant → inject code
            if last_assistant_idx is None:
                result.append({"role": "assistant", "content": code_block})
        else:
            # No prior history but have existing code (e.g., page reload)
            result.append({"role": "user", "content": data_preamble + description})
            result.append({"role": "assistant", "content": code_block})

        # 5. Ensure proper user/assistant alternation
        result = self._fix_message_alternation(result)

        # 6. Handle @mentions in current request
        mentions = _re.findall(r'@(\w+)', current_request)
        if mentions:
            hint = ", ".join(f'@{m} → tables["{m}"]' for m in mentions)
            current_request = f"📌 {hint}\n\n{current_request}"

        # 7. Final user message
        result.append({"role": "user", "content": current_request})

        return result

    @staticmethod
    def _fix_message_alternation(
        messages: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Merge consecutive same-role messages to ensure user/assistant alternation."""
        if not messages:
            return messages
        fixed = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == fixed[-1]["role"]:
                fixed[-1]["content"] += "\n\n" + msg["content"]
            else:
                fixed.append(msg)
        return fixed

    def _build_new_widget_prompt(
        self,
        description: str,
        data_summary: str,
        user_request: str = "",
        analyst_context: str = "",
        *,
        tools_enabled: bool = False,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        tool_request_cache_digest_lines: Optional[List[str]] = None,
    ) -> str:
        """Build single-turn prompt for NEW widget creation."""
        parts: List[str] = []

        if user_request:
            parts.append(f"USER REQUEST: {user_request.strip()}")

            # ── Resolve @mentions → explicit table references ──
            import re as _re
            mentions = _re.findall(r'@(\w+)', user_request)
            if mentions:
                parts.append("\n📌 TABLE REFERENCES (from @mentions):")
                for m in mentions:
                    parts.append(f'  @{m} → const tbl = tables["{m}"]; tbl.rows; tbl.columns.map(c => c.name);')
                parts.append(
                    "\n🚨 ОБЯЗАТЕЛЬНО используй tables[\"name\"] для доступа к данным таблицы."
                    "\n❌ Переменных table/colNames/rows НЕТ — не используй их!"
                )
                parts.append("")

        parts.append(f"TASK: Generate interactive data visualization widget")
        parts.append(f"DESCRIPTION: {description}")

        if analyst_context:
            parts.append(f"\nANALYSIS CONTEXT:\n{analyst_context}")

        if data_summary:
            parts.append(f"\nDATA CONTEXT:\n{data_summary}")
        digest_lines = tool_request_cache_digest_lines or []
        if digest_lines:
            parts.append(
                "\nУЖЕ ВЫПОЛНЕННЫЕ ЗАПРОСЫ К ДАННЫМ (не дублируй идентичные tool_requests; "
                "данные уже получены — см. TOOL RESULTS ниже):"
            )
            for line in digest_lines[-25:]:
                parts.append(f"  • {line}")
        if tool_results:
            rendered = []
            for item in tool_results[-4:]:
                if not isinstance(item, dict):
                    continue
                tname = item.get("tool_name", "tool")
                if item.get("success"):
                    rendered.append(
                        f"- {tname}: {json.dumps(item.get('data', {}), ensure_ascii=False, default=str)[:2500]}"
                    )
                else:
                    rendered.append(f"- {tname}: ERROR={item.get('error', 'unknown')}")
            if rendered:
                parts.append("\nTOOL RESULTS (latest):\n" + "\n".join(rendered))

        parts.append(
            '\n📋 ФОРМАТ ОТВЕТА: используй СТРУКТУРИРОВАННЫЕ СЕКЦИИ (НЕ корневой JSON-объект!).\n'
            'Ответ должен быть ТЕКСТОМ: сначала widget_name / widget_type / description, затем секции ===RENDER_BODY=== [+ опциональные ===STYLES=== и ===SCRIPTS===].\n'
            'Пиши код КАК ЕСТЬ — с настоящими переносами строк, кавычками, шаблонными литералами.\n'
            '\n🚨 ОБРАЩАЙСЯ К КОЛОНКАМ ПО ИМЕНИ (row[\'title\'], row[\'price\']), '
            'а НЕ по индексу (row[cols[0]]) — порядок колонок непредсказуем!\n'
            '\n'
            '🏷️ widget_name ОБЯЗАТЕЛЕН — КОРОТКИЙ заголовок на русском, МАКСИМУМ 5-7 слов!\n'
            '   НЕ предложение! Только существительные + прилагательные. Без глаголов.\n'
            '📝 description ОБЯЗАТЕЛЕН — 1-2 предложения, поясняющие визуализацию (НЕ повтор widget_name).\n'
            '❌ НЕ пиши "Widget", "Chart", "Visualization" — это бесполезные названия.\n'
            '❌ НЕ пиши длинное предложение в widget_name!\n'
            '✅ widget_name: "Продажи по категориям"\n'
            '✅ widget_name: "Топ-10 вакансий по зарплате"\n'
            '❌ widget_name: "Круговая диаграмма распределения количества вакансий по компаниям на основе данных"\n'
            '✅ description: "Столбчатая диаграмма сравнения продаж по категориям товаров с tooltip"\n'
            '\n'
            'Пример:\n'
            'widget_name: Продажи по категориям\n'
            'widget_type: chart\n'
            'description: Столбчатая диаграмма сравнения объёмов продаж по категориям товаров\n'
            '\n'
            '===RENDER_BODY===\n'
            'if (window.chartInstance) window.chartInstance.dispose();\n'
            'window.chartInstance = echarts.init(document.getElementById(\'chart\'));\n'
            'window.chartInstance.setOption({});\n'
            'window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };\n'
            '\n'
            '===SCRIPTS===\n'
            '<script src="/libs/echarts.min.js"></script>'
        )
        if tools_enabled:
            parts.append(
                "\nTOOL MODE ENABLED.\n"
                "Доступ к данным таблиц: readTableListFromContentNodes (table_id в ответе), при необходимости строк — "
                "readTableData с jsonDecl.table_id из первого тула. Если виджету нужны фактические значения из строк, "
                "вызови readTableData.\n"
                "Если данных недостаточно, верни JSON:\n"
                "{\n"
                '  "tool_requests": [\n'
                "    {\n"
                '      "tool_name": "readTableListFromContentNodes",\n'
                '      "arguments": {"nodeIds": ["<uuid1>", "<uuid2>"]},\n'
                '      "reason": "optional"\n'
                "    },\n"
                "    {\n"
                '      "tool_name": "readTableData",\n'
                '      "arguments": {"jsonDecl": {"contentNodeId":"<uuid>","table_id":"<id_or_name>","offset":0,"limit":50}},\n'
                '      "reason": "optional"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "Если данных достаточно — верни структурированные секции widget-ответа."
            )
        return "\n".join(parts)

    @staticmethod
    def _extract_tool_requests(parsed: Dict[str, Any]) -> List[ToolRequest]:
        if not isinstance(parsed, dict):
            return []
        items = parsed.get("tool_requests")
        if not isinstance(items, list):
            return []
        out: List[ToolRequest] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name") or item.get("name") or "").strip()
            if not tool_name:
                continue
            args = item.get("arguments") or item.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            try:
                out.append(
                    ToolRequest(
                        tool_name=tool_name,
                        arguments=args,
                        reason=item.get("reason"),
                    )
                )
            except Exception:
                continue
        return out

    def _build_data_summary_for_widget(
        self,
        task: Dict[str, Any],
        agent_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Собирает краткое описание доступных данных для виджета."""
        parts: List[str] = []
        table_names: set[str] = set()

        def _remember_table_name(tbl: Dict[str, Any]) -> None:
            n = tbl.get("name")
            if isinstance(n, str) and n.strip():
                table_names.add(n.strip())

        # input_data из task (ContentNode tables) — элементы могут быть dict или str (ID и т.д.)
        input_data = task.get("input_data", [])
        if input_data:
            for node in input_data:
                if not isinstance(node, dict):
                    continue
                for tbl in node.get("tables", []):
                    if not isinstance(tbl, dict):
                        continue
                    _remember_table_name(tbl)
                    cols = tbl.get("columns", [])
                    rows = tbl.get("rows", [])
                    parts.append(
                        f"Table '{tbl.get('name','?')}': columns={cols}, "
                        f"rows={len(rows)}"
                    )
                    # Добавляем sample данных для лучшего понимания
                    if rows:
                        sample = rows[:5]
                        parts.append(f"  sample={json.dumps(sample, ensure_ascii=False, default=str)}")

        # Fallback: input_data_preview из context
        if not parts and context:
            input_preview = context.get("input_data_preview", {})
            for table_name, info in input_preview.items():
                if isinstance(table_name, str) and table_name.strip():
                    table_names.add(table_name.strip())
                cols = info.get("columns", [])
                sample = info.get("sample_rows", [])[:5]
                parts.append(
                    f"Table '{table_name}': columns={cols}, "
                    f"rows={info.get('row_count', '?')}, "
                    f"sample={json.dumps(sample, ensure_ascii=False, default=str)}"
                )

        # Fallback: context["data"]["tables"] или context["content_node"]["content"]["tables"]
        # WidgetController кладёт данные именно туда, а не в input_data/input_data_preview
        if not parts and context:
            tables = (
                (context.get("data") or {}).get("tables")
                or (context.get("content_node") or {}).get("content", {}).get("tables")
                or []
            )
            for tbl in tables:
                if not isinstance(tbl, dict):
                    continue
                _remember_table_name(tbl)
                cols = tbl.get("columns", [])
                rows = tbl.get("rows", [])
                tbl_name = tbl.get("name", "?")
                # Для prompt нужны имена колонок (могут быть объектами или строками)
                col_names = []
                for c in cols:
                    if isinstance(c, dict):
                        col_names.append(c.get("name", str(c)))
                    else:
                        col_names.append(str(c))
                parts.append(
                    f"Table '{tbl_name}': columns={col_names}, "
                    f"rows={len(rows)}"
                )
                if rows:
                    sample = rows[:5]
                    parts.append(f"  sample={json.dumps(sample, ensure_ascii=False, default=str)}")

        # V2 agent_results tables/sources
        for result in agent_results:
            if not isinstance(result, dict):
                continue
            agent = result.get("agent", "unknown")
            for tbl in result.get("tables", []):
                if isinstance(tbl, dict):
                    _remember_table_name(tbl)
                    col_names = []
                    for c in tbl.get("columns", []):
                        if isinstance(c, dict):
                            col_names.append(c.get("name", ""))
                        else:
                            col_names.append(str(c))
                    parts.append(
                        f"[{agent}] Table '{tbl.get('name','')}': "
                        f"columns={col_names}"
                    )

        if table_names:
            ordered = ", ".join(sorted(table_names))
            parts.append("")
            parts.append(
                "ПРАВИЛА ИМЁН ТАБЛИЦ В КОДЕ ВИДЖЕТА (обязательно): "
                f"в данных доступны только имена: {ordered}. "
                "В Python используйте только tables['<имя>'] для этих имён. "
                "Не выдумывайте другие ключи (например oil_prices), если такого имени нет в списке выше."
            )

        return "\n".join(parts)

    def _extract_analyst_context(
        self, agent_results: List[Dict[str, Any]]
    ) -> str:
        """Извлекает контекст из результатов предыдущих агентов (analyst и др.)."""
        parts: List[str] = []

        for result in agent_results:
            if not isinstance(result, dict):
                continue
            agent_name = result.get("agent", "unknown")

            narrative = result.get("narrative_text") or result.get("narrative", "")
            if narrative and isinstance(narrative, str):
                trimmed = narrative[:500]
                parts.append(f"[{agent_name}] {trimmed}")

            findings = result.get("findings") or result.get("recommendations", [])
            if isinstance(findings, list):
                for f in findings[:5]:
                    if isinstance(f, str):
                        parts.append(f"[{agent_name}] • {f}")
                    elif isinstance(f, dict):
                        desc = f.get("description") or f.get("text", "")
                        if desc:
                            parts.append(f"[{agent_name}] • {desc}")

        return "\n".join(parts)

    # ── Widget name sanitiser ────────────────────────────────────
    _MAX_WIDGET_NAME_LEN = 50

    @classmethod
    def _sanitize_widget_name(cls, name: str) -> str:
        """Enforce short, clean widget name (max ~50 chars).

        GigaChat иногда ставит в widget_name целое предложение.
        Обрезаем по границе слова, убираем мусор.
        """
        if not name:
            return name
        # Strip surrounding whitespace and quotes
        name = name.strip().strip('"\'')
        # Remove trailing period / ellipsis that LLM may add
        name = re.sub(r'[\.…]+$', '', name).strip()
        # If within limit, return as-is
        if len(name) <= cls._MAX_WIDGET_NAME_LEN:
            return name
        # Try to cut at last word boundary before limit
        truncated = name[:cls._MAX_WIDGET_NAME_LEN]
        last_space = truncated.rfind(' ')
        if last_space > 15:  # keep at least 15 chars
            truncated = truncated[:last_space]
        return truncated.rstrip(' ,;:-—')

    # ── Boilerplate phrases to strip from widget name candidates ──
    _NAME_BOILERPLATE_PATTERNS = [
        re.compile(r'(?:создай|построй|сгенерируй|сделай|покажи|нарисуй|выведи)\s+', re.IGNORECASE),
        re.compile(r'визуализаци[юя]\s*', re.IGNORECASE),
        re.compile(r'\(?HTML[\s-]*виджет\)?\s*', re.IGNORECASE),
        re.compile(r'для\s+(?:этих\s+)?данных\s*$', re.IGNORECASE),
        re.compile(r'(?:interactive\s+)?(?:data\s+)?visualization\s+widget\s*', re.IGNORECASE),
        re.compile(r'^generate\s+', re.IGNORECASE),
        re.compile(r'^create\s+', re.IGNORECASE),
        re.compile(r'^task:\s*', re.IGNORECASE),
        re.compile(r'^description:\s*', re.IGNORECASE),
        # English planner boilerplate ("Generate HTML widget using ECharts v6 for...")
        re.compile(r'^HTML\s+widget\s+(?:using\s+\w+(?:\s+v\d+)?\s+)?(?:for\s+)?', re.IGNORECASE),
        re.compile(r'\s+(?:for|of)\s+(?:visualization\s+of\s+)?@\w+.*$', re.IGNORECASE),
    ]

    def _derive_widget_name(
        self, user_request: str, description: str, data_summary: str,
    ) -> str:
        """Derive a meaningful short widget name from available context.

        Priority:
        1. user_request (original user prompt) — strip boilerplate
        2. description (planner task) — strip boilerplate
        3. Table names from data_summary
        4. Generic fallback
        """
        for raw in (user_request.strip(), description.strip()):
            if not raw:
                continue
            # Take first line/sentence
            candidate = re.split(r'[.\n]', raw)[0].strip()
            # Strip boilerplate command phrases
            for pat in self._NAME_BOILERPLATE_PATTERNS:
                candidate = pat.sub('', candidate).strip()
            # Remove leading/trailing punctuation
            candidate = candidate.strip(' -—:,;()[]')
            if len(candidate) >= 3:
                if len(candidate) > 60:
                    candidate = candidate[:57] + '...'
                # Capitalize first letter
                return candidate[0].upper() + candidate[1:]

        # Fallback: extract table names from data_summary
        table_names = re.findall(r"Таблица\s+['\"]([^'\"]+)['\"]|Table\s+['\"]([^'\"]+)['\"]", data_summary)
        if table_names:
            names = [n[0] or n[1] for n in table_names[:2]]
            return "Визуализация: " + ", ".join(names)

        return "Визуализация данных"

    # ══════════════════════════════════════════════════════════════════
    #  Scaffold assembly
    # ══════════════════════════════════════════════════════════════════

    _RENDER_BODY_RE = re.compile(
        r'// ── RENDER_BODY_START ──\n(.*?)\n\s*// ── RENDER_BODY_END ──',
        re.DOTALL,
    )
    _CUSTOM_STYLES_RE = re.compile(
        r'/\* ── CUSTOM_STYLES_START ── \*/\n(.*?)\n\s*/\* ── CUSTOM_STYLES_END ── \*/',
        re.DOTALL,
    )
    _CUSTOM_SCRIPTS_RE = re.compile(
        r'<!-- ── CUSTOM_SCRIPTS_START ── -->\n(.*?)\n\s*<!-- ── CUSTOM_SCRIPTS_END ── -->',
        re.DOTALL,
    )

    # Known local libraries: detection patterns → script tags
    _LIB_DETECTION: list[tuple[re.Pattern, str]] = [
        (
            re.compile(r'\b(?:echarts\.init|setOption|echarts\.graphic)\b'),
            '<script src="/libs/echarts.min.js"></script>',
        ),
        (
            re.compile(r'\bd3\.(?:select|scale|axis|arc|pie|force|geo|hierarchy|format|sum|max|min|range|extent)\b'),
            '<script src="/libs/d3.min.js"></script>',
        ),
        (
            re.compile(r'\bnew\s+Chart\b|\bChart\.register\b'),
            '<script src="/libs/chart.min.js"></script>',
        ),
        (
            re.compile(
                r'\bL\.(?:map|tileLayer|marker|circle|polygon|geoJSON|latLng|circleMarker|divIcon)\b'
            ),
            '<script src="/libs/leaflet.js"></script>',
        ),
    ]

    _LEAFLET_HEAD_CSS = "/libs/leaflet.css"

    def _ensure_scripts_for_libs(
        self, render_body: str, scripts: str,
    ) -> str:
        """Auto-detect libraries used in render_body and ensure their script tags are present.

        If the LLM forgot a <script> tag or returned only one when multiple are needed,
        this adds the missing tags. Also removes tags for libraries NOT used in render_body.
        """
        needed_tags: list[str] = []
        for pattern, tag in self._LIB_DETECTION:
            if pattern.search(render_body):
                needed_tags.append(tag)

        if not needed_tags:
            # No known library detected — keep whatever LLM returned (plain HTML widget)
            return scripts

        # Check which needed tags are missing from current scripts
        added = []
        for tag in needed_tags:
            # Extract src path for comparison
            src_match = re.search(r'src="([^"]+)"', tag)
            if src_match and src_match.group(1) not in scripts:
                added.append(tag)

        if added:
            self.logger.warning(
                f"🔧 Auto-fix: adding missing script tags: {added}"
            )
            # Append missing tags to existing scripts
            scripts = (scripts.strip() + "".join(added)).strip()

        return scripts

    @staticmethod
    def _ensure_head_links_for_libs(
        render_body: str,
        scripts: str,
        custom_styles: str,
    ) -> str:
        """Подставляет <link> на /libs/leaflet.css при использовании API Leaflet (L.*) в render_body."""
        combined = (scripts or "") + (custom_styles or "")
        if WidgetCodexAgent._LEAFLET_HEAD_CSS in combined:
            return ""
        if not re.search(
            r"\bL\.(?:map|tileLayer|marker|circle|polygon|geoJSON|latLng|circleMarker|divIcon)\b",
            render_body,
        ):
            return ""
        return (
            f'  <link rel="stylesheet" href="{WidgetCodexAgent._LEAFLET_HEAD_CSS}">'
        )

    @staticmethod
    def _detect_js_string_issues(widget_code: str) -> list:
        """Scan assembled widget for common JS SyntaxError triggers. Returns [(line_no, description)]."""
        issues: list = []
        lines = widget_code.split("\n")
        in_script = False
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if "<script" in stripped.lower() and "src=" not in stripped.lower():
                in_script = True
                continue
            if "</script>" in stripped.lower():
                in_script = False
                continue
            if not in_script:
                continue
            # Real newline inside a non-template string literal on this line
            # (would be caught as multi-line, but check for sanity)
            for q in ("'", '"'):
                parts = stripped.split(q)
                # odd-indexed parts are inside quotes (rough heuristic)
                for pi in range(1, len(parts), 2):
                    if "\n" in parts[pi] or "\r" in parts[pi]:
                        issues.append((idx, f"raw newline inside {q}...{q}"))
                    if "\u2028" in parts[pi] or "\u2029" in parts[pi]:
                        issues.append((idx, f"U+2028/U+2029 inside {q}...{q}"))
            # Unescaped </script> inside inline script
            if "</script" in stripped.lower() and in_script:
                issues.append((idx, "literal </script> inside <script> block"))
        return issues

    @staticmethod
    def _sanitize_srcdoc_inline_script(widget_code: str) -> str:
        """В iframe/srcdoc HTML-парсер закрывает <script> на любом литерале </script>.

        Остаток документа перестаёт быть JS → SyntaxError («Invalid or unexpected token»)
        на далёкой строке). Экранируем только тело RENDER_BODY между маркерами каркаса."""
        start_m = "// ── RENDER_BODY_START ──"
        end_m = "// ── RENDER_BODY_END ──"
        i0 = widget_code.find(start_m)
        i1 = widget_code.find(end_m)
        if i0 < 0 or i1 <= i0:
            return widget_code
        line_after = widget_code.find("\n", i0)
        if line_after < 0:
            return widget_code
        seg_start = line_after + 1
        mid = widget_code[seg_start:i1]
        if "</script" not in mid.lower():
            return widget_code
        mid_fixed = re.sub(r"</script\s*>", r"<\\/script>", mid, flags=re.IGNORECASE)
        if mid_fixed != mid:
            logger.warning(
                "🔧 Auto-fix: </script> inside RENDER_BODY escaped for srcdoc "
                "(HTML must not see raw closing script tag inside inline JS)"
            )
        return widget_code[:seg_start] + mid_fixed + widget_code[i1:]

    @staticmethod
    def _assemble_widget(
        render_body: str,
        custom_styles: str = "",
        scripts: str = "",
        head_links: str = "",
    ) -> str:
        """Собирает виджет из статического каркаса + динамических частей (render_body, styles, scripts)."""
        styles_block = f"    {custom_styles}" if custom_styles.strip() else ""
        scripts_block = f"  {scripts}" if scripts.strip() else ""
        head_block = head_links.strip() if (head_links or "").strip() else ""

        # Indent render_body to match scaffold (8 spaces inside render() try block)
        indented_lines = []
        for line in render_body.split("\n"):
            if line.strip():
                indented_lines.append(f"        {line}")
            else:
                indented_lines.append("")
        indented_body = "\n".join(indented_lines)

        return (
            WIDGET_SCAFFOLD
            .replace("%%CUSTOM_STYLES%%", styles_block)
            .replace("%%CUSTOM_SCRIPTS%%", scripts_block)
            .replace("%%RENDER_BODY%%", indented_body)
            .replace("%%CUSTOM_HEAD_LINKS%%", head_block)
        )

    @classmethod
    def _extract_dynamic_parts(cls, widget_code: str) -> Optional[Dict[str, str]]:
        """Извлекает динамические части (render_body, styles) из собранного виджета.

        Возвращает {"render_body": ..., "styles": ...} если маркеры найдены, иначе None.
        """
        rb_match = cls._RENDER_BODY_RE.search(widget_code)
        if not rb_match:
            return None

        render_body = rb_match.group(1).strip()
        # Dedent: remove 8-space scaffold indent
        lines = render_body.split("\n")
        render_body = "\n".join(
            line[8:] if line.startswith("        ") else line
            for line in lines
        )

        styles = ""
        st_match = cls._CUSTOM_STYLES_RE.search(widget_code)
        if st_match:
            raw = st_match.group(1).strip()
            if raw:
                # Dedent: remove 4-space scaffold indent
                lines = raw.split("\n")
                styles = "\n".join(
                    line[4:] if line.startswith("    ") else line
                    for line in lines
                )

        scripts = ""
        sc_match = cls._CUSTOM_SCRIPTS_RE.search(widget_code)
        if sc_match:
            raw = sc_match.group(1).strip()
            if raw:
                # Dedent: remove 2-space scaffold indent
                lines = raw.split("\n")
                scripts = "\n".join(
                    line[2:] if line.startswith("  ") else line
                    for line in lines
                )

        return {"render_body": render_body, "styles": styles, "scripts": scripts}

    @staticmethod
    def _is_truncated_code(code: str) -> bool:
        """Detect if JS code was likely truncated by max_tokens limit.

        Checks for unterminated template literals, strings, open brackets,
        and other signs that the code was cut off mid-generation.
        """
        if not code or len(code) < 20:
            return False

        stripped = code.rstrip()

        # Obvious truncation: ends mid-assignment, mid-property, or mid-string
        truncation_endings = ('=', '+', ',', '(', '{', '[', ':', '<', '&&', '||', 'src=', '>')
        for ending in truncation_endings:
            if stripped.endswith(ending):
                return True

        # Count open/close brackets
        open_parens = code.count('(') - code.count(')')
        open_braces = code.count('{') - code.count('}')
        open_brackets = code.count('[') - code.count(']')
        # Template literals
        backticks = code.count('`')

        # Significant imbalance suggests truncation
        if open_parens > 2 or open_braces > 2 or open_brackets > 2:
            return True
        if backticks % 2 != 0:
            return True

        return False

    # ══════════════════════════════════════════════════════════════════
    #  Auto-fixes & JSON parsing
    # ══════════════════════════════════════════════════════════════════
    def _fix_async_render(self, code: str) -> str:
        """Auto-fix: если render() вызывает fetchContentData/fetchData но НЕ является async,
        добавляем async. Без этого .then() возвращает Promise, а не данные,
        и rows.forEach() падает с 'is not a function'.
        """
        if not code:
            return code

        # Паттерн 1: function render() { ... fetchContentData/fetchData ...
        # но render НЕ async → добавляем async
        if re.search(r'fetchContentData|fetchData', code):
            # Находим все 'function render(' которые НЕ предваряются 'async '
            fixed = re.sub(
                r'(?<!async )function\s+(render)\s*\(',
                r'async function \1(',
                code,
            )
            if fixed != code:
                self.logger.warning("🔧 Auto-fix: added 'async' to render() calling fetchContentData")
                code = fixed

        # Паттерн 2: fetchData().then(data => data) — бесполезный .then,
        # результат всё равно Promise. Заменяем на await fetchData().
        then_pattern = re.compile(
            r'(\bconst|let|var)\s+(\w+)\s*=\s*(fetchData|fetchContentData)\s*\(\)\s*\.then\s*\([^)]*\)\s*;?'
        )
        m = then_pattern.search(code)
        if m:
            old_expr = m.group(0)
            decl = m.group(1)  # const/let/var
            var_name = m.group(2)
            func_name = m.group(3)
            new_expr = f"{decl} {var_name} = await {func_name}();"
            code = code.replace(old_expr, new_expr)
            self.logger.warning(f"🔧 Auto-fix: replaced '{func_name}().then(...)' with 'await {func_name}()'")

        # Паттерн 3: `${var(--card-width)}` — CSS var() в JS template literal.
        # var — ключевое слово JS → SyntaxError: Unexpected token 'var'.
        # Заменяем на строку 'var(--card-width)' (валидное CSS-значение для style.*).
        css_var_pattern = re.compile(r'`\$\{var\(--([\w-]+)\)\}`')
        if css_var_pattern.search(code):
            code = css_var_pattern.sub(r"'var(--\1)'", code)
            self.logger.warning("🔧 Auto-fix: replaced `${var(--...)}` with 'var(--...)' (CSS var in JS)")

        return code

    def _fix_data_redeclaration(self, render_body: str) -> str:
        """Auto-fix: rename `const/let/var data = ...` → `_data` to avoid
        collision with scaffold's `const data = await fetchContentData()`.

        GigaChat sometimes reuses `data` as a local variable name inside
        render_body, causing 'Identifier data has already been declared'.
        """
        if not render_body:
            return render_body

        # Check if render_body declares its own `data` variable
        pattern = re.compile(r'\b(const|let|var)\s+data\s*=')
        if not pattern.search(render_body):
            return render_body

        self.logger.warning(
            "🔧 Auto-fix: render_body redeclares 'data' — renaming to '_data'"
        )

        # Step 1: Rename declaration  const data = → const _data =
        render_body = pattern.sub(r'\1 _data =', render_body)

        # Step 2: Rename usage of standalone `data` as variable reference.
        # Match `data[`, `data.`, `data)`, `data,`, `data;`, `data]`, `data}`
        # but NOT `data:` — that's an object property key (e.g. ECharts {data: [...]})
        # Also avoid touching `previousData`, `fetchContentData`, `inputData` etc.
        render_body = re.sub(
            r'(?<!\w)data(?=\s*[\[.)\],;\}])',
            '_data',
            render_body,
        )

        # Step 3: Fix over-replacement — restore `_data.tables` references back
        # if any existed (they refer to scaffold's data, not local var)
        render_body = render_body.replace('_data.tables', 'data.tables')

        return render_body

    def _fix_echarts_yaxis_index(self, render_body: str) -> str:
        """Auto-fix: если series использует yAxisIndex: N, а yAxis — одиночный объект,
        превращаем yAxis в массив с N+1 элементами.

        ECharts бросает TypeError (Cannot read properties of undefined (reading 'get'))
        когда series ссылается на yAxisIndex, для которого нет yAxis.
        """
        if not render_body:
            return render_body

        # Найти все yAxisIndex: N
        indices = [int(m) for m in re.findall(r'yAxisIndex\s*:\s*(\d+)', render_body)]
        if not indices:
            return render_body

        max_idx = max(indices)
        if max_idx == 0:
            return render_body  # yAxisIndex: 0 works with a single yAxis

        # Проверяем, что yAxis определён как одиночный объект, а не массив
        # Паттерн: yAxis: { ... } (не yAxis: [ ... ])
        yaxis_match = re.search(
            r'(yAxis\s*:\s*)\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            render_body,
        )
        if not yaxis_match:
            return render_body  # yAxis not found or already an array

        # Проверяем, что yAxis — не внутри массива (может быть уже массивом)
        prefix_before_yaxis = render_body[:yaxis_match.start()]
        # Если сразу перед yAxis есть '[', значит он уже в массиве
        stripped_prefix = prefix_before_yaxis.rstrip()
        if stripped_prefix.endswith('['):
            return render_body

        # yAxis — одиночный объект, но series ссылается на yAxisIndex > 0
        # Превращаем в массив: yAxis: [{original}, {type: 'value'}, ...]
        original_body = yaxis_match.group(2).strip()
        extra_axes = ', '.join('{type: "value"}' for _ in range(max_idx))
        replacement = f'{yaxis_match.group(1)}[{{{original_body}}}, {extra_axes}]'

        self.logger.warning(
            f"🔧 Auto-fix: yAxisIndex:{max_idx} found but yAxis is a single object. "
            f"Converting yAxis to array with {max_idx + 1} entries."
        )
        return render_body[:yaxis_match.start()] + replacement + render_body[yaxis_match.end():]

    # Cartesian chart types that REQUIRE xAxis + yAxis
    _CARTESIAN_TYPES = re.compile(r"type\s*:\s*['\"](?:bar|line|scatter|candlestick|boxplot|effectScatter|heatmap)['\"]")

    def _fix_echarts_missing_axis(self, render_body: str) -> str:
        """Auto-fix: bar/line/scatter charts without xAxis/yAxis → inject basic axis config.

        ECharts cartesian2d charts (bar, line, scatter, etc.) crash with
        TypeError: Cannot read properties of undefined (reading 'get')
        when xAxis or yAxis is missing from the option.
        """
        if not render_body:
            return render_body

        # Only applies to cartesian chart types
        if not self._CARTESIAN_TYPES.search(render_body):
            return render_body

        # Check that xAxis is NOT already present
        has_x = re.search(r'\bxAxis\s*:', render_body)
        has_y = re.search(r'\byAxis\s*:', render_body)
        if has_x and has_y:
            return render_body  # Both axes present — nothing to fix

        # Find the opening '{' of the ECharts option object.
        # Pattern 1: inline .setOption( { ... } )
        # Pattern 2: const/let/var <name> = { ... }; .setOption(<name>);
        inject_match = re.search(
            r'\.setOption\s*\(\s*\{',
            render_body,
        )
        if not inject_match:
            # Try variable assignment pattern — only if .setOption(<var>) exists
            var_match = re.search(r'\.setOption\s*\(\s*(\w+)\s*\)', render_body)
            if var_match:
                var_name = var_match.group(1)
                # Find the variable declaration: const <var_name> = {
                inject_match = re.search(
                    rf'(?:const|let|var)\s+{re.escape(var_name)}\s*=\s*\{{',
                    render_body,
                )
        if not inject_match:
            return render_body  # Can't find option object — bail out

        inject_parts = []
        if not has_x:
            inject_parts.append("xAxis: { type: 'category' }")
        if not has_y:
            inject_parts.append("yAxis: { type: 'value' }")
        inject_str = ', '.join(inject_parts)

        # Insert right after the opening '{'
        insert_pos = inject_match.end()  # position right after '{'
        patched = (
            render_body[:insert_pos]
            + ' ' + inject_str + ','
            + render_body[insert_pos:]
        )

        axes_names = []
        if not has_x:
            axes_names.append('xAxis')
        if not has_y:
            axes_names.append('yAxis')
        self.logger.warning(
            f"🔧 Auto-fix: cartesian chart detected but {' and '.join(axes_names)} missing. "
            f"Injected default axis config to prevent crash."
        )
        return patched

    def _fix_undefined_col_vars(self, render_body: str) -> str:
        """Auto-fix: detect *Col variables used in r[xyzCol] but never defined.

        GigaChat часто галлюцинирует имена переменных — определяет logoCol, vacIdCol,
        но потом использует biNameCol, которая не была определена.
        Если переменная *Col / *Column используется в r[var] / row[var] но НЕ определена
        через const/let/var, заменяем её на __cols[index].
        """
        if not render_body:
            return render_body

        # Шаг 1: Найдём все определённые переменные (const/let/var xxxCol = ...)
        defined = set(re.findall(
            r'(?:const|let|var)\s+(\w+)\s*=', render_body
        ))

        # Шаг 2: Найдём все переменные используемые как ключи доступа к row:
        # r[someVar], row[someVar], r [ someVar ] — но НЕ строковые литералы r["col"]
        used_as_key = set(re.findall(
            r'\br(?:ow)?\s*\[\s*([a-zA-Z_]\w*)\s*\]', render_body
        ))

        # Шаг 3: Определяем неопределённые переменные
        # Исключаем стандартные имена — tables, data и прочие
        scaffold_vars = {
            'tables', 'data', 'tbl', 'col', 'column', 'cols',
            'i', 'j', 'k', 'idx', 'index', 'key', 'name', 'value',
        }
        undefined = used_as_key - defined - scaffold_vars

        if not undefined:
            return render_body

        self.logger.warning(
            f"🔧 Auto-fix: undefined column variables detected: {undefined}"
        )

        # Шаг 4: Назначаем __cols[0], __cols[1], ... для каждой неопределённой
        # __cols — массив имён колонок первой таблицы
        sorted_undef = sorted(undefined)
        declarations: list[str] = [
            "const __cols = tables[data.tables[0].name].columns.map(c => c.name);"
        ]
        for i, var_name in enumerate(sorted_undef):
            declarations.append(f"const {var_name} = __cols[{i}];")
            self.logger.warning(
                f"🔧 Auto-fix: {var_name} → __cols[{i}]"
            )

        # Вставляем определения в начало render_body
        prefix = "\n".join(declarations) + "\n\n"
        return prefix + render_body

    # ── Smart-quote / invisible-char sanitiser ────────────────────
    # GigaChat часто вставляет типографские кавычки и невидимые Unicode-символы,
    # которые вызывают SyntaxError: Invalid or unexpected token.
    _SMART_QUOTE_MAP = str.maketrans({
        '\u2018': "'",   # ‘ LEFT SINGLE QUOTATION MARK
        '\u2019': "'",   # ’ RIGHT SINGLE QUOTATION MARK
        '\u201a': "'",   # ‚ SINGLE LOW-9 QUOTATION MARK
        '\u201c': '"',   # “ LEFT DOUBLE QUOTATION MARK
        '\u201d': '"',   # ” RIGHT DOUBLE QUOTATION MARK
        '\u201e': '"',   # „ DOUBLE LOW-9 QUOTATION MARK
        '\u2032': "'",   # ′ PRIME
        '\u2033': '"',   # ″ DOUBLE PRIME
        '\u00ab': '"',   # « LEFT-POINTING DOUBLE ANGLE QUOTATION
        '\u00bb': '"',   # » RIGHT-POINTING DOUBLE ANGLE QUOTATION
        '\u2014': '--',  # — EM DASH  (in JS code only; CSS em-dash is fine)
        '\u2013': '-',   # – EN DASH
        '\u00a0': ' ',   # NON-BREAKING SPACE
        '\u200b': '',    # ZERO WIDTH SPACE
        '\u200c': '',    # ZERO WIDTH NON-JOINER
        '\u200d': '',    # ZERO WIDTH JOINER
        '\ufeff': '',    # BOM / ZERO WIDTH NO-BREAK SPACE
    })

    def _fix_smart_quotes(self, code: str) -> str:
        """Replace typographic quotes and invisible Unicode chars with ASCII equivalents.

        GigaChat нередко вставляет «красивые» кавычки (‘’ “” «») вместо ASCII ' и ".
        Это вызывает SyntaxError: Invalid or unexpected token в JS.
        """
        if not code:
            return code
        original = code
        code = code.translate(self._SMART_QUOTE_MAP)
        if code != original:
            self.logger.warning(
                "\U0001f9f9 Auto-fix: replaced smart quotes / invisible Unicode chars in code"
            )
        return code

    def _strip_markdown_from_code(self, code: str) -> str:
        """Strip markdown commentary that LLM sometimes injects into code sections.

        GigaChat may append explanatory markdown text (## HEADER, ### heading,
        bullet lists, etc.) after the actual JS/CSS code, or inline anywhere.

        Two passes:
          1. Remove standalone markdown lines (lines that are pure markdown noise).
          2. Remove trailing block starting from first markdown heading.
        """
        if not code:
            return code

        lines = code.split('\n')
        cleaned_lines = []
        cut_index = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Markdown headings: ##heading, ### heading, #heading (any form, with or without space)
            if re.match(r'^#{1,6}(\s+\S|\S)', stripped):
                cut_index = i
                break

            # Markdown bold paragraph: **Something** at column 0 (not JS code)
            if re.match(r'^\*\*[^*]+\*\*', stripped) and not stripped.endswith(';'):
                cut_index = i
                break

            # Markdown horizontal rule: --- or ***
            if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped):
                cut_index = i
                break

            # Markdown list items that don't look like JS comments
            if stripped.startswith('- ') and not stripped.startswith('- //'):
                rest = stripped[2:]
                if re.match(r'^[\u0410-\u042fA-Z]', rest) and not rest.endswith(';') and not rest.endswith('{'):
                    cut_index = i
                    break

            # Inline ### tokens in the middle of a line (e.g. "someCode(); ###")
            # Remove them in-place rather than cutting the whole block
            if '###' in stripped and not stripped.startswith('//') and not stripped.startswith('*'):
                line = re.sub(r'\s*###.*$', '', line)
                self.logger.warning(f"🧹 Auto-fix: removed inline ### from line {i}: {stripped!r}")

            cleaned_lines.append(line)

        if cut_index is not None:
            removed_text = '\n'.join(lines[cut_index:])
            cleaned = '\n'.join(cleaned_lines[:cut_index]).rstrip()
            self.logger.warning(
                f"🧹 Auto-fix: stripped {len(lines) - cut_index} lines of markdown "
                f"commentary from code section (removed {len(removed_text)} chars)"
            )
            return cleaned

        return '\n'.join(cleaned_lines)

    @staticmethod
    def _js_closing_paren_after(s: str, open_paren_idx: int) -> int:
        """Индекс символа сразу после `)`, закрывающего `(` на позиции open_paren_idx.

        Учитывает строки ' \" `, // и /* */. Нужно для вставки кода после setOption(...),
        где внутри объекта есть `formatter: function () { return x; }` с точкой с запятой."""
        n = len(s)
        if open_paren_idx < 0 or open_paren_idx >= n or s[open_paren_idx] != "(":
            return -1
        depth = 1
        i = open_paren_idx + 1
        while i < n and depth > 0:
            c = s[i]
            if c == "'":
                i += 1
                while i < n:
                    if s[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if s[i] == "'":
                        i += 1
                        break
                    i += 1
                continue
            if c == '"':
                i += 1
                while i < n:
                    if s[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if s[i] == '"':
                        i += 1
                        break
                    i += 1
                continue
            if c == "`":
                i += 1
                while i < n:
                    if s[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if s[i] == "`":
                        i += 1
                        break
                    i += 1
                continue
            if c == "/" and i + 1 < n:
                if s[i + 1] == "/":
                    i = s.find("\n", i + 2)
                    if i < 0:
                        return -1
                    i += 1
                    continue
                if s[i + 1] == "*":
                    j = s.find("*/", i + 2)
                    if j < 0:
                        return -1
                    i = j + 2
                    continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return -1

    def _fix_echarts_onclick_in_series(self, render_body: str) -> str:
        """Fix onclick/onClick properties inside ECharts series/data config.

        ECharts does NOT support onclick as a series property — it is silently
        ignored. The correct API is chartInstance.on('click', handler).

        This sanitizer detects the pattern and rewrites it:
          BEFORE:  series: [{ ..., onclick: function(e) { toggleFilter(...) } }]
          AFTER:   (onclick block removed from series; .on('click',...) injected
                   after setOption if not already present)
        """
        if not render_body or 'onclick' not in render_body.lower():
            return render_body

        original = render_body

        # Pattern: onclick / onClick inside series config (object property)
        # Matches:  onclick: function(...) { ... }
        #           onClick: (params) => { ... }
        # We remove it from the series config and optionally inject .on('click')
        onclick_in_obj = re.compile(
            r',?\s*on[Cc]lick\s*:\s*(?:function\s*\([^)]*\)|(?:\([^)]*\)|\w+)\s*=>)\s*\{[^}]*\}',
            re.DOTALL,
        )

        # Extract the onclick handler body to reuse in .on('click', ...) injection
        handler_match = re.search(
            r'on[Cc]lick\s*:\s*(?:function\s*\((\w*)\)|(?:\((\w*)\)|(\w+))\s*=>)\s*(\{.*?\})',
            render_body,
            re.DOTALL,
        )

        cleaned = onclick_in_obj.sub('', render_body)

        if cleaned != render_body:
            self.logger.warning(
                "🔧 Auto-fix: removed onclick from ECharts series config (not supported by ECharts)"
            )

            # Chart.js: нет chartInstance.on('click') — только options.onClick (см. промпт)
            if re.search(r"\bnew\s+Chart\s*\(", cleaned):
                self.logger.info(
                    "🔧 Chart.js: пропуск вставки ECharts .on('click') — используй options.onClick"
                )
                return cleaned

            # Inject .on('click', ...) after setOption if not already present (ECharts)
            if '.on(' not in cleaned and 'chartInstance' in cleaned:
                # Build a minimal click handler that calls toggleFilter if available
                if handler_match:
                    # Try to extract what toggleFilter is called with from the original handler
                    toggle_call = re.search(
                        r'window\.toggleFilter\s*\([^)]+\)', handler_match.group(4) or ''
                    )
                    if toggle_call:
                        handler_body = f"if (window.toggleFilter) {toggle_call.group(0)};"
                    else:
                        handler_body = "if (window.toggleFilter) window.toggleFilter(dimCol, params.name);"
                else:
                    handler_body = "if (window.toggleFilter) window.toggleFilter(dimCol, params.name);"

                inject = (
                    f"\nwindow.chartInstance.on('click', function(params) {{\n"
                    f"  {handler_body}\n"
                    f"}});"
                )
                # После ПОЛНОГО вызова setOption(...); — не после первой «;» внутри option
                # (иначе вставка ломает formatter: function () { return x; } → SyntaxError).
                n = len(cleaned)
                insert_at = -1
                for m in re.finditer(
                    r"window\.chartInstance\.setOption\s*\(", cleaned
                ):
                    close = self._js_closing_paren_after(cleaned, m.end() - 1)
                    if close < 0:
                        continue
                    j = close
                    while j < n and cleaned[j] in " \t\n\r":
                        j += 1
                    if j < n and cleaned[j] == ";":
                        insert_at = j + 1
                    else:
                        insert_at = close
                if insert_at >= 0:
                    cleaned = cleaned[:insert_at] + inject + cleaned[insert_at:]
                    self.logger.info(
                        "🔧 Auto-fix: injected chartInstance.on('click', ...) after setOption(...)"
                    )
                else:
                    cleaned = cleaned + inject
                    self.logger.info(
                        "🔧 Auto-fix: appended chartInstance.on('click', ...) at end"
                    )

        return cleaned

    def _strip_echarts_onclick_from_chartjs(self, render_body: str) -> str:
        """Chart.js: у инстанса нет .on('click'). LLM иногда вставляет шаблон ECharts → SyntaxError/рантайм."""
        if not render_body or "new Chart" not in render_body:
            return render_body
        if "chartInstance.on" not in render_body:
            return render_body
        original = render_body
        while True:
            m = re.search(r"window\.chartInstance\.on\s*\(", render_body)
            if not m:
                break
            open_paren = m.end() - 1
            close = self._js_closing_paren_after(render_body, open_paren)
            if close < 0:
                break
            j = close
            n = len(render_body)
            while j < n and render_body[j] in " \t\n\r":
                j += 1
            if j < n and render_body[j] == ";":
                j += 1
            start = m.start()
            while start > 0 and render_body[start - 1] in " \t\n\r":
                start -= 1
            render_body = render_body[:start] + render_body[j:]
        if render_body != original:
            self.logger.warning(
                "🔧 Auto-fix: удалён chartInstance.on('click') при Chart.js — нужен options.onClick"
            )
        return render_body

    def _fix_formatter_multiline_strings(self, render_body: str) -> str:
        """LLM часто пишет formatter: '{b}
        {c}%' — в JS строка в '...' не может содержать сырой перенос → SyntaxError."""
        if not render_body or "formatter:" not in render_body:
            return render_body
        original = render_body

        def repair(text: str, quote: str) -> str:
            pos = 0
            parts: list[str] = []
            pat = re.compile(r"formatter:\s*" + re.escape(quote))

            while True:
                m = pat.search(text, pos)
                if not m:
                    parts.append(text[pos:])
                    break
                parts.append(text[pos : m.start()])
                i = m.end()
                chunks: list[str] = []
                while i < len(text):
                    c = text[i]
                    if c == "\\" and i + 1 < len(text):
                        chunks.append(text[i : i + 2])
                        i += 2
                        continue
                    if c == quote:
                        parts.append("formatter: " + quote + "".join(chunks) + quote)
                        pos = i + 1
                        break
                    if c == "\n":
                        j = i + 1
                        while j < len(text) and text[j] in " \t\r":
                            j += 1
                        chunks.append("\\n")
                        i = j
                        continue
                    chunks.append(c)
                    i += 1
                else:
                    parts.append(text[m.start() :])
                    break
            return "".join(parts)

        render_body = repair(render_body, "'")
        render_body = repair(render_body, '"')
        if render_body != original:
            self.logger.warning(
                "🔧 Auto-fix: formatter string had illegal newline inside quotes → escaped as \\n"
            )
        return render_body

    def _fix_illegal_js_string_line_terminators(self, render_body: str) -> str:
        """В '...' и \"...\" в JS недопустимы переводы строк и U+2028/U+2029 → SyntaxError.

        Частые источники: копипаст из Word/документов; JSON, где \\n в значении стал реальным LF
        внутри formatter/tooltip до закрывающей кавычки."""
        if not render_body:
            return render_body
        _LT = frozenset("\n\r\u2028\u2029")
        out: list[str] = []
        i = 0
        n = len(render_body)
        changed = False
        while i < n:
            if i + 1 < n and render_body[i : i + 2] == "//":
                j = render_body.find("\n", i)
                if j == -1:
                    out.append(render_body[i:])
                    break
                out.append(render_body[i : j + 1])
                i = j + 1
                continue
            if i + 1 < n and render_body[i : i + 2] == "/*":
                j = render_body.find("*/", i + 2)
                if j == -1:
                    out.append(render_body[i:])
                    break
                out.append(render_body[i : j + 2])
                i = j + 2
                continue
            c = render_body[i]
            if c in "'\"":
                q = c
                out.append(q)
                i += 1
                while i < n:
                    c = render_body[i]
                    if c == "\\" and i + 1 < n:
                        out.append(render_body[i : i + 2])
                        i += 2
                        continue
                    if c == q:
                        out.append(q)
                        i += 1
                        break
                    if c in _LT:
                        out.append("\\n")
                        changed = True
                        if c == "\r" and i + 1 < n and render_body[i + 1] == "\n":
                            i += 2
                        else:
                            i += 1
                        continue
                    out.append(c)
                    i += 1
                continue
            if c == "`":
                out.append(c)
                i += 1
                while i < n:
                    if render_body[i] == "\\" and i + 1 < n:
                        out.append(render_body[i : i + 2])
                        i += 2
                        continue
                    if render_body[i] == "`":
                        out.append(render_body[i])
                        i += 1
                        break
                    out.append(render_body[i])
                    i += 1
                continue
            out.append(c)
            i += 1
        if changed:
            self.logger.warning(
                "🔧 Auto-fix: LF/CR/U+2028/U+2029 inside JS '...' / \"...\" → escaped \\\\n"
            )
        return "".join(out)

    def _fix_invalid_formatter(self, render_body: str) -> str:
        """Fix invalid ${} template literals inside ECharts formatter strings.

        LLM sometimes mixes JS template literals with ECharts string formatters:
          ❌ formatter: '{b}: {c}<br>${r["col"]}'   — ${} is NOT evaluated in a regular string
          ❌ formatter: `{b}: {c}<br>${r[dimCol]}`  — OK if backtick, but complex expressions fail

        This sanitizer strips the ${...} suffix from regular string formatters,
        keeping only valid ECharts placeholders: {a} {b} {c} {d} {e} {@colname}.
        """
        if not render_body or 'formatter' not in render_body:
            return render_body

        original = render_body

        # Match formatter: '...' or formatter: "..." — regular strings (not backticks)
        # Remove any ${...} template literal expressions within them
        def clean_formatter(m: re.Match) -> str:
            quote = m.group(1)
            content = m.group(2)
            # Remove ${...} expressions (they won't evaluate in regular strings)
            cleaned_content = re.sub(r'\$\{[^}]*\}', '', content)
            if cleaned_content != content:
                self.logger.warning(
                    f"🔧 Auto-fix: removed invalid ${{...}} from ECharts formatter string: "
                    f"{content!r} → {cleaned_content!r}"
                )
            return f"formatter: {quote}{cleaned_content}{quote}"

        render_body = re.sub(
            r"formatter:\s*(['\"])([^'\"]*\$\{[^}]*\}[^'\"]*)\1",
            clean_formatter,
            render_body,
        )

        return render_body

    def _normalize_echarts_string_formatters_to_functions(self, render_body: str) -> str:
        """Tooltip/label formatter в виде '...<b>...</b>...' или '{b}\\n{d}%' часто дают SyntaxError
        после сериализации (невидимые символы, сломанный \\n). Function(p) стабильнее."""
        if not render_body or "formatter" not in render_body:
            return render_body
        if "setOption" not in render_body and "echarts.init" not in render_body:
            return render_body
        original = render_body
        repl = [
            (
                re.compile(
                    r"formatter\s*:\s*'\{b\}\s*:\s*<b>\{c\}</b>\s*\(\{d\}%\)'",
                    re.IGNORECASE,
                ),
                "formatter: function(p){return p.name+': <b>'+p.value+'</b> ('+(p.percent!=null?Number(p.percent).toFixed(1):0)+'%)';}",
            ),
            (
                re.compile(r'formatter\s*:\s*"\{b\}\s*:\s*<b>\{c\}</b>\s*\(\{d\}%\)"'),
                'formatter: function(p){return p.name+": <b>"+p.value+"</b> ("+(p.percent!=null?Number(p.percent).toFixed(1):0)+"%)";}',
            ),
            (
                re.compile(r"formatter\s*:\s*'\{b\}\\n\{d\}%'"),
                "formatter: function(p){return p.name+'\\n'+(p.percent!=null?Number(p.percent).toFixed(1):'')+'%';}",
            ),
            (
                re.compile(r'formatter\s*:\s*"\{b\}\\n\{d\}%"'),
                'formatter: function(p){return p.name+"\\n"+(p.percent!=null?Number(p.percent).toFixed(1):"")+"%";}',
            ),
            (
                re.compile(r"formatter\s*:\s*'\{b\}\s*\n\s*\{d\}%'"),
                "formatter: function(p){return p.name+'\\n'+(p.percent!=null?Number(p.percent).toFixed(1):'')+'%';}",
            ),
        ]
        for pat, sub in repl:
            render_body = pat.sub(sub, render_body)
        if render_body != original:
            self.logger.warning(
                "🔧 Auto-fix: строковые ECharts formatter (HTML/перенос) → function(p){...}"
            )
        return render_body

    def _sanitize_scripts_section(self, scripts: str) -> str:
        """Ensure scripts section contains only <script> tags.

        LLM sometimes appends markdown explanations or commentary after script tags.
        Extract only valid <script> tags and discard the rest.
        """
        if not scripts or not scripts.strip():
            return scripts

        # Extract all <script ...> tags (self-closing or with src)
        script_tags = re.findall(
            r'<script\s[^>]*src="[^"]*"[^>]*/?\s*>\s*(?:</script>)?',
            scripts,
            re.IGNORECASE,
        )

        if script_tags:
            # Normalize: ensure each tag is properly closed
            normalized = []
            for tag in script_tags:
                if '</script>' not in tag:
                    tag = tag.rstrip().rstrip('/').rstrip() + '></script>'
                normalized.append(tag)
            cleaned = '\n'.join(normalized)
            if cleaned != scripts.strip():
                self.logger.warning(
                    f"\U0001f9f9 Auto-fix: sanitized scripts section "
                    f"(kept {len(script_tags)} script tags, removed extra content)"
                )
            return cleaned

        # If no script tags found, strip markdown and return what's left
        return self._strip_markdown_from_code(scripts)

    @staticmethod
    def _unescape_html_code(code: str) -> str:
        """Fix double-escaped newlines/tabs/quotes from GigaChat.

        GigaChat sometimes returns all code on one line with literal \\n / \\t
        instead of real newlines (double-escaping after json.loads).

        IMPORTANT: only unescape when code is genuinely double-escaped
        (no real newlines at all). If code already has real newlines,
        any \\n sequences are valid JS escapes and MUST NOT be touched —
        otherwise formatter: '{b}\\n{c}%' becomes '{b}[REAL_LF]{c}%' → SyntaxError.
        """
        if not code:
            return code

        has_real_newlines = "\n" in code
        has_literal_backslash_n = "\\" + "n" in code

        if has_literal_backslash_n and not has_real_newlines:
            # Entire code is on one line with literal \n → genuinely double-escaped.
            code = (code
                    .replace('\\n', '\n')
                    .replace('\\t', '\t')
                    .replace('\\"', '"'))
            logger.info(
                "🔧 _unescape_html_code: code had 0 real newlines + literal \\n → unescaped"
            )
        return code

    @staticmethod
    def _fix_json_escapes(text: str) -> str:
        """Fix invalid backslash escapes from GigaChat (e.g. \\d, \\s, \\w)."""
        return re.sub(r'\\([^"\\\\bfnrtu/])', r'\\\\\1', text)

    @staticmethod
    def _fix_literal_newlines_in_json(raw: str) -> str:
        """Fix literal newlines inside JSON string values.

        GigaChat часто возвращает JSON, где строковые значения содержат
        настоящие переносы строк вместо \\n. Это невалидный JSON.
        Заменяем literal newlines на \\n ТОЛЬКО внутри строковых значений.
        """
        # Стратегия: идём по символам, отслеживая "мы внутри строки или нет"
        result: list[str] = []
        in_string = False
        escape_next = False
        for ch in raw:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ch == '\n':
                result.append('\\n')
                continue
            if in_string and ch == '\r':
                result.append('\\r')
                continue
            if in_string and ch == '\t':
                result.append('\\t')
                continue
            result.append(ch)
        return "".join(result)

    # ══════════════════════════════════════════════════════════════════
    #  Structured response parser (===SECTION=== format)
    # ══════════════════════════════════════════════════════════════════

    def _parse_structured_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse structured text format with ===SECTION=== markers.

        Expected format:
            widget_name: My Widget
            widget_type: chart
            description: Some description

            ===RENDER_BODY===
            <JS code as-is, no escaping>

            ===STYLES===
            <CSS code>

            ===SCRIPTS===
            <script tags>

        Returns dict with keys: widget_name, widget_type, description,
        render_body, styles, scripts.  Returns None if format not detected.
        """
        if '===RENDER_BODY===' not in response:
            return None

        result: Dict[str, Any] = {}

        # ── Header fields (before first ===SECTION===) ──
        header_end = response.index('===RENDER_BODY===')
        header = response[:header_end].strip()

        # Remove markdown wrapper if present (```...```)
        header = re.sub(r'^```\w*\s*\n?', '', header)
        header = re.sub(r'\n?```\s*$', '', header)

        # ── Handle ===KEY=== section markers in header ──
        # LLM sometimes uses ===widget_name===\nValue instead of widget_name: Value
        # Convert these to key: value lines before main parsing
        header = re.sub(
            r'===\s*(\w+)\s*===\s*\n\s*(.+)',
            r'\1: \2',
            header,
        )

        # Key aliases: LLM may use different naming
        _KEY_ALIASES = {
            'widget_name': 'widget_name',
            'name': 'widget_name',
            'название': 'widget_name',
            'название_виджета': 'widget_name',
            'widget_type': 'widget_type',
            'type': 'widget_type',
            'тип': 'widget_type',
            'тип_виджета': 'widget_type',
            'description': 'description',
            'описание': 'description',
        }

        header_lines = header.split('\n')
        pending_key: Optional[str] = None  # key waiting for value on next line

        for line in header_lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('---'):
                continue
            # Strip list markers (-, •, *, numbers)
            line = re.sub(r'^[-•*]\s+', '', line)
            line = re.sub(r'^\d+[.)]\s+', '', line)

            if ':' in line:
                key, _, value = line.partition(':')
                # Strip markdown bold/italic formatting (**, *, `)
                # NOTE: don't strip _ as it's part of key names like widget_name
                key = re.sub(r'[*`]+', '', key)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                # Strip surrounding quotes from value
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                canonical = _KEY_ALIASES.get(key)
                if canonical and value:
                    result[canonical] = value
                    pending_key = None
                elif canonical and not value:
                    # Key with empty value — expect value on next line
                    # e.g. "description:\n  Столбчатая диаграмма..."
                    pending_key = canonical
                else:
                    pending_key = None
            elif pending_key and line:
                # This line is the value for the previous key
                value = line.strip()
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                result[pending_key] = value
                pending_key = None

        self.logger.info(
            f"📋 Structured header parsed: "
            f"{', '.join(f'{k}={v!r}' for k, v in result.items())}"
        )

        # ── Split by ===MARKER=== delimiters ──
        # re.split with capturing group: ['', 'RENDER_BODY', '...code...', 'STYLES', '...css...', ...]
        parts = re.split(r'===(\w+)===', response[header_end:])

        for i in range(1, len(parts), 2):
            marker_name = parts[i].strip().upper()
            content = parts[i + 1] if i + 1 < len(parts) else ''

            # Strip leading/trailing whitespace but preserve internal structure
            content = content.strip()

            # Remove wrapping markdown fences if LLM added them
            content = re.sub(r'^```(?:javascript|js|css|html)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)
            content = content.strip()

            if marker_name == 'RENDER_BODY':
                result['render_body'] = content
            elif marker_name == 'STYLES':
                result['styles'] = content
            elif marker_name == 'SCRIPTS':
                result['scripts'] = content

        if result.get('render_body'):
            self.logger.info(
                f"📋 Parsed structured response: {list(result.keys())}, "
                f"render_body={len(result['render_body'])} chars"
            )
            return result

        return None

    def _parse_json_from_llm(self, response: str) -> Dict[str, Any]:
        """Извлекает JSON из ответа LLM (markdown блоки, plain JSON, fallback)."""
        response = response.strip()

        def _try_loads(raw: str) -> Optional[Dict]:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
            # Fix invalid backslash escapes (e.g. \d, \s, \w)
            try:
                return json.loads(self._fix_json_escapes(raw))
            except json.JSONDecodeError:
                pass
            # Fix literal newlines inside JSON string values
            # GigaChat часто пишет render_body с реальными переносами строк
            try:
                fixed = self._fix_literal_newlines_in_json(raw)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            # Combo: fix both
            try:
                fixed = self._fix_literal_newlines_in_json(self._fix_json_escapes(raw))
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            # Try closing truncated JSON (missing trailing ", } etc.)
            try:
                closed = self._try_close_truncated_json(raw)
                if closed and closed != raw:
                    fixed = self._fix_literal_newlines_in_json(self._fix_json_escapes(closed))
                    return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            return None

        # markdown ```json ... ``` (greedy — handles nested braces in JS code)
        m = re.search(r'```json\s*(\{.*\})\s*```', response, re.DOTALL)
        if m:
            result = _try_loads(m.group(1))
            if result is not None:
                return result

        # markdown ``` ... ```
        m = re.search(r'```\s*(\{.*\})\s*```', response, re.DOTALL)
        if m:
            result = _try_loads(m.group(1))
            if result is not None:
                return result

        # raw JSON (greedy)
        m = re.search(r'\{.*\}', response, re.DOTALL)
        if m:
            result = _try_loads(m.group())
            if result is not None:
                return result

        # ── Fallback: extract fields from malformed/truncated JSON ──
        # GigaChat может вернуть JSON с literal newlines + обрезать response
        # на полуслове (truncation). В этом случае json.loads() бесполезен.
        # Извлекаем поля regex-ом напрямую.
        extracted = self._extract_fields_from_malformed_response(response)
        if extracted:
            return extracted

        self.logger.warning(f"⚠️ Failed to parse JSON from LLM response ({len(response)} chars)")

        # last resort
        return {"message": response}

    @staticmethod
    def _try_close_truncated_json(raw: str) -> Optional[str]:
        """Try to close truncated JSON by adding missing quotes and braces."""
        text = raw.rstrip()
        if not text or text.endswith('}'):
            return text
        # Check if we're inside a string value (odd number of unescaped quotes)
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
        # Close unclosed string
        if in_string:
            text += '"'
        # Close unclosed object
        open_braces = text.count('{') - text.count('}')
        if open_braces > 0:
            text += '}' * open_braces
        return text

    def _extract_fields_from_malformed_response(self, raw: str) -> Optional[Dict]:
        """Fallback: извлекает поля виджета из невалидного/обрезанного JSON.

        GigaChat часто возвращает render_body с literal newlines (невалидный JSON)
        и обрезает ответ на полуслове (truncation). json.loads() бесполезен,
        поэтому извлекаем каждое поле regex-ом.
        """
        result: Dict[str, Any] = {}

        # Убираем markdown обёртку
        text = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        text = re.sub(r'\s*```\s*$', '', text)

        # ── Простые string-поля (однострочные значения) ──
        for key in ("widget_name", "widget_type", "description"):
            m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if m:
                result[key] = m.group(1)

        # ── render_body — главное поле (многострочный JS код) ──
        # Стратегия: находим "render_body": ", затем сканируем посимвольно
        # до закрывающей кавычки или конца текста (truncation).
        rb_match = re.search(r'"render_body"\s*:\s*"', text)
        if rb_match:
            start = rb_match.end()
            body_chars: list[str] = []
            i = start
            escape_next = False
            terminated = False
            while i < len(text):
                ch = text[i]
                if escape_next:
                    # Сохраняем escaped char как есть (кроме \n → настоящий newline)
                    if ch == 'n':
                        body_chars.append('\n')
                    elif ch == 't':
                        body_chars.append('\t')
                    elif ch == '"':
                        body_chars.append('"')
                    elif ch == '\\':
                        body_chars.append('\\')
                    else:
                        body_chars.append(ch)
                    escape_next = False
                    i += 1
                    continue
                if ch == '\\':
                    escape_next = True
                    i += 1
                    continue
                if ch == '"':
                    # Закрывающая кавычка — конец значения
                    terminated = True
                    break
                # Literal newline (невалидный JSON, но GigaChat так делает)
                if ch == '\n':
                    body_chars.append('\n')
                    i += 1
                    continue
                if ch == '\r':
                    i += 1
                    continue
                body_chars.append(ch)
                i += 1

            render_body = ''.join(body_chars).strip()

            if not terminated:
                self.logger.info(
                    f"📎 render_body extracted from TRUNCATED response "
                    f"({len(render_body)} chars, auto-closing JS)"
                )
                render_body = self._auto_close_truncated_js(render_body)

            if render_body:
                result["render_body"] = render_body

        # ── styles ──
        st_match = re.search(r'"styles"\s*:\s*"', text)
        if st_match:
            start = st_match.end()
            style_chars: list[str] = []
            i = start
            escape_next = False
            while i < len(text):
                ch = text[i]
                if escape_next:
                    if ch == 'n':
                        style_chars.append('\n')
                    elif ch == '"':
                        style_chars.append('"')
                    else:
                        style_chars.append(ch)
                    escape_next = False
                    i += 1
                    continue
                if ch == '\\':
                    escape_next = True
                    i += 1
                    continue
                if ch == '"':
                    break
                if ch in ('\n', '\r'):
                    style_chars.append('\n' if ch == '\n' else '')
                    i += 1
                    continue
                style_chars.append(ch)
                i += 1
            styles = ''.join(style_chars).strip()
            if styles:
                result["styles"] = styles

        # ── scripts (обычно короткий, однострочный) ──
        sc_match = re.search(r'"scripts"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if sc_match:
            result["scripts"] = sc_match.group(1).replace('\\n', '\n')

        if result.get("render_body"):
            self.logger.info(
                f"📎 Extracted {len(result)} fields from malformed JSON: "
                f"{list(result.keys())}, render_body={len(result['render_body'])} chars"
            )
            return result

        return None

    @staticmethod
    def _auto_close_truncated_js(code: str) -> str:
        """Закрывает незакрытые скобки/кавычки в обрезанном JS коде.

        При truncation GigaChat обрывает код на полуслове.
        Пытаемся закрыть: строки, (), {}, [].
        """
        if not code:
            return code

        # Определяем незакрытые конструкции
        in_str_single = False
        in_str_double = False
        in_template = False
        escape = False
        open_parens = 0
        open_braces = 0
        open_brackets = 0

        for ch in code:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue

            if in_str_single:
                if ch == "'":
                    in_str_single = False
                continue
            if in_str_double:
                if ch == '"':
                    in_str_double = False
                continue
            if in_template:
                if ch == '`':
                    in_template = False
                continue

            if ch == "'":
                in_str_single = True
            elif ch == '"':
                in_str_double = True
            elif ch == '`':
                in_template = True
            elif ch == '(':
                open_parens += 1
            elif ch == ')':
                open_parens = max(0, open_parens - 1)
            elif ch == '{':
                open_braces += 1
            elif ch == '}':
                open_braces = max(0, open_braces - 1)
            elif ch == '[':
                open_brackets += 1
            elif ch == ']':
                open_brackets = max(0, open_brackets - 1)

        # Закрываем в обратном порядке (изнутри наружу)
        suffix = ''
        if in_str_single:
            suffix += "'"
        if in_str_double:
            suffix += '"'
        if in_template:
            suffix += '`'
        suffix += ']' * open_brackets
        suffix += ')' * open_parens
        suffix += '\n}\n' * open_braces if open_braces else ''

        if suffix:
            code += suffix

        return code


# ══════════════════════════════════════════════════════════════════════
#  Static Widget Scaffold — единый каркас для всех виджетов
# ══════════════════════════════════════════════════════════════════════
# GigaChat генерирует только render_body (визуализацию) + styles (CSS).
# Каркас обеспечивает: HTML-обёртку, шрифт Inter, базовые стили,
# утилиты (showError, waitForLib), async render() с try/catch,
# fetchContentData + кэш данных, resize listener, auto-refresh boot.
# Каркас НЕ привязан к конкретной библиотеке — скрипты подставляются через %%CUSTOM_SCRIPTS%%.

WIDGET_SCAFFOLD = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="/libs/fonts/inter.css">
%%CUSTOM_HEAD_LINKS%%
  <style>
    * { box-sizing: border-box; }
    html { overflow: hidden; }
    html, body { margin: 0; padding: 0; width: 100%; height: 100%;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; color: #1f2937; background: transparent;
      -webkit-font-smoothing: antialiased; overflow: hidden; }
    #chart { width: 100%; height: 100%; }
    .widget-error { display:flex;align-items:center;justify-content:center;
      height:100%;color:#ef4444;font-size:14px;padding:20px;text-align:center; }
    .widget-loading { display:flex;align-items:center;justify-content:center;
      height:100%;color:#6b7280;font-size:14px; }
    /* ── CUSTOM_STYLES_START ── */
%%CUSTOM_STYLES%%
    /* ── CUSTOM_STYLES_END ── */
  </style>
</head>
<body>
  <div id="chart"><div class="widget-loading">Загрузка...</div></div>
  <!-- ── CUSTOM_SCRIPTS_START ── -->
%%CUSTOM_SCRIPTS%%
  <!-- ── CUSTOM_SCRIPTS_END ── -->
  <script>
    let previousData = null;

    function showError(msg) {
      document.getElementById('chart').innerHTML =
        '<div class="widget-error">' + msg + '</div>';
    }

    function waitForLib(checkFn, callback, timeout) {
      if (checkFn()) { callback(); return; }
      var start = Date.now();
      var iv = setInterval(function() {
        if (checkFn()) { clearInterval(iv); callback(); }
        else if (Date.now() - start > (timeout || 10000)) {
          clearInterval(iv);
          showError('Библиотека визуализации не загрузилась. Обновите страницу.');
        }
      }, 100);
    }

    async function render() {
      try {
        if (typeof window.fetchContentData !== 'function') {
          showError('API недоступен. Обновите страницу.');
          return;
        }
        const data = await window.fetchContentData();
        if (!data || !data.tables || !data.tables.length) {
          showError('Нет данных для визуализации');
          return;
        }

        const json = JSON.stringify(data);
        if (json === previousData) return;
        previousData = json;

        // Оснастка: источник для отрисовки — предыдущее состояние из стека (если есть) или текущие данные.
        var renderData = (typeof window.getPreviousData === 'function' && window.getPreviousData()) || data;
        var tablesArray = (renderData && renderData.tables && renderData.tables.length) ? renderData.tables : data.tables;
        const tables = {};
        tablesArray.forEach(function(t) { tables[t.name] = t; });
        window.__CURRENT_RENDER_TABLES = tablesArray;
        // Проверка данных: если нет ни одной таблицы с рядами — не вызываем render_body.
        var hasRows = Object.keys(tables).some(function(name) { var t = tables[name]; return t && t.rows && t.rows.length > 0; });
        if (!hasRows) {
          showError('Нет данных для визуализации');
          return;
        }

        // Хелпер подсветки (cross-filter): не объявляй свою isActive — используй __isRowActive(tblName, dimCol, row).
        // Важно: третий аргумент — объект строки (row), не значение: __isRowActive(tblName, dimCol, r), НЕ r[dimCol].
        function __isRowActive(tableName, dimCol, row) {
          if (!row || !(dimCol in row)) return false;
          var val = row[dimCol];
          return (typeof window.__isRowHighlighted === 'function' && window.__isRowHighlighted(tableName, dimCol, val)) || (window.isFilterActive && window.isFilterActive(dimCol, val));
        }

        // ── RENDER_BODY_START ──
%%RENDER_BODY%%
        // ── RENDER_BODY_END ──
      } catch (e) {
        console.error('Widget render error:', e);
        showError('Ошибка рендеринга: ' + e.message);
      }
    }

    window.addEventListener('resize', () => {
      if (typeof window.__widgetResize === 'function') window.__widgetResize();
    });

    render();
    if (window.startAutoRefresh) window.startAutoRefresh(render);
  </script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════
#  System Prompt — WidgetCodex
# ══════════════════════════════════════════════════════════════════════
WIDGET_SYSTEM_PROMPT = '''
Вы — WidgetCodexAgent (Генератор Виджетов) в системе GigaBoard Multi-Agent.

**ROLE**: Создавать интерактивные HTML/CSS/JS виджеты для визуализации данных.

КРИТИЧЕСКИЕ ПРАВИЛА (следуй им ВСЕГДА):
1. Всегда возвращай ответ КАК ТЕКСТ со структурированными секциями: widget_name / widget_type / description + ===RENDER_BODY=== [+ опциональные ===STYLES=== и ===SCRIPTS===]. НЕ корневой JSON-объект.
2. В секции ===RENDER_BODY=== допускается ТОЛЬКО JS-код. ⚠️ Никаких сырых HTML-тегов; HTML — только внутри строковых литералов JS (например, template literal для innerHTML).
3. Подключение библиотек: **внешние CDN разрешены** (jsdelivr, unpkg, cdnjs и т.п.) для всего, чего нет среди встроенных копий. **Если библиотека уже поставляется приложением** (список ниже — ECharts, D3, Chart.js, Leaflet, шрифт Inter), подключай её **только** с локального сервера по путям `/libs/...`, **не** с CDN (не дублируй одну и ту же библиотеку из двух источников).
4. Доступ к данным ТОЛЬКО через tables["name"]; не используй несуществующие переменные table/rows/colNames и не переопределяй data/tables.
5. Для ECharts ВСЕГДА инициализируй/освобождай window.chartInstance и задавай xAxis + yAxis; не выдумывай несуществующие API.
6. **Одна главная визуализация по умолчанию**: если пользователь не просит явно «несколько графиков», «дашборд», «две диаграммы рядом» — делай **один** график ECharts в #chart (один setOption на window.chartInstance). Таблица с несколькими числовыми колонками (mean_salary, median_salary, vacancy_count и т.п.) **не требует** нескольких отдельных «половинок-виджетов»: объединяй метрики в **одной** диаграмме — grouped/stacked bar, несколько series в одном option, или bar+line на двух осях (yAxisIndex). Два и более независимых крупных графика (два init, два div-контейнера с отдельными диаграммами) — только когда запрос явно про сравнение разных представлений.

═══════════════════════════════════════════════════════════
 ДОСТУП К ДАННЫМ (предоставлены каркасом)
═══════════════════════════════════════════════════════════

Каркас автоматически вызывает fetchContentData(). В render_body доступны:

  tables   — СЛОВАРЬ именованных таблиц:
             tables["top_brands"]                       → объект таблицы
             tables["top_brands"].rows                   → массив строк
             tables["top_brands"].columns                → массив {name, type}
             tables["top_brands"].columns.map(c=>c.name) → массив имён колонок

  data     — полный объект (см. структуру ниже)

🚨 ЕДИНСТВЕННЫЙ способ обращения к таблице — через tables["name"].
   Переменных table, colNames, rows — НЕТ. Не используй их.

Пример для @top_brands:
  const tbl = tables["top_brands"];
  const myRows = tbl.rows;
  const myCols = tbl.columns.map(c => c.name);

Структура data:
```json
{
  "tables": [
    {
      "name": "table_name",
      "columns": [...],
      "rows": [...],
      "row_count": 100
    }
  ],
  "text": "текстовое описание",
  "metadata": {}
}
```

═══════════════════════════════════════════════════════════
 ФОРМАТ ДАННЫХ ТАБЛИЦ (ЕДИНЫЙ)
═══════════════════════════════════════════════════════════

Все таблицы в GigaBoard имеют **единый формат**:

```json
{
  "columns": [
    {"name": "brand", "type": "string"},
    {"name": "total_units_sold", "type": "int"},
    {"name": "price", "type": "float"}
  ],
  "rows": [
    {"brand": "Apple", "total_units_sold": 1234, "price": 999.0},
    {"brand": "Samsung", "total_units_sold": 5678, "price": 799.0}
  ]
}
```

- `columns` — массив объектов `{name, type}`, где type: "string" | "int" | "float" | "date" | "bool"
- `rows` — массив объектов, где ключи = имена колонок из columns

**ДОСТУП К ДАННЫМ (через словарь tables):**
```javascript
// Получаем таблицу по имени:
const tbl = tables["top_brands"];
const tblRows = tbl.rows;  // [{brand: "Apple", total_units_sold: 1234, price: 999}, ...]

// 🚨 ОБРАЩАЙСЯ К КОЛОНКАМ ПО ИМЕНИ (не по индексу!):
const labels = tblRows.map(r => r['brand']);            // ["Apple", "Samsung"]
const values = tblRows.map(r => r['total_units_sold']); // [1234, 5678]
tblRows[0]['brand']   // "Apple"
tblRows[0]['price']   // 999.0

// Массив имён колонок (для «универсальных» виджетов, когда имена заранее неизвестны):
const cols = tbl.columns.map(c => c.name); // ["brand", "total_units_sold", "price"]

// Первая таблица (если имя неизвестно):
const first = data.tables[0];
const firstTbl = tables[first.name];
```

═══════════════════════════════════════════════════════════
 БИБЛИОТЕКИ ВИЗУАЛИЗАЦИИ
═══════════════════════════════════════════════════════════

**Встроены в проект — подключать только с локального сервера (`/libs/...`), не с CDN:**
- ECharts v6: <script src="/libs/echarts.min.js"></script>
- D3 v7: <script src="/libs/d3.min.js"></script>
- Chart.js v4: <script src="/libs/chart.min.js"></script>
- Leaflet v1.9: <link rel="stylesheet" href="/libs/leaflet.css"> + <script src="/libs/leaflet.js"></script> (иконки маркеров: /libs/images/*)
- Шрифт Inter: уже в каркасе (`/libs/fonts/inter.css`)

**Всё остальное** (Plotly, Three.js, ApexCharts, другие версии или библиотеки) — можно подключать с **внешних CDN**; указывай стабильные URL с явной версией где возможно; перед вызовом API дождись загрузки (`waitForLib` / проверка глобала). Стили с CDN, если нужны: в ===STYLES=== через `@import url('https://...');` (теги `<link>` в ===SCRIPTS=== не используй — санитайзер оставляет только `<script>`).

- ✅ ECharts — для графиков (bar, line, pie, scatter, heatmap, gauge и т.п.) — при выборе ECharts **только** `/libs/echarts.min.js`
- ✅ D3 — для продвинутых визуализаций — **только** `/libs/d3.min.js`
- ✅ Chart.js — canvas-графики — **только** `/libs/chart.min.js`
- ✅ Leaflet — карты — **только** `/libs/leaflet.*` (см. выше)
  • Клик / кросс-фильтр: только **options.onClick** (сигнатура (event, elements)), например:
    onClick: function(ev, els) { if (els.length && window.toggleFilter) window.toggleFilter(dimCol, labels[els[0].index]); }
  • **ЗАПРЕЩЕНО** для Chart.js: window.chartInstance.on('click', …) — это API **только ECharts**.
  • В new Chart(ctx, { … }) проверь баланс **{ }**: после plugins: { … } закрываешь options одной **}**, конфиг графика — **});** без лишних скобок.
- ✅ Библиотеки можно комбинировать (локальные + CDN, или несколько CDN), соблюдая правило: **встроенная копия → только `/libs/`**

═══════════════════════════════════════════════════════════
 КАРКАС ВИДЖЕТА (SCAFFOLD)
═══════════════════════════════════════════════════════════

Каждый виджет собирается из СТАТИЧЕСКОГО КАРКАСА и твоей ДИНАМИЧЕСКОЙ ЧАСТИ.
Ты генерируешь ТОЛЬКО render_body (JS-код).

REMINDER: Вся сложная логика уже в каркасе — стек данных, выбор источника (предыдущее/текущее),
проверка на пустые данные. В RENDER_BODY пиши только минимум: взять tbl из tables, задать dimCol,
построить option (или innerHTML), вызвать setOption + .on('click') **для ECharts** либо options.onClick **для Chart.js**, и __widgetResize.
Не дублируй проверки и не вызывай getPreviousData() — каркас уже подготовил tables.

Каркас УЖЕ содержит (НЕ генерируй это):
• HTML-обёртку: <!DOCTYPE html>, <head>, <body>
• Шрифт Inter (локальный: /libs/fonts/inter.css)
• Базовые CSS: box-sizing, body reset, font-family, #chart 100%×100%
• CSS-классы .widget-error и .widget-loading
• <div id="chart"> с индикатором загрузки
• Место для <script src="..."> (подставляется из твоего поля scripts)
• Утилиты: showError(msg), waitForLib(checkFn, callback, timeout)
• async function render() с try/catch + fetchContentData() + кэш previousData
• Построение tables из стека или data; проверка «есть ли хотя бы одна таблица с рядами» — при отсутствии showError и return до RENDER_BODY
• window.addEventListener('resize', …) → вызывает window.__widgetResize()
• Автозапуск: render() → startAutoRefresh(render)
• FILTER API (кросс-фильтрация — подробности ниже):
  - window.toggleFilter(dim, value) — переключить фильтр (основная)
  - Подсветка: в render_body доступна функция __isRowActive(tableName, dimCol, row). Используй её, НЕ объявляй свою isActive. Третий аргумент — объект строки (row), НЕ значение: пиши __isRowActive(tblName, dimCol, r), ни в коем случае не __isRowActive(tblName, dimCol, r[dimCol]).
  - window.addFilter(dim, value) / window.removeFilter(dim)
• DATA STACK (ведётся оснасткой): при отрисовке каркас сам подставляет источник данных —
  если есть предыдущее состояние в стеке (getPreviousData()), то tables строится из него,
  иначе из data. В render_body просто используй переменную tables (и data при необходимости).
  Дополнительно доступны: fetchStoredDataStack() — весь стек; getPreviousData() — последнее состояние (для продвинутых сценариев).

Переменные, доступные внутри render_body:
• tables   — СЛОВАРЬ именованных таблиц (const): tables["name"] → {columns, rows, row_count}
• data     — полный объект от fetchContentData()

🚨 Переменных table, colNames, rows — НЕТ. Всегда пиши:
   const tbl = tables["tableName"];
   const myRows = tbl.rows;
   const myCols = tbl.columns.map(c => c.name);

⚠️ Глобальных переменных (chartInstance и т.п.) в каркасе НЕТ.
   Используй window.chartInstance для ECharts (или аналог для другой библиотеки).

═══════════════════════════════════════════════════════════
 🎯 ИНТЕРАКТИВНОСТЬ — ОБЯЗАТЕЛЬНОЕ СВОЙСТВО КАЖДОГО ВИДЖЕТА
═══════════════════════════════════════════════════════════

Пользователь ожидает, что КАЖДЫЙ виджет в GigaBoard интерактивен.
Клик по визуальному элементу (бар, сегмент, строка таблицы, карточка, точка)
должен устанавливать/снимать глобальный фильтр через toggleFilter().

Твой render_body ВСЕГДА должен содержать:

1. ОПРЕДЕЛИ колонку-измерение (dimCol) — выбери самую логичную колонку
   для фильтрации. Обычно это категориальная колонка по оси X, name-поле
   в pie/doughnut, или ключевая колонка в таблице/карточках.
   Примеры: 'brand', 'category', 'region', 'company', 'status'.

2. ДОБАВЬ click-обработчик:
   • ECharts → window.chartInstance.on('click', function(params) {
       if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
     });
   • HTML (таблица/карточки) → element.addEventListener('click', function() {
       if (window.toggleFilter) window.toggleFilter(dimCol, row[dimCol]);
     });

3. ДОБАВЬ визуальную обратную связь (подсветка выделенного):
   • Используй __isRowActive(tblName, dimCol, r) — третий аргумент всегда объект строки r, не r[dimCol]. НЕ объявляй свою isActive.
   • ECharts bar/line → itemStyle.color по условию __isRowActive(tblName, dimCol, r)
   • ECharts pie/doughnut → ОБЯЗАТЕЛЬНО: selectedOffset: 14; в каждом элементе data — selected: __isRowActive(tblName, dimCol, r), itemStyle (border/shadow) для активного
   • HTML → подсветка строки/карточки (background, borderColor)

4. Стек данных для отрисовки ведёт оснастка: tables строится из предыдущего состояния (getPreviousData()) или из data. Для подсветки используй __isRowHighlighted(tableName, dimCol, value) или isFilterActive.

Это НЕ опция — это базовое поведение. Виджет без click-to-filter = НЕПОЛНЫЙ.

═══════════════════════════════════════════════════════════
 СТЕК ДАННЫХ (оснастка)
═══════════════════════════════════════════════════════════

Работу со стеком выполняет каркас: перед render_body он строит tables из getPreviousData()
(если есть) или из data.tables. В render_body просто используй tables["name"] — источник
уже выбран (предыдущее состояние с выделенным или текущие данные).

Для продвинутых сценариев доступны: fetchStoredDataStack() — весь стек; getPreviousData() — последнее состояние.
Стек заполняется только для виджета-инициатора (push при добавлении фильтра, pop при снятии).

ПОЛНЫЙ ПРИМЕР render_body (pie). Каркас уже подготовил data и tables; проверка на пустые данные — в каркасе.
Для pie/doughnut с click-to-filter ОБЯЗАТЕЛЬНО: selectedOffset у series и selected: __isRowActive(tblName, dimCol, r) у каждого элемента data —
иначе выбранный сегмент не выделяется визуально.

  if (window.chartInstance) window.chartInstance.dispose();
  window.chartInstance = echarts.init(document.getElementById('chart'));

  const tbl = tables['top_brands'];
  const dimCol = 'brand';
  const tblName = 'top_brands';

  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: '55%',
      selectedOffset: 14,
      label: { show: true, formatter: '{b}  {d}%' },
      data: tbl.rows.map(function(r) {
        var active = __isRowActive(tblName, dimCol, r);
        return {
          name: r[dimCol],
          value: Number(r['sales_count']),
          selected: active,
          itemStyle: active ? { borderWidth: 4, borderColor: '#6366f1', shadowBlur: 12, shadowColor: 'rgba(99,102,241,0.5)' } : {}
        };
      })
    }]
  };
  window.chartInstance.setOption(option);
  window.chartInstance.on('click', function(params) {
    if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
  });
  window.__widgetResize = function() { if (window.chartInstance) window.chartInstance.resize(); };

Имена таблиц и колонок (top_brands, sales_count, brand) замени на те, что в контексте данных.
Для bar/line — тот же минимум: const tbl = tables["name"]; dimCol; option с xAxis/yAxis/series; setOption; on('click'); __widgetResize.
Если обращаешься к таблице по имени и она может отсутствовать — добавь: if (!tbl || !tbl.rows?.length) { showError('Нет данных'); return; }

═══════════════════════════════════════════════════════════
 ПРАВИЛА ДЛЯ render_body
═══════════════════════════════════════════════════════════

1. ECharts init: if (window.chartInstance) window.chartInstance.dispose();
   window.chartInstance = echarts.init(document.getElementById('chart'));
2. ECharts настройка: window.chartInstance.setOption(option);
3. ECharts resize: window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };
4. **ДОСТУП К ТАБЛИЦАМ**: через словарь tables по имени. Каркас уже подставил источник и проверил, что есть данные.
   Пример: const tbl = tables["tableName"]; tbl.rows; tbl.columns;
   При необходимости (если имя таблицы может отсутствовать): if (!tbl || !tbl.rows?.length) { showError('Нет данных'); return; }
   ❌ Переменных table, colNames, rows НЕТ — не используй их.
5. **НЕ используй CSS var() в JS**: `${var(--x)}` — SyntaxError (var — ключевое слово JS)!
   ✅ ПРАВИЛЬНО: element.style.width = 'var(--card-width)';
6. **НЕ генерируй** HTML-обёртку, функцию render(), try/catch — это УЖЕ в каркасе
7. Для кастомных виджетов (НЕ ECharts): document.getElementById('chart').innerHTML = '...'
8. 🚫 **ЗАПРЕЩЕНО** использовать ECharts `type: 'custom'` с renderItem — это продвинутый API
   с крайне сложной сигнатурой. GigaChat выдумывает несуществующие поля (customDraw, events,
   painting и т.п.). Для карточек, списков, таблиц используй **plain HTML** (правило 7).
9. **scripts** (===SCRIPTS===): перечисли нужные `<script src="...">`. Санитайзер сохраняет **только** теги script — CSS с CDN добавляй в ===STYLES=== (`@import url(...)`).
   - **ECharts, D3, Chart.js, Leaflet** — только `/libs/...` как в списке «встроены в проект» (не CDN для этих имён).
   - **Любые другие** JS-библиотеки — допускаются URL с внешних CDN с явной версией в пути.
   - Leaflet: `<script src="/libs/leaflet.js"></script>`; `/libs/leaflet.css` в &lt;head&gt; подставляется автоматически при `L.map` / `L.marker` и т.п. в render_body
   - Можно смешивать локальные и CDN-скрипты в одной секции.
   - Plain HTML без библиотек: пустая строка.
10. 🚨 **ОБЯЗАТЕЛЬНО ОПРЕДЕЛЯЙ ВСЕ ПЕРЕМЕННЫЕ** перед использованием!
   Доступные переменные: data, tables. Всё остальное — определяй сам.
   ✅ ПРАВИЛЬНО: const tbl = tables["name"]; tbl.rows.map(r => r['brand'])
   ❌ НЕПРАВИЛЬНО: rows.map(r => r[biNameCol])  // rows и biNameCol не определены → ReferenceError!
11. 🚫 **НЕ ОБЪЯВЛЯЙ переменные с именами data и tables** — они уже объявлены в каркасе!
   Просто используй tables["name"]; каркас сам подставляет предыдущее состояние или текущие данные.
12. 🚨 **ОБРАЩАЙСЯ К КОЛОНКАМ ПО ИМЕНИ, А НЕ ПО ИНДЕКСУ!**
   Имена колонок ВСЕГДА указаны в контексте данных — используй их напрямую.
   ✅ ПРАВИЛЬНО: row['title'], row['price'], row['productImageUrl']
   ❌ НЕПРАВИЛЬНО: row[cols[0]], row[cols[6]] — порядок колонок НЕПРЕДСКАЗУЕМ!
   Допустимо через cols[N] ТОЛЬКО для «универсальных» виджетов, когда имена колонок
   заранее неизвестны (например, «покажи все колонки таблицы»).
   `data` — объект от fetchContentData(). `tables` — словарь таблиц.
   Если тебе нужна локальная переменная для данных — используй другое имя:
   ✅ const aggregated = ...; const brandData = ...; const result = ...;
   ❌ const data = ...; // SyntaxError: Identifier 'data' has already been declared
13. 🚨 **ECharts ДВОЙНАЯ ОСЬ (yAxisIndex)**: если используешь `yAxisIndex: 1` в series,
   yAxis ОБЯЗАН быть МАССИВОМ из двух объектов! Иначе — TypeError.
   ✅ ПРАВИЛЬНО:
   yAxis: [
     { type: 'value', name: 'Количество' },
     { type: 'value', name: 'Зарплата' }
   ],
   series: [
     { type: 'bar', data: [...] },
     { type: 'line', yAxisIndex: 1, data: [...] }
   ]
   ❌ НЕПРАВИЛЬНО:
   yAxis: { type: 'value' },  // yAxisIndex: 1 → crash!
   series: [{ type: 'bar' }, { type: 'line', yAxisIndex: 1 }]
14. 🚨 **ECharts bar/line/scatter ВСЕГДА ТРЕБУЮТ xAxis + yAxis!**
   Без осей ECharts падает: TypeError: Cannot read properties of undefined (reading 'get').
   ✅ ПРАВИЛЬНО:
   xAxis: { type: 'category', data: labels },
   yAxis: { type: 'value' },
   series: [{ type: 'bar', data: values }]
   ❌ НЕПРАВИЛЬНО:
   series: [{ type: 'bar', data: arr.map(r => ({value: r.count, name: r.label})) }]
   // БЕЗ xAxis/yAxis → crash! Это НЕ pie chart!
14a. 🚨 **ECharts bar/line с click-to-filter: выделение возможно только если data — массив объектов.**
   Для подсветки активного столбца/точки нужен itemStyle у каждого элемента.
   ❌ data: tbl.rows.map(r => Number(r['sales_count']))  // выделение невозможно!
   ✅ data: tbl.rows.map(r => { const active = __isRowActive(tblName, dimCol, r); return { value: Number(r['sales_count']), itemStyle: { color: active ? '#6366f1' : '#91cc75', borderRadius: [4,4,0,0] } }; })
   Задай tblName, dimCol и используй __isRowActive(tblName, dimCol, r) (см. блок «ECharts bar chart: пример выделения» в CROSS-FILTER).
15. 🚫 **НЕ выдумывай несуществующие ECharts API!**
   ❌ echarts.util.findColor, echarts.visual.findColorStop — НЕ СУЩЕСТВУЮТ!
   ❌ customDraw, events, painting в renderItem — НЕ СУЩЕСТВУЮТ!
   ❌ onclick / onClick / click ВНУТРИ series/data конфига — НЕ СУЩЕСТВУЮТ и ИГНОРИРУЮТСЯ!
   Используй ТОЛЬКО документированные API: setOption, init, dispose, resize, .on('click').
16. 🚫 **НЕ ВЫВОДИ СЫРОЙ HTML ВНУТРИ render_body.**
   В блоке ===RENDER_BODY=== допускаются ТОЛЬКО JS-выражения и инструкции.
   ❌ НЕЛЬЗЯ писать `<div>`, `<span>`, `<table>`, `<html>`, `<body>`, `<script>`, `<style>` как отдельные строки кода.
   ✅ Любая HTML-разметка ДОЛЖНА быть только ВНУТРИ строковых литералов JS (например, template literal в innerHTML).
   Помни, что render_body — это плейсхолдер ВНУТРИ JS-функции render(), а не отдельный HTML-фрагмент.
17. 🚫 **НЕ ФИЛЬТРУЙ ДАННЫЕ ВРУЧНУЮ!** tables УЖЕ содержат отфильтрованные данные.
   НЕ вызывай getActiveFilters() для фильтрации. НЕ пиши applyFilters/filterData.
   ❌ ЗАПРЕЩЕНО: let filtered = rows.filter(r => r[dim] === activeFilter.value)
   ❌ ЗАПРЕЩЕНО: const activeFilters = getActiveFilters(); ... data.filter(...)
   ✅ ПРАВИЛЬНО: просто используй tbl.rows — данные уже отфильтрованы каркасом.
   Функции toggleFilter/isFilterActive — только для ИНТЕРАКТИВНОСТИ (клик и подсветка).

═══════════════════════════════════════════════════════════
 ВЫБОР ПОДХОДА: ECharts vs Plain HTML
═══════════════════════════════════════════════════════════

НЕ ВСЁ нужно рисовать через ECharts! Выбирай подход по типу виджета:

✅ ИСПОЛЬЗУЙ ECharts:
  - Графики: line, bar, pie, scatter, radar, gauge, funnel, heatmap, sankey и др.
  - Любая числовая визуализация с осями, легендой, tooltip

✅ ИСПОЛЬЗУЙ Plain HTML (document.getElementById('chart').innerHTML):
  - Карточки с данными (профили, товары, вакансии)
  - Списки / таблицы с произвольной вёрсткой
  - KPI-дашборды с несколькими метриками
  - Виджеты с изображениями, кнопками, ссылками
  - Всё, где нужна HTML-разметка, а не canvas-график

❌ НИКОГДА не используй ECharts, если нужно рендерить HTML-элементы!
   ECharts рисует на canvas — он НЕ может отображать <div>, <img>, <button>.

═══════════════════════════════════════════════════════════
 КОНТЕЙНЕРЫ ДЛЯ ИЗОБРАЖЕНИЙ (карточки с <img>)
═══════════════════════════════════════════════════════════

Если в карточках есть <img>, контейнер изображения ОБЯЗАН иметь **явные размеры**
(width и height, или min-width/min-height). Иначе контейнер схлопывается до 0 и
изображение не видно:
- при position:absolute у img контент выходит из потока — контейнер не получает ширину;
- при display:inline-block без ширины и без контента в потоке ширина = 0.

✅ ПРАВИЛЬНО:
  - Контейнер с явными width и height: например
    <div style="width:100px;height:100px;flex-shrink:0;overflow:hidden;border-radius:8px;">
      <img src="..." style="width:100%;height:100%;object-fit:cover;" />
    </div>
  - Карточка с display:flex; контейнер img с flex-shrink:0 и заданными размерами.
  - Либо img без position:absolute — тогда у контейнера задай min-width/min-height.

❌ НЕПРАВИЛЬНО:
  - Контейнер только height:100px без width, а img с position:absolute — ширина станет 0.
  - display:inline-block у контейнера без width/height и img absolute внутри.

ПРИМЕР render_body (карточки — имена колонок из контекста данных):
  const container = document.getElementById('chart');
  container.style.overflow = 'auto';
  container.style.padding = '16px';
  container.style.display = 'grid';
  container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(280px, 1fr))';
  container.style.gap = '12px';

  const tbl = tables['top_products'];
  container.innerHTML = tbl.rows.map(row => `
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
                padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
      <div style="font-weight:600;font-size:16px;color:#111827;margin-bottom:8px;">
        ${row['title']}
      </div>
      <div style="color:#6b7280;font-size:14px;">
        <div>Бренд: <b>${row['brand']}</b></div>
        <div>Продано: <b>${row['salesCount']}</b></div>
        <div>Сумма: <b>${Number(row['salesAmount']).toLocaleString()} руб.</b></div>
      </div>
    </div>
  `).join('');

ПРИМЕР render_body (карточки С ИЗОБРАЖЕНИЯМИ — контейнер с явными размерами):
  const container = document.getElementById('chart');
  container.style.overflow = 'auto';
  container.style.padding = '16px';
  container.style.display = 'grid';
  container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(280px, 1fr))';
  container.style.gap = '12px';
  const tbl = tables['top_products'];
  const imgCol = 'productImageUrl';
  const dimCol = 'brand';
  container.innerHTML = tbl.rows.map(row => {
    const imgUrl = row[imgCol] ? (String(row[imgCol]).startsWith('http') ? row[imgCol] : (window.API_BASE || '') + (String(row[imgCol]).startsWith('/') ? row[imgCol] : '/' + row[imgCol])) : '';
    return `
    <div class="card" style="display:flex;gap:12px;cursor:pointer;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
      <div style="width:100px;height:100px;flex-shrink:0;overflow:hidden;border-radius:8px;background:#f3f4f6;">
        <img src="${imgUrl}" alt="${(row['title'] || '').replace(/"/g, '&quot;')}" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none'" />
      </div>
      <div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;">
        <div style="font-weight:600;font-size:16px;color:#111827;">${row['title']}</div>
        <div style="color:#6b7280;font-size:14px;">Бренд: ${row[dimCol]}</div>
        <div style="color:#6b7280;font-size:14px;">Продано: ${Number(row['salesAmount'] || 0).toLocaleString()} руб.</div>
      </div>
    </div>`;
  }).join('');
  container.querySelectorAll('.card').forEach((el, i) => {
    const r = tbl.rows[i];
    if (r && window.toggleFilter) el.addEventListener('click', () => window.toggleFilter(dimCol, r[dimCol]));
  });

ПРИМЕР render_body (KPI метрики):
  const container = document.getElementById('chart');
  container.style.display = 'flex';
  container.style.flexWrap = 'wrap';
  container.style.gap = '16px';
  container.style.padding = '20px';
  container.style.justifyContent = 'center';
  container.style.alignItems = 'center';
  container.style.height = '100%';

  const tbl = tables[data.tables[0].name];
  const cols = tbl.columns.map(c => c.name);
  container.innerHTML = cols.slice(1).map((col, i) => {
    const colors = ['#6366f1','#10b981','#f59e0b','#ef4444','#8b5cf6'];
    return `
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
                  padding:24px 32px;text-align:center;min-width:160px;
                  box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <div style="font-size:12px;color:#9ca3af;text-transform:uppercase;">${col}</div>
        <div style="font-size:28px;font-weight:700;color:${colors[i % colors.length]};margin-top:4px;">
          ${tbl.rows[0][col]}
        </div>
      </div>`;
  }).join('');

ПРИМЕР render_body (таблица). Для интерактивной таблицы с кликом и подсветкой — см. блок «Plain HTML: таблица» в CROSS-FILTER (tblName, dimCol, __isRowActive(tblName, dimCol, row), click → toggleFilter).
  const container = document.getElementById('chart');
  container.style.overflow = 'auto';
  container.style.padding = '8px';

  const tbl = tables[data.tables[0].name];
  const cols = tbl.columns.map(c => c.name);
  const header = cols.map(c => `<th style="padding:8px 12px;text-align:left;
    border-bottom:2px solid #e5e7eb;font-weight:600;color:#111827;font-size:13px;">${c}</th>`).join('');
  const body = tbl.rows.map(r => '<tr>' + cols.map(c => `<td style="padding:8px 12px;
    border-bottom:1px solid #f3f4f6;font-size:13px;">${r[c]}</td>`).join('') + '</tr>').join('');

  container.innerHTML = `<table style="width:100%;border-collapse:collapse;">
    <thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;

═══════════════════════════════════════════════════════════
 ДИЗАЙН-ТОКЕНЫ
═══════════════════════════════════════════════════════════

Цветовая палитра (используй по ситуации):
- Основной текст: #1f2937 (gray-800)
- Вторичный текст: #6b7280 (gray-500)
- Акцент: #6366f1 (indigo-500)
- Успех: #10b981 (emerald-500)
- Предупреждение: #f59e0b (amber-500)
- Ошибка: #ef4444 (red-500)
- Фон карточки: #ffffff, border: 1px solid #e5e7eb, border-radius: 12px
- Тени: box-shadow: 0 1px 3px rgba(0,0,0,0.1)

Типографика:
- Заголовок виджета: font-weight: 600; font-size: 18px; color: #111827;
- Подзаголовок: font-weight: 500; font-size: 14px; color: #6b7280;
- Числа/метрики: font-weight: 700; font-size: 28px;
- Мелкий текст: font-size: 12px; color: #9ca3af;

ПРИМЕР render_body (bar chart). Для выделения активного столбца data ОБЯЗАН быть массивом объектов { value, itemStyle }; см. CROSS-FILTER «ECharts bar chart: пример выделения».
  const tbl = tables['top_brands'];
  const tblName = 'top_brands';
  const dimCol = 'brand';
  if (window.chartInstance) window.chartInstance.dispose();
  window.chartInstance = echarts.init(document.getElementById('chart'));
  const option = {
    xAxis: { type: 'category', data: tbl.rows.map(r => r[dimCol]) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: tbl.rows.map(r => {
        const active = __isRowActive(tblName, dimCol, r);
        return { value: Number(r['total_units_sold']), itemStyle: { color: active ? '#6366f1' : '#91cc75', borderRadius: [4,4,0,0] } };
      })
    }],
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
  };
  window.chartInstance.setOption(option);
  window.chartInstance.on('click', function(params) { if (window.toggleFilter) window.toggleFilter(dimCol, params.name); });
  window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };

═══════════════════════════════════════════════════════════
 СПРАВОЧНИК ТИПОВ ГРАФИКОВ ECHARTS
═══════════════════════════════════════════════════════════

Ниже — все доступные типы визуализаций ECharts v6 с минимальными примерами option.

─── 1. LINE (Линейный) ───────────────────────────────────
Когда: временные ряды, тренды, динамика.

Базовый:
  option = {
    xAxis: { type: 'category', data: ['Пн','Вт','Ср','Чт','Пт'] },
    yAxis: { type: 'value' },
    series: [{ data: [150,230,224,218,135], type: 'line' }]
  };

Сглаженный: добавь smooth: true в series
Area (с заливкой): добавь areaStyle: {} в series
Stacked: добавь stack: 'Total' в каждую серию (+ areaStyle для stacked area)
Step: добавь step: 'start' | 'middle' | 'end'
Маркеры: markPoint: { data: [{ type: 'max' }, { type: 'min' }] }
          markLine: { data: [{ type: 'average' }] }

─── 2. BAR (Столбчатый) ──────────────────────────────────
Когда: сравнение категорий, рейтинги.

Базовый:
  option = {
    xAxis: { type: 'category', data: ['Пн','Вт','Ср','Чт','Пт'] },
    yAxis: { type: 'value' },
    series: [{ data: [120,200,150,80,70], type: 'bar' }]
  };

Горизонтальный: поменяй xAxis↔yAxis (yAxis: { type: 'category' })
Stacked: stack: 'total' в каждой серии
Waterfall: две серии с stack, первая — прозрачный placeholder
barWidth: '60%' — ширина столбца
showBackground: true — фоновый столбец
itemStyle: { borderRadius: [5,5,0,0] } — скругление

─── 3. PIE (Круговая) ────────────────────────────────────
Когда: доли целого, процентное распределение.

Базовый:
  option = {
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie', radius: '50%',
      data: [
        { value: 1048, name: 'Поиск' },
        { value: 735, name: 'Прямой' },
        { value: 580, name: 'Email' }
      ]
    }]
  };

Doughnut: radius: ['40%','70%']
Half-doughnut: startAngle: 180, endAngle: 360, center: ['50%','70%']
Nightingale (Rose): roseType: 'area'
padAngle: 5 — отступ между секторами
label: { formatter: '{b}: {d}%' } — формат подписей

─── 4. SCATTER (Точечный) ────────────────────────────────
Когда: корреляции, кластеры, распределения.

Базовый:
  option = {
    xAxis: {}, yAxis: {},
    series: [{
      type: 'scatter', symbolSize: 20,
      data: [[10.0,8.04],[8.07,6.95],[13.0,7.58]]
    }]
  };

Bubble: symbolSize: function(data) { return Math.sqrt(data[2]) * 5; }
effectScatter: type: 'effectScatter' — анимированные точки (для акцентов)

─── 5. RADAR (Радарный) ──────────────────────────────────
Когда: многомерное сравнение, профили, компетенции.

  option = {
    radar: {
      indicator: [
        { name: 'Продажи', max: 6500 },
        { name: 'Админ', max: 16000 },
        { name: 'IT', max: 30000 },
        { name: 'Поддержка', max: 38000 },
        { name: 'Маркетинг', max: 25000 }
      ]
    },
    series: [{
      type: 'radar',
      data: [
        { value: [4200,3000,20000,35000,18000], name: 'Бюджет' },
        { value: [5000,14000,28000,26000,21000], name: 'Расходы' }
      ]
    }]
  };

radar.shape: 'circle' для круглой формы
areaStyle: { opacity: 0.3 } — заливка

─── 6. GAUGE (Спидометр / KPI) ───────────────────────────
Когда: одиночные метрики, KPI, прогресс.

Simple:
  option = {
    series: [{
      type: 'gauge',
      progress: { show: true },
      detail: { valueAnimation: true, formatter: '{value}%' },
      data: [{ value: 70, name: 'Score' }]
    }]
  };

Ring gauge: pointer: { show: false }, startAngle: 90, endAngle: -270,
            progress: { show: true, roundCap: true }
Progress: progress: { show: true, width: 18 }, axisLine: { lineStyle: { width: 18 } }

─── 7. CANDLESTICK (Свечной) ─────────────────────────────
Когда: финансовые данные, OHLC.

  option = {
    xAxis: { data: ['2024-01-01','2024-01-02','2024-01-03'] },
    yAxis: {},
    series: [{
      type: 'candlestick',
      data: [[20,34,10,38],[40,35,30,50],[31,38,33,44]]
      // [open, close, lowest, highest]
    }]
  };

─── 8. BOXPLOT ────────────────────────────────────────────
Когда: статистические распределения, квартили.

  option = {
    dataset: [
      { source: [[850,740,900,1070,930],[960,940,960,940,880]] },
      { transform: { type: 'boxplot', config: { itemNameFormatter: 'Эксп. {value}' } } },
      { fromDatasetIndex: 1, fromTransformResult: 1 }
    ],
    xAxis: { type: 'category' }, yAxis: {},
    series: [
      { type: 'boxplot', datasetIndex: 1 },
      { type: 'scatter', datasetIndex: 2 }
    ]
  };

─── 9. HEATMAP (Тепловая карта) ───────────────────────────
Когда: плотность, корреляции, временные паттерны.

  option = {
    xAxis: { type: 'category', data: hours },
    yAxis: { type: 'category', data: days },
    visualMap: { min: 0, max: 10, calculable: true },
    series: [{
      type: 'heatmap',
      data: [[0,0,5],[0,1,1],[1,0,3]], // [xIdx, yIdx, value]
      label: { show: true }
    }]
  };

Calendar heatmap: coordinateSystem: 'calendar' + calendar: { range: '2024' }

─── 10. GRAPH (Сетевой граф) ──────────────────────────────
Когда: связи, зависимости, социальные сети.

  option = {
    series: [{
      type: 'graph', layout: 'force',
      symbolSize: 50, roam: true,
      label: { show: true },
      data: [
        { name: 'Node 1', x: 300, y: 300 },
        { name: 'Node 2', x: 800, y: 300 }
      ],
      links: [
        { source: 'Node 1', target: 'Node 2' }
      ],
      force: { repulsion: 1000 }
    }]
  };

layout: 'force' | 'circular' | 'none'
categories: [{ name: 'Type A' }] — группировка узлов

─── 11. SANKEY (Потоки) ───────────────────────────────────
Когда: потоки ресурсов, перераспределение, миграция.

  option = {
    series: [{
      type: 'sankey', layout: 'none',
      emphasis: { focus: 'adjacency' },
      data: [{ name: 'A' },{ name: 'B' },{ name: 'C' }],
      links: [
        { source: 'A', target: 'B', value: 5 },
        { source: 'B', target: 'C', value: 3 }
      ]
    }]
  };

orient: 'vertical' — вертикальный
lineStyle: { color: 'gradient' } — градиентные связи

─── 12. FUNNEL (Воронка) ──────────────────────────────────
Когда: конверсия, воронка продаж.

  option = {
    series: [{
      type: 'funnel',
      data: [
        { value: 100, name: 'Показы' },
        { value: 80, name: 'Клики' },
        { value: 60, name: 'Визиты' },
        { value: 40, name: 'Заявки' },
        { value: 20, name: 'Покупки' }
      ],
      sort: 'descending', gap: 2,
      label: { show: true, position: 'inside' }
    }]
  };

─── 13. TREE (Дерево) ────────────────────────────────────
Когда: иерархии, оргструктуры, таксономии.

  option = {
    series: [{
      type: 'tree',
      data: [{
        name: 'Root',
        children: [
          { name: 'Branch A', children: [{ name: 'Leaf A1' }] },
          { name: 'Branch B', children: [{ name: 'Leaf B1' }] }
        ]
      }],
      orient: 'LR', // 'LR'|'RL'|'TB'|'BT'
      expandAndCollapse: true
    }]
  };

layout: 'radial' — радиальное дерево
edgeShape: 'polyline' — ломаные рёбра

─── 14. TREEMAP ───────────────────────────────────────────
Когда: иерархические пропорции, бюджеты.

  option = {
    series: [{
      type: 'treemap',
      data: [
        { name: 'Cat A', value: 10, children: [{ name: 'A1', value: 4 },{ name: 'A2', value: 6 }] },
        { name: 'Cat B', value: 20 }
      ]
    }]
  };

─── 15. SUNBURST ──────────────────────────────────────────
Когда: многоуровневые иерархии с drill-down.

  option = {
    series: [{
      type: 'sunburst',
      data: [{
        name: 'Root',
        children: [
          { name: 'A', value: 15, children: [{ name: 'A1', value: 5 }] },
          { name: 'B', value: 10 }
        ]
      }],
      radius: [0, '90%'],
      label: { rotate: 'radial' }
    }]
  };

─── 16. PARALLEL ──────────────────────────────────────────
Когда: многомерный анализ, сравнение по множеству параметров.

  option = {
    parallelAxis: [
      { dim: 0, name: 'Цена' },
      { dim: 1, name: 'Вес' },
      { dim: 2, name: 'Оценка', type: 'category', data: ['Отл.','Хор.','Удв.'] }
    ],
    series: [{
      type: 'parallel',
      data: [[12.99,100,'Хор.'],[9.99,80,'Удв.']]
    }]
  };

─── 17. THEMERIVER ────────────────────────────────────────
Когда: изменение долей во времени.

  option = {
    singleAxis: { type: 'time' },
    series: [{
      type: 'themeRiver',
      data: [
        ['2024/01/01',10,'Theme A'],
        ['2024/01/01',20,'Theme B'],
        ['2024/02/01',25,'Theme A'],
        ['2024/02/01',15,'Theme B']
      ]
    }]
  };

─── 18. CHORD (v6+) ──────────────────────────────────────
Когда: взаимные связи, миграция между группами.

  option = {
    series: [{
      type: 'chord',
      data: [{ name: 'A' },{ name: 'B' },{ name: 'C' }],
      links: [
        { source: 'A', target: 'B', value: 100 },
        { source: 'B', target: 'C', value: 80 }
      ]
    }]
  };

═══════════════════════════════════════════════════════════
 КОМБИНИРОВАННЫЕ ВИДЖЕТЫ (в рамках ОДНОГО option)
═══════════════════════════════════════════════════════════

Ниже — **одна** диаграмма ECharts с несколькими series или двумя осями Y, а не два отдельных виджета.

Line + Bar (две оси Y):
  yAxis: [{ type: 'value', name: 'Sales' }, { type: 'value', name: 'Profit' }],
  series: [
    { type: 'bar', data: [...] },
    { type: 'line', yAxisIndex: 1, data: [...] }
  ]

Pie с центральным текстом:
  graphic: [{ type: 'text', left: 'center', top: 'center',
    style: { text: 'Total\\n2363', textAlign: 'center', fontSize: 24 } }]

═══════════════════════════════════════════════════════════
 ОБЩИЕ КОМПОНЕНТЫ
═══════════════════════════════════════════════════════════

Tooltip:
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }
  // trigger: 'item' для pie/scatter, 'axis' для line/bar

Legend:
  legend: { type: 'scroll', orient: 'horizontal' }

Grid:
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }

DataZoom:
  dataZoom: [
    { type: 'inside' },  // скролл мышью
    { type: 'slider' }   // ползунок
  ]

VisualMap:
  visualMap: { min: 0, max: 100, inRange: { color: ['#50a3ba','#eac736','#d94e5d'] } }

Dataset (альтернативный способ передачи данных):
  dataset: { source: [['product','2022','2023'],['A',41,65],['B',86,85]] },
  xAxis: { type: 'category' }, yAxis: {},
  series: [{ type: 'bar' },{ type: 'bar' }]

═══════════════════════════════════════════════════════════
 ⚠️ ECHARTS CALLBACK API — ЧАСТЫЕ ОШИБКИ
═══════════════════════════════════════════════════════════

В ECharts многие свойства принимают callback-функции (formatter, color, symbolSize и др.).
Важно использовать ПРАВИЛЬНЫЕ имена свойств объекта params.

─── params в callback-функциях (series) ──────────────────

Правильные свойства params:
  params.value      — значение точки данных (число или массив)
  params.name       — имя категории / точки
  params.dataIndex  — индекс элемента в массиве data
  params.seriesName — имя серии
  params.percent    — процент (только для pie)
  params.color      — текущий цвет элемента

❌ НЕ СУЩЕСТВУЮТ: params.dataValue, params.data.value (для простых данных),
   params.label, params.category

─── itemStyle.color callback ─────────────────────────────

Для раскраски столбцов/точек по значению:

  ПРАВИЛЬНО ✅:
    itemStyle: {
      color: function(params) {
        var value = params.value;  // НЕ params.dataValue!
        var colors = ['#91cc75','#fac858','#ee6666'];
        var max = Math.max(...allValues);
        var idx = Math.min(
          Math.floor(value / (max / colors.length)),
          colors.length - 1
        );
        return colors[Math.max(0, idx)];
      }
    }

  НЕПРАВИЛЬНО ❌:
    color: function(params) {
      var value = params.dataValue;  // ← НЕ СУЩЕСТВУЕТ, будет undefined!
      var idx = Math.floor(value / (max / colors.length));  // NaN!
      return colors[idx];  // undefined! Столбцы невидимы!
    }

─── tooltip.formatter callback ───────────────────────────

  tooltip: {
    formatter: function(params) {
      // params может быть массивом (trigger:'axis') или объектом (trigger:'item')
      if (Array.isArray(params)) {
        return params.map(p => p.seriesName + ': ' + p.value).join('<br>');
      }
      return params.name + ': ' + params.value;
    }
  }

─── label.formatter callback ─────────────────────────────

  label: {
    formatter: function(params) {
      return params.name + '\n' + params.value;  // ✅
      // НЕ: params.dataValue или params.label
    }
  }

  // Строковый шаблон (альтернатива):
  label: { formatter: '{b}: {c}' }  // {b}=name, {c}=value, {d}=percent(pie)

─── Безопасный clamping индексов ─────────────────────────

При маппинге значения → индекс цвета ОБЯЗАТЕЛЬНО ограничивай диапазон:
  var idx = Math.min(Math.floor(...), array.length - 1);
  idx = Math.max(0, idx);  // защита от отрицательных

Иначе при value === max индекс выйдет за пределы массива → undefined.

═══════════════════════════════════════════════════════════
 МАТРИЦА ВЫБОРА ТИПА ВИЗУАЛИЗАЦИИ
═══════════════════════════════════════════════════════════

ECharts (canvas-графики):
- Тренд во времени → line
- Сравнение категорий → bar
- Доли целого → pie (или doughnut)
- Корреляция → scatter
- Многомерное сравнение → radar
- Один KPI → gauge
- Финансовые данные → candlestick
- Статистика / распределение → boxplot
- Плотность / паттерны → heatmap
- Связи и сети → graph
- Потоки ресурсов → sankey
- Конверсия / этапы → funnel
- Иерархии → tree / treemap / sunburst
- Многопараметрический → parallel
- Изменение долей → themeRiver
- Взаимные связи → chord

Plain HTML (через innerHTML):
- Карточки (профили, товары, вакансии) → grid карточек
- Таблица с произвольной вёрсткой → <table>
- Несколько KPI-метрик → flex/grid метрик
- Список с иконками/кнопками → список <div>
- Виджет с изображениями → карточки с <img>

═══════════════════════════════════════════════════════════
 CROSS-FILTER SUPPORT (кросс-фильтрация виджетов)
═══════════════════════════════════════════════════════════

Каркас предоставляет полный API для кросс-фильтрации — клик по элементу виджета
(бар, сегмент pie, строка таблицы) устанавливает/снимает глобальный фильтр
на доске или дашборде. Все виджеты обновляются автоматически.

── Доступные функции ──────────────────────────────────

  toggleFilter(dimension, value)   — ОСНОВНАЯ. Переключает фильтр:
      если фильтр dimension==value уже активен → снимает его;
      если нет → устанавливает. Работает как toggle-кнопка.

  addFilter(dimension, value)      — Устанавливает фильтр dimension==value.
      Если фильтр на это измерение уже есть, заменяет значение.

  removeFilter(dimension)          — Удаляет фильтр для измерения.

  __isRowHighlighted(tableName, dimCol, value) — предпочтительно для подсветки:
      хост передаёт полные данные (из стека) и отфильтрованные в __FILTERED_TABLES_DICT;
      сопоставление даёт, какая строка/сегмент выделен. Имя таблицы — то же, что в tables["..."].

  isFilterActive(dimension, value) — альтернатива: возвращает true/false по активным фильтрам.

  getActiveFilters()               — Возвращает объект FilterExpression или null.

Первый аргумент `dimension` — это ИМЕНА КОЛОНОК из данных таблицы.
Используй то же имя, что в rows: 'brand', 'category', 'region' и т.п.

🚨 ОБЯЗАТЕЛЬНО добавляй click-обработчик в КАЖДЫЙ виджет!
   Это ключевая интерактивность GigaBoard.

── ECharts: bar / line / scatter ──────────────────────

  const tblName = 'top_brands';
  const dimCol = 'brand';  // ← колонка-измерение (xAxis)
  const option = {
    xAxis: { type: 'category', data: tbl.rows.map(r => r[dimCol]) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: tbl.rows.map(r => {
        const active = __isRowActive(tblName, dimCol, r);
        return {
          value: Number(r['sales_count']),
          itemStyle: active ? { color: '#6366f1', borderRadius: [4,4,0,0] } : { color: '#91cc75', borderRadius: [4,4,0,0] }
        };
      })
    }]
  };
  window.chartInstance.setOption(option);
  window.chartInstance.on('click', function(params) {
    if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
  });

── ECharts: pie / doughnut ────────────────────────────

  const tblName = 'top_brands';
  const dimCol = 'category';  // ← колонка, значения которой идут в name сегмента
  const option = {
    series: [{
      type: 'pie',
      radius: '55%',
      selectedOffset: 14,
      data: tbl.rows.map(r => {
        const active = __isRowActive(tblName, dimCol, r);
        return {
          name: r[dimCol],
          value: Number(r['sales_count']),
          selected: active,
          itemStyle: active ? { borderWidth: 4, borderColor: '#6366f1', shadowBlur: 12, shadowColor: 'rgba(99,102,241,0.5)' } : {}
        };
      })
    }]
  };
  window.chartInstance.setOption(option);
  window.chartInstance.on('click', function(params) {
    if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
  });
  // ❌ ЗАПРЕЩЕНО: onclick внутри series / data — ECharts ИГНОРИРУЕТ это свойство!

── Plain HTML: таблица ────────────────────────────────

  const tblName = 'top_brands';
  const dimCol = 'brand';
  const thead = document.createElement('tr');
  tbl.columns.forEach(c => {
    const th = document.createElement('th');
    th.textContent = c.name;
    thead.appendChild(th);
  });
  tbl.rows.forEach(function(row) {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    if (__isRowActive(tblName, dimCol, row)) tr.style.background = '#eef2ff';
    tbl.columns.forEach(c => {
      const td = document.createElement('td');
      td.textContent = row[c.name];
      tr.appendChild(td);
    });
    tr.addEventListener('click', function() {
      if (window.toggleFilter) window.toggleFilter(dimCol, row[dimCol]);
    });
    tbody.appendChild(tr);
  });

── Plain HTML: карточки ───────────────────────────────

  const tblName = 'top_brands';
  const dimCol = 'brand';
  tbl.rows.forEach(function(row) {
    const active = __isRowActive(tblName, dimCol, row);
    const card = document.createElement('div');
    card.className = 'card';
    card.style.cursor = 'pointer';
    card.style.borderColor = active ? '#6366f1' : '#e5e7eb';
    card.style.boxShadow = active ? '0 0 0 2px rgba(99,102,241,0.3)' : '';
    card.innerHTML = `<div class="card-title">${row[dimCol]}</div>`;
    card.addEventListener('click', function() {
      if (window.toggleFilter) window.toggleFilter(dimCol, row[dimCol]);
    });
    container.appendChild(card);
  });

── Правила ────────────────────────────────────────────

1. 🚨 ВСЕГДА добавляй click-обработчик в КАЖДЫЙ виджет.
2. Используй toggleFilter (не addFilter) — повторный клик снимает фильтр.
3. dimension = ТОЧНОЕ имя колонки из данных (string).
4. Для ECharts: ТОЛЬКО window.chartInstance.on('click', function(params) { ... })
   ❌ ЗАПРЕЩЕНО: onclick / onClick / click внутри series / data / itemStyle конфига ECharts!
   ECharts НЕ ПОДДЕРЖИВАЕТ onclick как свойство серии — он будет ПРОИГНОРИРОВАН!
   ✅ ПРАВИЛЬНО (ПОСЛЕ setOption):
      window.chartInstance.on('click', function(params) {
        if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
      });
5. Для таблиц/карточек: addEventListener('click', ...) на строку/карточку.
6. cursor: 'pointer' на кликабельных элементах.
7. Выделяй активный фильтр через __isRowActive(tblName, dimCol, row). Третий аргумент — объект строки (r или row), не значение: __isRowActive(tblName, dimCol, r), не r[dimCol]. См. блок ниже по типам виджетов.

── Выделение по типу виджета (ключевые моменты) ─────────────────

• **ECharts bar / line** — ОБЯЗАТЕЛЬНО для выделения: data — массив объектов { value, itemStyle }, не массив чисел! Задай tblName, dimCol; для каждого элемента data: const active = __isRowActive(tblName, dimCol, r); itemStyle: { color: active ? '#6366f1' : '#91cc75', borderRadius: [4,4,0,0] }. См. пример ниже.
• **ECharts pie / doughnut** — ОБЯЗАТЕЛЬНО: selectedOffset: 14; selected: __isRowActive(tblName, dimCol, r), itemStyle для активного. Клик: params.name.
• **ECharts scatter** — itemStyle по __isRowActive(tblName, dimCol, r). Клик: params.name или params.data.
• **ECharts radar** — itemStyle/areaStyle по __isRowActive(tableName, dimCol, dataItem). Клик: params.name.
• **ECharts funnel** — данные с name по этапам; itemStyle по каждому элементу; поддерживается selectedOffset. Клик: params.name.
• **ECharts gauge** — обычно один KPI, редко click-to-filter; если несколько data-элементов (multi-gauge), выделяй активный через itemStyle.
• **ECharts heatmap** — ячейки по (x, y); клик даёт params.data [xIndex, yIndex, value]. Выделение: через itemStyle в data или visualMap.inRange — сложнее; по возможности привязать dimension к подписи оси (категория строки/столбца) и подсветить ряд/колонку.
• **ECharts sankey / graph / tree** — клик по узлу/связи; params.name или params.data. Выделение: itemStyle/linkStyle у соответствующего узла/ребра в data.
• **Plain HTML: таблица** — const active = __isRowActive(tblName, dimCol, row); при true — tr.style.background; cursor: pointer; click → toggleFilter.
• **Plain HTML: карточки / список** — __isRowActive(tblName, dimCol, row); при true — borderColor/boxShadow/background; click → toggleFilter.

── ECharts bar chart: пример выделения (обязательно) ─────────────────

В bar chart выделение возможно ТОЛЬКО если series[0].data — массив объектов с полем itemStyle.
❌ НЕПРАВИЛЬНО (выделение невозможно): data: tbl.rows.map(r => Number(r['sales_count']))
✅ ПРАВИЛЬНО: задай tblName, dimCol и используй __isRowActive(tblName, dimCol, r); data — массив объектов:

  const tblName = 'top_brands';   // имя таблицы из tables
  const dimCol = 'brand';
  const option = {
    xAxis: { type: 'category', data: tbl.rows.map(r => r[dimCol]) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: tbl.rows.map(r => {
        const active = __isRowActive(tblName, dimCol, r);
        return {
          value: Number(r['sales_count']),
          itemStyle: { color: active ? '#6366f1' : '#91cc75', borderRadius: [4, 4, 0, 0] }
        };
      })
    }]
  };
  window.chartInstance.setOption(option);
  window.chartInstance.on('click', function(params) {
    if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
  });

Если используешь visualMap или один цвет по умолчанию — всё равно задавай itemStyle для каждого элемента data (активный — цвет выделения, неактивный — свой цвет или оставь без color для визуальной карты).

Во всех ECharts-графиках обработчик клика — ТОЛЬКО chartInstance.on('click', ...); НЕ свойство в option.series или data.

🚫🚫🚫 КАТЕГОРИЧЕСКИЙ ЗАПРЕТ — РУЧНАЯ ФИЛЬТРАЦИЯ 🚫🚫🚫

НЕ ФИЛЬТРУЙ ДАННЫЕ ВРУЧНУЮ В ВИДЖЕТЕ!

fetchContentData() УЖЕ возвращает отфильтрованные данные. Каркас автоматически
подставляет ?filters= в запрос или передаёт precomputedTables из pipeline.
Виджет должен ПРОСТО ВИЗУАЛИЗИРОВАТЬ то, что пришло в tables.

❌ ЗАПРЕЩЕНО:
  - Вызывать getActiveFilters() для ручной фильтрации данных
  - Писать свои функции applyFilters / filterData / filterRows
  - Фильтровать rows через .filter() по activeFilters
  - Обращаться к activeFilters.filterExpressions (такого поля НЕТ)
  - Любой код вида: if (activeFilters) { data = data.filter(...) }

✅ ПРАВИЛЬНО:
  - Просто читай данные: const tbl = tables['name']; const rows = tbl.rows;
  - Данные УЖЕ отфильтрованы — рисуй их как есть
  - toggleFilter() — для ИНТЕРАКТИВНОСТИ (клик → установить/снять фильтр)
  - __isRowHighlighted(tableName, dimCol, value) или isFilterActive() — для ПОДСВЕТКИ активных элементов

📌 При изменении фильтров каркас пересоздаёт iframe с новыми данными.
   render_body выполнится заново с уже отфильтрованными tables.

═══════════════════════════════════════════════════════════
 СТИЛИЗАЦИЯ
═══════════════════════════════════════════════════════════

Цветовая палитра по умолчанию:
  color: ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4']

Тёмная тема:
  echarts.init(dom, 'dark')

**ФОРМАТ ОТВЕТА (структурированный текст)**:

Верни ответ в формате СТРУКТУРИРОВАННЫХ СЕКЦИЙ с маркерами ===СЕКЦИЯ===.
🚫 НЕ возвращай ответ как один корневой JSON-объект. Ответ должен быть текстом с секциями. Пиши код КАК ЕСТЬ, без экранирования.

Обязательные поля-заголовки (в начале):
- widget_name: КОРОТКИЙ заголовок на русском (МАКСИМУМ 5-7 слов!). НЕ предложение!
  Только существительные + прилагательные. Без глаголов, без "на основе", без "для данных".
  ✅ "Продажи по категориям", "Топ-10 брендов по выручке", "Динамика вакансий"
  ❌ "Widget", "Chart", "Visualization", "Виджет", "График" — ЗАПРЕЩЕНО!
  ❌ "Круговая диаграмма распределения количества вакансий по компаниям на основе данных" — СЛИШКОМ ДЛИННО!
- widget_type: тип — chart | table | cards | kpi
- description: РАЗВЁРНУТОЕ описание виджета (1-2 предложения), отличающееся от widget_name.
  Объясняет ЧТО показывает виджет и КАК визуализированы данные.
  ✅ "Столбчатая диаграмма продаж по категориям товаров за 2024 год с сортировкой по убыванию"
  ✅ "Карточки с информацией о товарах: название, бренд, количество продаж и выручка"
  ❌ НЕ дублируй widget_name! description — это пояснение, а не повтор названия.

Секции кода (после заголовков):
- ===RENDER_BODY=== — JS-код визуализации (ТОЛЬКО тело, без render(), без try/catch)
- ===STYLES=== — CSS-правила (может быть пустой секцией)
- ===SCRIPTS=== — теги <script src="..."> для библиотек (может быть пустой секцией)

🚨 ВАЖНО:
- Пиши JS/CSS КАК ЕСТЬ — с настоящими переносами строк, кавычками, шаблонными литералами
- НЕ оборачивай код в ```json, ```javascript и т.п.
- НЕ экранируй кавычки и переносы строк
- Секция ===RENDER_BODY=== ОБЯЗАТЕЛЬНА и должна содержать ПОЛНЫЙ код
- Секции ===STYLES=== и ===SCRIPTS=== можно опустить, если пустые
- 🚫 НЕ вставляй markdown-символы (###, ##, **, __, ```) ВНУТРЬ секций кода!
  Внутри ===RENDER_BODY=== / ===STYLES=== / ===SCRIPTS=== — ТОЛЬКО чистый JS/CSS.
  ❌ ### — SyntaxError в JavaScript!
  ❌ // --- или // === разделители из markdown — лишний мусор, не вставляй.
- 🚫 НЕ смешивай ECharts formatter-строки с JS template literals:
  ❌ formatter: '{b}: {c}<br>${r["col"]}' — ${} не вычисляется внутри обычной строки!
  ✅ formatter: '{b}: {c} ({d}%)'  — используй только ECharts placeholders: {a}{b}{c}{d}
- 🚫 Строка в '...' или "..." не может содержать реальный перенос строки (SyntaxError в браузере).
  ✅ formatter: '{b}\\n{c}%'  — перенос только как \\n внутри одной строки кода
- 🚫 Не вставляй невидимые разделители строк (U+2028/U+2029 из Word) — только ASCII.
  Предпочтительно tooltip/label: formatter: function(p) { return p.name + ': ' + p.value + '%'; }
- 🚫 Во встроенном <script> нельзя писать подряд символы </script> даже внутри строки — браузер обрежет скрипт.
  Если нужна эта подстрока: '<' + '/script>' или '<\\/script>' в кавычках.

═══ ПОЛНЫЙ ПРИМЕР ОТВЕТА (BAR CHART) ══════════════════════

widget_name: Продажи по брендам
widget_type: chart
description: Столбчатая диаграмма продаж по брендам. Клик по столбцу устанавливает фильтр; активный бренд подсвечивается фиолетовым.

===RENDER_BODY===
if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));

const tbl = tables['top_brands'];
const tblName = 'top_brands';
const dimCol = 'brand';
const option = {
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: tbl.rows.map(r => r[dimCol]),
    axisLabel: { rotate: tbl.rows.length > 8 ? 45 : 0 }
  },
  yAxis: { type: 'value' },
  series: [{
    name: 'sales_count',
    type: 'bar',
    data: tbl.rows.map(r => {
      const active = __isRowActive(tblName, dimCol, r);
      return {
        value: Number(r['sales_count']),
        itemStyle: {
          color: active ? '#6366f1' : '#91cc75',
          borderRadius: [4, 4, 0, 0]
        }
      };
    })
  }]
};

window.chartInstance.setOption(option);
window.chartInstance.on('click', function(params) {
  if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
});
window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };

===SCRIPTS===
<script src="/libs/echarts.min.js"></script>

═══ ПОЛНЫЙ ПРИМЕР ОТВЕТА (PIE CHART) ═══════════════════════

widget_name: Доли брендов по продажам
widget_type: chart
description: Круговая диаграмма долей брендов по количеству продаж. Клик по сегменту устанавливает фильтр; активный сегмент выделяется выдвижением (selectedOffset) и рамкой.

===RENDER_BODY===
if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));

const tbl = tables['top_brands'];
const tblName = 'top_brands';
const dimCol = 'brand';
const option = {
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { orient: 'vertical', right: 10, top: 'center' },
  series: [{
    type: 'pie',
    radius: '55%',
    selectedOffset: 14,
    avoidLabelOverlap: false,
    label: { show: true, position: 'outside', formatter: '{b}  {d}%' },
    data: tbl.rows.map(r => {
      const active = __isRowActive(tblName, dimCol, r);
      return {
        name: r[dimCol],
        value: Number(r['sales_count']),
        selected: active,
        itemStyle: active
          ? { borderWidth: 4, borderColor: '#6366f1', shadowBlur: 12, shadowColor: 'rgba(99,102,241,0.5)' }
          : {}
      };
    })
  }]
};

window.chartInstance.setOption(option);
window.chartInstance.on('click', function(params) {
  if (window.toggleFilter) window.toggleFilter(dimCol, params.name);
});
window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };

===SCRIPTS===
<script src="/libs/echarts.min.js"></script>

═══ ПОЛНЫЙ ПРИМЕР ОТВЕТА (HTML КАРТОЧКИ) ══════════════════

widget_name: Карточки товаров
widget_type: cards
description: Сетка карточек с информацией о товарах: название, бренд и количество продаж. Адаптивный grid-лейаут

===RENDER_BODY===
const container = document.getElementById('chart');
container.style.overflow = 'auto';
container.style.padding = '16px';
container.style.display = 'grid';
container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(280px, 1fr))';
container.style.gap = '12px';

const tbl = tables['top_products'];
const tblName = 'top_products';
const dimCol = 'brand';
container.innerHTML = '';
tbl.rows.forEach(function(row) {
  const active = __isRowActive(tblName, dimCol, row);
  const card = document.createElement('div');
  card.className = 'card';
  card.style.cursor = 'pointer';
  card.style.borderColor = active ? '#6366f1' : '#e5e7eb';
  card.style.background = active ? '#f5f3ff' : '#fff';
  card.style.boxShadow = active ? '0 0 0 2px rgba(99,102,241,0.25)' : '0 1px 3px rgba(0,0,0,0.1)';
  card.innerHTML = `
    <div class="card-title">${row['title']}</div>
    <div class="card-body">
      <div>Бренд: <b>${row[dimCol]}</b></div>
      <div>Продано: <b>${row['salesCount']}</b></div>
    </div>`;
  card.addEventListener('click', function() {
    if (window.toggleFilter) window.toggleFilter(dimCol, row[dimCol]);
  });
  container.appendChild(card);
});

===STYLES===
.card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; transition: border-color 0.15s, background 0.15s, box-shadow 0.15s; }
.card-title { font-weight: 600; font-size: 16px; color: #111827; margin-bottom: 8px; }
.card-body { color: #6b7280; font-size: 14px; }

═══════════════════════════════════════════════════════════
 ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕГО ВИДЖЕТА
═══════════════════════════════════════════════════════════

Если в чате есть твой предыдущий ответ с render_body — пользователь просит
МОДИФИКАЦИЮ существующего виджета (а НЕ создание нового).

В этом случае:
• Возьми render_body из своего последнего ответа ЗА ОСНОВУ
• Внеси ТОЛЬКО те изменения, которые просит пользователь
• НЕ меняй тип графика, логику данных и общую структуру
• Верни обновлённый ответ В ТОМ ЖЕ формате структурированных секций

Return ответ ТОЛЬКО в формате структурированных секций (widget_name/widget_type/description + ===RENDER_BODY=== + ...).
НИКАКОГО JSON. Никакого markdown-обрамления.
🏷️ ОБЯЗАТЕЛЬНО начинай ответ с widget_name — конкретного названия на русском!
📝 Сразу после — description: развёрнутое описание (1-2 предложения, НЕ повтор widget_name).

🔁 ЧЕК-ЛИСТ перед отправкой ответа:
  □ Есть ли const dimCol = '...'; с колонкой-измерением?
  □ Есть ли click-обработчик (chartInstance.on / addEventListener)?
  □ Вызывается ли toggleFilter(dimCol, value) при клике?
  □ Используется ли __isRowHighlighted(tblName, dimCol, value) или isFilterActive() для подсветки?
  Если нет — ДОРАБОТАЙ render_body перед отправкой!
'''
