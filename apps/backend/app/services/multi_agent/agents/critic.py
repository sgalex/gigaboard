"""
CriticAgent — валидация результатов Multi-Agent системы.

Проверяет соответствие результатов работы агентов входному требованию пользователя.
См. docs/CRITIC_AGENT_SYSTEM.md
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from enum import Enum

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


class ExpectedOutcome(str, Enum):
    """Типы ожидаемых результатов."""
    CODE_GENERATION = "code_generation"
    DATA_EXTRACTION = "data_extraction"
    VISUALIZATION = "visualization"
    TRANSFORMATION = "transformation"
    RESEARCH = "research"


# System Prompt для CriticAgent
CRITIC_SYSTEM_PROMPT = '''
Вы — CriticAgent (Агент-Критик) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Валидация результатов работы агентов на соответствие требованиям пользователя.

**ЧТО ВЫ ОЦЕНИВАЕТЕ**:
1. Соответствие результата входному запросу (intent matching)
2. Полноту выполнения задачи
3. Качество и корректность результата
4. Наличие требуемых артефактов (код, данные, визуализация)

---

## АГЕНТЫ И ИХ ФОРМАТЫ ВЫВОДА

### SearchAgent
**Роль**: Поиск информации в интернете через DuckDuckGo
**Формат вывода**:
```json
{
  "query": "поисковый запрос",
  "results": [{"title": "...", "url": "...", "snippet": "...", "relevance": "high|medium|low"}],
  "summary": "Краткое резюме",
  "sources": ["url1", "url2"]
}
```
**Критерии успеха**: Есть results с url, summary не пустой

### ResearcherAgent
**Роль**: Получение данных из API, БД, веб-страниц
**Формат вывода**:
```json
{
  "content_type": "api_response|table|csv|json",
  "data": "<данные>",
  "schema": {"columns": ["col1", "col2"], "types": ["string", "int"]},
  "source": {"type": "api|database|web", "url": "..."},
  "statistics": {"row_count": 100, "size_bytes": 5000}
}
```
**Критерии успеха**: Есть data (не null), content_type определён, row_count > 0

### AnalystAgent
**Роль**: Анализ данных, поиск паттернов, генерация инсайтов
**Формат вывода**:
```json
{
  "insights": [
    {"type": "trend|anomaly|correlation", "severity": "high|medium|low", "title": "...", "description": "...", "evidence": {...}}
  ],
  "sql_query": "SELECT ... (если запрошен SQL)"
}
```
**Критерии успеха**: Есть insights (минимум 1), или sql_query если запрошен SQL

### TransformationAgent
**Роль**: Генерация Python кода для трансформаций ContentNode
**Формат вывода**:
```json
{
  "transformation_code": "# код pandas\ndf_result = df.groupby('col').sum()",
  "description": "Описание трансформации",
  "input_schemas": [{"node_id": "...", "columns": [...]}],
  "output_schema": {"columns": [...], "estimated_rows": 100},
  "validation_status": "success|error"
}
```
**Критерии успеха**: transformation_code содержит "df_result", validation_status = "success"

### ReporterAgent
**Роль**: Генерация HTML визуализаций (WidgetNode)
**Формат вывода**:
```json
{
  "widget_name": "Название виджета",
  "widget_code": "<!DOCTYPE html>...",
  "description": "Описание",
  "widget_type": "chart|table|metric|custom"
}
```
**Критерии успеха**: widget_code начинается с "<!DOCTYPE html>", widget_type определён

---

## ТИПЫ ОЖИДАЕМЫХ РЕЗУЛЬТАТОВ

### code_generation
Пользователь ожидает исполняемый код (Python, SQL, JavaScript)
- ✅ Есть блок кода или поле transformation_code/sql_query
- ✅ Код синтаксически корректен (без очевидных ошибок)
- ✅ Код решает поставленную задачу
- ❌ Только текстовое описание без кода

### data_extraction
Пользователь ожидает структурированные данные
- ✅ ResearcherAgent вернул data с row_count > 0
- ✅ Есть schema с columns
- ✅ content_type определён (table, json, csv)
- ❌ Только ссылки/URLs без загруженных данных

### visualization
Пользователь ожидает визуализацию
- ✅ ReporterAgent вернул widget_code с HTML
- ✅ widget_type определён (chart, table, metric)
- ✅ HTML содержит <script> для графиков
- ❌ Нет widget_code или пустой HTML

### transformation
Пользователь ожидает трансформацию данных
- ✅ TransformationAgent вернул transformation_code
- ✅ Код содержит "df_result"
- ✅ validation_status = "success"
- ❌ Нет df_result или ошибка валидации

### research
Пользователь ожидает информационный отчёт
- ✅ SearchAgent нашёл результаты с summary
- ✅ Или ResearcherAgent загрузил контент
- ✅ Или AnalystAgent дал insights
- ✅ Текстовый ответ с фактами приемлем
- ❌ Полное отсутствие информации

**ФОРМАТ ВЫВОДА (строго JSON)**:
{
    "valid": true/false,
    "confidence": 0.0-1.0,
    "issues": [
        {
            "severity": "critical|warning|info",
            "type": "missing_code|missing_data|incomplete|wrong_format",
            "message": "описание проблемы"
        }
    ],
    "recommendations": [
        {
            "action": "add_agent|modify_task|retry",
            "agent": "developer|reporter|transformation",
            "description": "что нужно сделать"
        }
    ],
    "suggested_replan": {
        "reason": "причина перепланирования",
        "additional_steps": [
            {
                "agent": "имя_агента",
                "task": {
                    "type": "тип_задачи",
                    "description": "описание"
                }
            }
        ]
    }
}

Если valid=true, поля issues, recommendations и suggested_replan могут быть пустыми.

**ВАЖНО**:
- Будьте СТРОГИ к code_generation: если нужен код — код должен быть
- Будьте гибки к research: текстовый ответ приемлем
- Рекомендации должны быть actionable (конкретные действия)
- Не рекомендуйте бесконечные итерации — если итерация >= 5, не давайте suggested_replan

**РЕКОМЕНДАЦИИ ПО АГЕНТАМ** (если результат invalid):
- Нет кода → добавить TransformationAgent (type: create_transformation) или DeveloperAgent
- Нет данных → добавить ResearcherAgent (type: fetch_from_api/fetch_urls)
- Нет визуализации → добавить ReporterAgent (type: create_visualization)
- Нет инсайтов → добавить AnalystAgent (type: analyze_data/find_insights)
- Нет информации → добавить SearchAgent (type: web_search) + ResearcherAgent (type: fetch_urls)
'''


class CriticAgent(BaseAgent):
    """
    CriticAgent — валидация результатов Multi-Agent системы.
    
    Проверяет:
    - Соответствие результата входному запросу
    - Наличие требуемых артефактов (код, данные, визуализация)
    - Полноту выполнения задачи
    
    При несоответствии формирует рекомендации для перепланирования.
    """
    
    # Ключевые слова для определения expected_outcome
    CODE_KEYWORDS = [
        "код", "напиши код", "сгенерируй код", "скрипт", "программу",
        "python", "sql", "javascript", "напиши скрипт", "создай код"
    ]
    DATA_KEYWORDS = [
        "данные", "загрузи", "получи данные", "скачай", "извлеки данные"
    ]
    VIZ_KEYWORDS = [
        "график", "визуализ", "диаграмм", "покажи на графике", "построй график"
    ]
    TRANSFORM_KEYWORDS = [
        "трансформируй", "преобразуй", "обработай данные", "добавь столбец",
        "отфильтруй", "сгруппируй"
    ]
    
    def __init__(
        self,
        message_bus: Optional[AgentMessageBus],
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        """
        Args:
            message_bus: Message Bus (может быть None для standalone использования)
            gigachat_service: GigaChat service для LLM валидации
            system_prompt: Кастомный system prompt (опционально)
        """
        if message_bus:
            super().__init__(
                agent_name="critic",
                message_bus=message_bus,
                system_prompt=system_prompt
            )
        else:
            self.agent_name = "critic"
            self.system_prompt = system_prompt or self._get_default_system_prompt()
            self.logger = logging.getLogger(f"agent.{self.agent_name}")
        
        self.gigachat = gigachat_service
    
    def _get_default_system_prompt(self) -> str:
        return CRITIC_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу валидации.
        
        Task format:
        {
            "type": "validate_result",
            "original_request": "исходный запрос пользователя",
            "expected_outcome": "code_generation|data_extraction|visualization|transformation|research",
            "aggregated_result": { результаты от агентов },
            "iteration": 1
        }
        """
        task_type = task.get("type")
        
        if task_type == "validate_result":
            return await self._validate_result(task, context)
        elif task_type == "determine_outcome":
            return self._determine_expected_outcome(task.get("user_message", ""))
        else:
            return {
                "error": f"Unknown task type: {task_type}",
                "valid": False
            }
    
    async def validate(
        self,
        user_message: str,
        aggregated_result: Dict[str, Any],
        expected_outcome: Optional[str] = None,
        iteration: int = 1,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Публичный метод для валидации результатов.
        
        Args:
            user_message: Исходный запрос пользователя
            aggregated_result: Результаты от всех агентов
            expected_outcome: Ожидаемый тип результата (если None — определяется автоматически)
            iteration: Текущая итерация валидации
            max_iterations: Максимальное количество итераций
            
        Returns:
            Dict с результатом валидации
        """
        # Определяем expected_outcome если не передан
        if not expected_outcome:
            outcome_result = self._determine_expected_outcome(user_message)
            expected_outcome = outcome_result.get("expected_outcome", "research")
        
        task = {
            "type": "validate_result",
            "original_request": user_message,
            "expected_outcome": expected_outcome,
            "aggregated_result": aggregated_result,
            "iteration": iteration,
            "max_iterations": max_iterations
        }
        
        return await self._validate_result(task, None)
    
    def _determine_expected_outcome(self, user_message: str) -> Dict[str, Any]:
        """
        Определяет ожидаемый тип результата по запросу пользователя.
        
        Returns:
            {"expected_outcome": "...", "confidence": 0.0-1.0}
        """
        message_lower = user_message.lower()
        
        # Проверяем ключевые слова в порядке приоритета
        if any(kw in message_lower for kw in self.CODE_KEYWORDS):
            return {"expected_outcome": ExpectedOutcome.CODE_GENERATION.value, "confidence": 0.9}
        elif any(kw in message_lower for kw in self.VIZ_KEYWORDS):
            return {"expected_outcome": ExpectedOutcome.VISUALIZATION.value, "confidence": 0.85}
        elif any(kw in message_lower for kw in self.TRANSFORM_KEYWORDS):
            return {"expected_outcome": ExpectedOutcome.TRANSFORMATION.value, "confidence": 0.85}
        elif any(kw in message_lower for kw in self.DATA_KEYWORDS):
            return {"expected_outcome": ExpectedOutcome.DATA_EXTRACTION.value, "confidence": 0.8}
        else:
            return {"expected_outcome": ExpectedOutcome.RESEARCH.value, "confidence": 0.7}
    
    async def _validate_result(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Валидирует результат через GigaChat.
        """
        original_request = task.get("original_request", "")
        expected_outcome = task.get("expected_outcome", "research")
        aggregated_result = task.get("aggregated_result", {})
        iteration = task.get("iteration", 1)
        max_iterations = task.get("max_iterations", 3)
        
        self.logger.info(
            f"🔍 CriticAgent validating result: expected={expected_outcome}, "
            f"iteration={iteration}/{max_iterations}"
        )
        
        # Сначала делаем быструю heuristic проверку
        heuristic_result = self._heuristic_validation(
            expected_outcome, aggregated_result, original_request
        )
        
        if heuristic_result.get("valid") and heuristic_result.get("confidence", 0) >= 0.9:
            # Высокая уверенность — пропускаем LLM
            self.logger.info(f"✅ Heuristic validation passed: {heuristic_result}")
            return heuristic_result
        
        # Делаем LLM валидацию для неочевидных случаев
        try:
            llm_result = await self._llm_validation(
                original_request, expected_outcome, aggregated_result,
                iteration, max_iterations
            )
            return llm_result
        except Exception as e:
            self.logger.error(f"❌ LLM validation failed: {e}")
            # Fallback на heuristic результат
            return heuristic_result
    
    def _heuristic_validation(
        self,
        expected_outcome: str,
        aggregated_result: Dict[str, Any],
        original_request: str
    ) -> Dict[str, Any]:
        """
        Быстрая эвристическая валидация без LLM.
        """
        # Преобразуем результаты в текст для анализа
        result_text = json.dumps(aggregated_result, ensure_ascii=False, default=str)
        
        if expected_outcome == ExpectedOutcome.CODE_GENERATION.value:
            # Ищем блоки кода
            has_code_block = bool(re.search(r'```(python|sql|javascript|js)\s*\n', result_text))
            has_inline_code = bool(re.search(r'(def |import |class |SELECT |FROM |CREATE )', result_text))
            
            if has_code_block:
                return {"valid": True, "confidence": 0.95, "message": "Найден блок кода"}
            elif has_inline_code:
                return {"valid": True, "confidence": 0.8, "message": "Найден inline код"}
            else:
                return {
                    "valid": False,
                    "confidence": 0.85,
                    "issues": [{
                        "severity": "critical",
                        "type": "missing_code",
                        "message": "Запрошен код, но результат не содержит блоков кода"
                    }],
                    "recommendations": [{
                        "action": "add_agent",
                        "agent": "developer",
                        "description": "Добавить DeveloperAgent для генерации кода"
                    }]
                }
        
        elif expected_outcome == ExpectedOutcome.VISUALIZATION.value:
            # Ищем widget_type или visualization config
            has_widget = "widget_type" in result_text or "chart" in result_text.lower()
            has_viz_data = "data_config" in result_text or "series" in result_text
            
            if has_widget or has_viz_data:
                return {"valid": True, "confidence": 0.9, "message": "Найдена конфигурация визуализации"}
            else:
                return {
                    "valid": False,
                    "confidence": 0.8,
                    "issues": [{
                        "severity": "critical",
                        "type": "missing_visualization",
                        "message": "Запрошена визуализация, но нет конфигурации виджета"
                    }],
                    "recommendations": [{
                        "action": "add_agent",
                        "agent": "reporter",
                        "description": "Добавить ReporterAgent для создания визуализации"
                    }]
                }
        
        elif expected_outcome == ExpectedOutcome.TRANSFORMATION.value:
            # Ищем df_result и pandas операции
            has_df_result = "df_result" in result_text
            has_pandas = "pd." in result_text or "pandas" in result_text or ".groupby(" in result_text
            
            if has_df_result and has_pandas:
                return {"valid": True, "confidence": 0.95, "message": "Найден код трансформации"}
            elif has_pandas:
                return {"valid": True, "confidence": 0.8, "message": "Найден pandas код (без df_result)"}
            else:
                return {
                    "valid": False,
                    "confidence": 0.8,
                    "issues": [{
                        "severity": "critical",
                        "type": "missing_transformation",
                        "message": "Запрошена трансформация, но нет pandas кода"
                    }],
                    "recommendations": [{
                        "action": "add_agent",
                        "agent": "transformation",
                        "description": "Добавить TransformationAgent для генерации кода"
                    }]
                }
        
        elif expected_outcome == ExpectedOutcome.DATA_EXTRACTION.value:
            # Ищем данные
            has_data = "DataFrame" in result_text or '"data"' in result_text
            has_columns = "columns" in result_text or "schema" in result_text
            
            if has_data:
                return {"valid": True, "confidence": 0.9, "message": "Найдены структурированные данные"}
            else:
                return {
                    "valid": False,
                    "confidence": 0.7,
                    "issues": [{
                        "severity": "warning",
                        "type": "missing_data",
                        "message": "Не найдены структурированные данные"
                    }]
                }
        
        else:  # RESEARCH
            # Для research почти любой текстовый ответ приемлем
            has_content = len(result_text) > 100
            return {
                "valid": has_content,
                "confidence": 0.85 if has_content else 0.5,
                "message": "Результат содержит текстовую информацию" if has_content else "Результат пуст"
            }
    
    async def _llm_validation(
        self,
        original_request: str,
        expected_outcome: str,
        aggregated_result: Dict[str, Any],
        iteration: int,
        max_iterations: int
    ) -> Dict[str, Any]:
        """
        Валидация через GigaChat.
        """
        # Формируем prompt
        result_summary = self._summarize_results(aggregated_result)
        
        user_prompt = f"""
Проверьте соответствие результата работы агентов запросу пользователя.

**Запрос пользователя**:
{original_request}

**Ожидаемый тип результата**: {expected_outcome}

**Результаты агентов**:
{result_summary}

**Итерация**: {iteration}/{max_iterations}
{"ВАЖНО: Это последняя итерация, не предлагайте suggested_replan" if iteration >= max_iterations else ""}

Проанализируйте и верните JSON с результатом валидации.
"""
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.gigachat.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )
        
        # Парсим JSON из ответа
        return self._parse_llm_response(response)
    
    def _summarize_results(self, aggregated_result: Dict[str, Any]) -> str:
        """
        Создаёт краткую сводку результатов для LLM.
        """
        parts = []
        
        for agent_name, result in aggregated_result.items():
            if isinstance(result, dict):
                # Извлекаем ключевые поля
                summary = {
                    "agent": agent_name,
                    "status": result.get("status", "unknown")
                }
                
                # Добавляем специфичные поля
                if "message" in result:
                    summary["message"] = result["message"][:500]  # Ограничиваем длину
                if "code" in result:
                    summary["has_code"] = True
                    summary["code_preview"] = result["code"][:300]
                if "widget_type" in result:
                    summary["widget_type"] = result["widget_type"]
                if "insights" in result:
                    summary["insights_count"] = len(result.get("insights", []))
                if "content_type" in result:
                    summary["content_type"] = result["content_type"]
                
                parts.append(json.dumps(summary, ensure_ascii=False, indent=2))
            else:
                parts.append(f"{agent_name}: {str(result)[:200]}")
        
        return "\n\n".join(parts)
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит JSON ответ от LLM.
        """
        try:
            # Пробуем извлечь JSON из ответа
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            else:
                self.logger.warning(f"No JSON found in LLM response: {response[:200]}")
                return {
                    "valid": True,  # Default to valid if can't parse
                    "confidence": 0.5,
                    "message": "Не удалось распарсить ответ валидации"
                }
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}, response: {response[:200]}")
            return {
                "valid": True,
                "confidence": 0.5,
                "message": f"Ошибка парсинга JSON: {e}"
            }


# Standalone helper функции
def determine_expected_outcome(user_message: str) -> str:
    """
    Standalone функция для определения expected_outcome.
    Используется в Orchestrator без создания экземпляра агента.
    """
    message_lower = user_message.lower()
    
    code_keywords = ["код", "напиши код", "сгенерируй код", "скрипт", "программу", "python", "sql"]
    viz_keywords = ["график", "визуализ", "диаграмм", "покажи на графике"]
    transform_keywords = ["трансформируй", "преобразуй", "обработай данные", "добавь столбец"]
    data_keywords = ["данные", "загрузи", "получи данные", "скачай"]
    
    if any(kw in message_lower for kw in code_keywords):
        return ExpectedOutcome.CODE_GENERATION.value
    elif any(kw in message_lower for kw in viz_keywords):
        return ExpectedOutcome.VISUALIZATION.value
    elif any(kw in message_lower for kw in transform_keywords):
        return ExpectedOutcome.TRANSFORMATION.value
    elif any(kw in message_lower for kw in data_keywords):
        return ExpectedOutcome.DATA_EXTRACTION.value
    else:
        return ExpectedOutcome.RESEARCH.value
