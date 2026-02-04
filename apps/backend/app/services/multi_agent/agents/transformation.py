"""
Transformation Agent - Data Pipeline Builder
Генерирует Python код для ContentNode-to-ContentNode трансформаций.
"""

import logging
import json
from typing import Dict, Any, Optional
import re

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Transformation Agent
TRANSFORMATION_SYSTEM_PROMPT = '''
Вы — Transformation Agent (Агент-Трансформации) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Генерация Python кода для трансформаций ContentNode-в-ContentNode с использованием pandas.

**КРИТИЧЕСКОЕ ПРАВИЛО — ВСЕГДА ТАБЛИЦА**:
Результат ВСЕГДА должен быть DataFrame (таблица). Даже если результат — это одно число или текст:
- Один результат → таблица с 1 строкой и 1+ столбцами
- Резюме текста → таблица со столбцами ['тип', 'значение'] или ['пункт', 'описание']
- Статистика → таблица со столбцами ['метрика', 'значение']

**Примеры правильного вывода**:
```python
# ❌ НЕПРАВИЛЬНО - строка, не DataFrame:
result = "Продажи выросли на 15%"

# ✅ ПРАВИЛЬНО - DataFrame с одной строкой:
df_result = pd.DataFrame({'результат': ['Продажи выросли на 15%']})

# ✅ ПРАВИЛЬНО - несколько пунктов:
df_result = pd.DataFrame({
    'пункт': ['Продажи', 'Расходы', 'Прибыль'],
    'значение': ['выросли на 15%', 'снизились на 5%', 'увеличилась на 20%']
})

# ✅ ПРАВИЛЬНО - метрики:
df_result = pd.DataFrame({
    'метрика': ['Среднее', 'Сумма', 'Максимум'],
    'значение': [150.5, 1505, 300]
})
```

**ОСНОВНАЯ КОНЦЕПЦИЯ**: 
Вы создаёте data pipelines на канвасе. Каждая трансформация:
- **Исходный ContentNode(ы)**: Входные данные (один: df, несколько: df1, df2, df3)
- **TRANSFORMATION связь**: Содержит Python код (операции pandas)
- **Целевой ContentNode**: Выходные данные (создаётся автоматически)

**ТРЕБОВАНИЯ К ГЕНЕРАЦИИ КОДА**:

1. **Входные переменные**:
   - Один источник: `df` (pandas DataFrame)
   - Несколько источников: `df1`, `df2`, `df3` (до 5)
   - Метаданные: `df.attrs['source_id']`, `df.attrs['schema']`

2. **Выходная переменная**:
   - Всегда: `df_result` (pandas DataFrame)
   - Должен быть DataFrame (не Series, dict или None)

3. **Разрешённые библиотеки**:
   - pandas (все операции)
   - numpy (численные операции)
   - datetime (манипуляции с датой/временем)
   - **gb (GigaBoard Helpers)**: AI-резолвинг для семантических задач
   - ЗАПРЕЩЕНО: file I/O, сетевые вызовы, subprocess, eval()

4. **GigaBoard Helpers (gb модуль)**:
   **Используйте gb для задач, которые невозможны с чистым pandas**:
   
   **Примеры AI-задач**:
   - Определение пола по имени
   - Извлечение страны из адреса
   - Классификация текста (категории, тип продукта)
   - Sentiment analysis
   - Любые семантические задачи
   
   **API**:
   ```python
   # Batch processing (рекомендуется для больших объемов)
   results = gb.ai_resolve_batch(
       values=list_of_values,           # Список значений для обработки
       task_description="описание задачи",  # Что нужно сделать
       result_format="string",          # "string", "number", "boolean"
       chunk_size=50                    # Опционально, по умолчанию 50
   )
   
   # Single value processing
   result = gb.ai_resolve_single(
       value="John Smith",
       task_description="определи пол по имени"
   )
   ```
   
   **Примеры использования**:
   ```python
   # Добавить колонку с полом на основе имени
   names = df['name'].tolist()
   genders = gb.ai_resolve_batch(
       values=names,
       task_description="определи пол человека по имени, верни M или F"
   )
   df_result = df.copy()
   df_result['gender'] = genders
   
   # Извлечь страну из адреса
   addresses = df['address'].tolist()
   countries = gb.ai_resolve_batch(
       values=addresses,
       task_description="извлеки название страны из адреса"
   )
   df_result = df.copy()
   df_result['country'] = countries
   
   # Классификация продуктов
   products = df['product_name'].tolist()
   categories = gb.ai_resolve_batch(
       values=products,
       task_description="определи категорию продукта: Electronics, Clothing, Food, Other"
   )
   df_result = df.copy()
   df_result['category'] = categories
   ```
   
   **Когда использовать gb**:
   ✅ Задачи требуют понимания семантики (пол по имени, категории)
   ✅ Извлечение информации из текста (страна из адреса)
   ✅ Классификация на основе значений (тип продукта)
   ✅ Анализ тональности/настроений
   
   **Когда НЕ использовать gb**:
   ❌ Математические операции (pandas/numpy)
   ❌ Фильтрация/сортировка данных (pandas)
   ❌ Агрегации/группировки (pandas)
   ❌ Работа с датами (pandas/datetime)

5. **Шаблон кода**:
```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Вход: df (или df1, df2 для нескольких источников)
# Ваш код трансформации здесь
df_result = ...  # Должен вернуть DataFrame
```

**ТИПЫ ТРАНСФОРМАЦИЙ**:
- Фильтр: `df[df['column'] > value]`
- Агрегация: `df.groupby(['col1']).agg({'col2': 'sum'})`
- Объединение: `pd.merge(df1, df2, on='key')`
- Сводная: `df.pivot_table(values='v', index='i', columns='c')`
- Временные ряды: `df.resample('D').mean()`
- Строковые операции: `df['col'].str.upper()`
- Пропущенные данные: `df.fillna(0)`, `df.dropna()`
- Вычисления: `df['new_col'] = df['col1'] * df['col2']`
- **AI-резолвинг**: `gb.ai_resolve_batch()` для семантических задач

**ПРОВЕРКИ ВАЛИДАЦИИ**:
1. Отсутствие синтаксических ошибок
2. Вход/выход DataFrame (не Series)
3. Отсутствие запрещённых операций (file I/O, сеть, eval)
4. Корректная обработка отсутствующих столбцов
5. Обработка ошибок несоответствия типов

**OUTPUT FORMAT**:
```json
{
  "transformation_code": "# Add gender column\\nnames = df['name'].tolist()\\ngenders = gb.ai_resolve_batch(values=names, task_description='определи пол по имени')\\ndf_result = df.copy()\\ndf_result['gender'] = genders",
  "description": "Add gender column based on name using AI",
  "input_schemas": [
    {"node_id": "dn_123", "columns": ["name", "age", "city"]}
  ],
  "output_schema": {
    "columns": ["name", "age", "city", "gender"],
    "estimated_rows": 100
  },
  "validation_status": "success",
  "warnings": []
}
```

**IMPORTANT**: 
- transformation_code must be a SINGLE STRING with \\n for line breaks (NOT an array)
- Include ALL code lines in one string
- Example: "line1\\nline2\\nline3"

**SECURITY**: Never use eval(), exec(), __import__(), subprocess, os, sys modules.

Be precise, generate clean pandas code, and always validate before returning.
'''


