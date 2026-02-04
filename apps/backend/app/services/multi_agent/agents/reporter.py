"""
Reporter Agent - Visualization Code Generator
Генерирует WidgetNode визуализации с HTML/CSS/JS кодом.
"""

import logging
import json
from typing import Dict, Any, Optional, List
import re

from .base import BaseAgent
from ..message_bus import AgentMessageBus
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
2. Подключай нужные библиотеки через CDN:
   - Chart.js v4: https://cdn.jsdelivr.net/npm/chart.js@4
   - Plotly v2.35+: https://cdn.plot.ly/plotly-2.35.2.min.js
   - D3 v7: https://cdn.jsdelivr.net/npm/d3@7
   - ECharts v5: https://cdn.jsdelivr.net/npm/echarts@5
3. Данные получай через: const data = await window.fetchContentData();
4. Структура данных: data.tables[0].columns (названия колонок), data.tables[0].rows (массив строк)
5. Вызывай render() при загрузке
6. ВСЕГДА вызывай window.startAutoRefresh(render) БЕЗ второго параметра - интервал задается пользователем

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
- Отвечай ТОЛЬКО JSON объектом'''


class ReporterAgent(BaseAgent):
    """
    Reporter Agent - генерация WidgetNode визуализаций.
    
    Основные функции:
    - Генерация HTML/CSS/JS кода для визуализаций
    - Поддержка различных типов графиков и таблиц
    - Интеграция postMessage для обновления данных
    - Валидация HTML кода
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="reporter",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
    def _get_default_system_prompt(self) -> str:
        return REPORTER_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу генерации визуализации.
        
        Работает без явного task.type - определяет намерение из описания задачи.
        Поддерживаемые операции:
        - create_visualization: Генерация WidgetNode из ContentNode
        - update_visualization: Обновление существующей визуализации
        """
        # Получаем описание задачи (используется PlannerAgent вместо type)
        description = task.get("description", "").lower()
        task_type = task.get("type")  # Может отсутствовать в новой архитектуре
        
        # Умная детекция типа операции из описания
        is_update = any(keyword in description for keyword in ["update", "обнов", "изменить", "modify"])
        
        # По умолчанию создание визуализации (основной use case)
        if task_type == "update_visualization" or (is_update and "widget_id" in task):
            return await self._update_visualization(task, context)
        else:
            # create_visualization, generate_visualization, или описание без типа
            return await self._create_visualization(task, context)
    
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
            
            # === Попробуем получить результаты аналитика из Redis для enrichment ===
            if session_id:
                analyst_result = await self.get_agent_result(session_id, "analyst")
                if analyst_result and analyst_result.get("status") == "success":
                    analyst_insights = analyst_result.get("insights", [])
                    self.logger.info(f"📊 Got {len(analyst_insights) if analyst_insights else 0} insights from AnalystAgent")
            
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
                        "table_name": first_table.get("name", "data"),
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
                analyst_insights=analyst_insights
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
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.4,  # Средняя температура для креативности
                max_tokens=8000  # Увеличено для больших HTML/CSS/JS кодов
            )
            
            self.logger.info(f"✅ GigaChat response received: {len(response)} chars")
            
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
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.4
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
        analyst_insights: Optional[List[Dict[str, Any]]] = None
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
        
        # Добавляем insights от аналитика для более информативной визуализации
        if analyst_insights:
            prompt_parts.append("Аналитические выводы (используй для заголовков/подписей):")
            for insight in analyst_insights[:3]:  # Берём топ-3
                if isinstance(insight, dict):
                    prompt_parts.append(f"- {insight.get('title', '')}: {insight.get('description', '')}")
                else:
                    prompt_parts.append(f"- {insight}")
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
