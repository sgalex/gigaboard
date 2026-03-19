"""
Reporter Agent - Final Report Assembly
Собирает итоговый отчёт из результатов всех предыдущих агентов.

V2: Только narrative assembly. Генерация виджетов — WidgetCodexAgent.
    Возвращает AgentPayload(narrative=..., code_blocks=[passthrough], tables=[passthrough]).
    См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
import json
from typing import Dict, Any, Optional, List
import re

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import (
    CodeBlock,
    Finding,
    Narrative,
    PayloadContentTable,
)
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Reporter Agent
REPORTER_SYSTEM_PROMPT = '''Ты генератор интерактивных визуализаций данных. Отвечай ТОЛЬКО валидным JSON.

ФОРМАТ ОТВЕТА:
{
  "widget_name": "Краткое название (2-4 слова)",
  "widget_code": "<!DOCTYPE html>...",
  "description": "Краткое описание виджета",
  "widget_type": "chart|table|metric|custom"
}

ТРЕБОВАНИЯ К widget_code:
1. Полный HTML документ с <!DOCTYPE html>
2. Подключай нужные библиотеки:
   - Chart.js v4: https://cdn.jsdelivr.net/npm/chart.js@4
   - Plotly v2.35+: https://cdn.plot.ly/plotly-2.35.2.min.js
   - D3 v7: https://cdn.jsdelivr.net/npm/d3@7
   - ECharts v6 (локально): /libs/echarts.min.js
3. Данные получай через: const data = await window.fetchContentData();
4. Структура данных: data.tables[0].columns (названия колонок), data.tables[0].rows (массив строк)
5. Вызывай render() при загрузке
6. ВСЕГДА вызывай window.startAutoRefresh(render) БЕЗ второго параметра - интервал задается пользователем
7. **КРИТИЧЕСКИ ВАЖНО**: render() ОБЯЗАН быть `async function render()` — fetchContentData() возвращает Promise!
   ❌ НЕПРАВИЛЬНО: `function render() { fetchData().then(d => d); rows.forEach(...) }` → TypeError: not a function
   ✅ ПРАВИЛЬНО: `async function render() { const data = await window.fetchContentData(); ... }`

НЕ ВЫДУМЫВАЙ КЛАССЫ И ФУНКЦИИ:
- Используй ТОЛЬКО стандартные API перечисленных библиотек
- НЕ используй несуществующие классы вроде LinearColorScale, ColorScale, DataProcessor и т.п.
- Для цветовых шкал в D3 используй: d3.scaleLinear(), d3.scaleSequential(), d3.interpolateBlues и т.п.
- Для Chart.js используй встроенные цвета или массивы цветов
- Если не уверен в API - используй простые встроенные методы библиотеки

ОПТИМИЗАЦИЯ AUTO-REFRESH (ОБЯЗАТЕЛЬНО ДЛЯ ВСЕХ ВИДЖЕТОВ):
- Сохраняй previousData через window.previousData = null (НЕ let/const!)
- Проверяй изменение данных ПЕРЕД обновлением: if(JSON.stringify(table.rows) === window.previousData) return;
- НЕ обновляй виджет если данные не изменились (избегай лишних перерисовок)
- Отключай анимации при auto-refresh (animation: false, transitions: { duration: 0 })
- Уничтожай старые инстансы перед созданием новых (destroy, remove, clear)
- Используй window.chartInstance для Chart.js (НЕ let/const!)

АДАПТИВНАЯ ВЕРСТКА (ОБЯЗАТЕЛЬНО):
- html, body: margin:0; padding:0; width:100%; height:100%; overflow:hidden;
- Контейнер графика: width:100%; height:100%;
- Для Chart.js v4: responsive:true, maintainAspectRatio:false
- Для Plotly: Plotly.newPlot(el, data, layout, {responsive:true}), layout должен содержать autosize:true
- Для таблиц: width:100%; overflow:auto;

ЗАГРУЗКА CDN БИБЛИОТЕК (КРИТИЧЕСКИ ВАЖНО — ДЛЯ ВСЕХ СТОРОННИХ БИБЛИОТЕК):
- ВСЕГДА жди загрузки ЛЮБОЙ библиотеки перед использованием!
- Это касается Chart.js, Plotly, D3, ECharts, Three.js, Leaflet, ApexCharts, HighCharts, и ЛЮБЫХ других CDN библиотек
- Используй DOMContentLoaded + проверку наличия объекта библиотеки
- Паттерн для гарантированной загрузки (ОБЯЗАТЕЛЕН для всех библиотек):
  
  function waitForLibrary(checkFn, callback, maxWait = 5000) {
    const start = Date.now();
    const check = () => {
      if (checkFn()) { callback(); }
      else if (Date.now() - start < maxWait) { setTimeout(check, 50); }
      else { console.error('Library failed to load'); }
    };
    check();
  }
  
  // Примеры проверок для разных библиотек:
  // Chart.js:   () => typeof Chart !== 'undefined'
  // Plotly:     () => typeof Plotly !== 'undefined'
  // D3:         () => typeof d3 !== 'undefined'
  // ECharts:    () => typeof echarts !== 'undefined'
  // Three.js:   () => typeof THREE !== 'undefined'
  // Leaflet:    () => typeof L !== 'undefined'
  // ApexCharts: () => typeof ApexCharts !== 'undefined'
  // Любая:      () => typeof GlobalObjectName !== 'undefined'
  
  document.addEventListener('DOMContentLoaded', () => {
    waitForLibrary(() => typeof LIBRARY !== 'undefined', () => {
      render();
      window.startAutoRefresh(render);
    });
  });

- НИКОГДА не вызывай render() сразу после тега </script>!
- ВСЕГДА проверяй в начале render(): if (typeof LibraryName === 'undefined') return;
- Правило применяется к ЛЮБОЙ внешней библиотеке загружаемой через CDN

СЕЛЕКТОРЫ DOM ЭЛЕМЕНТОВ (ВАЖНО):
- document.getElementById('myId') - передавай ID БЕЗ решётки (#)
- Plotly.newPlot('plot-container', ...) - ID БЕЗ решётки ИЛИ сам DOM элемент
- Plotly.purge('plot-container') - ID БЕЗ решётки
- new Chart(document.getElementById('chart'), ...) - DOM элемент, не строка
- echarts.init(document.getElementById('chart')) - DOM элемент
- НЕПРАВИЛЬНО: Plotly.purge('#plot-container') - решётка вызовет ошибку!
- ПРАВИЛЬНО: Plotly.purge('plot-container') или Plotly.purge(document.getElementById('plot-container'))

CHART.JS v4 СИНТАКСИС:
- Используй Chart.js v4.x: <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
- Конфигурация scales: scales: { y: {...}, x: {...} } (НЕ yAxes/xAxes!)
- Перед созданием: if(window.chartInstance) window.chartInstance.destroy();
- Сохраняй инстанс: window.chartInstance = new Chart(...)

PLOTLY СИНТАКСИС:
- Используй Plotly v2.35+: <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
- Перед созданием: Plotly.purge('container-id'); // БЕЗ решётки!
- Создание: Plotly.newPlot('container-id', data, layout, {responsive: true});
- Или через DOM: Plotly.newPlot(document.getElementById('container-id'), data, layout);

ПРИМЕР widget_code:
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; }
    #chart-container { width:100%; height:100%; }
  </style>
</head>
<body>
  <div id="chart-container"><canvas id="chart"></canvas></div>
  <script>
    window.previousData = null;
    
    // Ожидание загрузки библиотеки
    function waitForLibrary(checkFn, callback, maxWait = 5000) {
      const start = Date.now();
      const check = () => {
        if (checkFn()) { callback(); }
        else if (Date.now() - start < maxWait) { setTimeout(check, 50); }
        else { console.error('Library failed to load'); }
      };
      check();
    }
    
    async function render() {
      // Проверка загрузки библиотеки
      if (typeof Chart === 'undefined') return;
      
      const data = await window.fetchContentData();
      const table = data.tables[0];
      if (!table) return;
      
      // Проверить изменились ли данные (НЕ обновлять без необходимости)
      const currentData = JSON.stringify(table.rows);
      if (currentData === window.previousData) return;
      window.previousData = currentData;
      
      // Уничтожить старый график перед созданием нового
      if (window.chartInstance) window.chartInstance.destroy();
      
      // Создать новый график
      window.chartInstance = new Chart(document.getElementById("chart"), {
        type: "bar",
        data: {
          labels: table.rows.map(r => r[0]),
          datasets: [{ label: "Значения", data: table.rows.map(r => r[1]) }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 0 },
          scales: { y: { beginAtZero: true } }
        }
      });
    }
    
    // Запуск после загрузки библиотеки
    document.addEventListener('DOMContentLoaded', () => {
      waitForLibrary(() => typeof Chart !== 'undefined', () => {
        render();
        window.startAutoRefresh(render);
      });
    });
  </script>
</body>
</html>

ВАЖНО:
- window.fetchContentData() и window.startAutoRefresh() уже определены, НЕ переопределяй их
- window.startAutoRefresh(render) - вызывай БЕЗ указания интервала (он задан пользователем)
- Используй table.rows (не table.data)
- Отвечай ТОЛЬКО JSON объектом

CROSS-FILTER SUPPORT (кросс-фильтрация виджетов):
Каркас предоставляет window.emitClick(field, value, metadata) для кросс-фильтрации.
ВСЕГДА добавляй click handlers, вызывающие emitClick() при клике на элементы визуализации.

Примеры:
- ECharts:  chart.on('click', (p) => window.emitClick && window.emitClick(p.seriesName || p.name, p.name))
- Chart.js: onClick handler → window.emitClick(label, value)
- Plotly:   plotDiv.on('plotly_click', (d) => window.emitClick && window.emitClick(d.points[0].data.name, d.points[0].label))
- Table:    row click → window.emitClick(firstColumnName, cellValue)
Всегда проверяй: if (window.emitClick) перед вызовом.'''


class ReporterAgent(BaseAgent):
    """
    Reporter Agent — финальная сборка отчёта (V2).

    V2:
      • Собирает narrative, findings, tables, code_blocks из agent_results
      • Через LLM формирует итоговый связный отчёт
      • Passthrough: code_blocks и tables из предыдущих агентов
      • Возвращает AgentPayload(narrative=..., code_blocks=[], tables=[], findings=[])

    V1 (legacy):
      • Генерация HTML/JS виджетов (сохранена для обратной совместимости)
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="reporter",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router
        
    def _get_default_system_prompt(self) -> str:
        return REPORTER_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        V2: Собирает итоговый отчёт → AgentPayload(narrative=..., code_blocks=[], tables=[], findings=[]).
        V1 fallback: Если task.type == create/update_visualization — legacy widget gen.
        """
        task_type = task.get("type", "")

        # ── V1 legacy widget generation ──────────────────────────────
        if task_type in ("create_visualization", "update_visualization"):
            return await self._create_visualization(task, context)

        # ── V2: narrative assembly (default) ─────────────────────────
        try:
            return await self._assemble_report(task, context)
        except Exception as e:
            self.logger.error(f"ReporterAgent error: {e}", exc_info=True)
            return self._error_payload(str(e))
    
    # ══════════════════════════════════════════════════════════════════
    #  V2: Narrative Assembly
    # ══════════════════════════════════════════════════════════════════
    async def _assemble_report(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        V2: Собирает итоговый отчёт из agent_results всех агентов.

        1. Извлекает narrative/findings/tables/code_blocks из каждого агента.
        2. Через LLM синтезирует связный текст.
        3. Passthrough: code_blocks и tables пробрасываются как есть.
        """
        description = task.get("description", "Сформируй итоговый отчёт")
        original_user_request = (
            (context or {}).get("original_user_request")
            or (context or {}).get("user_request")
            or description
        )
        direct_fact_mode = self._is_direct_fact_question(str(original_user_request))
        response_style = self._detect_response_style(str(original_user_request))

        reporter_style_instruction = self._build_reporter_style_instruction(
            direct_fact_mode=direct_fact_mode,
            response_style=response_style,
        )
        # Изменение #2: agent_results — list (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
        # FIX: Читаем только результаты текущего плана, чтобы не подтягивать
        # стейл code_blocks из предыдущих replan-циклов.
        all_agent_results = (context or {}).get("agent_results", [])
        results_start = (context or {}).get("current_plan_results_start", 0)
        agent_results = all_agent_results[results_start:]

        # Если нет данных — попытаться вытянуть из Redis
        session_id = (context or {}).get("session_id")
        if session_id and not agent_results:
            all_res = await self.get_all_previous_results(session_id)
            if all_res:
                # Redis может вернуть dict — конвертируем
                if isinstance(all_res, dict):
                    agent_results = list(all_res.values())
                else:
                    agent_results = all_res

        # ── Collect data from previous agents ────────────────────────
        all_findings: List[Finding] = []
        all_tables: List[PayloadContentTable] = []
        all_code_blocks: List[CodeBlock] = []
        narrative_parts: List[str] = []

        for result in agent_results:
            if not isinstance(result, dict):
                continue
            agent_name = result.get("agent", "unknown")

            # narrative text
            nar = result.get("narrative")
            if isinstance(nar, dict) and nar.get("text"):
                narrative_parts.append(f"[{agent_name}] {nar['text']}")
            elif isinstance(nar, str) and nar:
                narrative_parts.append(f"[{agent_name}] {nar}")

            # findings
            for f in result.get("findings", []):
                if isinstance(f, dict):
                    try:
                        all_findings.append(Finding(**f))
                    except Exception:
                        all_findings.append(Finding(type="insight", text=str(f)))

            # tables — passthrough as Pydantic models
            for t in result.get("tables", []):
                if isinstance(t, dict):
                    try:
                        all_tables.append(PayloadContentTable(**t))
                    except Exception:
                        pass

            # code_blocks — passthrough
            for cb in result.get("code_blocks", []):
                if isinstance(cb, dict):
                    try:
                        all_code_blocks.append(CodeBlock(**cb))
                    except Exception:
                        pass

        self.logger.info(
            f"📝 Report assembly: {len(narrative_parts)} narratives, "
            f"{len(all_findings)} findings, {len(all_tables)} tables, "
            f"{len(all_code_blocks)} code blocks"
        )

        # ── LLM synthesis ────────────────────────────────────────────
        if narrative_parts:
            synthesis_prompt = (
                "Сформулируй итоговый ответ пользователю на основе фрагментов ниже.\n"
                f"Оригинальный запрос пользователя: {original_user_request}\n"
                f"Техническое описание шага: {description}\n\n"
                + "\n\n".join(narrative_parts)
            )
            messages = [
                {"role": "system", "content": reporter_style_instruction},
                {"role": "user", "content": synthesis_prompt},
            ]
            try:
                synthesized = await self._call_llm(
                    messages, context=context, temperature=0.3, max_tokens=2000
                )
            except Exception as e:
                self.logger.warning(f"LLM synthesis failed, using raw: {e}")
                synthesized = "\n\n".join(narrative_parts)
        else:
            # Нет narrative от агентов — формируем ответ из того, что есть в контексте.
            # Принцип: что есть в контексте — используем; чего нет — не подставляем специальных сообщений.
            user_request = (context or {}).get("user_request", description)
            board_context = (context or {}).get("board_context", {})
            content_nodes = board_context.get("content_nodes", [])

            parts = [f"Запрос пользователя: {user_request or '(нет текста)'}", f"Описание задачи: {description}"]
            if content_nodes:
                parts.append("Данные на доске:")
                for cn in content_nodes[:5]:
                    parts.append(f"  • {cn.get('name', 'Node')}: {cn.get('content_summary', '')}")
            if all_findings:
                parts.append("Найденные факты:")
                for f in all_findings[:10]:
                    parts.append(f"  • {f.text if hasattr(f, 'text') else f.get('text', str(f))}")

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты — ReporterAgent. Сформируй ответ пользователю по запросу и имеющемуся контексту. "
                        "Используй только то, что передано; если контекста нет — отвечай по существу запроса. "
                        f"{reporter_style_instruction}"
                    ),
                },
                {"role": "user", "content": "\n\n".join(parts)},
            ]
            try:
                synthesized = await self._call_llm(
                    messages, context=context, temperature=0.5, max_tokens=2000
                )
            except Exception as e:
                self.logger.warning(f"Reporter LLM failed: {e}")
                synthesized = "Не удалось сформировать ответ. Попробуйте уточнить запрос."

        # Reporter не копирует чужие findings в свой payload,
        # чтобы _extract_findings не собирал дубли из analyst + reporter
        return self._success_payload(
            narrative=Narrative(text=synthesized, format="markdown"),
            findings=[],
            tables=all_tables,
            code_blocks=all_code_blocks,
        )

    @staticmethod
    def _is_direct_fact_question(user_request: str) -> bool:
        low = (user_request or "").lower()
        has_fact_pattern = any(
            p in low
            for p in (
                "какой самый",
                "кто самый",
                "самый ходовой",
                "самый продаваем",
                "топ-1",
                "лидер",
                "сколько",
                "какова",
            )
        )
        # Avoid forcing ultra-short style for broad ideation requests.
        broad_markers = (
            "рекомендац",
            "как улучшить",
            "варианты",
            "подробно",
            "сделай отчёт",
            "исследуй",
        )
        return has_fact_pattern and not any(m in low for m in broad_markers)

    @staticmethod
    def _detect_response_style(user_request: str) -> str:
        """Detect preferred response volume from user phrasing."""
        low = (user_request or "").lower()

        concise_markers = (
            "кратко",
            "в двух словах",
            "одним предложением",
            "без деталей",
            "коротко",
            "только ответ",
        )
        detailed_markers = (
            "подробно",
            "детально",
            "развернуто",
            "с отчётом",
            "с отчетом",
            "пошагово",
            "с примерами",
            "обоснуй",
        )
        if any(m in low for m in concise_markers):
            return "concise"
        if any(m in low for m in detailed_markers):
            return "detailed"
        return "normal"

    @staticmethod
    def _build_reporter_style_instruction(
        *,
        direct_fact_mode: bool,
        response_style: str,
    ) -> str:
        """Build response-style instruction for Reporter LLM call."""
        if direct_fact_mode:
            return (
                "Это узкий фактологический вопрос. "
                "Формат ответа: 1) первая строка — прямой факт-ответ с конкретным именем/значением; "
                "2) далее максимум 2 коротких пункта с ключевыми метриками. "
                "Не пиши длинный отчёт и общие рекомендации."
            )
        if response_style == "concise":
            return (
                "Отвечай кратко: максимум 3 коротких предложения, без лишних разделов и длинных списков. "
                "Сначала суть, потом (опционально) одна уточняющая деталь."
            )
        if response_style == "detailed":
            return (
                "Пользователь просит подробный ответ. Можно структурировать markdown-секциями и короткими списками, "
                "но только по делу запроса и на основе предоставленного контекста."
            )
        return (
            "Подбирай объём под запрос пользователя: не превращай каждый ответ в отчёт. "
            "Если вопрос узкий — отвечай компактно; если запрос исследовательский — можно подробнее."
        )

    # ══════════════════════════════════════════════════════════════════
    #  V1 legacy: Widget generation (kept for backward compatibility)
    # ══════════════════════════════════════════════════════════════════
    async def _create_visualization(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Создает WidgetNode визуализацию из DataNode или ContentNode.
        """
        try:
            session_id = context.get("session_id") if context else None
            
            # Support both old (DataNode) and new (ContentNode) format
            description = task.get("description") or task.get("user_prompt")
            if not description:
                # If no explicit prompt, analyze data and auto-generate
                description = "Create an appropriate visualization for this data"
            
            # Extract data from ContentNode or DataNode format
            content_node = task.get("content_node")
            data_preview = {}
            data_schema = {}
            analyst_insights = None
            analyst_recommendations = None
            
            # === Попробуем получить результаты аналитика из Redis для enrichment ===
            if session_id:
                analyst_result = await self.get_agent_result(session_id, "analyst")
                if analyst_result and analyst_result.get("status") == "success":
                    # Новый формат AnalystAgent: insights[], recommendations[]
                    analyst_insights = analyst_result.get("insights", [])
                    analyst_recommendations = analyst_result.get("recommendations", [])
                    insight_count = len(analyst_insights) if analyst_insights else 0
                    recommendation_count = len(analyst_recommendations) if analyst_recommendations else 0
                    self.logger.info(f"📊 Got {insight_count} insights, {recommendation_count} recommendations from AnalystAgent")
            
            if content_node:
                # New ContentNode format
                content = content_node.get("content", {})
                data_text = content.get("text", "")
                tables = content.get("tables", [])
                
                # Build data preview from tables
                data_preview = {}
                data_schema = {}
                
                if tables:
                    # Use first table for visualization
                    first_table = tables[0]
                    data_preview = {
                        "table_name": first_table.get("name", "данные"),
                        "columns": first_table.get("columns", []),
                        "rows": first_table.get("rows", [])[:5],  # First 5 rows
                        "row_count": first_table.get("row_count", len(first_table.get("rows", [])))
                    }
                    data_schema = {
                        "columns": first_table.get("columns", []),
                        "column_types": first_table.get("column_types", {})
                    }
                
                # If multiple tables, note in description
                if len(tables) > 1:
                    description += f" (Note: ContentNode has {len(tables)} tables, visualizing first one)"
                
            else:
                # Old DataNode format
                data_preview = task.get("data_preview", {})
                data_schema = task.get("data_schema", {})
            
            chart_type = task.get("chart_type", "auto")
            
            self.logger.info(f"📊 Creating visualization: {description[:100]}...")
            
            # Получаем текущий код виджета если есть
            existing_widget_code = task.get("existing_widget_code")
            
            # Формируем prompt для GigaChat
            viz_prompt = self._build_visualization_prompt(
                description=description,
                data_preview=data_preview,
                data_schema=data_schema,
                chart_type=chart_type,
                existing_widget_code=existing_widget_code,
                analyst_insights=analyst_insights,
                analyst_recommendations=analyst_recommendations
            )
            
            # Вызываем GigaChat с историей диалога
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Добавляем историю диалога если есть (кроме последнего сообщения, его добавим с данными)
            chat_history = task.get("chat_history", [])
            if chat_history:
                self.logger.info(f"💬 Adding chat history: {len(chat_history)} messages")
                # Добавляем все сообщения кроме последнего (его заменим на viz_prompt с данными)
                for msg in chat_history[:-1]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if content.strip():
                        messages.append({"role": role, "content": content})
            
            # Добавляем текущий запрос с данными
            messages.append({"role": "user", "content": viz_prompt})
            
            self.logger.info(f"📨 Sending {len(messages)} messages to GigaChat")
            
            response = await self._call_llm(
                messages,
                context=context,
                temperature=0.4,
                max_tokens=8000,
            )
            
            self.logger.info(f"✅ LLM response received: {len(response)} chars")
            
            # Логируем в файл для анализа
            try:
                import os
                from datetime import datetime
                log_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'logs')
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, 'gigachat_responses.log')
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                    f.write(f"Prompt: {description[:200]}...\n" if len(description) > 200 else f"Prompt: {description}\n")
                    f.write(f"Response ({len(response)} chars):\n{response}\n")
                self.logger.info(f"📝 Response logged to: {log_file}")
            except Exception as e:
                self.logger.warning(f"Could not write to log file: {e}")
            
            # Проверка на обрезанный ответ (после удаления markdown)
            cleaned_check = re.sub(r'^```(?:json|html|javascript)?\s*\n?', '', response.strip(), flags=re.IGNORECASE)
            cleaned_check = re.sub(r'\n?```\s*$', '', cleaned_check).strip()
            if not cleaned_check.endswith('}'):
                self.logger.warning(f"⚠️ Response might be truncated (doesn't end with '}}')")
            
            self.logger.info(f"📄 Full GigaChat response:\n{response}")
            
            # Парсим ответ
            result = self._parse_visualization_response(response)
            
            # Post-processing: автоматическое исправление ошибок GigaChat
            js_code = result.get("js_code", "")
            if js_code:
                fixes_applied = []
                
                # 1. Исправляем неправильные API calls
                if "fetch(" in js_code and "window.fetchContentData" not in js_code:
                    js_code = re.sub(
                        r"fetch\s*\(\s*['\"](?:/api/[^'\"]*)['\"]\s*\)",
                        "window.fetchContentData()",
                        js_code
                    )
                    fixes_applied.append("replaced fetch('/api/...') with window.fetchContentData()")
                
                # 2. Добавляем window.startAutoRefresh если отсутствует
                if "startAutoRefresh" not in js_code:
                    # Находим имя функции рендера
                    render_func_match = re.search(r"(?:async\s+)?function\s+(\w+)\s*\(", js_code)
                    if render_func_match:
                        render_func_name = render_func_match.group(1)
                        js_code += f"\n\n// Auto-refresh\nwindow.startAutoRefresh({render_func_name}, 5000);"
                        fixes_applied.append(f"added window.startAutoRefresh({render_func_name}, 5000)")
                    else:
                        # Попытка найти вызов функции в конце кода
                        func_call_match = re.search(r"(\w+)\s*\(\s*\)\s*;\s*$", js_code)
                        if func_call_match:
                            render_func_name = func_call_match.group(1)
                            js_code += f"\nwindow.startAutoRefresh({render_func_name}, 5000);"
                            fixes_applied.append(f"added window.startAutoRefresh({render_func_name}, 5000)")
                
                # 3. Переименовываем нестандартные функции
                if "requestData" in js_code and "render" not in js_code:
                    js_code = js_code.replace("requestData", "render")
                    fixes_applied.append("renamed requestData() to render()")
                
                if fixes_applied:
                    result["js_code"] = js_code
                    self.logger.warning(f"🔧 Auto-fixed GigaChat code: {', '.join(fixes_applied)}")
            
            # Проверяем наличие обязательных полей (поддержка обоих форматов)
            if not result.get("widget_code") and not result.get("html_code") and not result.get("js_code"):
                return self._format_error_response(
                    "Generated response missing widget_code, html_code or js_code",
                    suggestions=["Try again with simpler request"]
                )
            
            self.logger.info(f"✅ Visualization created successfully ({result.get('widget_type', 'unknown')})")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error creating visualization: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _update_visualization(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обновляет существующую визуализацию.
        """
        try:
            self._validate_task(task, ["widget_code", "update_instructions"])
            
            widget_code = task["widget_code"]
            update_instructions = task["update_instructions"]
            
            self.logger.info(f"🔄 Updating visualization: {update_instructions[:100]}...")
            
            # Формируем prompt для обновления
            update_prompt = f"""
EXISTING WIDGET CODE:
```html
{widget_code[:1000]}... [truncated]
```

UPDATE INSTRUCTIONS: {update_instructions}

Update the widget code according to instructions. Maintain:
- postMessage communication
- Responsive design
- Error handling
- Same visualization library

Return updated code as JSON: {{"widget_code": "...", "changes": ["..."]}}
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": update_prompt}
            ]
            response = await self._call_llm(
                messages, context=context, temperature=0.4
            )
            
            result = self._parse_json_response(response)
            
            # Валидация обновленного HTML
            updated_code = result.get("widget_code", widget_code)
            validation_result = self._validate_html(updated_code)
            
            if not validation_result["valid"]:
                self.logger.warning("Updated HTML failed validation, returning original")
                return {
                    "status": "success",
                    "widget_code": widget_code,
                    "changes": ["Update skipped - validation failed"],
                    "agent": self.agent_name
                }
            
            self.logger.info(f"✅ Visualization updated successfully")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error updating visualization: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    def _build_visualization_prompt(
        self,
        description: str,
        data_preview: Any,
        data_schema: Dict[str, Any],
        chart_type: str,
        existing_widget_code: str | None = None,
        analyst_insights: Optional[List[Dict[str, Any]]] = None,
        analyst_recommendations: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Формирует prompt для генерации визуализации.
        """
        prompt_parts = [
            f"Запрос: {description}",
            ""
        ]
        
        if chart_type != "auto":
            prompt_parts.append(f"Тип графика: {chart_type}")
            prompt_parts.append("")
        
        if data_preview:
            prompt_parts.append("Данные:")
            prompt_parts.append(json.dumps(data_preview, indent=2, ensure_ascii=False)[:800])
            prompt_parts.append("")
        
        # Добавляем insights от аналитика (новый формат: finding, confidence, column_refs)
        if analyst_insights:
            prompt_parts.append("📊 АНАЛИТИЧЕСКИЕ ВЫВОДЫ (используй для заголовков/подписей):")
            for insight in analyst_insights[:5]:  # Берём топ-5
                if isinstance(insight, dict):
                    # Новый формат: {finding, confidence, column_refs}
                    finding = insight.get('finding', '') or insight.get('title', '')
                    confidence = insight.get('confidence', 0)
                    column_refs = insight.get('column_refs', []) or insight.get('columns', [])
                    
                    if finding:
                        cols = f" [{', '.join(column_refs)}]" if column_refs else ""
                        conf = f" (уверенность: {confidence:.0%})" if confidence else ""
                        prompt_parts.append(f"  • {finding}{cols}{conf}")
                else:
                    prompt_parts.append(f"  • {insight}")
            prompt_parts.append("")
        
        # Добавляем recommendations от аналитика (новый формат: action, columns, priority)
        if analyst_recommendations:
            prompt_parts.append("💡 РЕКОМЕНДАЦИИ ПО ВИЗУАЛИЗАЦИИ:")
            for rec in analyst_recommendations[:3]:  # Берём топ-3
                if isinstance(rec, dict):
                    action = rec.get('action', '') or rec.get('title', '')
                    columns = rec.get('columns', [])
                    priority = rec.get('priority', '')
                    
                    if action:
                        cols = f" (колонки: {', '.join(columns)})" if columns else ""
                        prio = f" [{priority}]" if priority else ""
                        prompt_parts.append(f"  • {action}{cols}{prio}")
                else:
                    prompt_parts.append(f"  • {rec}")
            prompt_parts.append("")
        
        # Добавляем текущий код виджета для итерации
        if existing_widget_code:
            prompt_parts.append("Текущий код виджета (измени его согласно запросу):")
            prompt_parts.append(existing_widget_code[:3000])  # Ограничиваем размер
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def _parse_visualization_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ от LLM с визуализацией.
        """
        return self._parse_json_response(response)
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит JSON ответ от LLM.
        Обрабатывает случаи когда JSON находится внутри markdown блока или окружён текстом.
        """
        original_response = response
        response = response.strip()
        
        self.logger.debug(f"Parsing response (first 200 chars): {response[:200]}")
        
        # Метод 0: Прямой парсинг (когда весь ответ - чистый JSON)
        if response.startswith('{') and response.endswith('}'):
            try:
                parsed = json.loads(response)
                if "html_code" in parsed or "js_code" in parsed or "widget_code" in parsed:
                    self.logger.info(f"✅ Direct JSON parse successful")
                    return parsed
            except json.JSONDecodeError:
                pass  # Продолжаем другие методы
        
        # Метод 1: Найти все JSON блоки в markdown и выбрать тот, что содержит html_code/js_code
        json_blocks = re.findall(r'```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```', response)
        for json_str in json_blocks:
            json_str = json_str.strip()
            try:
                parsed = json.loads(json_str)
                # Проверяем, что это наш формат визуализации
                if "html_code" in parsed or "js_code" in parsed or "widget_code" in parsed:
                    self.logger.info(f"✅ Extracted visualization JSON from markdown block")
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Метод 2: Простое удаление markdown блоков (для случая когда весь ответ - один JSON блок)
        cleaned = response
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```html"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Попытка прямого парсинга
        try:
            parsed = json.loads(cleaned)
            if "html_code" in parsed or "js_code" in parsed or "widget_code" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
        
        # Метод 3: Найти все JSON объекты в тексте и выбрать тот с html_code/js_code
        # Используем более точный regex для поиска JSON объектов
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_matches = re.findall(json_pattern, original_response)
        
        for json_str in json_matches:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and ("html_code" in parsed or "js_code" in parsed or "widget_code" in parsed):
                    self.logger.info(f"✅ Extracted visualization JSON from text")
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Метод 4: Найти JSON с нужными ключами через поиск "html_code" и извлечение содержащего его блока
        html_code_match = re.search(r'\{\s*"html_code"[\s\S]*?\}\s*\}', original_response)
        if html_code_match:
            json_str = html_code_match.group(0)
            # Пробуем расширить до полного объекта
            try:
                parsed = json.loads(json_str)
                self.logger.info(f"✅ Extracted JSON by html_code key search")
                return parsed
            except json.JSONDecodeError:
                pass
        
        # Метод 5: Самый агрессивный - найти последний большой JSON блок
        all_json_matches = list(re.finditer(r'\{[\s\S]*?\}(?=\s*```|\s*$|\n\n)', original_response))
        for match in reversed(all_json_matches):
            json_str = match.group(0)
            if len(json_str) > 100:  # Игнорируем маленькие JSON
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and len(parsed) > 2:
                        self.logger.info(f"✅ Extracted last large JSON block")
                        return parsed
                except json.JSONDecodeError:
                    continue
        
        # Метод 6: Fallback - если это HTML, оборачиваем в JSON
        if "<!DOCTYPE" in original_response or "<html" in original_response:
            html_match = re.search(r'(<!DOCTYPE[\s\S]*</html>)', original_response, re.IGNORECASE)
            if html_match:
                return {
                    "widget_code": html_match.group(1),
                    "description": "Auto-extracted HTML",
                    "widget_type": "custom"
                }
        
        # Если ничего не сработало, выбрасываем ошибку
        self.logger.error(f"Could not extract valid JSON from response")
        self.logger.error(f"Response preview: {original_response[:500]}")
        raise ValueError(f"Could not extract valid JSON from GigaChat response")
    
    def _validate_html(self, html_code: str) -> Dict[str, Any]:
        """
        Валидирует HTML код на корректность и безопасность.
        """
        warnings = []
        
        # 1. Проверка базовой структуры HTML
        if not html_code.strip():
            return {
                "valid": False,
                "error": "HTML code is empty"
            }
        
        if "<!DOCTYPE" not in html_code and "<html" not in html_code:
            return {
                "valid": False,
                "error": "Missing <!DOCTYPE> or <html> tag"
            }
        
        # 2. Проверка postMessage communication
        if "postMessage" not in html_code:
            warnings.append("postMessage communication not found - widget may not receive data updates")
        
        if "addEventListener('message'" not in html_code and "addEventListener(\"message\"" not in html_code:
            warnings.append("Message event listener not found - widget may not respond to data updates")
        
        # 3. Проверка на опасные паттерны
        dangerous_patterns = [
            (r'<script[^>]*src=["\'](?!https?://cdn\.|https?://unpkg\.)', "External script from non-CDN source"),
            (r'\beval\(', "eval() usage detected"),
            (r'\bFunction\(', "Function() constructor detected"),
            (r'<iframe', "Nested iframe detected"),
        ]
        
        for pattern, error_msg in dangerous_patterns:
            if re.search(pattern, html_code, re.IGNORECASE):
                return {
                    "valid": False,
                    "error": error_msg,
                    "suggestions": ["Remove dangerous code", "Use only CDN libraries"]
                }
        
        # 4. Проверка responsive design
        if "width: 100%" not in html_code and "width:100%" not in html_code:
            warnings.append("Responsive width not detected - consider adding width: 100%")
        
        return {
            "valid": True,
            "warnings": warnings
        }


def get_reporter_agent(
    message_bus: Optional[AgentMessageBus] = None,
    gigachat_service: Optional[GigaChatService] = None
) -> ReporterAgent:
    """Создает экземпляр ReporterAgent."""
    if not gigachat_service:
        from app.services.gigachat_service import get_gigachat_service
        gigachat_service = get_gigachat_service()
    
    return ReporterAgent(message_bus, gigachat_service)
