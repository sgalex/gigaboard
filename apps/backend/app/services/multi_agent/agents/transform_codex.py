"""
Transform Codex Agent — Code Generation (V2)
Генерирует код трансформаций (Python/pandas).

Виджеты (HTML/CSS/JS) генерируются отдельным агентом WidgetCodexAgent.
См. widget_codex.py, docs/ECHARTS_WIDGET_REFERENCE.md

V2: Возвращает AgentPayload(code_blocks=[CodeBlock(...)], narrative=...).
    См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import ast
import json
import logging
import re
import textwrap
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import CodeBlock, Narrative
from app.services.gigachat_service import GigaChatService

logger = logging.getLogger(__name__)

# ── Forbidden code patterns ──────────────────────────────────────────
FORBIDDEN_PATTERNS: List[str] = [
    r'\beval\b', r'\bexec\b', r'\b__import__\b',
    r'\bsubprocess\b', r'\bos\.', r'\bsys\.',
    r'\bopen\(', r'\bfile\(', r'\bimport\s+os\b',
    r'\bimport\s+sys\b', r'\bimport\s+subprocess\b',
]


class TransformCodexAgent(BaseAgent):
    """
    Transform Codex Agent — генератор кода трансформаций (V2).

    Режим: purpose="transformation" — Python/pandas код для ContentNode → ContentNode.

    Для виджетов (purpose="widget") используйте WidgetCodexAgent (widget_codex.py).
    Если TransformCodexAgent получает purpose="widget", он логирует предупреждение
    и перенаправляет задачу (backward compatibility).

    Возвращает AgentPayload:
      code_blocks  — список CodeBlock
      narrative    — краткое описание
      metadata     — output_schema и т.д.
    """

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="transform_codex",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router

    # ── default prompt ───────────────────────────────────────────────
    def _get_default_system_prompt(self) -> str:
        return (
            "You are TransformCodexAgent — a Python/pandas transformation specialist in GigaBoard.\n"
            "You generate Python code for data transformations.\n"
            "Always return valid JSON."
        )

    # ── main entry ───────────────────────────────────────────────────
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Генерирует код трансформации (Python/pandas).
        Если получает purpose='widget' — логирует deprecation и делегирует
        внутреннему _generate_widget (backward compatibility).
        V2: Возвращает AgentPayload(code_blocks=..., narrative=...).
        """
        purpose = task.get("purpose", "transformation")
        try:
            if purpose == "widget":
                self.logger.warning(
                    "⚠️ TransformCodexAgent получил purpose='widget'. "
                    "Используйте WidgetCodexAgent (widget_codex) для виджетов. "
                    "Перенаправление для backward compatibility."
                )
                return await self._generate_widget(task, context)
            else:
                return await self._generate_transformation(task, context)
        except Exception as e:
            self.logger.error(f"TransformCodexAgent error: {e}", exc_info=True)
            return self._error_payload(str(e))

    # ══════════════════════════════════════════════════════════════════
    #  TRANSFORMATION mode
    # ══════════════════════════════════════════════════════════════════
    async def _generate_transformation(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        description = task.get("description", "")
        if not description:
            return self._error_payload("description is required")

        input_schemas = task.get("input_schemas", [])
        
        # Изменение #4: читаем схему из context.input_data_preview (основной источник)
        # PlannerAgent (LLM) не заполняет input_schemas в task,
        # TransformationController передаёт реальную схему в context
        if not input_schemas and context:
            input_preview = context.get("input_data_preview", {})
            if input_preview:
                for table_name, info in input_preview.items():
                    input_schemas.append({
                        "name": table_name,
                        "columns": info.get("columns", []),
                        "dtypes": info.get("dtypes", {}),
                        "row_count": info.get("row_count", 0),
                        "sample_rows": info.get("sample_rows", [])[:10],  # Увеличено с 3 до 10 строк для лучшего понимания данных
                    })
                self.logger.info(f"📊 Codex: loaded {len(input_schemas)} schema(s) from context")
        
        previous_errors = task.get("previous_errors", [])
        # FIX GAP 1: При error retry контроллер кладёт previous_error в context,
        # а не в task.previous_errors. Читаем из context как fallback.
        if not previous_errors and context and context.get("previous_error"):
            previous_errors = [context["previous_error"]]
            self.logger.info(f"⚠️ Codex: loaded previous_error from context (error retry)")
        
        # Изменение #7: context-first — сначала context, потом task
        existing_code = (context or {}).get("existing_code") or task.get("existing_code")
        
        # FIX GAP 2: При error retry previous_code содержит последний неудачный код,
        # который важнее оригинального existing_code для исправления.
        if context and context.get("error_retry") and context.get("previous_code"):
            existing_code = context["previous_code"]
            self.logger.info(f"⚠️ Codex: using previous_code from error retry (overrides existing_code)")
        
        if existing_code:
            self.logger.info(f"📄 Codex: existing_code present ({len(existing_code)} chars)")
        error_details = task.get("error_details")  # ← NEW: из suggested_replan ValidatorAgent
        # FIX GAP 1 (part 2): error_details может прийти из context при replan
        if not error_details and context and context.get("previous_error"):
            error_details = {
                "error": context["previous_error"],
                "error_type": "runtime",
            }

        # ── Контекст пользовательского запроса и результатов аналитика ──
        # Planner часто формирует generic description типа "Generate Python code
        # for transformation". Оригинальный запрос пользователя и результаты
        # предыдущих агентов (analyst) содержат конкретные инструкции.
        # Изменение #2: agent_results — list (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
        user_request = (context or {}).get("user_request", "")
        analyst_context = self._extract_analyst_context(
            (context or {}).get("agent_results", [])
        )
        
        # История диалога (для итеративных доработок кода)
        chat_history = (context or {}).get("chat_history", [])
        if chat_history:
            # Логируем количество сообщений в истории
            self.logger.info(f"💬 Codex: chat_history available ({len(chat_history)} messages)")
            # Для debug логируем последнее сообщение
            if len(chat_history) > 0:
                last_msg = chat_history[-1]
                self.logger.info(f"   Last message: {last_msg.get('role', 'user')}: {last_msg.get('content', '')[:100]}...")

        # ── Debug: логируем все входные параметры для верификации ──
        self.logger.debug(f"🔍 Codex Input Parameters:")
        self.logger.debug(f"  - description: {description}")
        self.logger.debug(f"  - input_schemas: {len(input_schemas)} schema(s)")
        self.logger.debug(f"  - previous_errors: {len(previous_errors)} error(s)")
        if existing_code:
            self.logger.debug(f"📄 Existing code FULL:\n{existing_code}")
        else:
            self.logger.debug(f"  - existing_code: None")
        if chat_history:
            self.logger.debug(f"💬 Chat history FULL ({len(chat_history)} messages):")
            for i, msg in enumerate(chat_history):
                self.logger.debug(f"   {i+1}. {msg.get('role', 'user')}: {msg.get('content', '')}")

        self.logger.info(f"🔧 Codex/transformation: {description[:100]}…")
        if user_request:
            self.logger.info(f"📝 Codex: user_request='{user_request[:120]}…'")

        is_error_retry = bool(error_details or previous_errors)

        messages = self._build_messages(
            description=description,
            input_schemas=input_schemas,
            previous_errors=previous_errors,
            existing_code=existing_code,
            user_request=user_request,
            analyst_context=analyst_context,
            chat_history=chat_history,
            error_details=error_details,
            is_error_retry=is_error_retry,
        )

        total_chars = sum(len(m.get("content", "")) for m in messages)
        self.logger.info(
            f"📨 Codex prompt to LLM ({total_chars} chars, {len(messages)} messages)"
        )
        
        response = await self._call_llm(
            messages, context=context, temperature=0.2, max_tokens=16384
        )

        parsed = self._parse_json_from_llm(response)
        raw_code = parsed.get("transformation_code", "")
        # Fallback: GigaChat иногда использует другое имя ключа
        if not raw_code:
            for alt_key in ("code", "python_code", "transform_code"):
                raw_code = parsed.get(alt_key, "")
                if raw_code:
                    self.logger.info(f"📎 Codex: found code under '{alt_key}' key (fallback)")
                    break
        # Fallback 2: извлечь python блок из raw response
        if not raw_code:
            py_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
            if py_match:
                raw_code = py_match.group(1)
                self.logger.info("📎 Codex: extracted Python from markdown block (fallback)")
        if isinstance(raw_code, list):
            raw_code = "\n".join(raw_code)
        
        # Clean up escape characters that GigaChat sometimes adds
        if raw_code:
            # ── Очистка артефактов GigaChat/JSON ──
            # 1. Удаляем markdown-обёртки ```python ... ```
            #    Также удаляем ВСЁ после закрывающего ``` (trailing JSON фрагменты)
            raw_code = re.sub(r'^\s*```(?:python)?\s*\n?', '', raw_code)
            raw_code = re.sub(r'\n?\s*```[\s\S]*$', '', raw_code)
            # 2. Удаляем trailing JSON фрагменты (,  "description": "..." и т.п.)
            raw_code = re.sub(r',\s*"(?:description|output_schema|output|message)[\s\S]*$', '', raw_code)
            # 3. Убираем backslashes перед кавычками/скобками (JSON escape артефакты)
            #    \\\" → ", \\" → ", \\[ → [, и т.д.
            raw_code = re.sub(r'\\+(["\'`\[\]])', r'\1', raw_code)
            # 4. Remove leading backslashes from each line
            raw_code = '\n'.join(line.lstrip('\\') for line in raw_code.split('\n'))
            # 5. Unescape literal \n sequences (but not \\n which is actual newline in repr)
            raw_code = raw_code.replace('\\n', '\n')
            # 6. Dedent: убираем общий leading whitespace (артефакт JSON formatting)
            raw_code = textwrap.dedent(raw_code)
            # 7. Убираем пустые строки в начале/конце
            raw_code = raw_code.strip('\n').strip()

        # ── Iterative auto-fix: prepend existing_code if LLM omitted df_ definitions ──
        # Happens when multi-turn LLM returns only the incremental line, e.g.:
        #   df_sales['new_col'] = df_sales['a'] / df_sales['b']   (NameError without df_sales def)
        if existing_code and not is_error_retry and raw_code.strip():
            existing_vars = set(re.findall(r'\b(df_[a-z_][a-z0-9_]*)\s*=', existing_code))
            raw_defined = set(re.findall(r'\b(df_[a-z_][a-z0-9_]*)\s*=', raw_code))
            raw_used = set(re.findall(r'\b(df_[a-z_][a-z0-9_]*)\b', raw_code))
            missing = (raw_used - raw_defined) & existing_vars
            if missing:
                self.logger.info(
                    f"🔧 Codex: iterative code uses {missing} from existing_code without re-defining — "
                    f"prepending existing_code as prefix"
                )
                raw_code = existing_code + "\n" + raw_code

        # ── Auto-fix: удаляем ошибочный getattr(gb, 'instance', None) ──
        # LLM иногда пишет `gb = getattr(gb, 'instance', None)` — это перезаписывает
        # gb в None, т.к. у GigaBoardHelpers нет атрибута 'instance'. gb уже является
        # готовым экземпляром и не требует разворачивания.
        if re.search(r"gb\s*=\s*getattr\s*\(\s*gb\s*,", raw_code):
            raw_code = re.sub(r".*\bgb\s*=\s*getattr\s*\(\s*gb\s*,.*\n?", "", raw_code)
            self.logger.warning("🔧 Auto-fix: removed 'gb = getattr(gb, ...)' — gb is already an instance")

        # ── Auto-fix: пропущенная ')' в named-tuple внутри .agg() ──
        # GigaChat систематически генерирует:
        #   key=('col', 'func'      ← нет закрывающей )
        # ).reset_index()
        # Паттерн: =('col', 'func'[пробел]\n → заменяем на =('col', 'func')\n
        raw_code, _n_agg_fixed = re.subn(
            r"(=\(['\"][^'\"]+['\"],\s*['\"][a-zA-Z_][a-zA-Z_0-9]*['\"])([ \t]*\n)",
            r"\1)\2",
            raw_code,
        )
        if _n_agg_fixed:
            self.logger.warning(
                f"🔧 Auto-fix: added {_n_agg_fixed} missing ')' in .agg() named-tuple(s)"
            )

        # Debug: log raw code before auto-fix
        self.logger.info(f"🔍 Codex raw code ({len(raw_code)} chars): {raw_code[:200]}...")
        # Full code logging for debugging
        if len(raw_code) > 200:
            self.logger.debug(f"📄 Codex FULL raw code:\n{raw_code}")
        else:
            self.logger.debug(f"📄 Codex FULL raw code: {raw_code}")

        # Auto-fix: если код есть, но нет df_ переменной — добавляем обёртку
        if raw_code.strip() and not re.search(r'\bdf_[a-z_][a-z0-9_]*\s*=', raw_code):
            self.logger.info("🔧 Codex: no df_ variable found, applying auto-fix...")
            # Ищем result = ... или другую переменную-результат (расширенный список)
            result_match = re.search(
                r'\b(result|results|output|outputs|transformed|transform|filtered|grouped|merged|final|data|processed)\s*=',
                raw_code
            )
            if result_match:
                var = result_match.group(1)
                raw_code += f"\ndf_{var} = {var}"
                self.logger.info(f"📎 Codex: auto-aliased '{var}' → 'df_{var}'")
            else:
                # Fallback: ищем ЛЮБОЕ присваивание переменной (кроме импортов и констант)
                # Паттерн: <var> = df... или <var> = pd... или просто <var> = ...
                all_assigns = re.findall(r'\b([a-z_][a-z0-9_]*)\s*=\s*(?!None|True|False|\d|["\'])', raw_code)
                if all_assigns:
                    # Берём последнюю присвоенную переменную (вероятно, это результат)
                    last_var = all_assigns[-1]
                    raw_code += f"\ndf_{last_var} = {last_var}"
                    self.logger.info(f"📎 Codex: auto-aliased '{last_var}' → 'df_{last_var}' (generic fallback)")
                else:
                    # Крайний случай: добавляем шаблонную обёртку
                    raw_code = f"df_result = None\n{raw_code}\n# Auto-fix: wrap result\ndf_result = df"
                    self.logger.warning("⚠️ Codex: could not find result variable, using df_result = df fallback")

        # Debug: log final code after auto-fix
        self.logger.info(f"✅ Codex final code after auto-fix ({len(raw_code)} chars): {raw_code[:200]}...")
        if len(raw_code) > 200:
            self.logger.debug(f"📄 Codex FINAL code (after auto-fix):\n{raw_code}")
        else:
            self.logger.debug(f"📄 Codex FINAL code: {raw_code}")

        # ── CRITICAL: если код пустой — вернуть error, a не success ──
        if not raw_code.strip():
            self.logger.error(
                "❌ Codex: GigaChat вернул пустой код! "
                f"Raw response preview: {response[:300]}..."
            )
            return self._error_payload(
                "GigaChat не сгенерировал код трансформации. "
                "Попробуйте переформулировать запрос более конкретно, "
                "например: 'Добавь столбец X = df[col].rank(ascending=False)'"
            )

        # Auto-fix: try to repair unbalanced parentheses before validation
        try:
            ast.parse(raw_code)
        except SyntaxError:
            fixed = self._try_fix_unbalanced_parens(raw_code)
            if fixed is not None:
                self.logger.info(
                    "🔧 Codex: auto-fixed unbalanced brackets "
                    f"({len(raw_code)} → {len(fixed)} chars)"
                )
                raw_code = fixed

        # Validate
        validation = self._validate_python_code(raw_code)

        # Log validation warnings for debugging
        if validation.get("warnings"):
            for w in validation["warnings"]:
                self.logger.warning(f"⚠️ Codex validation: {w}")

        # If validation detected a known code-level bug, return error immediately
        # so orchestrator can retry with the error hint instead of wasting execution
        if not validation["valid"]:
            error_msg = validation.get("error", "Unknown validation error")
            self.logger.warning(f"❌ Codex: static validation failed: {error_msg}")
            hint = self._get_error_hint(error_msg)
            if hint:
                error_msg = f"{error_msg}. 💡 {hint}"
            # FIX: Включаем неудачный код в error payload,
            # чтобы _execute_with_retry мог извлечь его и передать как previous_code
            # при повторном вызове. Без этого retry получает тот же промпт
            # и генерирует тот же сломанный код.
            error_payload = self._error_payload(error_msg)
            error_payload.code_blocks = [CodeBlock(
                code=raw_code,
                language="python",
                purpose="transformation",
                syntax_valid=False,
                description=f"Failed code: {error_msg}",
            )]
            return error_payload

        # Extract variable name (df_xxx = ...)
        var_match = re.search(r'\b(df_[a-z_][a-z0-9_]*)\s*=', raw_code)
        var_name = var_match.group(1) if var_match else None

        block = CodeBlock(
            code=raw_code,
            language="python",
            purpose="transformation",
            variable_name=var_name,
            syntax_valid=validation["valid"],
            warnings=validation.get("warnings", []),
            description=parsed.get("description", description),
        )

        self.logger.info(
            f"✅ Transformation code generated, valid={validation['valid']}"
        )

        return self._success_payload(
            code_blocks=[block],
            narrative_text=parsed.get("description", ""),
            metadata={
                "output_schema": parsed.get("output_schema"),
                "validation_error": validation.get("error"),
            },
        )

    # ══════════════════════════════════════════════════════════════════
    #  WIDGET mode
    # ══════════════════════════════════════════════════════════════════
    async def _generate_widget(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        description = task.get("description", "")
        if not description:
            return self._error_payload("description required for widget")

        # Collect data context from agent_results
        agent_results = (context or {}).get("agent_results", [])
        data_summary = self._build_data_summary_for_widget(task, agent_results, context)

        self.logger.info(f"🎨 Codex/widget: {description[:100]}…")

        prompt = self._build_widget_prompt(description, data_summary)

        messages = [
            {"role": "system", "content": WIDGET_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self._call_llm(
            messages, context=context, temperature=0.3, max_tokens=16384
        )

        parsed = self._parse_json_from_llm(response)

        widget_code = self._unescape_html_code(parsed.get("widget_code", ""))
        widget_name = parsed.get("widget_name", "Widget")
        widget_type = parsed.get("widget_type", "custom")

        # Fallback: если widget_code пустой, попробовать извлечь HTML из raw response
        if not widget_code.strip():
            html_match = re.search(r'(<!DOCTYPE\s+html>.*?</html>)', response, re.DOTALL | re.IGNORECASE)
            if html_match:
                widget_code = html_match.group(1)
                self.logger.info("📎 Extracted HTML from raw response (fallback)")
            else:
                # Try markdown html block
                html_block = re.search(r'```html\s*(.*?)\s*```', response, re.DOTALL)
                if html_block:
                    widget_code = html_block.group(1)
                    self.logger.info("📎 Extracted HTML from markdown block (fallback)")

        # Auto-fix: render() без async + fetchContentData → rows.forEach crash
        widget_code = self._fix_async_render_widget(widget_code)

        block = CodeBlock(
            code=widget_code,
            language="html",
            purpose="widget",
            syntax_valid=bool(widget_code.strip()),
            warnings=[],
            description=widget_name,
        )

        self.logger.info(f"✅ Widget generated: {widget_name} ({widget_type})")

        return self._success_payload(
            code_blocks=[block],
            narrative_text=parsed.get("description", widget_name),
            metadata={"widget_type": widget_type, "widget_name": widget_name},
        )

    def _fix_async_render_widget(self, code: str) -> str:
        """Auto-fix: добавляет async к render() если он вызывает fetchContentData."""
        if not code:
            return code
        if re.search(r'fetchContentData|fetchData', code):
            fixed = re.sub(
                r'(?<!async )function\s+(render)\s*\(',
                r'async function \1(',
                code,
            )
            if fixed != code:
                self.logger.warning("🔧 Auto-fix: added 'async' to render() calling fetchContentData")
                code = fixed
        # fetchData().then(data => data) → await fetchData()
        m = re.search(
            r'(\bconst|let|var)\s+(\w+)\s*=\s*(fetchData|fetchContentData)\s*\(\)\s*\.then\s*\([^)]*\)\s*;?',
            code,
        )
        if m:
            old_expr = m.group(0)
            new_expr = f"{m.group(1)} {m.group(2)} = await {m.group(3)}();"
            code = code.replace(old_expr, new_expr)
            self.logger.warning(f"🔧 Auto-fix: replaced '{m.group(3)}().then(...)' with 'await {m.group(3)}()'")
        # CSS var() в JS template literal → SyntaxError
        css_var_pat = re.compile(r'`\$\{var\(--([\w-]+)\)\}`')
        if css_var_pat.search(code):
            code = css_var_pat.sub(r"'var(--\1)'", code)
            self.logger.warning("🔧 Auto-fix: replaced `${var(--...)}` with 'var(--...)' (CSS var in JS)")
        return code

    # ══════════════════════════════════════════════════════════════════
    #  Message builders (multi-turn chat pattern)
    # ══════════════════════════════════════════════════════════════════

    def _build_messages(
        self,
        description: str,
        input_schemas: List[Dict[str, Any]],
        previous_errors: List[str],
        existing_code: Optional[str],
        user_request: str = "",
        analyst_context: str = "",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        is_error_retry: bool = False,
    ) -> List[Dict[str, str]]:
        """Build LLM messages array.

        For NEW/ERROR_RETRY: system + single user prompt.
        For ITERATIVE updates: system + multi-turn chat history (attention pattern).
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": TRANSFORMATION_SYSTEM_PROMPT},
        ]

        if existing_code and chat_history and not is_error_retry:
            # ── Multi-turn iterative mode ──
            messages.extend(
                self._build_iterative_messages(
                    description=description,
                    input_schemas=input_schemas,
                    user_request=user_request,
                    analyst_context=analyst_context,
                    existing_code=existing_code,
                    chat_history=chat_history,
                )
            )
        else:
            # ── Single-turn: NEW or ERROR_RETRY ──
            prompt = self._build_transformation_prompt(
                description, input_schemas, previous_errors, existing_code,
                user_request=user_request, analyst_context=analyst_context,
                chat_history=chat_history, error_details=error_details,
            )
            messages.append({"role": "user", "content": prompt})

        return messages

    def _build_iterative_messages(
        self,
        description: str,
        input_schemas: List[Dict[str, Any]],
        user_request: str,
        analyst_context: str,
        existing_code: str,
        chat_history: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Build multi-turn messages for iterative code refinement.

        Layout (attention-optimal):
          user:      [data context] + first user request
          assistant: first AI response
          ...
          assistant: last AI response + existing Python code
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
            m = _re.search(r'NEW REQUEST:\s*(.+?)(?:\n|$)', user_request)
            current_request = m.group(1).strip() if m else description

        # 2. Data context preamble (schemas, analyst context)
        data_preamble = self._build_data_context(input_schemas, analyst_context)

        # 3. Existing code → JSON block for assistant message
        code_block = (
            f'```json\n'
            f'{_json.dumps({"transformation_code": existing_code, "description": "текущий код"}, ensure_ascii=False)}\n'
            f'```'
        )

        # 4. Process history → multi-turn messages
        if history:
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

            # Edge case: history has user messages but no assistant
            if last_assistant_idx is None:
                result.append({"role": "assistant", "content": code_block})
        else:
            # No prior history but have existing code (e.g., page reload)
            result.append({"role": "user", "content": data_preamble + description})
            result.append({"role": "assistant", "content": code_block})

        # 5. Ensure proper user/assistant alternation
        result = self._fix_message_alternation(result)

        # 6. Handle @mentions in current request (@tableName and @tableName.columnName)
        _mention_re = _re.compile(r'@(\w+)(?:\.(\w+))?')
        mention_matches = list(_mention_re.finditer(current_request))
        if mention_matches:
            schema_names = [s.get("name", "") for s in input_schemas] if input_schemas else []
            # Extract df_xxx variables from existing_code (result tables from prior transform)
            result_df_map: dict = {}
            for _m in _re.finditer(r'\b(df_[a-z_][a-z0-9_]*)\s*=', existing_code):
                _v = _m.group(1)
                result_df_map[_v[3:]] = _v  # strip leading 'df_'
            hint_parts = []
            for mm in mention_matches:
                tbl_name, col_name = mm.group(1), mm.group(2)
                if tbl_name in schema_names:
                    idx = schema_names.index(tbl_name)
                    var = f"df{idx+1}" if len(input_schemas) > 1 else "df"
                elif tbl_name in result_df_map:
                    var = result_df_map[tbl_name]
                else:
                    var = "df"  # fallback
                if col_name:
                    hint_parts.append(f"@{tbl_name}.{col_name} → {var}['{col_name}']")
                else:
                    hint_parts.append(f"@{tbl_name} → {var}")
            current_request = f"📌 ССЫЛКИ: {', '.join(hint_parts)}\n\n{current_request}"

        # 7. Final user message — remind to generate full standalone code
        standalone_note = (
            "\n\n[ВАЖНО: верни ПОЛНЫЙ САМОДОСТАТОЧНЫЙ код — "
            "включи ВСЕ df_xxx определения из своего предыдущего ответа ПЛЮС "
            "реализацию нового запроса. Код должен работать с нуля без внешних переменных.]"
        )
        result.append({"role": "user", "content": current_request + standalone_note})

        return result

    def _build_data_context(
        self,
        input_schemas: List[Dict[str, Any]],
        analyst_context: str = "",
    ) -> str:
        """Build data context preamble for the first user message."""
        parts: List[str] = []
        if input_schemas:
            multiple = len(input_schemas) > 1
            parts.append("━━━ ВХОДНЫЕ ДАННЫЕ ━━━")
            for i, schema in enumerate(input_schemas):
                var = f"df{i+1}" if multiple else "df"
                name = schema.get("name", f"table_{i+1}")
                columns = schema.get("columns", [])
                dtypes = schema.get("dtypes", {})
                row_count = schema.get("row_count", "?")
                sample_rows = schema.get("sample_rows", [])

                parts.append(f"\nТаблица: {var} ('{name}', {row_count} строк)")
                if columns:
                    col_info = []
                    for col in columns:
                        dtype = dtypes.get(col, "")
                        col_info.append(f"  - {col} ({dtype})" if dtype else f"  - {col}")
                    parts.append("Колонки:")
                    parts.extend(col_info)
                if sample_rows:
                    display_rows = sample_rows[:5]
                    parts.append(f"Примеры данных ({len(display_rows)} из {row_count} строк):")
                    if columns:
                        parts.append("  | " + " | ".join(str(c) for c in columns) + " |")
                        parts.append("  |" + "|".join(["---"] * len(columns)) + "|")
                    for row in display_rows:
                        if isinstance(row, dict):
                            vals = [str(row.get(c, ""))[:20] for c in columns]
                        elif isinstance(row, (list, tuple)):
                            vals = [str(v)[:20] for v in row]
                        else:
                            continue
                        parts.append("  | " + " | ".join(vals) + " |")

            if multiple:
                parts.append("\n⚠️ Несколько таблиц: используй df1, df2 и т.д.")
        if analyst_context:
            parts.append(f"\nАНАЛИЗ ДАННЫХ:\n{analyst_context}")
        if parts:
            return "\n".join(parts) + "\n\n"
        return ""

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

    # ══════════════════════════════════════════════════════════════════
    #  Single-turn prompt builder (NEW + ERROR_RETRY)
    # ══════════════════════════════════════════════════════════════════
    def _build_transformation_prompt(
        self,
        description: str,
        input_schemas: List[Dict[str, Any]],
        previous_errors: List[str],
        existing_code: Optional[str],
        *,
        user_request: str = "",
        analyst_context: str = "",
        chat_history: List[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> str:
        parts: List[str] = []

        import re as _re

        # ── 1. Пользовательский запрос — главный приоритет ──
        if user_request:
            parts.append(f"ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {user_request}")

            # ── Resolve @mentions → explicit table/column references ──
            # Supports: @tableName  and  @tableName.columnName
            _mention_re = _re.compile(r'@(\w+)(?:\.(\w+))?')
            mention_matches = list(_mention_re.finditer(user_request))
            if mention_matches:
                schema_names = [s.get("name", "") for s in input_schemas] if input_schemas else []
                # Extract df_xxx variables from existing_code (result tables from prior transform)
                result_df_map: dict = {}
                if existing_code:
                    for _m in _re.finditer(r'\b(df_[a-z_][a-z0-9_]*)\s*=', existing_code):
                        _v = _m.group(1)
                        result_df_map[_v[3:]] = _v  # strip leading 'df_'
                parts.append("\n📌 ССЫЛКИ В ЗАПРОСЕ (@mentions):")
                for mm in mention_matches:
                    tbl_name, col_name = mm.group(1), mm.group(2)
                    # Resolve DataFrame variable for the table part
                    if tbl_name in schema_names:
                        idx = schema_names.index(tbl_name)
                        var = f"df{idx+1}" if len(input_schemas) > 1 else "df"
                    elif tbl_name in result_df_map:
                        var = result_df_map[tbl_name]
                    else:
                        var = "df"  # fallback
                    if col_name:
                        parts.append(f"  @{tbl_name}.{col_name} → {var}['{col_name}']")
                    else:
                        parts.append(f"  @{tbl_name} → DataFrame {var} (таблица '{tbl_name}')")
                parts.append("")
        parts.append(f"ОПИСАНИЕ ЗАДАЧИ: {description}")

        # ── 2. Ошибки — показываем СРАЗУ (до всего остального), чтобы LLM фокусировался ──
        if error_details:
            error_msg = error_details.get('error', 'Unknown error')
            parts.append("\n🛑 ОШИБКА ВЫПОЛНЕНИЯ (ИСПРАВЬ!):")
            parts.append(f"  Тип: {error_details.get('error_type', 'unknown')}")
            parts.append(f"  Сообщение: {error_msg}")
            # Smart hints — переводим runtime-ошибки в конкретные инструкции
            hint = self._get_error_hint(error_msg)
            if hint:
                parts.append(f"  💡 ПОДСКАЗКА: {hint}")
            parts.append("  → Сгенерируй ИСПРАВЛЕННЫЙ код, устраняющий эту ошибку.")
            parts.append("")

        if previous_errors:
            parts.append("⚠️ ПРЕДЫДУЩИЕ ОШИБКИ (учти при генерации):")
            for e in previous_errors:
                parts.append(f"  - {e}")
            parts.append("")

        # ── 3. Входные данные — структурированный формат ──
        if input_schemas:
            multiple = len(input_schemas) > 1
            parts.append("━━━ ВХОДНЫЕ ДАННЫЕ ━━━")
            for i, schema in enumerate(input_schemas):
                var = f"df{i+1}" if multiple else "df"
                name = schema.get("name", f"table_{i+1}")
                columns = schema.get("columns", [])
                dtypes = schema.get("dtypes", {})
                row_count = schema.get("row_count", "?")
                sample_rows = schema.get("sample_rows", [])

                parts.append(f"\nТаблица: {var} ('{name}', {row_count} строк)")

                # Явный список колонок — КРИТИЧЕСКИ ВАЖНО для правильной генерации
                if columns:
                    col_info_parts = []
                    for col in columns:
                        dtype = dtypes.get(col, "")
                        if dtype:
                            col_info_parts.append(f"  - {col} ({dtype})")
                        else:
                            col_info_parts.append(f"  - {col}")
                    parts.append("Колонки:")
                    parts.extend(col_info_parts)

                # ── Data quality warnings для проблемных колонок ──
                # Анализируем sample_rows чтобы предупредить LLM о строковых null,
                # object-dtype числовых колонках и других подводных камнях
                if sample_rows and columns and dtypes:
                    dq_warnings: list[str] = []
                    for col in columns:
                        col_dtype = dtypes.get(col, "")
                        if col_dtype != "object":
                            continue
                        # Собираем уникальные значения из sample_rows
                        sample_vals = []
                        for row in sample_rows[:20]:
                            if isinstance(row, dict):
                                v = row.get(col)
                            else:
                                continue
                            sample_vals.append(v)
                        # Проверяем: есть ли строковые 'null'/'None'/'nan'?
                        str_nulls = [v for v in sample_vals if isinstance(v, str) and v.lower() in ('null', 'none', 'nan', 'n/a', 'na', '')]
                        # Проверяем: выглядит ли колонка числовой (есть числа среди значений)?
                        numeric_count = 0
                        for v in sample_vals:
                            if v is None:
                                continue
                            try:
                                float(str(v))
                                numeric_count += 1
                            except (ValueError, TypeError):
                                pass
                        # Генерируем предупреждения
                        if str_nulls and numeric_count > 0:
                            example_vals = list(set(str(v) for v in sample_vals if v is not None))[:5]
                            dq_warnings.append(
                                f"  🛑 {col} (object) содержит СТРОКОВЫЕ null-значения: {str_nulls[:3]}\n"
                                f"     Примеры значений: {example_vals}\n"
                                f"     → ОБЯЗАТЕЛЬНО: pd.to_numeric(df['{col}'], errors='coerce') перед числовыми операциями!"
                            )
                        elif numeric_count > len(sample_vals) * 0.5 and col_dtype == "object":
                            example_vals = list(set(str(v) for v in sample_vals if v is not None))[:5]
                            dq_warnings.append(
                                f"  ⚠️ {col} (object) выглядит числовой, но dtype=object. Значения: {example_vals}\n"
                                f"     → Используй pd.to_numeric(df['{col}'], errors='coerce')"
                            )
                    if dq_warnings:
                        parts.append("\n🔴 ПРЕДУПРЕЖДЕНИЯ О КАЧЕСТВЕ ДАННЫХ (учти при генерации кода!):")
                        parts.extend(dq_warnings)

                # Примеры данных — компактная таблица
                if sample_rows:
                    # Показываем до 5 строк для краткости в промпте
                    display_rows = sample_rows[:5]
                    parts.append(f"Примеры данных ({len(display_rows)} из {row_count} строк):")
                    # Header
                    if columns:
                        parts.append("  | " + " | ".join(str(c) for c in columns) + " |")
                        parts.append("  |" + "|".join(["---"] * len(columns)) + "|")
                    for row in display_rows:
                        if isinstance(row, dict):
                            vals = [str(row.get(c, ""))[:20] for c in columns]
                        elif isinstance(row, (list, tuple)):
                            vals = [str(v)[:20] for v in row]
                        else:
                            continue
                        parts.append("  | " + " | ".join(vals) + " |")

            if multiple:
                parts.append("\n⚠️ Несколько таблиц: используй df1, df2 и т.д.")
                parts.append("  Для объединения: pd.merge(df1, df2, on='common_col', how='left')")
            parts.append("")

        # ── 4. Контекст от аналитика ──
        if analyst_context:
            parts.append("АНАЛИЗ ДАННЫХ (от аналитика):")
            parts.append(analyst_context)
            parts.append("")

        # ── 5. Режим: ERROR RETRY, ITERATIVE или NEW ──
        is_error_retry = bool(error_details or previous_errors)
        if existing_code and is_error_retry:
            # ── ERROR RETRY: код сломан, нужно ИСПРАВИТЬ ──
            parts.append("━━━ РЕЖИМ: ИСПРАВЛЕНИЕ ОШИБКИ ━━━")
            parts.append(f"ОШИБОЧНЫЙ КОД (содержит баг, нужно ИСПРАВИТЬ):\n```python\n{existing_code}\n```")
            parts.append(
                "\n🛑 ЗАДАЧА: Сгенерируй ИСПРАВЛЕННЫЙ код!\n"
                "1. НЕ копируй ошибочный код — он СЛОМАН и его нужно ПЕРЕПИСАТЬ\n"
                "2. Прочитай ОШИБКУ ВЫПОЛНЕНИЯ выше и пойми причину бага\n"
                "3. Прочитай ПОДСКАЗКУ (💡) — она объясняет как исправить\n"
                "4. Сгенерируй НОВЫЙ код, который решает ту же задачу, но БЕЗ ошибки\n"
                "5. Используй ТОЛЬКО колонки из секции ВХОДНЫЕ ДАННЫЕ\n"
                "\n⚠️ КРИТИЧЕСКИ ВАЖНО: Твой код ДОЛЖЕН ОТЛИЧАТЬСЯ от ошибочного! "
                "Если ты вернёшь тот же код — ошибка повторится!\n"
            )
        elif existing_code:
            # ── ITERATIVE: расширение рабочего кода ──
            parts.append("━━━ РЕЖИМ: ИТЕРАТИВНАЯ ТРАНСФОРМАЦИЯ ━━━")
            
            # История трансформаций — компактно
            if chat_history and len(chat_history) > 0:
                user_msgs = [m for m in chat_history if m.get("role") == "user"]
                if user_msgs:
                    parts.append("История запросов:")
                    for i, msg in enumerate(user_msgs[-5:], 1):  # Последние 5
                        parts.append(f"  {i}. {msg.get('content', '')[:120]}")
                    parts.append("")
            
            parts.append(f"ТЕКУЩИЙ КОД:\n```python\n{existing_code}\n```")
            parts.append(
                "\nЗАДАЧА: Сгенерируй ПОЛНЫЙ САМОДОСТАТОЧНЫЙ код, который:\n"
                "1. ВКЛЮЧАЕТ всю логику из ТЕКУЩЕГО КОДА выше (все df_ переменные, вычисления)\n"
                "2. ДОБАВЛЯЕТ реализацию нового запроса\n"
                "3. Работает с ВХОДНЫМИ ДАННЫМИ (df / df1 / df2) — начинает вычисления от исходных таблиц\n"
                "4. Выполняется от начала до конца БЕЗ внешних переменных — весь код в одном блоке\n"
                "\n⚠️ КРИТИЧЕСКИ ВАЖНО: Если ТЕКУЩИЙ КОД определяет df_xxx = ..., "
                "ты ОБЯЗАН включить это определение в свой ответ! Иначе будет NameError.\n"
            )
        else:
            parts.append("━━━ РЕЖИМ: НОВАЯ ТРАНСФОРМАЦИЯ ━━━")

        # ── 6. Напоминание о ключевых правилах ──
        # Извлекаем список колонок для явного напоминания
        all_columns = []
        for schema in input_schemas:
            all_columns.extend(schema.get("columns", []))
        if all_columns:
            parts.append(f"\n⚠️ ДОСТУПНЫЕ КОЛОНКИ: {all_columns}")
            parts.append("   Используй ТОЛЬКО эти имена колонок. НЕ придумывай новые!")

        parts.append(
            "\nОТВЕТ: верни JSON {transformation_code, description, output_schema}"
        )
        return "\n".join(parts)

    def _build_widget_prompt(
        self, description: str, data_summary: str
    ) -> str:
        parts = [
            f"TASK: Generate interactive data visualization widget",
            f"DESCRIPTION: {description}",
        ]
        if data_summary:
            parts.append(f"\nDATA CONTEXT:\n{data_summary}")
        parts.append(
            "\nReturn VALID JSON: {widget_name, widget_code, description, widget_type}."
            " В widget_code используй \\n для переносов строк, \\\" для кавычек."
            " НЕ используй двойное экранирование (\\\\n)."
        )
        return "\n".join(parts)

    def _build_data_summary_for_widget(
        self,
        task: Dict[str, Any],
        agent_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Собирает краткое описание доступных данных для виджета."""
        parts: List[str] = []

        # input_data из task (ContentNode tables)
        input_data = task.get("input_data", [])
        if input_data:
            for node in input_data:
                for tbl in node.get("tables", []):
                    cols = tbl.get("columns", [])
                    parts.append(
                        f"Table '{tbl.get('name','?')}': columns={cols}, "
                        f"rows={len(tbl.get('rows', []))}"
                    )

        # Fallback: input_data_preview из context
        if not parts and context:
            input_preview = context.get("input_data_preview", {})
            for table_name, info in input_preview.items():
                cols = info.get("columns", [])
                sample = info.get("sample_rows", [])[:5]  # Увеличено с 2 до 5 строк для лучшего понимания формата
                parts.append(
                    f"Table '{table_name}': columns={cols}, "
                    f"rows={info.get('row_count', '?')}, "
                    f"sample={json.dumps(sample, ensure_ascii=False)}"
                )

        # V2 agent_results tables/sources
        for result in agent_results:
            if not isinstance(result, dict):
                continue
            agent = result.get("agent", "unknown")
            for tbl in result.get("tables", []):
                if isinstance(tbl, dict):
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

        return "\n".join(parts)

    def _extract_analyst_context(
        self, agent_results: List[Dict[str, Any]]
    ) -> str:
        """
        Извлекает полезный контекст из результатов предыдущих агентов
        (прежде всего analyst) для использования в трансформации.

        Analyst обычно возвращает narrative с описанием рекомендуемых
        операций (group by, aggregate, filter и т.д.).
        """
        parts: List[str] = []

        for result in agent_results:
            if not isinstance(result, dict):
                continue
            agent_name = result.get("agent", "unknown")

            # narrative / narrative_text — текстовое описание от агента
            narrative = result.get("narrative_text") or result.get("narrative", "")
            if narrative and isinstance(narrative, str):
                # Ограничиваем длину, чтобы не раздувать промпт
                trimmed = narrative[:500]
                parts.append(f"[{agent_name}] {trimmed}")

            # findings / recommendations — структурированные выводы
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

    # ══════════════════════════════════════════════════════════════════
    #  Smart error hints — конкретные инструкции для retry
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _get_error_hint(error_msg: str) -> Optional[str]:
        """Translate runtime error into actionable fix hint for LLM."""
        hints = [
            (
                r'Bin labels must be one fewer than the number of bin edges',
                'pd.cut: если bins=[a,b,c,d,e] (5 границ = 4 интервала), '
                'labels должен содержать РОВНО 4 элемента, а НЕ 5! '
                'Формула: len(labels) == len(bins) - 1. '
                'Пример: bins=[20,25,30,35,40], labels=[\'20-24\',\'25-29\',\'30-34\',\'35-39\']'
            ),
            (
                r'do not exist|Cannot subset columns|SpecificationError',
                'Неправильный синтаксис groupby().agg()! '
                'Ключи в .agg({}) — это СУЩЕСТВУЮЩИЕ колонки DataFrame, НЕ новые имена!\n'
                '❌ НЕПРАВИЛЬНО (ключи не существуют в DataFrame):\n'
                '  df.groupby("brand")[["salesCount","salesAmount"]].agg({"sales_count": "sum", "sales_amount": "sum"})\n'
                '✅ ПРАВИЛЬНО — используй NAMED AGGREGATION (БЕЗ выбора колонок через [[]]]):\n'
                '  df.groupby("brand").agg(\n'
                '      sales_count=("salesCount", "sum"),\n'
                '      sales_amount=("salesAmount", "sum")\n'
                '  ).reset_index()\n'
                'Формат: new_col_name=("existing_col", "func"). '
                'ОБЯЗАТЕЛЬНО удали [[...]] перед .agg() — он НЕ нужен при named aggregation!'
            ),
            (
                r"KeyError:.*",
                'Колонка не найдена в DataFrame! ВНИМАТЕЛЬНО проверь:\n'
                '1) Точное написание колонки (регистр ИМЕЕТ значение: biName ≠ biname)\n'
                '2) КАКОЙ DataFrame ты используешь — df1 и df2 имеют РАЗНЫЕ колонки!\n'
                '   Смотри секцию INPUT DATA — какие колонки есть в каждой таблице.\n'
                '3) Если ошибка содержит "Доступные колонки DataFrame" — используй эту информацию.\n'
                '4) НЕ обращайся к колонке df2 через df1 — проверь правильный DataFrame.\n'
                '5) ВАЖНО: После groupby().agg() результирующий DataFrame содержит ТОЛЬКО агрегированные колонки!\n'
                '   Если нужна колонка из исходного df — присоедини её через map():\n'
                '   df_top["logo"] = df_top["brand"].map(df.drop_duplicates("brand").set_index("brand")["logoUrl"])'
            ),
            (
                r'unexpected indent',
                'Код содержит лишние отступы. Убедись что код начинается без отступов (столбец 0).'
            ),
            (
                r'SettingWithCopyWarning|A value is trying to be set on a copy',
                'Используй .copy() перед модификацией: df_new = df[condition].copy()'
            ),
            (
                r'cannot reindex from a duplicate axis',
                'DataFrame содержит дублирующиеся индексы. Добавь .reset_index(drop=True) перед операцией.'
            ),
            (
                r'No numeric types to aggregate',
                'Агрегация применена к нечисловой колонке. Используй pd.to_numeric() '
                'или выбери числовую колонку для агрегации.'
            ),
            (
                r'incompatible index of inserted column',
                'Индексы не совпадают при присваивании колонки. '
                'Используй .values или .reset_index(drop=True) при присваивании.'
            ),
            (
                r'do not exist|Cannot subset columns|SpecificationError',
                'Неправильный синтаксис groupby().agg(). '
                'Ключи в .agg({}) — это СУЩЕСТВУЮЩИЕ колонки, НЕ новые имена! '
                '❌ НЕПРАВИЛЬНО: df.groupby("x")[["col1","col2"]].agg({"new_name": ("col1","sum")}) '
                '✅ ПРАВИЛЬНО (named aggregation, БЕЗ выбора колонок): '
                'df.groupby("x").agg(new_name=("col1", "sum"), other=("col2", "mean")).reset_index()'
            ),
            (
                r'cannot convert the series to.*float|cannot convert Series',
                'В groupby.apply() лямбда получает Series (группу), а не скаляр. '
                'Используй .agg() вместо .apply() для агрегации: '
                'df.groupby("col").agg(result=("value_col", "mean")).reset_index()'
            ),
            (
                r"unhashable type:.*'Series'",
                'groupby.apply() возвращает Series, который нельзя присвоить в колонку DataFrame. '
                'НЕ используй .apply() для агрегации. Вместо этого: '
                '1) Сначала pd.to_numeric(df["col"], errors="coerce") для каждой числовой колонки, '
                '2) Затем df.groupby("col").agg(avg_salary=("salaryFrom", "mean")).reset_index()'
            ),
            (
                r'could not convert string to float|cannot convert.*string.*float',
                'Колонка содержит строковые значения (включая строки "null", "None", "nan" и т.д.). '
                'Перед числовыми операциями ОБЯЗАТЕЛЬНО: '
                'df["col"] = pd.to_numeric(df["col"], errors="coerce")'
            ),
            (
                r'agg function failed.*dtype.*object|No numeric types to aggregate',
                'Агрегация применена к колонке с dtype=object (строки). '
                'Сначала приведи к числам: df["col"] = pd.to_numeric(df["col"], errors="coerce"), '
                'затем выполняй агрегацию.'
            ),
            (
                r'unsupported operand type.*str.*and.*(?:int|float)',
                'Арифметическая операция над строковой колонкой. '
                'Сначала конвертируй: pd.to_numeric(df["col"], errors="coerce")'
            ),
            (
                r'InvalidIndexError|Reindexing only valid with uniquely valued',
                'Колонка содержит дублирующиеся значения — нельзя напрямую делать df.set_index("col")!\n'
                '❌ НЕПРАВИЛЬНО: df.set_index("brand")["brandImageUrl"]  # brand встречается несколько раз!\n'
                '✅ ПРАВИЛЬНО — сначала дедуплицируй, затем делай map():\n'
                '   df_top["brand_logo"] = df_top["brand"].map(\n'
                '       df.drop_duplicates("brand").set_index("brand")["brandImageUrl"]\n'
                '   )\n'
                'ИЛИ через groupby().first():\n'
                '   df_top["brand_logo"] = df_top["brand"].map(\n'
                '       df.groupby("brand")["brandImageUrl"].first()\n'
                '   )'
            ),
            (
                r"name 'df_\w+' is not defined",
                'Переменная НЕ определена в твоём коде! '
                'В режиме ИТЕРАТИВНОЙ ТРАНСФОРМАЦИИ ты получаешь ТЕКУЩИЙ КОД (existing_code). '
                'Ты ОБЯЗАН включить ВСЕ определения df_ переменных из ТЕКУЩЕГО КОДА в свой ответ. '
                '❌ НЕЛЬЗЯ просто ссылаться на df_xxx — она НЕ существует, пока ты её не определишь. '
                '✅ Скопируй определение df_xxx = ... из ТЕКУЩЕГО КОДА и ДОБАВЬ новую логику. '
                'Твой код должен быть ПОЛНЫМ и САМОДОСТАТОЧНЫМ — выполняться с нуля.'
            ),
        ]
        for pattern, hint in hints:
            if re.search(pattern, error_msg, re.IGNORECASE):
                return hint
        return None

    # ══════════════════════════════════════════════════════════════════
    #  Validation
    # ══════════════════════════════════════════════════════════════════
    def _validate_python_code(self, code: str) -> Dict[str, Any]:
        """Синтаксическая проверка + детекция запрещённых паттернов и артефактов."""
        warnings: List[str] = []

        # ── 1. Forbidden patterns (security) ──
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return {
                    "valid": False,
                    "error": f"Forbidden pattern: {pattern}",
                }

        # ── 2. Артефакты GigaChat / JSON ──
        # Markdown wrappers — должны быть удалены cleanup, но проверяем
        if re.search(r'```(?:python)?', code):
            warnings.append("Markdown ``` wrapper detected in code (should be cleaned)")

        # Escaped quotes/brackets — JSON escape artifacts
        if re.search(r'\\["\'\[\]]', code):
            warnings.append("Escaped quotes/brackets detected (JSON artifact)")

        # ── 3. df_ variable existence ──
        if not re.search(r'\bdf_[a-z_][a-z0-9_]*\s*=', code):
            return {
                "valid": False,
                "error": "Output variable with 'df_' prefix not found",
            }

        # ── 4. Syntax check via AST ──
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "error": f"SyntaxError: {e}"}

        # ── 5. AST-based quality checks ──
        # Detect df_ = scalar assignments (common GigaChat mistake)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.startswith('df_'):
                        # Check for obviously scalar RHS: bare method call like df['col'].mean()
                        val = node.value
                        if isinstance(val, ast.Call):
                            func = val.func
                            if isinstance(func, ast.Attribute) and func.attr in (
                                'mean', 'sum', 'min', 'max', 'std', 'var',
                                'count', 'median', 'first', 'last', 'nunique',
                                'item', 'any', 'all', 'prod',
                            ):
                                # Check if it's chained on Subscript (df['col'].mean())
                                # but NOT on groupby (df.groupby().mean() returns DF)
                                if isinstance(func.value, ast.Subscript):
                                    warnings.append(
                                        f"df_ variable '{target.id}' likely assigned a scalar "
                                        f"(.{func.attr}() on Series). Wrap in pd.DataFrame()."
                                    )

        if ".iterrows()" in code:
            warnings.append("iterrows() detected — prefer vectorised ops")

        # ── 6. pd.cut bins/labels mismatch detection ──
        # Catch: bins=[a,b,c,d,e] (5 edges → 4 intervals) with labels=[...] (5 items)
        cut_matches = re.finditer(
            r'pd\.cut\s*\([^)]*bins\s*=\s*\[([^\]]+)\][^)]*labels\s*=\s*\[([^\]]+)\]',
            code, re.DOTALL
        )
        for m in cut_matches:
            bins_str, labels_str = m.group(1), m.group(2)
            n_bins = len([x.strip() for x in bins_str.split(',') if x.strip()])
            n_labels = len([x.strip() for x in labels_str.split(',') if x.strip()])
            expected_labels = n_bins - 1
            if n_labels != expected_labels:
                return {
                    "valid": False,
                    "error": (
                        f"pd.cut: bins has {n_bins} edges ({expected_labels} intervals) "
                        f"but labels has {n_labels} elements. "
                        f"Fix: labels must have exactly {expected_labels} elements."
                    ),
                }

        return {"valid": True, "warnings": warnings}

    # ══════════════════════════════════════════════════════════════════
    #  Syntax auto-repair
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _try_fix_unbalanced_parens(code: str) -> Optional[str]:
        """Try to fix code with unbalanced parentheses/brackets.

        GigaChat often drops a closing paren in multi-line calls, e.g.:
            sales_amount=('salesAmount', 'sum'
            ).reset_index()
        Missing ) after 'sum' causes SyntaxError.

        Strategy: for each unmatched opener, find a line before a line that
        starts with the closer and append the missing closer there.
        """
        pairs = [('(', ')'), ('[', ']'), ('{', '}')]
        close_to_open = {')': '(', ']': '[', '}': '{'}
        open_to_close = {'(': ')', '[': ']', '{': '}'}

        MAX_ITERATIONS = 5  # safety guard

        for _ in range(MAX_ITERATIONS):
            # Find which delimiter is unbalanced
            imbalance = {}
            for open_ch, close_ch in pairs:
                diff = code.count(open_ch) - code.count(close_ch)
                if diff != 0:
                    imbalance[(open_ch, close_ch)] = diff

            if not imbalance:
                break  # balanced

            fixed_any = False
            for (open_ch, close_ch), diff in imbalance.items():
                if diff > 0:
                    # More openers than closers — need to add close_ch
                    lines = code.split('\n')
                    for _ in range(diff):
                        inserted = False
                        # Find a line starting with close_ch, insert before it
                        for li in range(len(lines) - 1, 0, -1):
                            stripped = lines[li].lstrip()
                            if stripped.startswith(close_ch) and li > 0:
                                lines[li - 1] = lines[li - 1].rstrip() + close_ch
                                inserted = True
                                break
                        if not inserted:
                            # Fallback: append at end of last non-empty line
                            for li in range(len(lines) - 1, -1, -1):
                                if lines[li].strip():
                                    lines[li] = lines[li].rstrip() + close_ch
                                    break
                    code = '\n'.join(lines)
                    fixed_any = True
                elif diff < 0:
                    # More closers than openers — remove extra closers
                    lines = code.split('\n')
                    to_remove = abs(diff)
                    for li in range(len(lines) - 1, -1, -1):
                        while to_remove > 0 and close_ch in lines[li]:
                            # Remove the last occurrence of close_ch on this line
                            idx = lines[li].rfind(close_ch)
                            if idx >= 0:
                                lines[li] = lines[li][:idx] + lines[li][idx + 1:]
                                to_remove -= 1
                        if to_remove <= 0:
                            break
                    code = '\n'.join(lines)
                    fixed_any = True

            if not fixed_any:
                break

        try:
            ast.parse(code)
            return code
        except SyntaxError:
            return None

    # ══════════════════════════════════════════════════════════════════
    #  JSON parsing
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _unescape_html_code(code: str) -> str:
        """Fix double-escaped newlines/tabs/quotes from GigaChat.

        GigaChat often returns JSON with \\\\n instead of \\n inside string values.
        After json.loads() these become literal 2-char sequences (backslash + n)
        instead of real newline characters, rendering the HTML as one long line.
        """
        if not code:
            return code
        # Detect double-escaping: if code looks like HTML but has literal \n
        if '\\n' in repr(code) and ('<' in code):
            code = (code
                    .replace('\\n', '\n')
                    .replace('\\t', '\t')
                    .replace('\\"', '"'))
        return code

    @staticmethod
    def _fix_literal_escapes_outside_strings(text: str) -> str:
        """Convert literal \\n / \\t OUTSIDE JSON string values to real whitespace.

        GigaChat sometimes returns JSON with literal \\n between fields:
            {"key": "value", \\n  "key2": "value2"}
        Standard JSON does not allow backslash outside strings.
        """
        result: list[str] = []
        in_string = False
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == '\\' and in_string:
                # Inside string: JSON escape — copy \X verbatim
                result.append(ch)
                if i + 1 < n:
                    i += 1
                    result.append(text[i])
            elif ch == '"':
                in_string = not in_string
                result.append(ch)
            elif not in_string and ch == '\\' and i + 1 < n:
                nxt = text[i + 1]
                if nxt == 'n':
                    result.append('\n')
                    i += 1
                elif nxt == 't':
                    result.append('\t')
                    i += 1
                else:
                    result.append(ch)
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    @staticmethod
    def _fix_json_escapes(text: str) -> str:
        """Fix invalid backslash escapes from GigaChat (e.g. \\d, \\s, \\w)."""
        # Replace \X where X is NOT a valid JSON escape char (" \\ / b f n r t u)
        return re.sub(r'\\([^"\\\\bfnrtu/])', r'\\\\\1', text)

    @staticmethod
    def _sanitize_json_newlines(text: str) -> str:
        """Escape literal newlines/tabs inside JSON string values.
        
        GigaChat часто возвращает JSON с literal newlines в значениях строк:
            "transformation_code": "
            df_result = df.groupby(...)
            "
        Стандартный JSON не допускает literal \\n внутри строк — только \\\\n.
        
        Алгоритм: проходим посимвольно, внутри строк (между ") заменяем
        literal \\n → \\\\n, \\t → \\\\t, \\r → (удаляем).
        """
        result = []
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            
            if ch == '"' and (i == 0 or text[i - 1] != '\\'):
                in_string = not in_string
                result.append(ch)
            elif in_string:
                if ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    pass  # skip CR
                elif ch == '\t':
                    result.append('\\t')
                else:
                    result.append(ch)
            else:
                result.append(ch)
            
            i += 1
        
        return ''.join(result)

    def _parse_json_from_llm(self, response: str) -> Dict[str, Any]:
        """Извлекает JSON из ответа LLM (markdown блоки, plain JSON, fallback).
        Автоматически исправляет невалидные escape-последовательности и
        literal newlines в строковых значениях."""
        response = response.strip()

        def _fix_triple_quotes(raw: str) -> str:
            """Заменяет Python-style тройные кавычки на валидные JSON строки.
            GigaChat иногда возвращает: "key": \"""code\""" вместо "key": "code"
            """
            def _replace(m: re.Match) -> str:
                content = m.group(1).strip()
                return json.dumps(content)  # json.dumps экранирует \n, " и т.д.
            return re.sub(r'"""\s*(.*?)\s*"""', _replace, raw, flags=re.DOTALL)

        def _try_loads(raw: str) -> Optional[Dict]:
            # Варианты raw-текста: оригинал + с исправленными тройными кавычками
            triple_fixed = _fix_triple_quotes(raw)
            variants = [raw] if triple_fixed == raw else [raw, triple_fixed]

            for variant in variants:
                # 1. Прямой парсинг
                try:
                    return json.loads(variant)
                except json.JSONDecodeError:
                    pass
                # 2. Фикс невалидных escape-последовательностей
                try:
                    return json.loads(self._fix_json_escapes(variant))
                except json.JSONDecodeError:
                    pass
                # 3. Фикс literal newlines в строковых значениях
                #    (самая частая проблема GigaChat)
                try:
                    sanitized = self._sanitize_json_newlines(variant)
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    pass
                # 4. Комбинация обоих фиксов
                try:
                    sanitized = self._sanitize_json_newlines(variant)
                    return json.loads(self._fix_json_escapes(sanitized))
                except json.JSONDecodeError:
                    pass
                # 5. Фикс literal \n/\t OUTSIDE JSON strings
                #    GigaChat иногда ставит \n между полями: {"k":"v", \n "k2":"v2"}
                try:
                    fixed_outside = self._fix_literal_escapes_outside_strings(variant)
                    return json.loads(fixed_outside)
                except json.JSONDecodeError:
                    pass
                # 6. Комбинация: fix outside escapes + sanitize inside strings
                try:
                    fixed_outside = self._fix_literal_escapes_outside_strings(variant)
                    sanitized = self._sanitize_json_newlines(fixed_outside)
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    pass
                # 7. Ядерный вариант: all fixes combined
                try:
                    fixed_outside = self._fix_literal_escapes_outside_strings(variant)
                    sanitized = self._sanitize_json_newlines(fixed_outside)
                    return json.loads(self._fix_json_escapes(sanitized))
                except json.JSONDecodeError:
                    pass
            return None

        # markdown ```json ... ```
        m = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            result = _try_loads(m.group(1))
            if result is not None:
                return result

        # markdown ``` ... ```
        m = re.search(r'```\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            result = _try_loads(m.group(1))
            if result is not None:
                return result

        # raw JSON
        m = re.search(r'\{.*\}', response, re.DOTALL)
        if m:
            result = _try_loads(m.group())
            if result is not None:
                return result

        # regex fallback: извлекаем transformation_code напрямую
        # Работает даже когда код содержит " внутри строковых значений
        # Try on original response + version with literal \n fixed
        response_variants = [response]
        fixed_resp = self._fix_literal_escapes_outside_strings(response)
        if fixed_resp != response:
            response_variants.append(fixed_resp)

        tc_match = None
        for resp_variant in response_variants:
            tc_match = re.search(
                r'"transformation_code"\s*:\s*"([\s\S]*?)"\s*,\s*"(?:description|output)',
                resp_variant,
            )
            if tc_match:
                break
            # Попробовать тройные кавычки: """code"""
            tc_match = re.search(
                r'"transformation_code"\s*:\s*"{3}([\s\S]*?)"{3}\s*,\s*"(?:description|output)',
                resp_variant,
            )
            if tc_match:
                break
        if tc_match:
            code = tc_match.group(1).strip()
            desc_m = re.search(r'"description"\s*:\s*"([^"]*)"', response)
            return {
                "transformation_code": code,
                "description": desc_m.group(1) if desc_m else "",
            }

        # last resort
        return {"message": response}


# ══════════════════════════════════════════════════════════════════════
#  System Prompts (сокращённые — полные в TransformationAgent/ReporterAgent)
# ══════════════════════════════════════════════════════════════════════
TRANSFORMATION_SYSTEM_PROMPT = '''
Вы — TransformCodexAgent, генератор Python/pandas кода в системе GigaBoard.

Ваша задача: получить описание трансформации и входные данные, сгенерировать рабочий Python-код.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ФОРМАТ ОТВЕТА — СТРОГО JSON, НИЧЕГО КРОМЕ JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "transformation_code": "<чистый Python-код>",
  "description": "<что делает код>",
  "output_schema": {"columns": ["col1", "col2"], "estimated_rows": 100}
}

🚫 ЗАПРЕЩЕНО в transformation_code:
- НЕ оборачивай код в ```python ... ``` — ТОЛЬКО чистый Python
- НЕ экранируй кавычки: пиши df['col'], а НЕ df[\\"col\\"]
- НЕ добавляй отступы в начале строк (код идёт без общего отступа)
- НЕ используй тройные кавычки (\"\"\"...\"\"\") для многострочного кода
- Для переноса строк внутри JSON используй \\n
- НЕ пиши ничего кроме Python-кода (никаких комментариев с объяснениями)

Пример ПРАВИЛЬНОГО ответа:
{"transformation_code": "df_top_cities = df.groupby('city')['salary'].mean().reset_index()\\ndf_top_cities = df_top_cities.nlargest(10, 'salary')", "description": "Топ-10 городов по средней зарплате", "output_schema": {"columns": ["city", "salary"], "estimated_rows": 10}}

━━━ ПРАВИЛО 0: ИСПОЛЬЗУЙ ТОЛЬКО СУЩЕСТВУЮЩИЕ КОЛОНКИ ━━━
Это самая частая ошибка! Перед написанием кода ПРОВЕРЬ список колонок в секции INPUT DATA.
- Обращайся ТОЛЬКО к тем колонкам, которые перечислены в INPUT DATA
- НЕ придумывай колонки — если нужной колонки нет, создай её через вычисление
- Имена колонок РЕГИСТРОЗАВИСИМЫ: 'Amount' ≠ 'amount' ≠ 'AMOUNT'

━━━ ПРАВИЛО 1: ВХОДНЫЕ ПЕРЕМЕННЫЕ ━━━
- Одна таблица: df
- Несколько таблиц: df1, df2, df3... (а также доступны по имени таблицы)

━━━ ПРАВИЛО 2: ВЫХОДНЫЕ ПЕРЕМЕННЫЕ — ТОЛЬКО df_ DataFrame ━━━
Каждая переменная df_* становится ОТДЕЛЬНОЙ ТАБЛИЦЕЙ на экране пользователя.

КРИТИЧНО: df_ переменная ОБЯЗАНА быть pd.DataFrame!
❌ df_avg = df['salary'].mean()  ← ЭТО СКАЛЯР! Executor отвергнет!
✅ df_avg = pd.DataFrame({'average_salary': [df['salary'].mean()]})

❌ df_series = df['salary']  ← ЭТО Series! Не DataFrame!
✅ df_salaries = df[['salary']]  ← DataFrame с одной колонкой

✅ Используй описательные имена: df_sales_by_brand, df_top_10, df_monthly_revenue
❌ НЕ используй: df_result, df_output, df_final, df_data

❌ НИКОГДА не создавай алиасы:
   df_avg = df.groupby('city')['salary'].mean()
   df_stats = df_avg  # ← ДУБЛИКАТ! Будет 2 одинаковые таблицы!
✅ Для промежуточных вычислений — переменные БЕЗ df_ префикса:
   grouped = df.groupby('city')['salary'].mean()  # промежуточная
   df_city_stats = grouped.reset_index()  # финальный результат

━━━ ПРАВИЛО 3: GROUPBY + AGG — КРИТИЧЕСКИ ВАЖНО ━━━
Ключи в .agg({}) — это СУЩЕСТВУЮЩИЕ колонки, НЕ новые имена!

❌ НЕПРАВИЛЬНО:
df.groupby('brand').agg({'total_revenue': 'sum'})  # колонки 'total_revenue' нет!

✅ ПРАВИЛЬНО (named aggregation — ПРЕДПОЧТИТЕЛЬНЫЙ способ):
df.groupby('brand').agg(
    total_revenue=('amount', 'sum'),
    avg_qty=('quantity', 'mean')
).reset_index()

⚠️ ВСЕГДА добавляй .reset_index() после groupby — иначе группирующая колонка будет в индексе.

━━━ ПРАВИЛО 4: ИТЕРАТИВНАЯ ТРАНСФОРМАЦИЯ (ОБНОВЛЕНИЕ КОДА) ━━━
Если в чате есть твой предыдущий ответ с transformation_code — пользователь
просит МОДИФИКАЦИЮ существующего кода (а НЕ создание нового).

В этом случае:
• Возьми transformation_code из своего последнего ответа ЗА ОСНОВУ
• Внеси ТОЛЬКО те изменения, которые просит пользователь
• Сохрани ВСЕ определения df_xxx = ... — иначе будет NameError
• Верни ПОЛНЫЙ САМОДОСТАТОЧНЫЙ код в том же JSON-формате
• ❌ НЕ ссылайся на df_xxx без определения — будет NameError!

━━━ ПРАВИЛО 5: БЕЗОПАСНОСТЬ И БИБЛИОТЕКИ ━━━
✅ Разрешено: pandas (pd), numpy (np), re, datetime, gb (ИИ-ассистент)
🚫 Запрещено: eval, exec, __import__, os, sys, subprocess, open, файловый I/O

━━━ ПРАВИЛО 6: ТИПЫ ДАННЫХ ━━━
- Результат ОБЯЗАН быть DataFrame. Даже одно значение — обернуть в pd.DataFrame({'name': [value]})
- Используй .copy() при модификации подмножества данных (избегай SettingWithCopyWarning)
- Для дат: pd.to_datetime(df['date_col']) перед операциями с датами

━━━ ПРАВИЛО 7: SQL-СИНТАКСИС → PANDAS ━━━
Пользователь может писать запросы в SQL-стиле. Всегда переводи в pandas:
- rank() over (order by X desc) → df['col'].rank(ascending=False, method='min')
- row_number() over (partition by A order by B) → df.groupby('A')['B'].rank(method='first')
- CASE WHEN x > 10 THEN 'yes' ELSE 'no' → np.where(df['x'] > 10, 'yes', 'no')
- COALESCE(a, b) → df['a'].fillna(df['b'])
- DISTINCT → df.drop_duplicates()
- LIMIT N → df.head(N)
- HAVING count > 5 → (после groupby) фильтр по агрегату

━━━ ПРАВИЛО 8: AI-ЗАДАЧИ через gb.ai_resolve_batch() ━━━
`gb` — это готовый объект-помощник, уже доступный в пространстве имён.
❌ НЕЛЬЗЯ: gb = getattr(gb, 'instance', None)  ← перезапишет gb в None!
❌ НЕЛЬЗЯ: if gb is not None: ...               ← gb всегда доступен, проверка не нужна

Используй gb ТОЛЬКО для задач, которые НЕЛЬЗЯ решить через данные:
  ✅ Классификация/перевод/обогащение внешними данными:
```python
names = df['name'].tolist()
genders = gb.ai_resolve_batch(names, "определи пол: M или F")
df_with_gender = df.copy()
df_with_gender['gender'] = genders
```

  ❌ НЕ используй gb если нужная колонка УЖЕ ЕСТЬ в исходном df — используй map():
```python
# Добавить brandImageUrl в df_top_brands (после groupby, где эта колонка потерялась):
df_top_brands['brand_logo'] = df_top_brands['brand'].map(
    df.drop_duplicates('brand').set_index('brand')['brandImageUrl']
)
```

━━━ ПРАВИЛО 9: MERGE / JOIN (несколько таблиц) ━━━
При работе с df1, df2: используй pd.merge() с явным указанием on= или left_on=/right_on=.

━━━ ПРАВИЛО 10: pd.cut / pd.qcut — ПРОВЕРЯЙ КОЛИЧЕСТВО ━━━
pd.cut(data, bins=[...], labels=[...]):
- bins задают ГРАНИЦЫ интервалов. N границ → N-1 интервалов.
- labels должен содержать РОВНО N-1 элементов (по одному на интервал).

❌ bins=[20,25,30,35,40], labels=['a','b','c','d','e']  ← 5 границ, 4 интервала, но 5 labels!
✅ bins=[20,25,30,35,40], labels=['20-24','25-29','30-34','35-39']  ← 4 labels для 4 интервалов

Всегда считай: len(labels) == len(bins) - 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 СПРАВОЧНИК PANDAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── АГРЕГИРУЮЩИЕ ФУНКЦИИ В .agg() ──
Числовые: 'sum', 'mean', 'median', 'min', 'max', 'std', 'var', 'count', 'nunique'
Строковые: 'first', 'last', 'min', 'max', 'count', 'nunique'
► 'first' — берёт первое ненулевое значение в группе (для логотипов, названий, URL):
  df.groupby('brand').agg(
      sales=('amount', 'sum'),
      logo=('brandImageUrl', 'first'),   # первый логотип бренда в группе
      category=('category', 'first'),    # первая категория в группе
  ).reset_index()

── ФИЛЬТРАЦИЯ ──
df[df['col'] > 100]                             # числовое условие
df[df['col'] == 'value']                        # строковое равенство
df[(df['col1'] > 0) & (df['col2'] == 'A')]      # AND (обязательны скобки!)
df[(df['col1'] > 0) | (df['col2'] == 'A')]      # OR
df[~df['col'].isna()]                           # не NULL
df[df['col'].isin(['A', 'B', 'C'])]             # вхождение в список
df[df['col'].notna()]                           # не NULL (альтернативно)
df.query("col > 100 and category == 'food'")    # SQL-стиль (удобно для сложных условий)

── СОЗДАНИЕ И ИЗМЕНЕНИЕ КОЛОНОК ──
df['new_col'] = df['a'] + df['b']               # арифметика
df['new_col'] = df['price'] * df['qty']         # умножение
df['new_col'] = np.where(df['x'] > 0, 'pos', 'neg')  # условное значение (аналог CASE WHEN)
df['new_col'] = df['col'].apply(lambda x: x * 2)     # применить функцию к каждому значению
df['new_col'] = pd.to_numeric(df['col'], errors='coerce')  # конвертация в число (null если не число)
df['new_col'] = df['a'].fillna(df['b'])         # замена null из другой колонки (COALESCE)
df['new_col'] = df['col'].fillna(0)             # замена null константой

► np.select — несколько условий (аналог CASE WHEN с многими ветками):
  conditions = [df['score'] >= 90, df['score'] >= 70, df['score'] >= 50]
  choices    = ['A', 'B', 'C']
  df['grade'] = np.select(conditions, choices, default='F')

── СТРОКОВЫЕ ОПЕРАЦИИ (.str.*) ──
df['col'].str.lower()                    # в нижний регистр
df['col'].str.upper()                    # в верхний регистр
df['col'].str.strip()                    # убрать пробелы по краям
df['col'].str.replace('old', 'new')     # замена подстроки
df['col'].str.contains('pattern')       # фильтр по подстроке (возвращает bool Series)
df['col'].str.startswith('prefix')      # начинается с...
df['col'].str.len()                      # длина строки
df['col'].str.split(',').str[0]          # разбить по разделителю, взять первый элемент
df[['first', 'last']] = df['full_name'].str.split(' ', n=1, expand=True)  # разбить в 2 колонки

── ОПЕРАЦИИ С ДАТАМИ ──
df['date'] = pd.to_datetime(df['date_col'])  # обязательно перед .dt.*!
df['year']    = df['date'].dt.year
df['month']   = df['date'].dt.month          # 1-12
df['day']     = df['date'].dt.day
df['weekday'] = df['date'].dt.dayofweek      # 0=понедельник, 6=воскресенье
df['week']    = df['date'].dt.isocalendar().week.astype(int)
df['quarter'] = df['date'].dt.quarter
df['month_name'] = df['date'].dt.strftime('%Y-%m')   # '2024-03'
df['days_ago'] = (pd.Timestamp.now() - df['date']).dt.days

── СОРТИРОВКА И РАНЖИРОВАНИЕ ──
df.sort_values('col', ascending=False)                       # по убыванию
df.sort_values(['col1', 'col2'], ascending=[False, True])    # по нескольким колонкам
df.nlargest(10, 'amount')                                    # топ-10 по значению (эффективнее sort+head)
df.nsmallest(5, 'price')                                     # 5 наименьших
df['rank'] = df['amount'].rank(ascending=False, method='min')  # ранг (1 = наибольший)
df['rank'] = df.groupby('category')['amount'].rank(ascending=False)  # ранг внутри группы

── ДОБАВЛЕНИЕ КОЛОНКИ ИЗ ДРУГОГО DataFrame ЧЕРЕЗ map() ──
►  СИТУАЦИЯ: после groupby() нужная строковая колонка потеряна, ней нет в результате.
►  РЕШЕНИЕ: map() по ключу из исходного df.
df_top['brand_logo'] = df_top['brand'].map(
    df.groupby('brand')['brandImageUrl'].first()    # уникальный URL на бренд
)
# ИЛИ через drop_duplicates (когда одна запись = один бренд):
df_top['brand_logo'] = df_top['brand'].map(
    df.drop_duplicates('brand').set_index('brand')['brandImageUrl']
)

── MERGE / JOIN ──
pd.merge(df1, df2, on='id')                             # inner join по одной колонке
pd.merge(df1, df2, on=['id', 'date'])                   # inner join по нескольким
pd.merge(df1, df2, left_on='city_id', right_on='id')    # разные имена колонок
pd.merge(df1, df2, on='id', how='left')                 # left join (все строки из df1)
pd.merge(df1, df2, on='id', how='outer')                # full outer join

── RESHAPE: PIVOT / MELT ──
► pivot_table — сводная таблица (как сводная в Excel):
  df_pivot = df.pivot_table(
      index='region',        # строки
      columns='category',    # колонки
      values='sales',        # значения
      aggfunc='sum',         # агрегация
      fill_value=0           # null → 0
  ).reset_index()

► melt — из "широкого" формата в "длинный":
  df_long = df.melt(id_vars=['date', 'region'], value_vars=['sales', 'returns'],
                    var_name='metric', value_name='value')

── НАКОПИТЕЛЬНЫЕ / СКОЛЬЗЯЩИЕ ──
df['cumulative'] = df['sales'].cumsum()                        # накопительная сумма
df['running_avg'] = df['sales'].rolling(window=7).mean()       # скользящее среднее (7 дней)
df['pct_of_total'] = df['sales'] / df['sales'].sum() * 100    # % от общего
df['pct_of_group'] = df.groupby('cat')['sales'].transform(
    lambda x: x / x.sum() * 100
)   # % от суммы своей группы

── ДЕДУПЛИКАЦИЯ И ОЧИСТКА ──
df.drop_duplicates()                          # удалить полные дубликаты
df.drop_duplicates(subset=['id'])             # дубликаты по колонке
df.drop_duplicates(subset=['id'], keep='last') # оставить последнее вхождение
df.dropna(subset=['col'])                     # удалить строки где col = null
df['col'] = df['col'].clip(lower=0, upper=1000)  # ограничить диапазон
'''

WIDGET_SYSTEM_PROMPT = '''
Вы — TransformCodexAgent (Генератор Виджетов, legacy fallback) в системе GigaBoard Multi-Agent.

**ROLE**: Generate interactive HTML/CSS/JS data visualization widgets.

**DATA ACCESS**: const data = await window.fetchContentData();
  Structure: data.tables[0].columns, data.tables[0].rows

**VISUALIZATION LIBRARIES** (use as needed):
- Chart.js v4: https://cdn.jsdelivr.net/npm/chart.js@4
- Plotly v2.35+: https://cdn.plot.ly/plotly-2.35.2.min.js
- D3 v7: https://cdn.jsdelivr.net/npm/d3@7
- ECharts v6 (local): /libs/echarts.min.js

**RULES**:
1. Full HTML doc with <!DOCTYPE html>.
2. Responsive: width/height 100%, no overflow.
3. Wait for CDN library load before calling render().
4. Call window.startAutoRefresh(render) for auto-update.
5. Cache previousData to skip redundant redraws.
6. Destroy old chart instances before creating new ones.
7. **CRITICAL**: render() MUST be `async function render()` — fetchContentData() returns Promise!
   ❌ WRONG: `function render() { fetchData().then(d => d).forEach(...) }` → TypeError: not a function
   ✅ RIGHT: `async function render() { const data = await window.fetchContentData(); ... }`

**OUTPUT FORMAT (JSON)**:

Верни ТОЛЬКО валидный JSON-объект. Пример:
```json
{
  "widget_name": "Short Name",
  "widget_code": "<!DOCTYPE html>\\n<html>\\n<head>...</head>\\n<body>...</body>\\n</html>",
  "description": "Brief description",
  "widget_type": "chart"
}
```

⚠️ КРИТИЧЕСКИ ВАЖНО — правила экранирования в значении "widget_code":
- Переносы строк: используй \\n (один обратный слэш + n)
- Табуляцию: используй \\t (один обратный слэш + t)
- Кавычки внутри HTML: используй \\" (один обратный слэш + кавычка)
- НЕ используй двойное экранирование (\\\\n, \\\\t, \\\\") — это ОШИБКА
- Весь HTML-код должен быть в ОДНОЙ строке JSON с правильными escape-последовательностями
- Пример правильно: "<div id=\\"chart\\">\\n  <p>Hello</p>\\n</div>"
- Пример НЕПРАВИЛЬНО: "<div id=\\\\"chart\\\\">\\\\n  <p>Hello</p>\\\\n</div>"

Return ONLY valid JSON, nothing else.
'''
