"""
Analyst Agent - Data Analysis & Insights
Отвечает за анализ данных и формирование выводов.

V2: Возвращает AgentPayload(narrative=..., findings=[...]) вместо Dict.
    См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import Finding, Narrative
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# System Prompt для Widget Suggestions (визуализации)
# Используется когда context.controller == "widget_suggestions"
# ══════════════════════════════════════════════════════════════════
WIDGET_SUGGESTIONS_SYSTEM_PROMPT = '''
Вы — Analyst Agent в режиме ВИЗУАЛИЗАЦИИ в системе GigaBoard.
Ваша ЕДИНСТВЕННАЯ задача — проанализировать данные и предложить РАЗНООБРАЗНЫЕ варианты визуализации.

## ВАША РОЛЬ:
✅ Анализ структуры и содержания данных
✅ Генерация 8-10 РАЗНООБРАЗНЫХ рекомендаций по визуализации
✅ Покрытие РАЗНЫХ категорий: chart, table, kpi, map
✅ Оценка актуальности каждой визуализации для конкретных данных

## КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ВЫВОДА:

**ВСЕГДА возвращай ТОЛЬКО чистый JSON без markdown-обёрток!**

❌ НЕПРАВИЛЬНО:
```json
{"text": "...", "insights": [...], "recommendations": [...]}
```

✅ ПРАВИЛЬНО:
{"text": "...", "insights": [...], "recommendations": [...]}

## ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА:

{
  "text": "Описание данных и рекомендации по визуализации.",
  "insights": [
    {
      "finding": "Краткий вывод о данных",
      "confidence": 0.9,
      "column_refs": ["col1", "col2"],
      "importance": "high"
    }
  ],
  "recommendations": [
    {
      "action": "Столбчатая диаграмма сравнения городов по зарплате",
      "columns": ["city", "avg_salary"],
      "rationale": "Позволит наглядно сравнить средние зарплаты между городами",
      "type": "bar_chart",
      "relevance": 0.95,
      "priority": "high",
      "confidence": 0.95,
      "category": "chart",
      "prompt": "Построй столбчатую диаграмму сравнения городов по средней зарплате"
    }
  ],
  "data_quality_issues": [],
  "tables": [],
  "confidence": 0.9
}

## ПРАВИЛА:

1. **text** — ОБЯЗАТЕЛЬНО. Краткое описание данных и подходящих визуализаций.

2. **insights** — 1-2 ключевых вывода о данных (краткие).

3. **recommendations** — ОБЯЗАТЕЛЬНО. Массив из 8-10 рекомендаций по ВИЗУАЛИЗАЦИИ:
   - action: ЧТО построить (название визуализации + описание)
   - columns: какие колонки использовать
   - rationale: ПОЧЕМУ эта визуализация подходит для данных
   - type: тип визуализации — одно из:
     • bar_chart — столбчатая / гистограмма
     • line_chart — линейный график
     • pie_chart — круговая диаграмма
     • scatter — точечная диаграмма
     • heatmap — тепловая карта
     • table — интерактивная таблица
     • kpi — KPI-карточки / метрики
     • map — географическая карта
     • treemap — древовидная карта
     • radar — радарная диаграмма
     • funnel — воронка
     • gauge — спидометр / gauge
   - relevance: актуальность (0.0-1.0)
   - priority: high/medium/low
   - confidence: уверенность (0.0-1.0)
   - category: "chart" | "table" | "kpi" | "map"
   - prompt: текст запроса для генерации виджета

   ВАЖНО:
   - Генерируй МИНИМУМ 8 рекомендаций
   - Покрывай МИНИМУМ 3-4 РАЗНЫХ категории (chart, table, kpi, map)
   - Используй КОНКРЕТНЫЕ названия колонок из данных!
   - Для каждой рекомендации давай ГОТОВЫЙ prompt для генерации

4. **data_quality_issues** — может быть пустым

## ПРИМЕРЫ РАЗНООБРАЗНЫХ РЕКОМЕНДАЦИЙ:

Для данных: Table \"sales\" [product, region, revenue, quantity, date]

Ответ должен включать:
1. Bar chart: "Столбчатая диаграмма выручки по регионам" (category: chart)
2. Pie chart: "Круговая диаграмма долей продаж по продуктам" (category: chart)
3. Line chart: "Динамика выручки по датам" (category: chart)
4. KPI cards: "KPI-карточки: общая выручка, среднее quantity, кол-во регионов" (category: kpi)
5. Table: "Интерактивная таблица с сортировкой и фильтрами" (category: table)
6. Heatmap: "Тепловая карта revenue по product × region" (category: chart)
7. Scatter: "Точечная диаграмма revenue vs quantity" (category: chart)
8. Treemap: "Древовидная карта выручки по регионам и продуктам" (category: chart)

## ОГРАНИЧЕНИЯ:
- НЕ оборачивай JSON в markdown-блоки
- НЕ добавляй текст до или после JSON
- Числовые значения — числа, не строки
- Все строки — в двойных кавычках
- Используй \\n для переносов строк в text
- НЕ рекомендуй трансформации данных (filter, aggregation) — только ВИЗУАЛИЗАЦИИ!
'''


# System Prompt для Analyst Agent
ANALYST_SYSTEM_PROMPT = '''
Вы — Analyst Agent в системе GigaBoard. 
Ваша ЕДИНСТВЕННАЯ задача — анализ структурированных данных и формирование логических выводов.

## ВАША РОЛЬ:
✅ Анализ существующих структурированных данных
✅ Формирование insights и выводов
✅ Рекомендации по метрикам и визуализациям
✅ Выявление паттернов, трендов и аномалий
✅ Оценка качества данных

## ВЫ НЕ ДЕЛАЕТЕ:
❌ Извлечение структуры из текста — это задача StructurizerAgent
❌ Генерацию кода — это задача TransformCodexAgent
❌ Визуализацию — это задача ReporterAgent/WidgetCodexAgent
❌ Поиск информации — это задача DiscoveryAgent

## КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ВЫВОДА:

**ВСЕГДА возвращай ТОЛЬКО чистый JSON без markdown-обёрток!**

❌ НЕПРАВИЛЬНО:
```json
{"text": "...", "insights": [...]}
```

✅ ПРАВИЛЬНО:
{"text": "...", "insights": [...]}

## ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА:

{
  "text": "Текстовое описание результатов анализа. Ключевые выводы, инсайты и пояснения.",
  "insights": [
    {
      "finding": "Бренд 'Apple' лидирует по выручке с долей 35%",
      "confidence": 0.92,
      "column_refs": ["brand", "salesAmount"],
      "importance": "high"
    }
  ],
  "recommendations": [
    {
      "action": "Агрегировать данные по бренду: сумма выручки и количество продаж",
      "columns": ["brand", "salesAmount"],
      "rationale": "Выявить топ-бренды по выручке",
      "type": "aggregation",
      "relevance": 0.85,
      "priority": "high",
      "confidence": 0.85
    },
    {
      "action": "Отфильтровать товары с ценой > 1000",
      "columns": ["price"],
      "rationale": "Анализ премиум-сегмента",
      "type": "filter",
      "relevance": 0.7,
      "priority": "medium",
      "confidence": 0.8
    },
    {
      "action": "Добавить столбец average_price = salesAmount / salesCount",
      "columns": ["salesAmount", "salesCount"],
      "rationale": "Рассчитать среднюю цену продажи",
      "type": "calculation",
      "relevance": 0.9,
      "priority": "medium",
      "confidence": 0.9
    }
  ],
  "data_quality_issues": [
    {"column": "date", "issue": "15% пропущенных значений", "severity": "medium"}
  ],
  "tables": [],
  "confidence": 0.85
}

## ПРАВИЛА:

1. **text** — ОБЯЗАТЕЛЬНО. Общее описание анализа в Markdown:
   - Краткое резюме данных
   - Ключевые выводы
   - Рекомендации по следующим шагам

2. **insights** — ОБЯЗАТЕЛЬНО. Массив аналитических выводов:
   - finding: конкретный вывод
   - confidence: уверенность (0-1)
   - column_refs: ссылки на реальные колонки!
   - importance: high/medium/low

3. **recommendations** — ОБЯЗАТЕЛЬНО. Массив рекомендаций (минимум 5-8 штук):
   - action: что сделать (краткое описание)
   - columns: какие колонки использовать
   - rationale: почему это полезно
   - type: тип трансформации — одно из:
     • filter — фильтрация данных (WHERE, отбор строк)
     • aggregation — группировка и агрегация (GROUP BY, сумма, среднее, COUNT)
     • calculation — вычисляемые столбцы (новые колонки, формулы)
     • sorting — сортировка и ранжирование (ORDER BY, TOP N, RANK)
     • cleaning — очистка данных (NULL, дубликаты, форматирование)
     • merge — объединение данных (JOIN таблиц)
     • reshape — изменение структуры (PIVOT, транспонирование)
   - relevance: актуальность рекомендации (0.0-1.0):
     • 0.9-1.0 — критически важная операция
     • 0.7-0.9 — очень полезная операция
     • 0.5-0.7 — полезная опция
     • 0.3-0.5 — возможная альтернатива
     • 0.0-0.3 — низкоприоритетная
   - priority: high/medium/low (legacy)
   - confidence: уверенность (0-1, legacy)
   - ВАЖНО: Генерируй РАЗНООБРАЗНЫЕ рекомендации, покрывая разные типы трансформаций

4. **data_quality_issues** — Проблемы качества данных (может быть пустым)

5. **tables** — Дополнительные таблицы (обычно пустой, если не нужны агрегации)

## РЕЖИМ АНАЛИЗА:

Если в задаче есть секция **AVAILABLE INPUT DATA** или **STRUCTURED DATA**:
- Тебе предоставлены РЕАЛЬНЫЕ данные (названия колонок, типы, sample data)
- КРИТИЧЕСКИ ВАЖНО: используй ТОЧНЫЕ названия колонок
- НЕ придумывай обобщённые рекомендации ("средняя цена", "количество продаж")
- ВСЕГДА ссылайся на КОНКРЕТНЫЕ колонки, которые видишь в данных

Пример ПРАВИЛЬНОГО анализа:
Input: Table 'sales' with columns: price, salesCount, salesAmount, brand, title
Ответ text должен содержать:
"На основе анализа таблицы 'sales' (4 колонки, 150 строк) предлагаю:
1. **Анализ по брендам**: используя колонку 'brand', посчитать топ-10 брендов по 'salesAmount'
2. **Ценовой анализ**: распределение 'price', выявление outliers
3. **Корреляция**: связь между 'price' и 'salesCount'
..."

Пример НЕПРАВИЛЬНОГО анализа (обобщённые названия):
"Предлагаю посчитать среднюю цену товара, количество продаж по категориям..."
❌ Нет ссылок на реальные колонки! Откуда "категории", если в данных только brand?

## РЕЖИМ АНАЛИЗА ДАННЫХ ОТ STRUCTURIZERАГЕНТА:

Если в задаче есть секция **STRUCTURED DATA** (от StructurizerAgent):
- Тебе предоставлены УЖЕ извлечённые таблицы и сущности
- Проанализируй структуру данных
- Сформируй insights и recommendations
- НЕ нужно заново извлекать структуру — она уже есть!

## ПРИМЕРЫ:

### Задача: Анализ структурированных данных от StructurizerAgent
Input (STRUCTURED DATA):
```json
{
  "tables": [{"name": "frameworks", "columns": [...], "rows": [...]}],
  "entities": [{"type": "company", "value": "GitHub"}],
  "extraction_confidence": 0.9
}
```

Ответ:
{
  "text": "## Анализ данных о фреймворках\\n\\nНа основе структурированных данных (1 таблица, 5 строк):\\n\\n### Ключевые выводы:\\n- Django лидирует по GitHub stars\\n- Flask и FastAPI конкурируют за второе место",
  "insights": [
    {"finding": "Django лидирует с 71k stars", "confidence": 0.95, "column_refs": ["Framework", "Stars"], "importance": "high"},
    {"finding": "Все фреймворки активно развиваются", "confidence": 0.8, "column_refs": ["Stars"], "importance": "medium"}
  ],
  "recommendations": [
    {"action": "Bar chart сравнения по stars", "columns": ["Framework", "Stars"], "rationale": "Визуальное ранжирование", "priority": "high"}
  ],
  "data_quality_issues": [],
  "tables": [],
  "confidence": 0.9
}

### Задача: Анализ данных ContentNode (discussion mode)
Input (AVAILABLE INPUT DATA):
- Table 'sales': columns [price, salesCount, salesAmount, brand, title], 150 rows
- Sample: price=100, salesCount=5, salesAmount=500, brand="Apple", title="iPhone 12"

Ответ:
{
  "text": "## Рекомендации по анализу данных 'sales'\\n\\n**Доступные данные:** 150 товаров, 5 колонок\\n\\n### Предлагаемые анализы:\\n\\n1. **По брендам** — топ-10 по 'salesAmount'\\n2. **Ценовой** — распределение 'price', outliers\\n3. **Корреляция** — 'price' vs 'salesCount'",
  "insights": [
    {"finding": "5 колонок доступны для анализа: price, salesCount, salesAmount, brand, title", "confidence": 1.0, "column_refs": ["price", "salesCount", "salesAmount", "brand", "title"], "importance": "high"}
  ],
  "recommendations": [
    {"action": "Группировка по бренду: топ-10 по выручке", "columns": ["brand", "salesAmount"], "rationale": "Определить лидеров рынка", "priority": "high", "confidence": 0.9},
    {"action": "Фильтрация дорогих товаров (price > median)", "columns": ["price"], "rationale": "Анализ премиум-сегмента", "priority": "medium", "confidence": 0.85},
    {"action": "Сортировка по salesCount (убывание)", "columns": ["salesCount"], "rationale": "Найти популярные товары", "priority": "medium", "confidence": 0.8},
    {"action": "Добавить столбец revenue_per_sale = salesAmount / salesCount", "columns": ["salesAmount", "salesCount"], "rationale": "Рассчитать среднюю цену продажи", "priority": "high", "confidence": 0.9},
    {"action": "Удалить строки с пустым brand", "columns": ["brand"], "rationale": "Очистка данных от неполных записей", "priority": "low", "confidence": 0.75},
    {"action": "Группировка price по диапазонам: <100, 100-500, >500", "columns": ["price"], "rationale": "Сегментация по ценовым категориям", "priority": "medium", "confidence": 0.8}
  ],
  "data_quality_issues": [],
  "tables": [],
  "confidence": 0.95
}

### Задача: Данные не найдены
Ответ:
{
  "text": "## Результаты анализа\\n\\nНе удалось провести анализ: входные данные отсутствуют или некорректны.",
  "insights": [],
  "recommendations": [],
  "data_quality_issues": [{"column": "N/A", "issue": "Входные данные отсутствуют", "severity": "critical"}],
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
    ):
        """
        Обрабатывает задачу анализа. Возвращает AgentPayload (V2).
        
        V2: Возвращает AgentPayload(narrative=, findings=[])
        """
        try:
            description = task.get("description", "")
            if not description:
                return self._error_payload("Task description is required")
            
            self.logger.info(f"🔍 Processing task: {description[:100]}...")
            
            # Изменение #2: agent_results — list (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
            session_id = context.get("session_id") if context else None
            agent_results = (context or {}).get("agent_results", [])
            
            if session_id and not agent_results:
                all_results = await self.get_all_previous_results(session_id)
                if all_results:
                    # Redis может вернуть dict — конвертируем
                    if isinstance(all_results, dict):
                        agent_results = list(all_results.values())
                    else:
                        agent_results = all_results
                    self.logger.info(f"📦 Loaded {len(agent_results)} results from Redis")
            
            # Изменение #5/#7: извлекаем input_data из контекста в отдельный метод, не мутируем task
            input_data_for_prompt = task.get("input_data")
            if not input_data_for_prompt and context:
                input_data_for_prompt = self._input_data_from_context(context)
                if input_data_for_prompt:
                    self.logger.info(
                        f"📊 Enriched from context: {len(input_data_for_prompt)} table(s)"
                    )

            # Формируем prompt
            task_for_prompt = {**task, "input_data": input_data_for_prompt} if input_data_for_prompt else task
            task_prompt = self._build_universal_prompt(task_for_prompt, agent_results)
            
            # Выбор system prompt: специализированный для widget_suggestions,
            # стандартный для остального
            controller = (context or {}).get("controller", "")
            is_widget_mode = controller == "widget_suggestions"
            effective_prompt = WIDGET_SUGGESTIONS_SYSTEM_PROMPT if is_widget_mode else self.system_prompt
            effective_max_tokens = 3000 if is_widget_mode else 2000
            
            if is_widget_mode:
                self.logger.info("🎨 Using WIDGET_SUGGESTIONS system prompt for visualization recommendations")
            
            messages = [
                {"role": "system", "content": effective_prompt},
                {"role": "user", "content": task_prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=effective_max_tokens
            )
            
            # Парсим результат
            raw = self._parse_generic_response(response)
            
            # V2: Конвертируем в AgentPayload
            narrative_text = raw.get("text") or raw.get("message", "")
            
            # Конвертируем insights в Finding
            findings: List[Finding] = []
            for ins in raw.get("insights", []):
                if isinstance(ins, dict):
                    findings.append(Finding(
                        type="insight",
                        text=ins.get("finding", ""),
                        severity=self._map_importance(ins.get("importance", "medium")),
                        confidence=ins.get("confidence"),
                        refs=ins.get("column_refs", []),
                    ))
            
            for rec in raw.get("recommendations", []):
                if isinstance(rec, dict):
                    # Confidence: берём из LLM или выводим из priority
                    priority = rec.get("priority", "medium")
                    conf = rec.get("confidence")
                    if conf is None:
                        conf = {"critical": 0.95, "high": 0.85, "medium": 0.7, "low": 0.5}.get(priority, 0.7)
                    
                    # Маппинг полей: используем action как основное описание,
                    # а rationale как дополнительное обоснование
                    action_text = rec.get("action", "")
                    rationale_text = rec.get("rationale", "")
                    
                    # Fallback: если action пустой, используем rationale
                    main_text = action_text or rationale_text or "Рекомендация без описания"
                    
                    # DEBUG: логируем если есть проблемы с данными
                    if not action_text:
                        self.logger.warning(f"⚠️ Recommendation without 'action' field: {rec}")
                    
                    # Собираем metadata: transformation type, relevance, prompt, category
                    metadata = {}
                    if "type" in rec:
                        metadata["type"] = rec["type"]  # filter/aggregation/bar_chart/etc
                    if "relevance" in rec:
                        metadata["relevance"] = rec["relevance"]  # 0.0-1.0
                    if "category" in rec:
                        metadata["category"] = rec["category"]  # chart/table/kpi/map
                    # Добавляем prompt для UI (что отправить при клике)
                    # Приоритет: явный prompt от LLM > action > rationale
                    metadata["prompt"] = rec.get("prompt") or action_text or rationale_text
                    
                    findings.append(Finding(
                        type="recommendation",
                        text=main_text,
                        severity=self._map_importance(priority),
                        confidence=conf,
                        refs=rec.get("columns", []),
                        action=rationale_text if action_text else None,
                        metadata=metadata if metadata else None,
                    ))
            
            for dq in raw.get("data_quality_issues", []):
                if isinstance(dq, dict):
                    findings.append(Finding(
                        type="data_quality_issue",
                        text=f"{dq.get('column', 'N/A')}: {dq.get('issue', '')}",
                        severity=dq.get("severity", "medium"),  # type: ignore[arg-type]
                    ))
            
            self.logger.info(f"✅ Analysis done: {len(findings)} findings")
            
            # Если narrative_text пустой, но есть findings — построить narrative из них.
            # Это критически важно: без narrative reporter/controller не смогут
            # сформировать ответ пользователю.
            if not narrative_text and findings:
                parts = []
                for f in findings[:10]:
                    prefix = {"insight": "📊", "recommendation": "💡", "data_quality_issue": "⚠️"}.get(f.type, "•")
                    parts.append(f"{prefix} {f.text}")
                narrative_text = "## Результаты анализа\n\n" + "\n".join(parts)
                self.logger.info(f"📝 Built narrative from {len(parts)} findings (LLM returned no text field)")
            
            return self._success_payload(
                narrative=Narrative(text=narrative_text, format="markdown"),
                findings=findings,
                metadata={"confidence": raw.get("confidence", 0.0)},
            )
            
        except Exception as e:
            self.logger.error(f"Error processing task: {e}", exc_info=True)
            return self._error_payload(str(e))
    
    @staticmethod
    def _map_importance(value: str) -> str:
        """Маппинг importance/priority в severity для Finding."""
        mapping = {"high": "high", "medium": "medium", "low": "low"}
        return mapping.get(value, "medium")  # type: ignore[return-value]
    
    # ══════════════════════════════════════════════════════════════════
    #  Helper: extract input_data from context
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _input_data_from_context(context: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Извлекает input_data из context.input_data_preview.
        
        Изменение #5: выделено в отдельный метод, чтобы не мутировать task.
        """
        input_data_preview = context.get("input_data_preview")
        if not input_data_preview:
            return None
        result: List[Dict[str, Any]] = []
        for table_name, info in input_data_preview.items():
            columns_raw = info.get("columns", [])
            columns = []
            for c in columns_raw:
                if isinstance(c, dict):
                    columns.append(c)
                else:
                    columns.append({"name": str(c), "type": "string"})
            result.append({
                "node_name": table_name,
                "tables": [{
                    "name": table_name,
                    "columns": columns,
                    "row_count": info.get("row_count", 0),
                    "sample_rows": info.get("sample_rows", []),
                }],
            })
        return result or None

    def _build_universal_prompt(
        self,
        task: Dict[str, Any],
        agent_results: List[Dict[str, Any]]
    ) -> str:
        """
        Формирует универсальный prompt для любой задачи.
        """
        description = task.get("description", "")
        
        # Собираем все параметры задачи (кроме description, input_data, structured_data - обрабатываем отдельно)
        task_params = {k: v for k, v in task.items() if k not in ["description", "input_data", "structured_data"]}
        
        prompt_parts = [
            "**TASK**:",
            description,
            ""
        ]
        
        # Специальная обработка для input_data (данные из ContentNodes)
        if "input_data" in task:
            input_data = task["input_data"]
            if input_data and isinstance(input_data, list):
                prompt_parts.append("**AVAILABLE INPUT DATA** (from ContentNodes):")
                for node_info in input_data:
                    node_name = node_info.get("node_name", "unknown")
                    prompt_parts.append(f"\n📊 Node: {node_name}")
                    
                    # Tables with sample data
                    tables = node_info.get("tables", [])
                    if tables:
                        for table in tables:
                            table_name = table.get("name", "таблица")
                            columns = table.get("columns", [])
                            row_count = table.get("row_count", 0)
                            sample_rows = table.get("sample_rows", [])
                            
                            col_names = [c["name"] for c in columns]
                            
                            prompt_parts.append(f"  • Table '{table_name}':")
                            prompt_parts.append(f"    - Columns ({len(columns)}): {', '.join(col_names)}")
                            prompt_parts.append(f"    - Total rows: {row_count}")
                            
                            if sample_rows:
                                prompt_parts.append(f"    - Sample data (first {len(sample_rows)} rows):")
                                for i, row in enumerate(sample_rows, 1):
                                    # Форматируем строку для читаемости - показываем ВСЕ колонки
                                    if isinstance(row, dict):
                                        row_items = [f"{k}={repr(v)}" for k, v in row.items()]
                                        row_str = ", ".join(row_items)
                                        prompt_parts.append(f"      Row {i}: {row_str}")
                                    else:
                                        # Fallback если это array
                                        prompt_parts.append(f"      Row {i}: {row}")
                    
                    # Text preview
                    if node_info.get("text_preview"):
                        text_len = node_info.get("text_length", 0)
                        prompt_parts.append(f"  • Text content: {text_len} chars")
                        prompt_parts.append(f"    Preview: {node_info['text_preview']}...")
                
                prompt_parts.append("")
        
        # Специальная обработка для structured_data (данные от StructurizerAgent)
        if "structured_data" in task:
            structured = task["structured_data"]
            if structured and isinstance(structured, dict):
                prompt_parts.append("**STRUCTURED DATA** (extracted by StructurizerAgent):")
                
                # Confidence извлечения структуры
                extraction_confidence = structured.get("extraction_confidence", 0)
                prompt_parts.append(f"Extraction confidence: {extraction_confidence}")
                prompt_parts.append("")
                
                # Tables
                tables = structured.get("tables", [])
                if tables:
                    prompt_parts.append(f"📊 EXTRACTED TABLES ({len(tables)}):")
                    for table in tables:
                        table_name = table.get("name", "таблица")
                        columns = table.get("columns", [])
                        rows = table.get("rows", [])
                        
                        prompt_parts.append(f"\n  • Table '{table_name}':")
                        prompt_parts.append(f"    - Columns ({len(columns)}): {', '.join(columns)}")
                        prompt_parts.append(f"    - Rows: {len(rows)}")
                        
                        if rows:
                            # Показываем первые 10 строк для анализа
                            sample_size = min(10, len(rows))
                            prompt_parts.append(f"    - Sample data (first {sample_size} rows):")
                            for i, row in enumerate(rows[:sample_size], 1):
                                if isinstance(row, dict):
                                    # Убираем служебные поля типа row_id
                                    row_data = {k: v for k, v in row.items() if k != "row_id"}
                                    row_items = [f"{k}={repr(v)}" for k, v in row_data.items()]
                                    row_str = ", ".join(row_items)
                                    prompt_parts.append(f"      Row {i}: {row_str}")
                                else:
                                    prompt_parts.append(f"      Row {i}: {row}")
                    prompt_parts.append("")
                
                # Entities
                entities = structured.get("entities", [])
                if entities:
                    prompt_parts.append(f"🏷️ EXTRACTED ENTITIES ({len(entities)}):")
                    for entity in entities[:20]:  # Лимит на 20 сущностей
                        entity_name = entity.get("name", "")
                        entity_type = entity.get("type", "")
                        prompt_parts.append(f"  • {entity_name} ({entity_type})")
                    if len(entities) > 20:
                        prompt_parts.append(f"  ... and {len(entities) - 20} more entities")
                    prompt_parts.append("")
                
                # Key-value pairs
                key_values = structured.get("key_value_pairs", {})
                if key_values:
                    prompt_parts.append(f"🔑 KEY-VALUE PAIRS ({len(key_values)}):")
                    for key, value in list(key_values.items())[:30]:  # Лимит на 30 пар
                        prompt_parts.append(f"  • {key}: {value}")
                    if len(key_values) > 30:
                        prompt_parts.append(f"  ... and {len(key_values) - 30} more pairs")
                    prompt_parts.append("")
                
                prompt_parts.append("")
        
        # Добавляем остальные параметры задачи если есть
        if task_params:
            prompt_parts.append("**TASK PARAMETERS**:")
            prompt_parts.append(json.dumps(task_params, indent=2, ensure_ascii=False))
            prompt_parts.append("")
        
        # Добавляем результаты предыдущих шагов если есть
        # Изменение #2: agent_results — list
        if agent_results:
            prompt_parts.append("**PREVIOUS RESULTS** (from other agents):")
            for result in agent_results:
                if not isinstance(result, dict):
                    continue
                agent_name = result.get("agent", "unknown")
                prompt_parts.append(f"\n--- {agent_name.upper()} ---")
                
                # V2: AgentPayload — десериализованный dict
                if isinstance(result, dict) and result.get("agent"):
                    # sources — контент страниц (discovery/research)
                    sources = result.get("sources", [])
                    fetched = [s for s in sources if isinstance(s, dict) and s.get("fetched")]
                    if fetched:
                        prompt_parts.append(f"Sources fetched: {len(fetched)}")
                        for i, src in enumerate(fetched, 1):
                            prompt_parts.append(f"PAGE {i}:")
                            prompt_parts.append(f"URL: {src.get('url', 'N/A')}")
                            prompt_parts.append(f"Title: {src.get('title', 'N/A')}")
                            content = src.get("content", "")
                            if len(content) > 5000:
                                prompt_parts.append(f"Content (first 5000 chars): {content[:5000]}...")
                            else:
                                prompt_parts.append(f"Content: {content}")
                            prompt_parts.append("")
                    
                    # tables — структурированные данные (structurizer)
                    tables = result.get("tables", [])
                    if tables:
                        prompt_parts.append(f"Tables: {len(tables)}")
                        for tbl in tables:
                            if isinstance(tbl, dict):
                                tbl_name = tbl.get("name", "без названия")
                                cols = tbl.get("columns", [])
                                rows = tbl.get("rows", [])
                                col_names = [c["name"] for c in cols]
                                prompt_parts.append(f"  Table '{tbl_name}': columns={col_names}, rows={len(rows)}")
                                for ri, row in enumerate(rows[:10], 1):
                                    prompt_parts.append(f"    Row {ri}: {row}")
                        prompt_parts.append("")
                    
                    # narrative — текстовый вывод
                    narrative = result.get("narrative")
                    if isinstance(narrative, dict) and narrative.get("text"):
                        prompt_parts.append(f"Summary: {narrative['text'][:2000]}")
                        prompt_parts.append("")
                    
                    # findings — выводы (от другого analyst)
                    findings = result.get("findings", [])
                    if findings:
                        prompt_parts.append(f"Findings ({len(findings)}):")
                        for f in findings[:20]:
                            if isinstance(f, dict):
                                prompt_parts.append(f"  - [{f.get('type','')}] {f.get('text','')}")
                        prompt_parts.append("")
                    continue
                
                # V1 fallback: researcher pages
                if isinstance(result, dict):
                    pages = result.get("pages", [])
                    if pages:
                        prompt_parts.append(f"Pages fetched: {len(pages)}")
                        for i, page in enumerate(pages, 1):
                            prompt_parts.append(f"PAGE {i}:")
                            prompt_parts.append(f"URL: {page.get('url', 'N/A')}")
                            prompt_parts.append(f"Title: {page.get('title', 'N/A')}")
                            content = page.get('content', '')
                            if len(content) > 5000:
                                prompt_parts.append(f"Content (first 5000 chars): {content[:5000]}...")
                            else:
                                prompt_parts.append(f"Content: {content}")
                            prompt_parts.append("")
                        continue
                
                # V1 fallback: generic
                result_str = json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else str(result)
                if len(result_str) > 2000:
                    prompt_parts.append(result_str[:2000] + "... (truncated)")
                else:
                    prompt_parts.append(result_str)
            prompt_parts.append("")
        
        # Специальные инструкции в зависимости от типа задачи
        if "input_data" in task and task["input_data"]:
            # ANALYSIS MODE - анализ существующих данных
            prompt_parts.extend([
                "**INSTRUCTIONS FOR ANALYSIS MODE**:",
                "🚨 CRITICAL: You have REAL data with specific column names above.",
                "",
                "1. READ the 'AVAILABLE INPUT DATA' section carefully",
                "2. IDENTIFY exact column names from the provided tables",
                "3. In your recommendations, ALWAYS reference SPECIFIC column names",
                "4. DO NOT use generic terms like 'price column', 'sales data' - use EXACT names",
                "5. Base your analysis on ACTUAL columns you see in the data",
                "6. If sample data is provided, reference actual values you see",
                "",
                "Example GOOD response:",
                "\"Для анализа таблицы 'sales' (колонки: price, salesCount, brand):",
                "1. Топ-10 брендов по колонке 'salesCount'",
                "2. Средняя 'price' по брендам из колонки 'brand'\"",
                "",
                "Example BAD response (DO NOT DO THIS):",
                "\"Предлагаю посчитать среднюю цену товара по категориям\"",
                "❌ No mention of actual column names! No 'категории' column exists!",
                "",
                "Return ONLY valid JSON with 'text' and 'tables' fields."
            ])
        else:
            # RESEARCH MODE - извлечение данных из текста
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
    
    @staticmethod
    def _fix_json_escapes(text: str) -> str:
        """Fix invalid backslash escapes from GigaChat (e.g. \d, \s, \w)."""
        import re as _re
        # Replace \X where X is NOT a valid JSON escape char (" \\ / b f n r t u)
        return _re.sub(r'\\([^"\\\\bfnrtu/])', r'\\\\\1', text)

    def _parse_generic_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ LLM в универсальном формате.
        Поддерживает: чистый JSON, JSON в markdown блоках, plain text.
        Автоматически исправляет невалидные escape-последовательности от GigaChat.
        """
        try:
            import re
            
            # 1. Проверяем markdown блок кода ```json ... ```
            markdown_json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if markdown_json_match:
                raw = markdown_json_match.group(1)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return json.loads(self._fix_json_escapes(raw))
            
            # 2. Проверяем markdown блок без языка ``` ... ```
            markdown_match = re.search(r'```\s*(\{.*?\})\s*```', response, re.DOTALL)
            if markdown_match:
                raw = markdown_match.group(1)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return json.loads(self._fix_json_escapes(raw))
            
            # 3. Ищем чистый JSON блок (без markdown)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                raw = json_match.group()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return json.loads(self._fix_json_escapes(raw))
            
            # 4. Если JSON не найден, возвращаем как message
            return {
                "message": response.strip()
            }
            
        except json.JSONDecodeError as e:
            # Если не удалось распарсить даже после fix, возвращаем как текст
            self.logger.warning(f"Failed to parse JSON from response: {e}")
            return {
                "message": response.strip()
            }

