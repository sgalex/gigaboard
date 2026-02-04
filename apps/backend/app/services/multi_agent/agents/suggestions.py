from typing import Dict, Any, List
import json
import re
import uuid
import logging

from .base import BaseAgent
from ..message_types import AgentMessage, MessageType
from app.services.content_node_service import ContentNodeService
from sqlalchemy.ext.asyncio import AsyncSession


class WidgetSuggestionAgent(BaseAgent):
    """
    AI Agent for generating widget improvement suggestions.
    
    Capabilities:
    - Analyzes data structure (columns, types, cardinality)
    - Analyzes current widget code (libraries, interactivity)
    - Considers chat history context
    - Generates 3-5 prioritized recommendations
    
    Usage:
    1. Direct sync call (for HTTP endpoints):
       agent = WidgetSuggestionAgent(llm, db)
       result = await agent.execute_sync(content_id, chat, code)
    
    2. Async via Message Bus (for AI Assistant):
       await message_bus.publish("suggestions.analyze", payload)
    """
    
    def __init__(self, message_bus, gigachat_service):
        """
        Initialize WidgetSuggestionAgent.
        
        Can work in two modes:
        1. Full multi-agent mode (message_bus provided) - for complex analysis with other agents
        2. Direct HTTP mode (message_bus=None) - lightweight sync execution
        """
        # Initialize without BaseAgent if message_bus is None (direct HTTP mode)
        if message_bus is not None:
            super().__init__(
                agent_name="suggestions",
                message_bus=message_bus
            )
        else:
            # Minimal initialization for direct HTTP mode
            self.agent_name = "suggestions"
            self.message_bus = None
            self.task_count = 0
            self.error_count = 0
        
        self.gigachat = gigachat_service
        self.logger = logging.getLogger(f"agent.{self.agent_name}")
    
    def _get_default_system_prompt(self) -> str:
        """Default system prompt for WidgetSuggestionAgent."""
        return """Ты — эксперт по визуализации данных.
Анализируй структуру данных и код виджетов, предлагай конкретные улучшения на русском языке.
Фокусируйся на:
- Best practices в data visualization
- Интерактивные функции и UX улучшения
- Альтернативные типы графиков на основе характеристик данных
- Инсайты из данных (корреляции, тренды, выбросы)
- Рекомендации по библиотекам для конкретных случаев
- Современный стиль и доступность"""
    
    async def process_task(self, task: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Process task from Message Bus (for multi-agent coordination).
        
        Task format:
        {
            "type": "analyze_suggestions",
            "content_node_id": "uuid",
            "chat_history": [...],
            "current_widget_code": "...",
            "max_suggestions": 5
        }
        """
        task_type = task.get("type")
        
        if task_type != "analyze_suggestions":
            return {
                "error": f"Unknown task type: {task_type}",
                "supported_types": ["analyze_suggestions"]
            }
        
        # Get db from context (provided by caller)
        db = context.get("db") if context else None
        if not db:
            return {
                "error": "Database session not provided in context"
            }
        
        # Execute analysis
        try:
            result = await self._analyze_and_suggest(
                db=db,
                content_node_id=task["content_node_id"],
                chat_history=task.get("chat_history", []),
                widget_code=task.get("current_widget_code"),
                max_suggestions=task.get("max_suggestions", 5)
            )
            return result
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}", exc_info=True)
            return {
                "error": str(e)
            }
    
    async def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Message Bus handler - NOT YET IMPLEMENTED.
        
        TODO: Implement db session management for Message Bus execution.
        For now, use execute_sync() directly from HTTP endpoints.
        """
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.ERROR,
            sender=self.agent_name,
            receiver=message.sender,
            payload={"error": "Message Bus execution not yet supported. Use execute_sync()"},
            metadata={"status": "not_implemented"}
        )
    
    async def execute_sync(
        self,
        db: AsyncSession,
        content_node_id: str,
        chat_history: List[Dict[str, str]],
        current_widget_code: str | None,
        max_suggestions: int = 5
    ) -> Dict[str, Any]:
        """
        Synchronous execution for HTTP endpoints.
        Bypasses Message Bus for faster response.
        
        Args:
            db: Database session (provided by endpoint)
            content_node_id: ID of ContentNode to analyze
            chat_history: Previous AI Assistant conversation
            current_widget_code: Current widget HTML/JS code
            max_suggestions: Maximum number of suggestions to return
        """
        return await self._analyze_and_suggest(
            db=db,
            content_node_id=content_node_id,
            chat_history=chat_history,
            widget_code=current_widget_code,
            max_suggestions=max_suggestions
        )
    
    async def _analyze_and_suggest(
        self,
        db: AsyncSession,
        content_node_id: str,
        chat_history: List[Dict[str, str]],
        widget_code: str | None,
        max_suggestions: int
    ) -> Dict[str, Any]:
        """Core analysis logic."""
        
        # 1. Fetch ContentNode
        content_node = await ContentNodeService.get_content_node(db, content_node_id)
        if not content_node:
            raise ValueError(f"ContentNode {content_node_id} not found")
        
        # 2. Analyze data structure
        data_analysis = self._analyze_data_structure(content_node)
        
        # 3. Analyze widget code
        code_analysis = None
        if widget_code:
            code_analysis = self._analyze_widget_code(widget_code)
        
        # 4. Build LLM prompt
        prompt = self._build_suggestions_prompt(
            data_analysis=data_analysis,
            code_analysis=code_analysis,
            chat_history=chat_history,
            max_suggestions=max_suggestions
        )
        
        # 5. Call GigaChat
        messages = [
            {"role": "system", "content": "Ты — эксперт по визуализации данных. Анализируй структуру данных и код виджетов, предлагай конкретные улучшения на русском языке. Все рекомендации должны быть actionable и соответствовать best practices в data visualization."},
            {"role": "user", "content": prompt}
        ]
        response = await self.gigachat.chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=2000
        )
        
        # Log the raw response for debugging
        self.logger.info(f"GigaChat raw response (first 1000 chars): {response[:1000]}")
        self.logger.debug(f"GigaChat full response: {response}")
        
        # 6. Parse JSON response
        try:
            # Try direct JSON parse
            suggestions_data = json.loads(response)
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            self.logger.warning("Direct JSON parse failed, trying to extract from markdown")
            try:
                # Extract JSON from ```json ... ``` or ``` ... ```
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    suggestions_data = json.loads(json_str)
                    self.logger.info("Successfully extracted JSON from markdown code block")
                else:
                    # Try to find any JSON object in response
                    match = re.search(r'\{.*"suggestions".*\}', response, re.DOTALL)
                    if match:
                        suggestions_data = json.loads(match.group(0))
                        self.logger.info("Successfully extracted JSON from response text")
                    else:
                        self.logger.error(f"Failed to parse LLM response: {response[:500]}")
                        raise ValueError(f"Invalid JSON response from LLM. Response: {response[:200]}")
            except Exception as e:
                self.logger.error(f"Failed to extract JSON: {e}, response: {response[:500]}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
            except Exception as e:
                self.logger.error(f"Failed to extract JSON: {e}, response: {response[:500]}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
        
        # 7. Format response
        suggestions = [
            {
                "id": f"sug_{i}",
                "type": s["type"],
                "priority": s["priority"],
                "title": s["title"],
                "description": s["description"],
                "prompt": s["prompt"],
                "reasoning": s.get("reasoning", "")
            }
            for i, s in enumerate(suggestions_data.get("suggestions", []))
        ]
        
        return {
            "suggestions": suggestions,
            "analysis_summary": {
                "data_structure": data_analysis.get("summary", ""),
                "current_visualization": code_analysis.get("summary", "") if code_analysis else "Нет виджета",
                "chat_context": self._summarize_chat(chat_history)
            }
        }
    
    def _analyze_data_structure(self, content_node) -> Dict[str, Any]:
        """Analyze table structure, text content and data patterns."""
        content = content_node.content or {}
        tables = content.get("tables", [])
        text_content = content.get("text", "")
        
        # Analyze text content if present
        text_analysis = None
        if text_content and len(text_content.strip()) > 50:
            text_analysis = self._analyze_text_content(text_content)
        
        if not tables and not text_analysis:
            return {"summary": "Нет данных для анализа", "tables": [], "text": None}
        
        # If only text content (no tables)
        if not tables and text_analysis:
            return {
                "summary": text_analysis["summary"],
                "tables": [],
                "text": text_analysis,
                "has_text_only": True
            }
        
        analysis = {"tables": []}
        
        for table in tables:
            columns = table.get("columns", [])
            rows = table.get("rows", [])
            row_count = table.get("row_count", len(rows))
            
            # Infer column types
            column_types = self._infer_column_types(columns, rows)
            
            table_analysis = {
                "name": table.get("name", "Table"),
                "row_count": row_count,
                "column_count": len(columns),
                "columns": columns,
                "column_types": column_types,
                "numeric_columns": [c for c, t in column_types.items() if t == "numeric"],
                "categorical_columns": [c for c, t in column_types.items() if t == "categorical"],
                "temporal_columns": [c for c, t in column_types.items() if t == "temporal"],
            }
            
            analysis["tables"].append(table_analysis)
        
        # Summary
        total_numeric = sum(len(t["numeric_columns"]) for t in analysis["tables"])
        total_categorical = sum(len(t["categorical_columns"]) for t in analysis["tables"])
        total_temporal = sum(len(t["temporal_columns"]) for t in analysis["tables"])
        total_rows = sum(t["row_count"] for t in analysis["tables"])
        
        analysis["summary"] = (
            f"{len(tables)} таблица, {total_rows} строк, "
            f"{total_numeric} числовых, {total_categorical} категориальных, "
            f"{total_temporal} временных колонок"
        )
        
        # Add text analysis if present
        if text_analysis:
            analysis["text"] = text_analysis
            analysis["summary"] += f" + текстовый контент ({text_analysis.get('char_count', 0)} символов)"
        
        return analysis
    
    def _analyze_text_content(self, text: str) -> Dict[str, Any]:
        """Analyze text content for NLP/extraction suggestions."""
        text = text.strip()
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split('\n'))
        
        # Detect content patterns
        has_numbers = bool(re.search(r'\d+[.,]?\d*\s*(%|руб|₽|\$|€|тыс|млн|млрд)?', text))
        has_dates = bool(re.search(r'\d{1,4}[-./]\d{1,2}[-./]\d{1,4}|\d{1,2}\s+(янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)', text, re.IGNORECASE))
        has_lists = bool(re.search(r'^\s*[-•*]\s+|\d+\.\s+', text, re.MULTILINE))
        has_headers = bool(re.search(r'^#+\s+|^[А-ЯA-Z][а-яa-z]+:?\s*$', text, re.MULTILINE))
        has_urls = bool(re.search(r'https?://\S+', text))
        has_entities = bool(re.search(r'[А-ЯA-Z][а-яa-z]+\s+[А-ЯA-Z][а-яa-z]+|ООО|ОАО|АО|ИП|ФГУП', text))
        
        # Estimate content type
        content_type = "general_text"
        if has_numbers and has_dates:
            content_type = "report_or_analytics"
        elif has_lists and has_headers:
            content_type = "structured_document"
        elif has_entities:
            content_type = "business_text"
        elif word_count > 500:
            content_type = "long_form_text"
        
        # Suggested transformations for text
        suggested_transforms = []
        if content_type in ["report_or_analytics", "business_text"]:
            suggested_transforms.extend(["extract_numbers", "extract_entities", "summarize"])
        if has_lists or has_headers:
            suggested_transforms.extend(["extract_structure", "convert_to_table"])
        if word_count > 200:
            suggested_transforms.append("summarize")
        if has_dates and has_numbers:
            suggested_transforms.append("extract_timeline")
        
        # Make unique
        suggested_transforms = list(dict.fromkeys(suggested_transforms))
        
        return {
            "char_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "content_type": content_type,
            "patterns": {
                "has_numbers": has_numbers,
                "has_dates": has_dates,
                "has_lists": has_lists,
                "has_headers": has_headers,
                "has_urls": has_urls,
                "has_entities": has_entities
            },
            "suggested_transforms": suggested_transforms,
            "text_preview": text[:500] + ("..." if len(text) > 500 else ""),
            "summary": f"Текст: {word_count} слов, тип: {content_type}"
        }
    
    def _infer_column_types(self, columns: List[str], rows: List[List]) -> Dict[str, str]:
        """Infer column types from sample data."""
        if not rows or len(rows) < 1:
            return {col: "unknown" for col in columns}
        
        types = {}
        sample_row = rows[0] if isinstance(rows[0], list) else []
        
        for i, col in enumerate(columns):
            if i >= len(sample_row):
                types[col] = "unknown"
                continue
            
            value = sample_row[i]
            
            # Check if numeric
            if isinstance(value, (int, float)):
                types[col] = "numeric"
            # Check if temporal (common date patterns)
            elif isinstance(value, str) and any(
                keyword in col.lower() for keyword in ["date", "time", "timestamp", "created", "updated"]
            ):
                types[col] = "temporal"
            # Default to categorical
            else:
                types[col] = "categorical"
        
        return types
    
    def _analyze_widget_code(self, widget_code: str) -> Dict[str, Any]:
        """Analyze current widget code for patterns."""
        analysis = {}
        
        # Detect libraries
        libraries = []
        if "Chart.js" in widget_code or "new Chart(" in widget_code:
            libraries.append("Chart.js")
        if "Plotly" in widget_code or "Plotly.newPlot" in widget_code:
            libraries.append("Plotly")
        if "echarts" in widget_code.lower():
            libraries.append("ECharts")
        if "d3" in widget_code.lower():
            libraries.append("D3.js")
        
        analysis["libraries"] = libraries
        
        # Detect interactivity
        has_hover = "onmouseover" in widget_code or "hover" in widget_code.lower()
        has_click = "onclick" in widget_code or "addEventListener" in widget_code
        has_tooltips = "tooltip" in widget_code.lower()
        
        analysis["interactivity"] = {
            "hover": has_hover,
            "click": has_click,
            "tooltips": has_tooltips
        }
        
        # Detect chart type
        chart_type = "unknown"
        if "type: 'bar'" in widget_code or "'bar'" in widget_code:
            chart_type = "bar"
        elif "type: 'line'" in widget_code or "'line'" in widget_code:
            chart_type = "line"
        elif "type: 'pie'" in widget_code or "'pie'" in widget_code:
            chart_type = "pie"
        elif "<table" in widget_code:
            chart_type = "table"
        
        analysis["chart_type"] = chart_type
        
        # Summary
        lib_str = libraries[0] if libraries else "Vanilla JS"
        interactive_str = "интерактивный" if (has_hover or has_click or has_tooltips) else "статический"
        
        analysis["summary"] = f"{chart_type.capitalize()} chart ({lib_str}), {interactive_str}"
        
        return analysis
    
    def _summarize_chat(self, chat_history: List[Dict[str, str]]) -> str:
        """Summarize chat context."""
        if not chat_history:
            return "Нет истории диалога"
        
        user_messages = [msg for msg in chat_history if msg.get("role") == "user"]
        
        if not user_messages:
            return "Нет запросов пользователя"
        
        last_user_msg = user_messages[-1].get("content", "")
        return f"Последний запрос: '{last_user_msg[:50]}...', всего сообщений: {len(chat_history)}"
    
    def _build_suggestions_prompt(
        self,
        data_analysis: Dict,
        code_analysis: Dict | None,
        chat_history: List[Dict],
        max_suggestions: int
    ) -> str:
        """Build LLM prompt for generating suggestions."""
        
        # Check if we have text-only content
        has_text_only = data_analysis.get("has_text_only", False)
        text_data = data_analysis.get("text")
        
        # Build prompt for TEXT-ONLY content (no tables)
        if has_text_only and text_data:
            return self._build_text_suggestions_prompt(
                text_analysis=text_data,
                code_analysis=code_analysis,
                chat_history=chat_history,
                max_suggestions=max_suggestions
            )
        
        # Different prompts for new widget vs existing widget
        if code_analysis is None:
            # New widget creation - suggest visualization options
            prompt = f"""Ты — эксперт по data visualization. Пользователь хочет создать новую визуализацию для данных.

**ДАННЫЕ:**
{json.dumps(data_analysis, ensure_ascii=False, indent=2)}

**ИСТОРИЯ ДИАЛОГА:**
{json.dumps(chat_history[-5:], ensure_ascii=False, indent=2) if chat_history else "Нет истории"}

**ЗАДАЧА:**
Предложи {max_suggestions} РАЗНЫХ вариантов визуализации, которые лучше всего подойдут для этих данных.

**ТИПЫ РЕКОМЕНДАЦИЙ ДЛЯ НОВОГО ВИДЖЕТА:**
- `alternative`: Варианты типов графиков (bar chart, line chart, pie chart, scatter plot, heatmap, table и др.)

**ПРИОРИТЕТЫ:**
- `high`: Лучший вариант для данного типа данных
- `medium`: Хороший альтернативный вариант
- `low`: Нестандартный, но интересный вариант

**ПРАВИЛА:**
1. Каждая рекомендация — это ДРУГОЙ тип визуализации
2. Учитывай структуру данных (числовые колонки, категории, временные ряды)
3. Prompt должен быть готов к отправке AI (например: "создай bar chart с группировкой по категориям")
4. Title — краткое название типа визуализации (например: "Bar Chart", "Line Graph", "Pie Chart")
5. Приоритизируй: самый подходящий тип — high, альтернативы — medium/low

**ФОРМАТ ОТВЕТА:**
Ответь СТРОГО в формате JSON. НЕ добавляй никакой текст до или после JSON. НЕ используй markdown блоки (```).
Только чистый JSON объект:

{{
  "suggestions": [
    {{
      "type": "alternative",
      "priority": "high",
      "title": "Bar Chart",
      "description": "Столбчатая диаграмма для сравнения категорий",
      "prompt": "создай bar chart с группировкой по категориям",
      "reasoning": "Идеально для сравнения числовых значений по категориям"
    }}
  ]
}}

ВАЖНО: Ответ должен начинаться с {{ и заканчиваться на }}. Никаких дополнительных символов."""
        else:
            # Existing widget - suggest improvements
            prompt = f"""Ты — эксперт по data visualization. Проанализируй текущий виджет и предложи улучшения.

**ДАННЫЕ:**
{json.dumps(data_analysis, ensure_ascii=False, indent=2)}

**ТЕКУЩИЙ ВИДЖЕТ:**
{json.dumps(code_analysis, ensure_ascii=False, indent=2)}

**ИСТОРИЯ ДИАЛОГА:**
{json.dumps(chat_history[-5:], ensure_ascii=False, indent=2) if chat_history else "Нет истории"}

**ЗАДАЧА:**
Сгенерируй {max_suggestions} рекомендаций для улучшения существующей визуализации.

**ТИПЫ РЕКОМЕНДАЦИЙ:**
- `improvement`: Улучшения текущей визуализации (интерактивность, стиль, читаемость)
- `alternative`: Альтернативные типы графиков, более подходящие для данных
- `insight`: Инсайты из данных (группировки, фильтры, агрегации)
- `library`: Рекомендации по библиотекам (переход на более подходящую)
- `style`: Стилистические улучшения (цвета, шрифты, layout)

**ПРИОРИТЕТЫ:**
- `high`: Критично для UX или качества визуализации
- `medium`: Полезное улучшение
- `low`: Опциональное, эстетическое

**ПРАВИЛА:**
1. Рекомендации должны быть конкретными и actionable
2. Prompt должен быть готов к отправке AI (краткий императив)
3. Reasoning объясняет, почему эта рекомендация полезна
4. Учитывай контекст диалога (не повторяй то, что пользователь уже отклонил)
5. Приоритизируй на основе impact/effort ratio

**ФОРМАТ ОТВЕТА:**
Ответь СТРОГО в формате JSON. НЕ добавляй никакой текст до или после JSON. НЕ используй markdown блоки (```).
Только чистый JSON объект:

{{
  "suggestions": [
    {{
      "type": "improvement",
      "priority": "high",
      "title": "Краткий заголовок (до 6 слов)",
      "description": "Развёрнутое описание (1-2 предложения)",
      "prompt": "добавь интерактивные tooltips",
      "reasoning": "Почему это важно (1 предложение)"
    }}
  ]
}}

ВАЖНО: Ответ должен начинаться с {{ и заканчиваться на }}. Никаких дополнительных символов."""
        
        return prompt
    
    def _build_text_suggestions_prompt(
        self,
        text_analysis: Dict,
        code_analysis: Dict | None,
        chat_history: List[Dict],
        max_suggestions: int
    ) -> str:
        """Build LLM prompt for text content transformation suggestions."""
        
        text_preview = text_analysis.get("text_preview", "")
        content_type = text_analysis.get("content_type", "general_text")
        patterns = text_analysis.get("patterns", {})
        suggested_transforms = text_analysis.get("suggested_transforms", [])
        word_count = text_analysis.get("word_count", 0)
        
        prompt = f"""Ты — эксперт по обработке текста и извлечению данных. Пользователь имеет ТЕКСТОВЫЙ контент (без структурированных таблиц) и хочет его обработать/трансформировать.

**ТЕКСТОВЫЙ КОНТЕНТ:**
- Тип контента: {content_type}
- Объём: {word_count} слов, {text_analysis.get('char_count', 0)} символов
- Обнаруженные паттерны:
  - Числа/суммы: {"да" if patterns.get("has_numbers") else "нет"}
  - Даты: {"да" if patterns.get("has_dates") else "нет"}
  - Списки: {"да" if patterns.get("has_lists") else "нет"}
  - Заголовки/структура: {"да" if patterns.get("has_headers") else "нет"}
  - Названия организаций/имена: {"да" if patterns.get("has_entities") else "нет"}
  - URL-ссылки: {"да" if patterns.get("has_urls") else "нет"}

**ПРЕВЬЮ ТЕКСТА:**
{text_preview}

**ПРЕДЛАГАЕМЫЕ ТРАНСФОРМАЦИИ (на основе анализа):**
{json.dumps(suggested_transforms, ensure_ascii=False)}

**ИСТОРИЯ ДИАЛОГА:**
{json.dumps(chat_history[-5:], ensure_ascii=False, indent=2) if chat_history else "Нет истории"}

**ЗАДАЧА:**
Предложи {max_suggestions} вариантов ТРАНСФОРМАЦИИ текста. Это НЕ визуализация, а ОБРАБОТКА текста.

**ТИПЫ ТРАНСФОРМАЦИЙ ДЛЯ ТЕКСТА:**
- `extract`: Извлечение структурированных данных (числа, даты, имена, организации → таблица)
- `summarize`: Суммаризация длинного текста в краткий обзор
- `structure`: Преобразование неструктурированного текста в таблицу/список
- `analyze`: Аналитика текста (sentiment, ключевые слова, статистика)
- `transform`: Преобразование формата (markdown → таблица, список → JSON)

**ПРИОРИТЕТЫ:**
- `high`: Наиболее полезная трансформация для данного типа текста
- `medium`: Альтернативный полезный вариант
- `low`: Опциональная, но интересная обработка

**ПРАВИЛА:**
1. НЕ предлагай визуализации (charts, graphs) — это ТЕКСТОВЫЙ контент без таблиц
2. Предлагай ТРАНСФОРМАЦИИ: извлечение данных, структурирование, суммаризацию
3. Prompt должен быть готов к отправке AI (например: "извлеки все числа и даты в таблицу")
4. Учитывай обнаруженные паттерны (если есть числа → извлечь числа, если есть имена → NER)
5. Title — краткое название трансформации (например: "Извлечь числа", "Суммаризация", "Создать таблицу")

**ФОРМАТ ОТВЕТА:**
Ответь СТРОГО в формате JSON. НЕ добавляй никакой текст до или после JSON. НЕ используй markdown блоки (```).
Только чистый JSON объект:

{{
  "suggestions": [
    {{
      "type": "extract",
      "priority": "high",
      "title": "Извлечь ключевые данные",
      "description": "Извлечь числовые показатели, даты и названия организаций в структурированную таблицу",
      "prompt": "извлеки все числа, даты и названия организаций из текста и создай таблицу",
      "reasoning": "Текст содержит числовые данные и названия, которые можно структурировать"
    }},
    {{
      "type": "summarize",
      "priority": "medium",
      "title": "Краткое резюме",
      "description": "Создать краткое резюме ключевых тезисов текста",
      "prompt": "сделай краткое резюме основных тезисов текста в 3-5 пунктах",
      "reasoning": "Длинный текст удобнее воспринимать в виде краткого резюме"
    }}
  ]
}}

ВАЖНО: Ответ должен начинаться с {{ и заканчиваться на }}. Никаких дополнительных символов."""
        
        return prompt
