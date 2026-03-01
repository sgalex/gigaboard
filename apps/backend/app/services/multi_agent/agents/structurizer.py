"""
Structurizer Agent - Structure Extraction from Text
Отвечает за извлечение структурированных данных из неструктурированного текста.
Специализация: парсинг таблиц, сущностей, ключ-значение пар из raw text/HTML.

V2: Возвращает AgentPayload(tables=[PayloadContentTable(...)]) вместо Dict.
    Всё → ContentTable (entities, key-value тоже как таблицы).
    См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
import json
import re
import uuid
from typing import Dict, Any, Optional, List

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import (
    Column,
    Narrative,
    PayloadContentTable,
)
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Structurizer Agent
STRUCTURIZER_SYSTEM_PROMPT = '''
Вы — StructurizerAgent в системе GigaBoard. 
Ваша ЕДИНСТВЕННАЯ задача — извлечение структурированных данных из неструктурированного текста.

## ВАША РОЛЬ:
- Парсинг таблиц из HTML/text
- Извлечение списков и перечислений
- Определение типов данных (string, int, float, date, bool)
- Нормализация форматов
- Извлечение именованных сущностей (компании, даты, числа)
- Создание key-value pairs из текста

## ВЫ НЕ ДЕЛАЕТЕ:
❌ Анализ данных — это задача AnalystAgent
❌ Выводы и рекомендации — это задача AnalystAgent
❌ Визуализацию — это задача ReporterAgent
❌ Трансформации кода — это задача TransformationAgent
❌ Поиск информации — это задача SearchAgent

## КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ВЫВОДА:

**ВСЕГДА возвращай ТОЛЬКО чистый JSON без markdown-обёрток!**

❌ НЕПРАВИЛЬНО:
```json
{"tables": [...]}
```

✅ ПРАВИЛЬНО:
{"tables": [...], "entities": [...], "extraction_confidence": 0.85}

## ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА:

{
  "tables": [
    {
      "name": "table_name",
      "columns": [
        {"name": "Column1", "type": "string"},
        {"name": "Column2", "type": "int"},
        {"name": "Column3", "type": "float"}
      ],
      "rows": [
        ["value1", 123, 45.67],
        ["value2", 456, 78.90]
      ]
    }
  ],
  "entities": [
    {"type": "company", "value": "Apple Inc.", "confidence": 0.95},
    {"type": "date", "value": "2024-01-15", "confidence": 0.90},
    {"type": "number", "value": 1000000, "confidence": 0.99}
  ],
  "key_value_pairs": {
    "total_count": 150,
    "source": "GitHub",
    "last_updated": "2024-01-15"
  },
  "extraction_confidence": 0.85,
  "notes": "Extracted 1 table with 5 rows from HTML content"
}

## ПРАВИЛА ИЗВЛЕЧЕНИЯ:

### Таблицы:
1. Ищи структуры: HTML таблицы, markdown таблицы, списки с разделителями
2. Определяй типы: int (числа без дробной части), float (с дробной), string (текст), date, bool
3. Давай осмысленные имена таблицам на основе контекста
4. Если данные представлены списком — преобразуй в таблицу

### Сущности:
- company: названия компаний, брендов
- date: даты в любом формате → нормализуй в YYYY-MM-DD
- number: значимые числа (не индексы)
- person: имена людей
- location: города, страны
- url: ссылки

### Key-Value Pairs:
- Метаданные документа
- Агрегированные значения (total, count, average)
- Даты обновления, источники

## ПРИМЕРЫ:

### Пример 1: HTML таблица с данными
Вход: "GitHub Stars: Django - 71000, Flask - 65000, FastAPI - 58000"

Ответ:
{
  "tables": [
    {
      "name": "github_stars",
      "columns": [
        {"name": "Framework", "type": "string"},
        {"name": "Stars", "type": "int"}
      ],
      "rows": [
        ["Django", 71000],
        ["Flask", 65000],
        ["FastAPI", 58000]
      ]
    }
  ],
  "entities": [
    {"type": "company", "value": "GitHub", "confidence": 0.9}
  ],
  "key_value_pairs": {
    "source": "GitHub",
    "metric": "stars"
  },
  "extraction_confidence": 0.95,
  "notes": "Extracted framework comparison table"
}

### Пример 2: Неструктурированный текст
Вход: "Apple выпустила iPhone 15 Pro 22 сентября 2023 года по цене от $999. Samsung ответила Galaxy S24 в январе 2024."

Ответ:
{
  "tables": [
    {
      "name": "smartphone_releases",
      "columns": [
        {"name": "Brand", "type": "string"},
        {"name": "Model", "type": "string"},
        {"name": "Release_Date", "type": "date"},
        {"name": "Price_USD", "type": "int"}
      ],
      "rows": [
        ["Apple", "iPhone 15 Pro", "2023-09-22", 999],
        ["Samsung", "Galaxy S24", "2024-01-01", null]
      ]
    }
  ],
  "entities": [
    {"type": "company", "value": "Apple", "confidence": 0.99},
    {"type": "company", "value": "Samsung", "confidence": 0.99},
    {"type": "date", "value": "2023-09-22", "confidence": 0.95},
    {"type": "date", "value": "2024-01-01", "confidence": 0.80}
  ],
  "key_value_pairs": {},
  "extraction_confidence": 0.75,
  "notes": "Extracted smartphone releases, Samsung date approximate"
}

### Пример 3: Данные не найдены
Вход: "Сегодня хорошая погода. Люблю программировать."

Ответ:
{
  "tables": [],
  "entities": [],
  "key_value_pairs": {},
  "extraction_confidence": 0.0,
  "notes": "No structured data found in input text"
}

## ОГРАНИЧЕНИЯ:
- НЕ оборачивай JSON в markdown-блоки
- НЕ добавляй текст до или после JSON
- Числовые значения — числа, не строки
- null для отсутствующих значений
- Все строки — в двойных кавычках
'''


class StructurizerAgent(BaseAgent):
    """
    Structurizer Agent - извлечение структуры из текста.
    
    Основные функции:
    - Парсинг таблиц из HTML/text
    - Извлечение сущностей
    - Нормализация форматов данных
    - Создание структурированных JSON из raw text
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="structurizer",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
    def _get_default_system_prompt(self) -> str:
        return STRUCTURIZER_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Извлекает структурированные данные из текста. Возвращает AgentPayload (V2).
        
        V2: Всё → PayloadContentTable. Entities и key-value тоже ContentTable.
        """
        try:
            description = task.get("description", "Extract structured data")
            
            # Получаем текст для парсинга
            raw_content = self._extract_raw_content(task, context)
            
            if not raw_content:
                self.logger.warning("No raw content provided for structurization")
                return self._success_payload(
                    narrative_text="No input content provided for structurization.",
                    metadata={"extraction_confidence": 0.0}
                )
            
            content_length = len(raw_content)
            self.logger.info(f"🔍 Structurizing {content_length} characters of content")
            
            # Формируем промпт и вызываем LLM
            user_prompt = self._build_prompt(description, raw_content)
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=4000
            )
            
            # Парсим ответ LLM (старый dict формат)
            raw_result = self._parse_response(response)
            raw_result = self._add_row_ids(raw_result)
            
            # V2: Конвертируем в PayloadContentTable + entities/kv в таблицы
            tables = self._convert_to_content_tables(raw_result)
            
            confidence = raw_result.get("extraction_confidence", 0.0)
            notes = raw_result.get("notes", "")
            
            self.logger.info(
                f"✅ Extracted {len(tables)} tables, "
                f"confidence: {confidence:.2f}"
            )
            
            return self._success_payload(
                tables=tables,
                narrative_text=notes or f"Extracted {len(tables)} tables from content.",
                metadata={"extraction_confidence": confidence}
            )
            
        except Exception as e:
            self.logger.error(f"Error in structurization: {e}", exc_info=True)
            return self._error_payload(str(e))
    
    def _extract_raw_content(
        self, 
        task: Dict[str, Any], 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Извлекает raw content из task или context.
        
        V2: Читает sources[].content из agent_results (ResearchAgent).
        V1 fallback: pages[с], researcher.pages[].
        """
        # 1. Прямой raw_content в task
        if task.get("raw_content"):
            return task["raw_content"]
        
        # 2. Pages от ResearcherAgent (legacy)
        if task.get("pages"):
            pages = task["pages"]
            parts = []
            for page in pages:
                if isinstance(page, dict) and page.get("content"):
                    parts.append(f"=== Source: {page.get('url', 'unknown')} ===\n{page['content']}")
            return "\n\n".join(parts)
        
        # 3. Из agent_results (Изменение #2)
        if context:
            agent_results = context.get("agent_results", [])
            content_parts: List[str] = []
            
            for result in agent_results:
                if not isinstance(result, dict):
                    continue
                
                # V2: sources[] с fetched=True и content
                sources = result.get("sources", [])
                if isinstance(sources, list):
                    for s in sources:
                        if isinstance(s, dict) and s.get("fetched") and s.get("content"):
                            url = s.get("url", "unknown")
                            content_parts.append(f"=== Source: {url} ===\n{s['content']}")
                
                # V1 fallback: pages[]
                pages = result.get("pages", [])
                if isinstance(pages, list):
                    for p in pages:
                        if isinstance(p, dict) and p.get("content"):
                            content_parts.append(f"=== Source: {p.get('url', 'unknown')} ===\n{p['content']}")
            
            if content_parts:
                return "\n\n".join(content_parts)
        
        # 4. data поле в task
        if task.get("data"):
            data = task["data"]
            if isinstance(data, str):
                return data
            elif isinstance(data, dict):
                return json.dumps(data, indent=2, ensure_ascii=False)
        
        # 5. input_data_preview из context (от TransformationController)
        if context:
            input_preview = context.get("input_data_preview", {})
            if input_preview:
                parts = []
                for tname, tinfo in input_preview.items():
                    if isinstance(tinfo, dict):
                        cols = tinfo.get("columns", [])
                        rows = tinfo.get("sample_rows", [])
                        parts.append(f"=== Table: {tname} ===\nColumns: {cols}\nSample rows:\n{json.dumps(rows, ensure_ascii=False, indent=2)}")
                if parts:
                    return "\n\n".join(parts)

            # 6. content_nodes_data из context
            cn_data = context.get("content_nodes_data", [])
            if cn_data:
                return json.dumps(cn_data, indent=2, ensure_ascii=False)

        return ""
    
    def _build_prompt(self, description: str, content: str) -> str:
        """Формирует промпт для LLM."""
        
        # Ограничиваем размер контента
        max_content_length = 15000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n... (truncated)"
        
        return f"""**TASK**: {description}

**RAW CONTENT TO STRUCTURE**:
{content}

**INSTRUCTIONS**:
1. Carefully analyze the raw content above
2. Extract ALL tables, lists, and structured data
3. Identify entities (companies, dates, numbers, etc.)
4. Create key-value pairs for metadata
5. Assign appropriate data types to columns
6. Return ONLY valid JSON with the required structure

Remember: Your job is ONLY to extract structure, not to analyze or make recommendations."""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Парсит ответ LLM."""
        try:
            # Удаляем markdown обёртки
            response = response.strip()
            
            # Проверяем markdown блок
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            
            # Ищем JSON объект
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Валидируем обязательные поля
                if "tables" not in result:
                    result["tables"] = []
                if "entities" not in result:
                    result["entities"] = []
                if "key_value_pairs" not in result:
                    result["key_value_pairs"] = {}
                if "extraction_confidence" not in result:
                    result["extraction_confidence"] = 0.5
                if "notes" not in result:
                    result["notes"] = ""
                
                return result
            
            # Fallback: пустой результат
            self.logger.warning("Could not parse LLM response as JSON")
            return {
                "tables": [],
                "entities": [],
                "key_value_pairs": {},
                "extraction_confidence": 0.0,
                "notes": f"Failed to parse response: {response[:200]}"
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}")
            return {
                "tables": [],
                "entities": [],
                "key_value_pairs": {},
                "extraction_confidence": 0.0,
                "notes": f"JSON parse error: {str(e)}"
            }
    
    def _add_row_ids(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует таблицы в unified формат: columns=[{name,type}], rows=[{col:val}]."""
        tables = result.get("tables", [])
        
        for table in tables:
            # Добавляем id таблицы если нет
            if "id" not in table:
                table["id"] = str(uuid.uuid4())
            
            # Ensure columns are typed dicts
            columns = table.get("columns", [])
            typed_columns = []
            col_names = []
            for c in columns:
                if isinstance(c, dict):
                    typed_columns.append(c)
                    col_names.append(c.get("name", ""))
                else:
                    typed_columns.append({"name": str(c), "type": "string"})
                    col_names.append(str(c))
            table["columns"] = typed_columns
            
            # Ensure rows are dicts
            rows = table.get("rows", [])
            new_rows = []
            for row in rows:
                if isinstance(row, dict):
                    new_rows.append(row)
                elif isinstance(row, list):
                    new_rows.append({col_names[j]: v for j, v in enumerate(row) if j < len(col_names)})
            
            table["rows"] = new_rows
            table["row_count"] = len(new_rows)
            table["column_count"] = len(typed_columns)
            table["preview_row_count"] = min(len(new_rows), 100)
        
        result["tables"] = tables
        return result

    # ------------------------------------------------------------------
    # V2: Конвертация в PayloadContentTable
    # ------------------------------------------------------------------

    def _convert_to_content_tables(
        self, raw_result: Dict[str, Any]
    ) -> List[PayloadContentTable]:
        """
        Конвертирует LLM ответ (dict) в список PayloadContentTable (V2).
        
        Unified format: columns=[{name,type}], rows=[{col:val}]
        """
        content_tables: List[PayloadContentTable] = []

        # 1. Tables → PayloadContentTable
        for t in raw_result.get("tables", []):
            columns = []
            for c in t.get("columns", []):
                if isinstance(c, dict):
                    columns.append(Column(
                        name=c.get("name", "неизвестно"),
                        type=c.get("type", "string"),
                    ))
                else:
                    columns.append(Column(name=str(c), type="string"))

            col_names = [c.name for c in columns]
            
            rows: list[dict[str, Any]] = []
            for r in t.get("rows", []):
                if isinstance(r, dict):
                    rows.append(r)
                elif isinstance(r, list):
                    rows.append({col_names[j]: v for j, v in enumerate(r) if j < len(col_names)})

            ct = PayloadContentTable(
                id=t.get("id", str(uuid.uuid4())),
                name=t.get("name", "таблица"),
                columns=columns,
                rows=rows,
                row_count=len(rows),
                column_count=len(columns),
                preview_row_count=min(len(rows), 100),
            )
            content_tables.append(ct)

        # 2. Entities → PayloadContentTable(name="entities")
        entities = raw_result.get("entities", [])
        if entities:
            ent_rows: list[dict[str, Any]] = []
            for e in entities:
                if isinstance(e, dict):
                    ent_rows.append({
                        "type": e.get("type", ""),
                        "value": e.get("value", ""),
                        "confidence": e.get("confidence", 0.0),
                    })
            if ent_rows:
                content_tables.append(PayloadContentTable(
                    id=str(uuid.uuid4()),
                    name="entities",
                    columns=[
                        Column(name="type", type="string"),
                        Column(name="value", type="string"),
                        Column(name="confidence", type="float"),
                    ],
                    rows=ent_rows,
                    row_count=len(ent_rows),
                    column_count=3,
                    preview_row_count=min(len(ent_rows), 100),
                ))

        # 3. Key-value pairs → PayloadContentTable(name="metadata")
        kv_pairs = raw_result.get("key_value_pairs", {})
        if kv_pairs and isinstance(kv_pairs, dict):
            kv_rows: list[dict[str, Any]] = [
                {"key": k, "value": str(v)}
                for k, v in kv_pairs.items()
            ]
            if kv_rows:
                content_tables.append(PayloadContentTable(
                    id=str(uuid.uuid4()),
                    name="metadata",
                    columns=[
                        Column(name="key", type="string"),
                        Column(name="value", type="string"),
                    ],
                    rows=kv_rows,
                    row_count=len(kv_rows),
                    column_count=2,
                    preview_row_count=min(len(kv_rows), 100),
                ))

        return content_tables