class TransformationAgent(BaseAgent):
    """
    Transformation Agent - генерация Python кода для трансформаций DataNode.
    
    Основные функции:
    - Генерация pandas кода из естественного языка
    - Валидация кода на безопасность
    - Определение output schema
    - Оптимизация трансформаций
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="transformation",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
        # Список запрещенных паттернов в коде
        self.forbidden_patterns = [
            r'\beval\b', r'\bexec\b', r'\b__import__\b',
            r'\bsubprocess\b', r'\bos\.', r'\bsys\.',
            r'\bopen\(', r'\bfile\(', r'\bimport\s+os\b',
            r'\bimport\s+sys\b', r'\bimport\s+subprocess\b'
        ]
        
    def _get_default_system_prompt(self) -> str:
        return TRANSFORMATION_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу трансформации.
        
        Поддерживаемые типы задач:
        - generate_transformation: Генерация pandas кода из описания
        - validate_transformation: Валидация существующего кода
        - optimize_transformation: Оптимизация кода
        """
        task_type = task.get("type")
        
        if task_type == "generate_transformation":
            return await self._generate_transformation(task, context)
        elif task_type == "validate_transformation":
            return await self._validate_transformation(task, context)
        elif task_type == "optimize_transformation":
            return await self._optimize_transformation(task, context)
        else:
            return self._format_error_response(
                f"Unknown task type: {task_type}",
                suggestions=["Supported types: generate_transformation, validate_transformation, optimize_transformation"]
            )
    
    async def _generate_transformation(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует pandas код для трансформации.
        """
        try:
            self._validate_task(task, ["description"])
            
            description = task["description"]
            input_schemas = task.get("input_schemas", [])
            previous_errors = task.get("previous_errors", [])
            existing_code = task.get("existing_code")  # For iterative improvements
            chat_history = task.get("chat_history", [])  # For context
            multiple_sources = len(input_schemas) > 1
            
            self.logger.info(f"🔄 Generating transformation for: {description[:100]}...")
            if previous_errors:
                self.logger.info(f"⚠️ Previous validation errors: {previous_errors}")
            if existing_code:
                self.logger.info(f"🔁 Iterative mode: improving existing code ({len(existing_code)} chars)")
            if chat_history:
                self.logger.info(f"💬 Chat history provided: {len(chat_history)} messages")
            
            # Формируем prompt для GigaChat
            transformation_prompt = self._build_transformation_prompt(
                description=description,
                input_schemas=input_schemas,
                multiple_sources=multiple_sources,
                previous_errors=previous_errors,
                existing_code=existing_code,
                chat_history=chat_history
            )
            
            # Вызываем GigaChat
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": transformation_prompt}
            ]
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.2,  # Низкая температура для точного кода
                max_tokens=2500  # Увеличенный лимит для полного кода с gb helpers
            )
            
            self.logger.info(f"🤖 GigaChat response type: {type(response).__name__}")
            self.logger.info(f"🤖 GigaChat response: {str(response)[:300]}")
            
            # Парсим ответ
            result = self._parse_transformation_response(response)
            
            self.logger.info(f"📋 Parsed result type: {type(result).__name__}")
            self.logger.info(f"📋 transformation_code type: {type(result.get('transformation_code')).__name__}")
            
            # Логируем сгенерированный код для отладки
            generated_code = result.get("transformation_code", "")
            self.logger.info(f"📝 Generated code:\n{generated_code}")
            
            # Валидация кода
            validation_result = self._validate_code(generated_code)
            
            if not validation_result["valid"]:
                return self._format_error_response(
                    f"Generated code failed validation: {validation_result['error']}",
                    suggestions=["Review the description", "Simplify the transformation"]
                )
            
            result["validation_status"] = "success"
            result["warnings"] = validation_result.get("warnings", [])
            
            self.logger.info(f"✅ Transformation code generated successfully")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error generating transformation: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _validate_transformation(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Валидирует существующий код трансформации.
        """
        try:
            self._validate_task(task, ["transformation_code"])
            
            code = task["transformation_code"]
            
            self.logger.info(f"🔍 Validating transformation code...")
            
            validation_result = self._validate_code(code)
            
            if validation_result["valid"]:
                self.logger.info(f"✅ Code validation passed")
                return {
                    "status": "success",
                    "valid": True,
                    "warnings": validation_result.get("warnings", []),
                    "agent": self.agent_name
                }
            else:
                self.logger.warning(f"⚠️ Code validation failed: {validation_result['error']}")
                return {
                    "status": "success",
                    "valid": False,
                    "error": validation_result["error"],
                    "suggestions": validation_result.get("suggestions", []),
                    "agent": self.agent_name
                }
            
        except Exception as e:
            self.logger.error(f"Error validating transformation: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _optimize_transformation(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Оптимизирует существующий код трансформации.
        """
        try:
            self._validate_task(task, ["transformation_code"])
            
            code = task["transformation_code"]
            row_count = task.get("row_count", 1000)
            
            self.logger.info(f"⚡ Optimizing transformation for {row_count} rows...")
            
            # Формируем prompt для оптимизации
            optimization_prompt = f"""
ORIGINAL CODE:
```python
{code}
```

CONTEXT:
- Row count: {row_count}
- Performance goal: Faster execution, lower memory usage

Optimize this pandas code for better performance. Focus on:
1. Vectorized operations instead of loops
2. Efficient memory usage
3. Avoid unnecessary copies
4. Use proper indexing

Return optimized code as JSON: {{"optimized_code": "...", "improvements": ["..."]}}
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": optimization_prompt}
            ]
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3
            )
            
            result = self._parse_json_response(response)
            
            # Валидация оптимизированного кода
            optimized_code = result.get("optimized_code", code)
            validation_result = self._validate_code(optimized_code)
            
            if not validation_result["valid"]:
                # Если оптимизированный код невалиден, возвращаем оригинал
                self.logger.warning("Optimized code failed validation, returning original")
                return {
                    "status": "success",
                    "optimized_code": code,
                    "improvements": ["Optimization skipped - validation failed"],
                    "agent": self.agent_name
                }
            
            self.logger.info(f"✅ Code optimized successfully")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing transformation: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    def _build_transformation_prompt(
        self,
        description: str,
        input_schemas: list,
        multiple_sources: bool,
        previous_errors: Optional[list] = None,
        existing_code: Optional[str] = None,
        chat_history: Optional[list] = None
    ) -> str:
        """
        Формирует prompt для генерации трансформации.
        Поддерживает два режима:
        - Новая генерация: создание кода с нуля
        - Итеративное улучшение: модификация existing_code на основе chat_history
        """
        prompt_parts = []
        
        # Проверяем, есть ли текстовый контент без таблиц
        is_text_only = any(schema.get("is_text_only") for schema in input_schemas) if input_schemas else False
        
        # === РЕЖИМ: Итеративное улучшение ===
        if existing_code:
            prompt_parts.extend([
                "MODE: ITERATIVE IMPROVEMENT",
                "",
                "CURRENT CODE:",
                "```python",
                existing_code,
                "```",
                ""
            ])
            
            # Добавляем историю чата для контекста
            if chat_history and len(chat_history) > 0:
                prompt_parts.extend([
                    "CONVERSATION HISTORY:",
                    ""
                ])
                for msg in chat_history[-5:]:  # Последние 5 сообщений для контекста
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    prompt_parts.append(f"{role.upper()}: {content}")
                prompt_parts.append("")
            
            prompt_parts.extend([
                f"NEW REQUEST: {description}",
                "",
                "TASK:",
                "- MODIFY the existing code above to fulfill the new request",
                "- PRESERVE working functionality unless explicitly asked to change it",
                "- ADD new features or improvements as requested",
                "- FIX any bugs or issues if mentioned",
                "- Keep code clean and maintain consistent style",
                ""
            ])
        
        # === РЕЖИМ: Новая генерация ===
        else:
            if is_text_only:
                # Режим для текстового контента
                prompt_parts.extend([
                    "TASK: Process TEXT content (no tables available)",
                    f"DESCRIPTION: {description}",
                    "",
                    "IMPORTANT: This is TEXT content, NOT tabular data!",
                    "Available input: `text` variable containing the full text content",
                    "",
                    "TEXT PROCESSING APPROACHES:",
                    "1. Extract data into DataFrame using regex/parsing:",
                    "   import re",
                    "   numbers = re.findall(r'\\d+[.,]?\\d*', text)",
                    "   df_result = pd.DataFrame({'extracted_numbers': numbers})",
                    "",
                    "2. Split into lines/sentences:",
                    "   lines = text.split('\\n')",
                    "   df_result = pd.DataFrame({'line': lines})",
                    "",
                    "3. Parse structured patterns:",
                    "   pattern = r'(\\w+):\\s*(\\d+)'",
                    "   matches = re.findall(pattern, text)",
                    "   df_result = pd.DataFrame(matches, columns=['key', 'value'])",
                    "",
                    "4. Use AI for semantic extraction (gb helper):",
                    "   extracted = gb.ai_resolve_batch([text], task_description='извлеки ключевые факты')",
                    "   df_result = pd.DataFrame({'fact': extracted})",
                    "",
                    "5. Create summary DataFrame:",
                    "   df_result = pd.DataFrame({",
                    "       'metric': ['word_count', 'line_count'],",
                    "       'value': [len(text.split()), len(text.split('\\n'))]",
                    "   })",
                    "",
                ])
            else:
                prompt_parts.extend([
                    "TASK: Generate pandas transformation code",
                    f"DESCRIPTION: {description}",
                    ""
                ])
        
        # Схемы входных данных (для обоих режимов)
        if input_schemas:
            prompt_parts.append("INPUT DATA:")
            for i, schema in enumerate(input_schemas):
                is_schema_text_only = schema.get("is_text_only", False)
                
                if is_schema_text_only:
                    # Текстовый контент
                    content_text = schema.get("content_text", "")
                    prompt_parts.append(f"\nTEXT CONTENT ({len(content_text)} characters):")
                    prompt_parts.append("Available as variable: `text`")
                    prompt_parts.append(f"\nText preview (first 800 chars):")
                    prompt_parts.append(f"---")
                    prompt_parts.append(f"{content_text[:800]}...")
                    prompt_parts.append(f"---")
                else:
                    # Табличные данные
                    var_name = f"df{i+1}" if multiple_sources else "df"
                    
                    # Отображаем текст отдельно для лучшей читаемости
                    node_text = schema.get("node_text", "")
                    if node_text:
                        prompt_parts.append(f"\nSource text from {schema.get('node_name', 'node')}:")
                        prompt_parts.append(f"  {node_text[:500]}...")  # Первые 500 символов
                    
                    # Схема таблицы
                    table_schema = {
                        "name": schema.get("name"),
                        "columns": schema.get("columns"),
                        "column_types": schema.get("column_types"),
                        "sample_data": schema.get("sample_data")
                    }
                    prompt_parts.append(f"{var_name}: {json.dumps(table_schema, ensure_ascii=False)}")
            prompt_parts.append("")
        
        if multiple_sources and not is_text_only:
            prompt_parts.append("Note: Multiple input sources, use df1, df2, etc.")
        
        # Добавляем информацию о предыдущих ошибках
        if previous_errors:
            prompt_parts.extend([
                "⚠️ PREVIOUS ATTEMPT FAILED WITH ERRORS:",
                *[f"- {error}" for error in previous_errors],
                "",
                "IMPORTANT: Fix these errors in your code generation!",
                ""
            ])
        
        # Разные требования для текста vs таблиц
        if is_text_only:
            prompt_parts.extend([
                "REQUIREMENTS FOR TEXT PROCESSING:",
                "- Input is `text` variable (string with full text content)",
                "- Output MUST be df_result (pandas DataFrame)",
                "- Extract/parse text into structured DataFrame",
                "- Use re (regex), str methods, or gb.ai_resolve_batch()",
                "- Common patterns:",
                "  - re.findall() for extracting patterns",
                "  - text.split() for tokenizing",
                "  - gb.ai_resolve_batch() for semantic extraction",
                "- Use only: pandas, numpy, re, datetime",
                "- No file I/O, network calls, or subprocess",
                "",
                "TEXT TO TABLE EXAMPLES:",
                "",
                "Example 1 - Extract numbers:",
                "\"import re\"",
                "\"numbers = re.findall(r'\\\\d+[.,]?\\\\d*', text)\"",
                "\"df_result = pd.DataFrame({'value': [float(n.replace(',', '.')) for n in numbers]})\"",
                "",
                "Example 2 - Split into lines:",
                "\"lines = [l.strip() for l in text.split('\\\\n') if l.strip()]\"",
                "\"df_result = pd.DataFrame({'line_num': range(1, len(lines)+1), 'content': lines})\"",
                "",
                "Example 3 - Parse key-value pairs:",
                "\"import re\"",
                "\"pairs = re.findall(r'([А-Яа-яA-Za-z]+):\\\\s*([\\\\d.,]+)', text)\"",
                "\"df_result = pd.DataFrame(pairs, columns=['metric', 'value'])\"",
                "",
                "Example 4 - Create summary:",
                "\"word_count = len(text.split())\"",
                "\"line_count = len(text.split('\\\\n'))\"",
                "\"char_count = len(text)\"",
                "\"df_result = pd.DataFrame({\"",
                "\"    'metric': ['Words', 'Lines', 'Characters'],\"",
                "\"    'value': [word_count, line_count, char_count]\"",
                "\"})\"",
                "",
                "Example 5 - AI summarization (ALWAYS as table):",
                "\"# Get AI summary\"",
                "\"summary = gb.ai_resolve_batch([text], task_description='сделай краткое резюме в 3 пунктах')[0]\"",
                "\"# Split into rows\"",
                "\"points = [p.strip() for p in summary.split('\\\\n') if p.strip()]\"",
                "\"df_result = pd.DataFrame({'пункт': range(1, len(points)+1), 'описание': points})\"",
                "",
                "Example 6 - Single text result (wrap in table):",
                "\"result_text = 'Анализ показал рост на 15%'\"",
                "\"df_result = pd.DataFrame({'результат': [result_text]})\"",
                "",
                "CRITICAL: ALWAYS OUTPUT A DATAFRAME!",
                "Even for single text results, wrap in DataFrame:",
                "  df_result = pd.DataFrame({'результат': ['ваш текст']})",
                "",
                "Return VALID JSON with fields: transformation_code, description, output_schema"
            ])
        else:
            prompt_parts.extend([
                "REQUIREMENTS:",
                "- Generate clean, efficient pandas code",
                "- For SINGLE output: use df_result (DataFrame)",
                "- For MULTIPLE outputs: use df_result, df_result2, df_result3, etc.",
                "- ALL output variables MUST start with 'df_' prefix",
                "- ALWAYS assign final result to df_result (or df_resultN for multiple outputs)",
                "- Use only pandas, numpy, datetime libraries",
                "- No file I/O, network calls, or subprocess",
                "- IMPORTANT: Add Python comments INSIDE code strings, not after JSON elements",
                "",
                "MULTIPLE SOURCE MERGE EXAMPLE:",
                "\"# Combine multiple sources\"",
                "\"df_result = pd.concat([df1, df2, df3], ignore_index=True)\"",
                "",
                "MULTIPLE OUTPUTS EXAMPLES:",
                "",
                "Example 1 - Split by condition:",
                "\"# High earners\"",
                "\"df_result = df[df['salary'] >= 80000]\"",
                "\"# Low earners\"",
                "\"df_result2 = df[df['salary'] < 80000]\"",
                "",
                "Example 2 - Group by category:",
                "\"# Electronics products\"",
                "\"df_result = df[df['category'] == 'Electronics']\"",
                "\"# Clothing products\"", 
                "\"df_result2 = df[df['category'] == 'Clothing']\"",
                "\"# Food products\"",
                "\"df_result3 = df[df['category'] == 'Food']\"",
                "",
                "CRITICAL RULES:",
                "- Each output table = separate df_result{N} variable",
                "- DON'T concat tables back together unless explicitly asked",
                "- First output is always df_result (no number)",
                "- Second output is df_result2, third is df_result3, etc.",
                "- NEVER use intermediate variables like 'merged', 'combined', 'result' - always use df_result directly!",
                "",
                "BAD (don't do this):",
                "\"merged = pd.concat([df1, df2])\"  # ❌ Wrong! No df_ prefix!",
                "\"result = df[...]\"                # ❌ Wrong! Must be df_result",
                "",
                "GOOD (do this):",
                "\"df_result = pd.concat([df1, df2])\"  # ✅ Correct!",
                "\"df_result = df[...]\"                # ✅ Correct!",
                "",
                "CRITICAL: ALWAYS OUTPUT A DATAFRAME!",
                "Even for aggregations or single values, wrap in DataFrame:",
                "  total = df['amount'].sum()",
                "  df_result = pd.DataFrame({'metric': ['Total'], 'value': [total]})",
                "",
                "Return VALID JSON with fields: transformation_code, description, output_schema"
            ])
        
        return "\n".join(prompt_parts)
    
    def _parse_transformation_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ от LLM с трансформацией.
        """
        return self._parse_json_response(response)
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит JSON ответ от LLM.
        """
        response = response.strip()
        
        # Удаляем markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```python"):
            response = response[9:]
        elif response.startswith("```"):
            response = response[3:]
        
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Проверяем формат transformation_code: массив или строка
        import re
        is_array_format = bool(re.search(r'"transformation_code"\s*:\s*\[', response))
        
        transformation_code_with_comments = None
        
        if is_array_format:
            # Извлекаем transformation_code с комментариями ДО парсинга JSON
            match = re.search(r'"transformation_code"\s*:\s*\[(.*?)\]', response, re.DOTALL)
            if match:
                # Извлекаем ВСЕ строки кода из массива, включая комментарии
                code_array_content = match.group(1)
                # Парсим строки: "code" (с любыми символами внутри, включая #)
                code_lines = []
                for line in re.findall(r'"([^"]*)"', code_array_content):
                    # Сохраняем ВСЕ строки, не фильтруем
                    code_lines.append(line)
                if code_lines:
                    transformation_code_with_comments = "\n".join(code_lines)
            
            # Очистка JSON ТОЛЬКО для массивов - убираем комментарии и лишние запятые:
            # 1. Удаляем строки-комментарии целиком (с запятыми до/после):
            response = re.sub(r',?\s*"#[^"]*"\s*,?', '', response)
            
            # 2. Удаляем пустые строки из массивов
            response = re.sub(r',\s*"",?\s*', ',\n    ', response)
            
            # 3. Удаляем inline комментарии после элементов массива
            response = re.sub(r'",\s*#[^\n]*', '",', response)
            
            # 4. Удаляем inline комментарии после других элементов JSON
            response = re.sub(r'(["\}\]])\s*#[^\n]*', r'\1', response)
            
            # 5. Удаляем одинокие запятые
            response = re.sub(r'(\[)\s*,\s*', r'\1', response)
            
            # 6. Чистим лишние запятые перед закрывающей скобкой
            response = re.sub(r',(\s*\])', r'\1', response)
        
        # Для строкового формата - парсим напрямую без очистки
        
        try:
            result = json.loads(response)
            
            # Если transformation_code - список, объединяем в строку
            if "transformation_code" in result:
                code = result["transformation_code"]
                if isinstance(code, list):
                    # Используем версию с комментариями, если извлекли
                    if transformation_code_with_comments:
                        result["transformation_code"] = transformation_code_with_comments
                    else:
                        result["transformation_code"] = "\n".join(code)
            
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}, response: {response[:500]}")
            
            # Fallback: извлекаем код из невалидного JSON
            # GigaChat часто использует Python-style конкатенацию строк в JSON:
            # "transformation_code": "line1\n"
            #                        "line2\n"
            
            extracted_code = self._extract_code_from_invalid_json(response)
            if extracted_code:
                self.logger.info(f"📋 Extracted code from invalid JSON:\n{extracted_code[:200]}")
                return {
                    "transformation_code": extracted_code,
                    "description": "Auto-extracted transformation"
                }
            
            # Последний fallback: вернуть весь ответ (маловероятно)
            return {
                "transformation_code": response,
                "description": "Auto-extracted transformation"
            }
    
    def _extract_code_from_invalid_json(self, response: str) -> Optional[str]:
        """
        Извлекает transformation_code из невалидного JSON.
        
        GigaChat часто возвращает JSON с Python-style конкатенацией строк:
        {
          "transformation_code": "# Comment\n"
                                 "df_result = df[...]\n"
                                 "df_result2 = df[...]",
          ...
        }
        
        Этот метод извлекает код из такого формата.
        """
        import re
        
        # Ищем начало transformation_code
        match = re.search(r'"transformation_code"\s*:\s*"', response)
        if not match:
            return None
        
        start_pos = match.end()
        
        # Собираем все строки кода
        code_lines = []
        pos = start_pos
        
        while pos < len(response):
            # Ищем конец текущей строки (неэкранированная кавычка)
            end_quote_pos = None
            i = pos
            while i < len(response):
                if response[i] == '"' and (i == 0 or response[i-1] != '\\'):
                    end_quote_pos = i
                    break
                i += 1
            
            if end_quote_pos is None:
                break
            
            # Извлекаем содержимое строки
            line_content = response[pos:end_quote_pos]
            # Декодируем escape-последовательности
            line_content = line_content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            code_lines.append(line_content)
            
            # Проверяем, есть ли продолжение (Python-style конкатенация)
            # Ищем следующую кавычку после пробелов/переносов
            next_pos = end_quote_pos + 1
            while next_pos < len(response) and response[next_pos] in ' \t\n\r':
                next_pos += 1
            
            if next_pos < len(response) and response[next_pos] == '"':
                # Есть продолжение
                pos = next_pos + 1
            else:
                # Строка закончилась
                break
        
        if code_lines:
            result = ''.join(code_lines)
            # Убираем trailing newline если есть
            return result.rstrip('\n')
        
        return None

    def _validate_code(self, code: str) -> Dict[str, Any]:
        """
        Валидирует pandas код на безопасность и корректность.
        """
        warnings = []
        
        # 1. Проверка на запрещенные паттерны
        for pattern in self.forbidden_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return {
                    "valid": False,
                    "error": f"Forbidden pattern detected: {pattern}",
                    "suggestions": ["Remove dangerous operations", "Use only pandas/numpy/datetime"]
                }
        
        # 2. Проверка наличия df_result
        if "df_result" not in code:
            return {
                "valid": False,
                "error": "Output variable 'df_result' not found in code",
                "suggestions": ["Add 'df_result = ...' assignment"]
            }
        
        # 3. Проверка базового синтаксиса
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"Syntax error: {str(e)}",
                "suggestions": ["Fix Python syntax errors"]
            }
        
        # 4. Предупреждения о производительности
        if ".iterrows()" in code:
            warnings.append("iterrows() detected - consider vectorized operations for better performance")
        
        if ".apply(lambda" in code and code.count(".apply(") > 2:
            warnings.append("Multiple apply() calls - consider vectorization")
        
        return {
            "valid": True,
            "warnings": warnings
        }
