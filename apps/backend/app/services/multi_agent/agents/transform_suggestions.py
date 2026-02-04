"""
Transform Suggestions Agent - Контекстные рекомендации для трансформаций
Анализирует текущий код, историю чата и данные для генерации релевантных подсказок.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List

from .base import BaseAgent
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для TransformSuggestionsAgent
SUGGESTIONS_SYSTEM_PROMPT = '''
Вы — Transform Suggestions Agent в системе GigaBoard.

**РОЛЬ**: Анализировать текущий Python код трансформации данных и предлагать релевантные улучшения или следующие шаги.

**ЗАДАЧА**: Генерировать 6 конкретных, полезных рекомендаций на основе:
1. Текущего кода пользователя (если есть)
2. Истории переписки (контекст намерений)
3. Схемы входных данных (доступные колонки ИЛИ текстовый контент)

**КАТЕГОРИИ РЕКОМЕНДАЦИЙ ДЛЯ ТАБЛИЧНЫХ ДАННЫХ**:

1. **filter** - Фильтрация данных
   - Примеры: "Отфильтровать строки где amount > 1000", "Удалить пустые значения в колонке name"

2. **aggregate** - Агрегация и группировка
   - Примеры: "Сгруппировать по category и посчитать сумму", "Найти топ-10 по продажам"

3. **compute** - Вычисления и новые колонки
   - Примеры: "Добавить колонку с процентом от общей суммы", "Рассчитать разницу между датами"

4. **reshape** - Изменение структуры
   - Примеры: "Отсортировать по убыванию", "Переименовать колонки", "Pivot таблицу"

5. **merge** - Объединение данных
   - Примеры: "Join с другой таблицей", "Concat нескольких источников"

**КАТЕГОРИИ РЕКОМЕНДАЦИЙ ДЛЯ ТЕКСТОВОГО КОНТЕНТА (is_text_only: true)**:

1. **extract** - Извлечение структурированных данных из текста
   - Примеры: "Извлечь все числа и даты в таблицу", "Выделить названия организаций (NER)", "Найти все суммы в рублях"

2. **summarize** - Суммаризация и резюмирование
   - Примеры: "Сделать краткое резюме в 5 пунктах", "Выделить ключевые тезисы", "Сократить до 200 слов"

3. **structure** - Преобразование в структурированный формат
   - Примеры: "Преобразовать в таблицу с колонками", "Разбить на секции", "Создать JSON-структуру"

4. **analyze** - Анализ текста
   - Примеры: "Определить тональность текста", "Найти ключевые слова", "Классифицировать по темам"

5. **transform** - Преобразование формата
   - Примеры: "Перевести на английский", "Форматировать как markdown", "Исправить грамматику"

**ФОРМАТ ОТВЕТА** (JSON):
```json
{
  "suggestions": [
    {
      "label": "Краткое название (2-4 слова)",
      "prompt": "Полный текст подсказки для отправки в чат",
      "category": "filter|aggregate|compute|reshape|merge|extract|summarize|structure|analyze|transform",
      "confidence": 0.0-1.0,
      "description": "Объяснение, зачем это нужно (опционально)"
    }
  ]
}
```

**ПРАВИЛА**:
- Если existing_code ЕСТЬ → предлагать **улучшения** текущего кода
- Если existing_code НЕТ → предлагать **базовые операции** на основе данных
- Если is_text_only: true → НЕ предлагать табличные операции (filter, aggregate), предлагать ТЕКСТОВЫЕ (extract, summarize, structure)
- Учитывать chat_history для понимания намерений пользователя
- Предлагать КОНКРЕТНЫЕ действия, а не абстрактные
- НЕ предлагать то, что уже сделано в existing_code
- Confidence выше для операций, которые логически следуют из контекста

**ПРИМЕР ДЛЯ ТЕКСТОВОГО КОНТЕНТА**:
Input:
  existing_code: null
  input_schemas: [{"name": "text_content", "columns": [], "is_text_only": true, "content_text": "Продажи за 2025 год составили 1.5 млрд руб. Основные клиенты: ООО Ромашка, АО Василёк..."}]

Output:
```json
{
  "suggestions": [
    {"label": "Извлечь числа", "prompt": "Извлеки все числовые показатели и суммы из текста в таблицу", "category": "extract", "confidence": 0.95},
    {"label": "Найти организации", "prompt": "Выдели все названия компаний и организаций (NER)", "category": "extract", "confidence": 0.9},
    {"label": "Краткое резюме", "prompt": "Сделай краткое резюме ключевых фактов в 3-5 пунктах", "category": "summarize", "confidence": 0.85},
    {"label": "Создать таблицу", "prompt": "Преобразуй текст в структурированную таблицу с колонками: показатель, значение, период", "category": "structure", "confidence": 0.8}
  ]
}
```

Возвращайте ТОЛЬКО JSON, без дополнительного текста.
'''


class TransformSuggestionsAgent(BaseAgent):
    """
    Агент для генерации контекстных рекомендаций по трансформациям.
    Анализирует текущий код и предлагает релевантные следующие шаги.
    """
    
    def __init__(
        self,
        gigachat_service: GigaChatService,
        agent_name: str = "TransformSuggestionsAgent",
        message_bus: Optional[Any] = None
    ):
        # Не вызываем super().__init__, так как BaseAgent требует message_bus
        # Используем упрощённую инициализацию для standalone режима
        self.agent_name = agent_name
        self.gigachat = gigachat_service
        self.system_prompt = SUGGESTIONS_SYSTEM_PROMPT
        self.logger = logger
        self.message_bus = message_bus
    
    def _get_default_system_prompt(self) -> str:
        """Возвращает дефолтный system prompt."""
        return SUGGESTIONS_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу генерации рекомендаций.
        
        Поддерживаемые типы задач:
        - generate_suggestions: Генерация рекомендаций на основе кода и данных
        """
        task_type = task.get("type")
        
        if task_type == "generate_suggestions":
            return await self._generate_suggestions(task, context)
        else:
            return self._format_error_response(
                f"Unknown task type: {task_type}",
                suggestions=["Supported types: generate_suggestions"]
            )
    
    async def _generate_suggestions(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует контекстные рекомендации для трансформаций.
        """
        try:
            existing_code = task.get("existing_code")
            chat_history = task.get("chat_history", [])
            input_schemas = task.get("input_schemas", [])
            
            self.logger.info(f"🎯 Generating transform suggestions...")
            if existing_code:
                self.logger.info(f"   Mode: IMPROVE (code length: {len(existing_code)} chars)")
            else:
                self.logger.info(f"   Mode: NEW (no existing code)")
            if chat_history:
                self.logger.info(f"   Chat history: {len(chat_history)} messages")
            
            # Формируем prompt для GigaChat
            suggestions_prompt = self._build_suggestions_prompt(
                existing_code=existing_code,
                chat_history=chat_history,
                input_schemas=input_schemas
            )
            
            # Вызываем GigaChat
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": suggestions_prompt}
            ]
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.4,  # Умеренная креативность для разнообразия
                max_tokens=1500
            )
            
            self.logger.info(f"🤖 GigaChat response type: {type(response).__name__}")
            
            # Парсим ответ
            result = self._parse_suggestions_response(response)
            
            suggestions = result.get("suggestions", [])
            self.logger.info(f"✅ Generated {len(suggestions)} suggestions")
            
            return {
                "status": "success",
                "suggestions": suggestions,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error generating suggestions: {e}", exc_info=True)
            # Fallback: базовые рекомендации
            return self._get_fallback_suggestions(task)
    
    def _build_suggestions_prompt(
        self,
        existing_code: Optional[str],
        chat_history: List[Dict[str, Any]],
        input_schemas: List[Dict[str, Any]]
    ) -> str:
        """
        Формирует prompt для генерации рекомендаций.
        """
        prompt_parts = []
        
        # Проверяем, есть ли текстовый контент без таблиц
        is_text_only = any(schema.get("is_text_only") for schema in input_schemas)
        
        # Режим работы
        if existing_code:
            prompt_parts.extend([
                "MODE: IMPROVE EXISTING CODE",
                "",
                "CURRENT CODE:",
                "```python",
                existing_code,
                "```",
                ""
            ])
        else:
            if is_text_only:
                prompt_parts.extend([
                    "MODE: NEW TRANSFORMATION FOR TEXT CONTENT",
                    "IMPORTANT: This is TEXT data, NOT tables. Suggest text processing operations!",
                    ""
                ])
            else:
                prompt_parts.extend([
                    "MODE: NEW TRANSFORMATION",
                    ""
                ])
        
        # История чата для контекста
        if chat_history and len(chat_history) > 0:
            prompt_parts.extend([
                "CHAT HISTORY (last 3 messages):",
                ""
            ])
            for msg in chat_history[-3:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]  # Ограничиваем длину
                prompt_parts.append(f"{role.upper()}: {content}")
            prompt_parts.append("")
        
        # Схемы данных
        if input_schemas:
            prompt_parts.append("INPUT SCHEMAS:")
            for schema in input_schemas[:2]:  # Первые 2 таблицы
                name = schema.get("name", "df")
                columns = schema.get("columns", [])[:10]  # Первые 10 колонок
                content_text = schema.get("content_text", "")
                is_text_schema = schema.get("is_text_only", False)
                
                if is_text_schema:
                    # Текстовый контент без таблиц
                    prompt_parts.append(f"\n  SOURCE TYPE: TEXT CONTENT (no tables)")
                    prompt_parts.append(f"  Text length: {len(content_text)} characters")
                    prompt_parts.append(f"\n  TEXT PREVIEW (first 600 chars):")
                    prompt_parts.append(f"  {content_text[:600]}...")
                    prompt_parts.append("")
                    prompt_parts.append("  IMPORTANT: Suggest TEXT processing operations:")
                    prompt_parts.append("  - extract: extract structured data from text")
                    prompt_parts.append("  - summarize: summarize, create key points")
                    prompt_parts.append("  - structure: convert to table/JSON")
                    prompt_parts.append("  - analyze: sentiment, keywords, classification")
                    prompt_parts.append("  - transform: translate, format, clean")
                else:
                    # Табличные данные
                    prompt_parts.append(f"  {name}: {json.dumps(columns, ensure_ascii=False)}")
                    # Добавляем текст если есть
                    if content_text:
                        prompt_parts.append(f"\n  Additional text context:")
                        prompt_parts.append(f"  {content_text[:300]}...")
            prompt_parts.append("")
        
        # Задача
        if is_text_only:
            prompt_parts.extend([
                "TASK:",
                "Generate 6 specific TEXT PROCESSING suggestions.",
                "DO NOT suggest table operations (filter, aggregate) - there are no tables!",
                "Suggest: extract, summarize, structure, analyze, transform",
                "",
                "REQUIREMENTS:",
                "- Analyze the TEXT content and suggest relevant text processing",
                "- Be SPECIFIC (mention what to extract, summarize, etc.)",
                "- Return ONLY valid JSON (no markdown, no extra text)",
                ""
            ])
        else:
            prompt_parts.extend([
                "TASK:",
                "Generate 6 specific, actionable transformation suggestions.",
                "",
                "REQUIREMENTS:",
                "- Be SPECIFIC (use actual column names from schemas)",
                "- Don't suggest what's already done in existing_code",
                "- Consider the conversation context",
                "- Return ONLY valid JSON (no markdown, no extra text)",
                ""
            ])
        
        return "\n".join(prompt_parts)
    
    def _parse_suggestions_response(self, response: Any) -> Dict[str, Any]:
        """
        Парсит ответ от GigaChat.
        """
        try:
            response_text = response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                response_text = response.choices[0].message.content
            elif hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, dict):
                response_text = response.get('content', str(response))
            
            # Удаляем markdown code blocks
            cleaned = re.sub(r'```json\s*', '', response_text)
            cleaned = re.sub(r'```\s*$', '', cleaned)
            cleaned = cleaned.strip()
            
            # Парсим JSON
            result = json.loads(cleaned)
            
            # Валидация структуры
            if "suggestions" not in result:
                raise ValueError("Missing 'suggestions' key in response")
            
            suggestions = result["suggestions"]
            if not isinstance(suggestions, list):
                raise ValueError("'suggestions' must be a list")
            
            # Валидация каждой рекомендации
            valid_suggestions = []
            for sug in suggestions:
                if not isinstance(sug, dict):
                    continue
                if "label" not in sug or "prompt" not in sug or "category" not in sug:
                    continue
                
                # Нормализация
                valid_suggestions.append({
                    "id": sug.get("id", f"sug-{len(valid_suggestions)+1}"),
                    "label": sug["label"],
                    "prompt": sug["prompt"],
                    "category": sug["category"],
                    "confidence": sug.get("confidence", 0.7),
                    "description": sug.get("description", "")
                })
            
            return {"suggestions": valid_suggestions}
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}")
            self.logger.error(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from GigaChat: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing suggestions response: {e}")
            raise
    
    def _get_fallback_suggestions(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Возвращает базовые рекомендации в случае ошибки.
        """
        existing_code = task.get("existing_code")
        input_schemas = task.get("input_schemas", [])
        
        # Проверяем, текстовый ли контент
        is_text_only = any(schema.get("is_text_only") for schema in input_schemas)
        
        if is_text_only:
            # Fallback для текстового контента
            suggestions = [
                {
                    "id": "fallback-1",
                    "label": "Извлечь данные",
                    "prompt": "Извлеки все числовые показатели и даты из текста в таблицу",
                    "category": "extract",
                    "confidence": 0.7
                },
                {
                    "id": "fallback-2",
                    "label": "Краткое резюме",
                    "prompt": "Сделай краткое резюме основных тезисов в 5 пунктах",
                    "category": "summarize",
                    "confidence": 0.65
                },
                {
                    "id": "fallback-3",
                    "label": "Создать таблицу",
                    "prompt": "Преобразуй текст в структурированную таблицу",
                    "category": "structure",
                    "confidence": 0.6
                },
                {
                    "id": "fallback-4",
                    "label": "Найти организации",
                    "prompt": "Выдели все названия организаций и имена людей",
                    "category": "extract",
                    "confidence": 0.55
                },
                {
                    "id": "fallback-5",
                    "label": "Ключевые слова",
                    "prompt": "Определи ключевые слова и темы текста",
                    "category": "analyze",
                    "confidence": 0.5
                },
                {
                    "id": "fallback-6",
                    "label": "Форматировать",
                    "prompt": "Отформатируй текст как структурированный markdown",
                    "category": "transform",
                    "confidence": 0.45
                }
            ]
        elif existing_code:
            # Улучшения существующего кода
            suggestions = [
                {
                    "id": "fallback-1",
                    "label": "Добавить сортировку",
                    "prompt": "Отсортировать результаты по первой числовой колонке",
                    "category": "reshape",
                    "confidence": 0.6
                },
                {
                    "id": "fallback-2",
                    "label": "Добавить фильтр",
                    "prompt": "Добавить дополнительное условие фильтрации",
                    "category": "filter",
                    "confidence": 0.55
                },
                {
                    "id": "fallback-3",
                    "label": "Вычислить агрегаты",
                    "prompt": "Добавить группировку и посчитать сумму/среднее",
                    "category": "aggregate",
                    "confidence": 0.5
                },
                {
                    "id": "fallback-4",
                    "label": "Новая колонка",
                    "prompt": "Добавить вычисляемую колонку на основе существующих",
                    "category": "compute",
                    "confidence": 0.5
                },
                {
                    "id": "fallback-5",
                    "label": "Удалить дубликаты",
                    "prompt": "Удалить повторяющиеся строки",
                    "category": "reshape",
                    "confidence": 0.45
                },
                {
                    "id": "fallback-6",
                    "label": "Переименовать колонки",
                    "prompt": "Переименовать колонки для лучшей читаемости",
                    "category": "reshape",
                    "confidence": 0.45
                }
            ]
        else:
            # Новая трансформация
            suggestions = [
                {
                    "id": "fallback-1",
                    "label": "Фильтрация данных",
                    "prompt": "Отфильтровать строки по условию",
                    "category": "filter",
                    "confidence": 0.7
                },
                {
                    "id": "fallback-2",
                    "label": "Группировка",
                    "prompt": "Сгруппировать данные и посчитать агрегаты",
                    "category": "aggregate",
                    "confidence": 0.65
                },
                {
                    "id": "fallback-3",
                    "label": "Вычисляемая колонка",
                    "prompt": "Добавить новую колонку с вычислением",
                    "category": "compute",
                    "confidence": 0.6
                },
                {
                    "id": "fallback-4",
                    "label": "Сортировка данных",
                    "prompt": "Отсортировать данные по колонке",
                    "category": "reshape",
                    "confidence": 0.55
                },
                {
                    "id": "fallback-5",
                    "label": "Выбор колонок",
                    "prompt": "Выбрать только нужные колонки",
                    "category": "reshape",
                    "confidence": 0.5
                },
                {
                    "id": "fallback-6",
                    "label": "Топ N строк",
                    "prompt": "Выбрать топ-10 строк по значению",
                    "category": "filter",
                    "confidence": 0.5
                }
            ]
        
        return {
            "status": "success",
            "suggestions": suggestions,
            "agent": self.agent_name,
            "fallback": True
        }
