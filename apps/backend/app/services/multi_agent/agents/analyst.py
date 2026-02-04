"""
Analyst Agent - Data Analysis & Structure Extraction
Отвечает за анализ данных, извлечение структуры из текста и подготовку данных для обработки.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Analyst Agent
ANALYST_SYSTEM_PROMPT = '''
Вы — Analyst Agent в системе GigaBoard. Ваша задача — извлекать структурированные данные из текста.

## КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ВЫВОДА:

**ВСЕГДА возвращай ТОЛЬКО чистый JSON без markdown-обёрток!**

❌ НЕПРАВИЛЬНО:
```json
{"text": "...", "tables": [...]}
```

✅ ПРАВИЛЬНО:
{"text": "...", "tables": [...]}

## ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА:

Твой ответ ВСЕГДА должен быть валидным JSON с полями "text" и "tables":

{
  "text": "Текстовое описание результатов анализа. Ключевые выводы, инсайты и пояснения к данным. Этот текст будет показан пользователю как основной контент.",
  "tables": [
    {
      "name": "название_таблицы",
      "columns": ["колонка1", "колонка2", "колонка3"],
      "rows": [
        ["значение1", "значение2", "значение3"],
        ["значение4", "значение5", "значение6"]
      ]
    }
  ],
  "confidence": 0.85
}

## ПРАВИЛА:

1. **text** — ОБЯЗАТЕЛЬНО. Содержит:
   - Краткое резюме найденных данных
   - Ключевые выводы и инсайты
   - Пояснения к таблицам
   - Можно использовать Markdown форматирование (заголовки, списки)

2. **tables** — ОБЯЗАТЕЛЬНО. Массив таблиц (может быть пустым []):
   - name: название таблицы
   - columns: массив названий колонок
   - rows: массив строк (каждая строка — массив значений)

3. **Не выдумывай данные** — если информации нет, верни пустой массив tables и напиши об этом в text

## ПРИМЕРЫ:

### Задача: Извлечь список кинотеатров
Ответ:
{
  "text": "## Анализ кинотеатров России\\n\\nНайдено 2 крупных кинотеатра с данными о посещаемости.\\n\\n### Ключевые выводы:\\n- Каро Фильм лидирует по количеству просмотров\\n- Средний рейтинг сетей: 4.35",
  "tables": [
    {
      "name": "cinemas",
      "columns": ["Кинотеатр", "Просмотры", "Жанры", "Рейтинг"],
      "rows": [
        ["Каро Фильм", 1234567, "Action, Comedy", 4.5],
        ["Синема Парк", 987654, "Drama, Horror", 4.2]
      ]
    }
  ],
  "confidence": 0.9
}

### Задача: Сравнить фреймворки
Ответ:
{
  "text": "## Сравнение Rust фреймворков\\n\\nПроанализировано 3 популярных фреймворка.\\n\\n**Лидер:** Tokio с 22k GitHub stars — стандарт для async Rust.\\n\\n**Веб-фреймворки:** Actix-web и Rocket конкурируют, Actix быстрее, Rocket удобнее.",
  "tables": [
    {
      "name": "frameworks_comparison",
      "columns": ["Фреймворк", "GitHub Stars", "Язык", "Категория"],
      "rows": [
        ["Actix-web", 18500, "Rust", "web"],
        ["Tokio", 22000, "Rust", "async"],
        ["Rocket", 19000, "Rust", "web"]
      ]
    }
  ],
  "confidence": 0.95
}

### Задача: Данные не найдены
Ответ:
{
  "text": "## Результаты поиска\\n\\nК сожалению, в предоставленных источниках не найдено структурированной информации по запросу.\\n\\nВозможные причины:\\n- Источники не содержат релевантных данных\\n- Информация представлена в неструктурированном виде",
  "tables": [],
  "confidence": 0.0
}

## ОГРАНИЧЕНИЯ:
- НЕ оборачивай JSON в markdown-блоки (```json ... ```)
- НЕ добавляй текст до или после JSON
- Числовые значения — числа, не строки
- Все строки — в двойных кавычках
- Используй \\n для переносов строк в text
'''


class AnalystAgent(BaseAgent):
    """
    Analyst Agent - анализ данных и генерация SQL запросов.
    
    Основные функции:
    - Генерация SQL запросов из естественного языка
    - Статистический анализ данных
    - Поиск трендов и аномалий
    - Формирование insights и рекомендаций
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="analyst",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
    def _get_default_system_prompt(self) -> str:
        return ANALYST_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает любую задачу анализа через LLM.
        
        Агент самостоятельно понимает намерение на основе:
        - Описания задачи (task.description)
        - Параметров задачи (все поля в task)
        - Контекста и результатов предыдущих шагов (context.previous_results)
        
        Не требует явного указания типа задачи.
        """
        try:
            description = task.get("description", "")
            if not description:
                return self._format_error_response("Task description is required")
            
            self.logger.info(f"🔍 Processing task: {description[:100]}...")
            
            # Получаем данные из Redis если есть session_id
            session_id = context.get("session_id") if context else None
            previous_results = context.get("previous_results", {}) if context else {}
            
            # Пытаемся обогатить данными из Redis
            if session_id and not previous_results:
                all_results = await self.get_all_previous_results(session_id)
                if all_results:
                    previous_results = all_results
                    self.logger.info(f"📦 Loaded {len(previous_results)} results from Redis")
            
            # Формируем универсальный prompt
            task_prompt = self._build_universal_prompt(task, previous_results)
            
            # Вызываем LLM
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": task_prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=2000
            )
            
            # Парсим результат
            result = self._parse_generic_response(response)
            
            self.logger.info(f"✅ Task completed successfully")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error processing task: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    def _build_universal_prompt(
        self,
        task: Dict[str, Any],
        previous_results: Dict[str, Any]
    ) -> str:
        """
        Формирует универсальный prompt для любой задачи.
        """
        description = task.get("description", "")
        
        # Собираем все параметры задачи (кроме description)
        task_params = {k: v for k, v in task.items() if k != "description"}
        
        prompt_parts = [
            "**TASK**:",
            description,
            ""
        ]
        
        # Добавляем параметры задачи если есть
        if task_params:
            prompt_parts.append("**TASK PARAMETERS**:")
            prompt_parts.append(json.dumps(task_params, indent=2, ensure_ascii=False))
            prompt_parts.append("")
        
        # Добавляем результаты предыдущих шагов если есть
        if previous_results:
            prompt_parts.append("**PREVIOUS RESULTS** (from other agents):")
            for agent_name, result in previous_results.items():
                prompt_parts.append(f"\n--- {agent_name.upper()} ---")
                
                # Умная обработка результатов ResearcherAgent
                if agent_name == "researcher" and isinstance(result, dict):
                    pages = result.get("pages", [])
                    if pages:
                        # Добавляем краткую статистику
                        prompt_parts.append(f"Pages fetched: {len(pages)}")
                        prompt_parts.append("")
                        
                        # Добавляем каждую страницу полностью (без обрезки content)
                        for i, page in enumerate(pages, 1):
                            prompt_parts.append(f"PAGE {i}:")
                            prompt_parts.append(f"URL: {page.get('url', 'N/A')}")
                            prompt_parts.append(f"Title: {page.get('title', 'N/A')}")
                            
                            content = page.get('content', '')
                            # Ограничиваем КАЖДУЮ страницу до 5000 символов
                            if len(content) > 5000:
                                prompt_parts.append(f"Content (first 5000 chars): {content[:5000]}...")
                            else:
                                prompt_parts.append(f"Content: {content}")
                            prompt_parts.append("")
                        continue
                
                # Для остальных агентов - прежняя логика
                result_str = json.dumps(result, indent=2, ensure_ascii=False)
                if len(result_str) > 2000:
                    prompt_parts.append(result_str[:2000] + "... (truncated)")
                else:
                    prompt_parts.append(result_str)
            prompt_parts.append("")
        
        prompt_parts.extend([
            "**INSTRUCTIONS**:",
            "1. Analyze the task description and parameters",
            "2. Use previous results if relevant to this task",
            "3. Extract ALL structured data from the provided pages",
            "4. Return result as valid JSON with requested fields",
            "",
            "Return ONLY valid JSON, no additional text."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_generic_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ LLM в универсальном формате.
        Поддерживает: чистый JSON, JSON в markdown блоках, plain text.
        """
        try:
            import re
            
            # 1. Проверяем markdown блок кода ```json ... ```
            markdown_json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if markdown_json_match:
                result = json.loads(markdown_json_match.group(1))
                return result
            
            # 2. Проверяем markdown блок без языка ``` ... ```
            markdown_match = re.search(r'```\s*(\{.*?\})\s*```', response, re.DOTALL)
            if markdown_match:
                result = json.loads(markdown_match.group(1))
                return result
            
            # 3. Ищем чистый JSON блок (без markdown)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            
            # 4. Если JSON не найден, возвращаем как message
            return {
                "message": response.strip()
            }
            
        except json.JSONDecodeError as e:
            # Если не удалось распарсить, возвращаем как текст
            self.logger.warning(f"Failed to parse JSON from response: {e}")
            return {
                "message": response.strip()
            }

