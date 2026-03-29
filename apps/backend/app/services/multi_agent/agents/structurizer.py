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
from ..runtime_overrides import ma_int
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import (
    Column,
    Narrative,
    PayloadContentTable,
    ToolRequest,
    AgentPayload,
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

## ЗАПРЕТ YAML И ПСЕВДОКОДА ДЛЯ ТАБЛИЦ (КРИТИЧЕСКИ)

- **Никогда** не оформляй таблицу как YAML (`tables:`, `- columns:`, `- rows:`) и не вставляй такой текст в `notes` вместо JSON.
- Весь табличный результат — только внутри JSON: `"tables": [ { "name", "columns", "rows" } ]`.
- Поле **`rows`** — это JSON-массив **массивов значений** в порядке колонок: `[ ["Строка1 кол1", 10], ["Строка2 кол1", null] ]`.
- Если отдаёшь строку как **объект** (редко), ключи полей должны **точно совпадать** с `"name"` из `columns` (те же символы). Предпочтительно всегда использовать **массивы значений** по порядку колонок — так меньше ошибок.
- **Нельзя** отдавать строки категорий отдельным списком строк в `rows` без массивов — каждая строка таблицы **обязана** быть массивом: `[["Cat A"], ["Cat B"]]` при одной колонке, `[["Cat A", null], ["Cat B", 3]]` при двух.
- Краткое пояснение — только в `notes` (обычный текст), без дублирования таблицы в виде YAML.

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

## ДВУХФАЗНАЯ МОДЕЛЬ ТАБЛИЦ (ОБЯЗАТЕЛЬНО)

Когда из текста или по **задаче пользователя** нужно получить табличные данные (в т.ч. если в документе **нет** готовой HTML/markdown-таблицы, но есть перечень, вложения, разделы с однотипными блоками):

1. **Сначала — схема (структура)**  
   Зафиксируй **имя таблицы** и **полный список колонок** `columns` с типами. Колонки выводи из **семантики задачи** (что пользователь просит извлечь) и из фрагмента текста (какие поля логично различать).  
   Не сокращай число колонок «из удобства» — лучше лишняя колонка с `null`, чем потеря структуры.

2. **Затем — заполнение**  
   Заполни массив `rows`: каждая строка — массив значений **в том же порядке**, что и `columns`. Значения бери из текста по смыслу.

3. **Пустые ячейки**  
   Если для колонки в источнике нет значения — ставь **`null`** (не удаляй колонку, не обрезай строку). Частично заполненная таблица **лучше**, чем отсутствие строк при наличии схемы.

4. **Таблица как артефакт**  
   Если пользователь явно просит «таблицу», «список полей», «сводку по строкам» — в ответе **должна быть хотя бы одна** запись в `tables` с осмысленными `columns`; `rows` могут быть пустым массивом `[]` **только** если в тексте действительно нет ни одной строки данных под эту схему. Если данные есть частично — заполни сколько можешь, остальное `null`.

5. **Не переносить данные только в `notes` или narrative downstream**  
   Итоговые извлекаемые значения для предпросмотра и пайплайна — в **`tables[].rows`**. Текстовое резюме в `notes` — дополнение, не замена строк таблицы.

## ПРАВИЛА ИЗВЛЕЧЕНИЯ:

### Таблицы:
1. Ищи структуры: HTML таблицы, markdown таблицы, списки с разделителями
2. Определяй типы: int (числа без дробной части), float (с дробной), string (текст), date, bool
3. Давай осмысленные имена таблицам на основе контекста
4. Если данные представлены списком — преобразуй в таблицу
5. Если готовой таблицы в тексте нет, но задача однозначно задаёт измерения (столбцы) — **создай таблицу по правилам двухфазной модели выше**

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

### Пример 3: В тексте нет таблицы, но пользователь просит таблицу по смыслу
Задача: «Извлеки перечень ключевых функций в виде таблицы: функция, описание».  
Вход (фрагмент): перечисление функций обычным текстом без pipe-таблицы.

Ответ (схема + заполнение; при невозможности значения — null):
{
  "tables": [
    {
      "name": "key_functions",
      "columns": [
        {"name": "Функция", "type": "string"},
        {"name": "Описание", "type": "string"}
      ],
      "rows": [
        ["Always-on помощник", "краткое описание из текста или null"],
        ["Нативные мессенджеры", null]
      ]
    }
  ],
  "entities": [],
  "key_value_pairs": {},
  "extraction_confidence": 0.75,
  "notes": "Schema fixed from user request; rows filled where text allows"
}

### Пример 4: Данные не найдены (общий текст без запроса на структуру)
Вход: "Сегодня хорошая погода. Люблю программировать." (без задачи на таблицу)

Ответ:
{
  "tables": [],
  "entities": [],
  "key_value_pairs": {},
  "extraction_confidence": 0.0,
  "notes": "No structured data found in input text"
}

**К примеру 4:** если по **TASK** нужна таблица или структурированный список, а во входном тексте есть абзацы,
маркированные списки, HTML/markdown-таблицы или перечисления — **не** своди ответ к пустому `tables: []`
по аналогии с примером 4: извлекай строки в `tables[].rows`; пустые `rows` допустимы только если под колонки
по смыслу задачи нет ни одного факта в тексте.

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
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="structurizer",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router
        
    def _get_default_system_prompt(self) -> str:
        from app.services.multi_agent.tabular_tool_contract import (
            TOOL_MODE_AGENT_SYSTEM_APPENDIX_RU,
        )

        return STRUCTURIZER_SYSTEM_PROMPT + "\n" + TOOL_MODE_AGENT_SYSTEM_APPENDIX_RU

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
            tools_enabled = bool((context or {}).get("tools_enabled")) if context else False
            force_tool_data_access = bool(
                (context or {}).get("force_tool_data_access")
            ) if context else False
            tool_results = (context or {}).get("tool_results", []) if context else []
            tool_request_cache_digest_lines: Optional[List[str]] = None
            if context and isinstance(context.get("tool_request_cache_digest_lines"), list):
                tool_request_cache_digest_lines = context["tool_request_cache_digest_lines"]
            content_node_id = str((context or {}).get("content_node_id") or "").strip()
            if not content_node_id and context and isinstance(context.get("selected_node_ids"), list):
                node_ids = [
                    str(item).strip()
                    for item in context.get("selected_node_ids", [])
                    if str(item).strip()
                ]
                if node_ids:
                    content_node_id = node_ids[0]
            node_ids_for_tools = []
            if context and isinstance(context.get("selected_node_ids"), list):
                for item in context.get("selected_node_ids", []):
                    text = str(item).strip()
                    if text and text not in node_ids_for_tools:
                        node_ids_for_tools.append(text)
            if context and isinstance(context.get("content_node_ids"), list):
                for item in context.get("content_node_ids", []):
                    text = str(item).strip()
                    if text and text not in node_ids_for_tools:
                        node_ids_for_tools.append(text)
            if context and isinstance(context.get("contentNodeIds"), list):
                for item in context.get("contentNodeIds", []):
                    text = str(item).strip()
                    if text and text not in node_ids_for_tools:
                        node_ids_for_tools.append(text)
            if content_node_id and content_node_id not in node_ids_for_tools:
                node_ids_for_tools.insert(0, content_node_id)
            
            if not raw_content:
                if tools_enabled and force_tool_data_access and not tool_results and node_ids_for_tools:
                    return AgentPayload.partial(
                        agent=self.agent_name,
                        tool_requests=[
                            ToolRequest(
                                tool_name="readTableListFromContentNodes",
                                arguments={"nodeIds": node_ids_for_tools},
                                reason="force_tool_data_access: table context is removed from prompt",
                            )
                        ],
                        narrative=Narrative(
                            text="Запрашиваю таблицы через инструменты для структуризации."
                        ),
                        metadata={"tool_mode": "forced_bootstrap"},
                    )
                self.logger.warning("No raw content provided for structurization")
                return self._success_payload(
                    narrative_text="No input content provided for structurization.",
                    metadata={"extraction_confidence": 0.0}
                )
            
            content_length = len(raw_content)
            self.logger.info(f"🔍 Structurizing {content_length} characters of content")

            _research_satellite = (
                str((context or {}).get("controller") or "").strip() == "research"
                and str((context or {}).get("mode") or "").strip() == "research"
            )

            # Формируем промпт и вызываем LLM
            user_prompt = self._build_prompt(
                description,
                raw_content,
                tool_results=tool_results,
                tools_enabled=tools_enabled,
                tool_request_cache_digest_lines=tool_request_cache_digest_lines,
                research_satellite=_research_satellite,
            )
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            _max_tok = (
                ma_int("MULTI_AGENT_STRUCTURIZER_RESEARCH_MAX_TOKENS", 5500)
                if _research_satellite
                else 4000
            )
            response = await self._call_llm(
                messages, context=context, temperature=0.3, max_tokens=_max_tok
            )

            self.logger.info(
                f"📥 Structurizer LLM response length: {len(response)} chars"
            )

            # Парсим ответ LLM (старый dict формат)
            raw_result = self._parse_response(response)
            tool_requests = self._extract_tool_requests(raw_result)
            _doc_extraction = (
                str((context or {}).get("task_type") or "").strip()
                == "document_extraction"
            )
            if tool_requests:
                if not tools_enabled or _doc_extraction or _research_satellite:
                    self.logger.info(
                        "Structurizer: ignoring %d tool_request(s) from LLM "
                        "(tools disabled, document_extraction, or research)",
                        len(tool_requests),
                    )
                    if isinstance(raw_result, dict):
                        raw_result.pop("tool_requests", None)
                else:
                    return AgentPayload.partial(
                        agent=self.agent_name,
                        tool_requests=tool_requests,
                        narrative=Narrative(
                            text="Для структуризации требуется догрузка данных таблиц."
                        ),
                        metadata={"tool_mode": "request"},
                    )
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
            is_research_sat = (
                str((context or {}).get("controller") or "").strip() == "research"
                and str((context or {}).get("mode") or "").strip() == "research"
            )
            content_parts: List[str] = []
            _max_per_source = (
                ma_int("MULTI_AGENT_STRUCTURIZER_RESEARCH_MAX_PER_SOURCE_CHARS", 2800)
                if is_research_sat
                else 4500
            )
            for result in agent_results:
                if not isinstance(result, dict):
                    continue

                # V2: sources[] с fetched=True и content
                sources = result.get("sources", [])
                if isinstance(sources, list):
                    for s in sources:
                        if isinstance(s, dict) and s.get("fetched") and s.get("content"):
                            url = s.get("url", "unknown")
                            mt = s.get("mime_type")
                            rk = s.get("resource_kind")
                            extra = ""
                            if mt or rk:
                                extra = f" [MIME={mt or '-'} kind={rk or '-'}]"
                            block = s["content"]
                            if len(block) > _max_per_source:
                                block = block[:_max_per_source] + "\n\n... (truncated per source)"
                            content_parts.append(f"=== Source: {url}{extra} ===\n{block}")

                # V1 fallback: pages[]
                pages = result.get("pages", [])
                if isinstance(pages, list):
                    for p in pages:
                        if isinstance(p, dict) and p.get("content"):
                            content_parts.append(
                                f"=== Source: {p.get('url', 'unknown')} ===\n{p['content']}"
                            )

            if content_parts:
                text_joined = "\n\n".join(content_parts)
                dr_block = StructurizerAgent._format_discovered_resources_block(
                    agent_results
                )
                if is_research_sat and dr_block:
                    combined = (
                        dr_block
                        + "\n\n=== ИЗВЛЕЧЁННЫЙ ТЕКСТ СТРАНИЦ (ниже) ===\n\n"
                        + text_joined
                    )
                elif dr_block:
                    combined = text_joined + "\n\n" + dr_block
                else:
                    combined = text_joined

                max_total = (
                    ma_int("MULTI_AGENT_STRUCTURIZER_RESEARCH_MAX_TOTAL_CHARS", 52000)
                    if is_research_sat
                    else 14000
                )
                if len(combined) > max_total:
                    if is_research_sat and dr_block:
                        sep = "\n\n=== ИЗВЛЕЧЁННЫЙ ТЕКСТ СТРАНИЦ (ниже) ===\n\n"
                        overhead = len(dr_block) + len(sep)
                        tail_budget = max_total - overhead
                        if tail_budget < 800:
                            if overhead >= max_total:
                                combined = (
                                    dr_block[: max_total - 80]
                                    + "\n\n... (truncated: сокращён JSON URL; уменьши список в research)"
                                )
                            else:
                                combined = combined[:max_total] + "\n\n... (truncated total)"
                        else:
                            combined = (
                                dr_block
                                + sep
                                + text_joined[:tail_budget]
                                + "\n\n... (truncated: хвост страниц обрезан; блок URL выше сохранён)"
                            )
                    else:
                        combined = combined[:max_total] + "\n\n... (truncated total)"
                return combined

        # 3b. document_extraction (файл на доске): не подставлять псевдо-таблицу input_data_preview —
        # тот же обогащённый запрос, что видит Planner, либо плоский текст из content_nodes_data.
        if context and str(context.get("task_type") or "").strip() == "document_extraction":
            ur = context.get("user_request")
            if isinstance(ur, str) and ur.strip():
                return ur
            plain = self._plain_document_text_from_content_nodes(context)
            if plain:
                return plain
        
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

    @staticmethod
    def _format_discovered_resources_block(agent_results: Any) -> str:
        """Каталог URL из research (страницы + embedded), для structurizer помимо текста страниц."""
        if not isinstance(agent_results, list):
            return ""
        max_n = ma_int("MULTI_AGENT_STRUCTURIZER_DISCOVERED_RESOURCES_MAX", 80)
        max_url = ma_int("MULTI_AGENT_STRUCTURIZER_DISCOVERED_RESOURCE_URL_CHARS", 2000)
        slim: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for result in agent_results:
            if not isinstance(result, dict):
                continue
            if result.get("agent") != "research":
                continue
            drs = result.get("discovered_resources") or []
            if not isinstance(drs, list):
                continue
            for r in drs:
                if not isinstance(r, dict):
                    continue
                u = r.get("url")
                if not u or not isinstance(u, str):
                    continue
                u = u.strip()
                if u in seen:
                    continue
                seen.add(u)
                slim.append(
                    {
                        "url": u[:max_url],
                        "resource_kind": r.get("resource_kind"),
                        "mime_type": r.get("mime_type"),
                        "parent_url": (str(r.get("parent_url"))[:max_url])
                        if r.get("parent_url")
                        else None,
                        "origin": r.get("origin"),
                        "tag": r.get("tag"),
                        "title": r.get("title"),
                    }
                )
                if len(slim) >= max_n:
                    break
            if len(slim) >= max_n:
                break
        if not slim:
            return ""
        return (
            "=== DISCOVERED_RESOURCES (from research; используй URL для фактов о медиа/страницах) ===\n"
            + json.dumps(slim, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _plain_document_text_from_content_nodes(context: Dict[str, Any]) -> str:
        """Плоский текст файла из content_nodes_data (без JSON-обёртки)."""
        cn_data = context.get("content_nodes_data")
        if not isinstance(cn_data, list) or not cn_data:
            return ""
        first = cn_data[0]
        if isinstance(first, dict):
            c = first.get("content")
            if isinstance(c, dict):
                t = c.get("text")
                if isinstance(t, str) and t.strip():
                    return t
        return ""
    
    def _sanitize_content_for_llm(
        self,
        content: str,
        *,
        preserve_urls: bool = False,
    ) -> str:
        """
        Уменьшает риск срабатывания blacklist/moderation GigaChat:
        ограничение длины; для обычных режимов — замена URL на плейсхолдер.

        Для Research Chat (preserve_urls=True) URL не маскируем: в DISCOVERED_RESOURCES
        нужны реальные адреса для колонок «Фото» и т.п.
        """
        if preserve_urls:
            max_content_length = ma_int(
                "MULTI_AGENT_STRUCTURIZER_RESEARCH_MAX_LLM_CONTENT_CHARS",
                52000,
            )
        else:
            max_content_length = ma_int(
                "MULTI_AGENT_STRUCTURIZER_MAX_CONTENT_CHARS",
                20000,
            )
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n... (truncated)"
        if not preserve_urls:
            content = re.sub(
                r"https?://[^\s\]\)\}\"']+",
                "[URL]",
                content,
                flags=re.IGNORECASE,
            )
        return content

    def _build_prompt(
        self,
        description: str,
        content: str,
        *,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        tools_enabled: bool = False,
        tool_request_cache_digest_lines: Optional[List[str]] = None,
        research_satellite: bool = False,
    ) -> str:
        """Формирует user-промпт для LLM (единый для всех режимов: документ, research, preview нод и т.д.)."""
        content = self._sanitize_content_for_llm(
            content, preserve_urls=research_satellite
        )
        research_extra = ""
        if research_satellite:
            research_extra = """
**РЕЖИМ RESEARCH (обязательно учти):**
- В начале входного текста блок `DISCOVERED_RESOURCES` — JSON с **реальными URL** страниц (`html_page`) и медиа (`image` и др.). Это не выдумка, их можно копировать в таблицу.
- Если в TASK есть колонки вроде «Фото», «URL», «Изображение», «Ссылка» — заполняй их **точными URL из DISCOVERED_RESOURCES** (для фото обычно `resource_kind: image`). Сопоставляй по смыслу с именами/фрагментами текста ниже; при сомнении — ближайший URL с той же страницы (`parent_url`).
- Возраст, фильмы, биографию — **только из извлечённого текста**; если факта нет — `null`. Не придумывай числа и названия фильмов.
- Таблица с именами из текста и URL фото из JSON **лучше**, чем ноль строк, когда имена в тексте есть, а в JSON есть кандидаты для колонки про медиа.

"""
        prompt = f"""**TASK (шаг плана / формулировка извлечения):**
{description}
{research_extra}
**ВХОДНОЙ ТЕКСТ ДЛЯ СТРУКТУРИРОВАНИЯ** (фрагмент документа, HTML, ответ research, выгрузка в виде таблицы, JSON-превью и т.п.):
{content}

**ИНСТРУКЦИИ:**
1. Только извлечение структуры из текста выше — без аналитики, выводов и рекомендаций (это другие агенты).
2. Следуй TASK: извлеки таблицы, сущности (`entities`), при необходимости `key_value_pairs`; типы колонок — см. system prompt.
3. Не утверждай в `notes`, что «данных нет» / «фрагмент пуст», если из текста (списки, абзацы, таблицы HTML/markdown, ячейки) можно заполнить колонки по смыслу TASK. Пустой `tables` или пустой `rows` — только если в тексте действительно нет фактов под запрошенную схему.
4. Списки и перечисления преобразуй в строки `tables[].rows` (двухфазная модель в system prompt: схема колонок, затем значения; пропуски — `null`).
5. Верни **только** валидный JSON без markdown-обёрток; `notes` — кратко, без YAML-копии таблицы. Итог для UI и пайплайна — в `tables[].rows`, не подменяй строки таблицы длинным текстом только в `notes`.
6. Формат `rows` — JSON-массив массивов значений в порядке колонок (см. system prompt).

**INSTRUCTIONS (English summary):** Extract structure only; fill `tables[].rows` from the input; return pure JSON as specified in the system prompt."""
        digest_lines = tool_request_cache_digest_lines or []
        if digest_lines:
            prompt += (
                "\n\nУЖЕ ВЫПОЛНЕННЫЕ ЗАПРОСЫ К ДАННЫМ (не дублируй идентичные tool_requests; "
                "данные уже получены — см. TOOL RESULTS ниже):\n"
            )
            for line in digest_lines[-25:]:
                prompt += f"  • {line}\n"
        if tool_results:
            rendered = []
            for item in tool_results[-4:]:
                if not isinstance(item, dict):
                    continue
                tname = item.get("tool_name", "tool")
                if item.get("success"):
                    rendered.append(
                        f"- {tname}: {json.dumps(item.get('data', {}), ensure_ascii=False)[:2200]}"
                    )
                else:
                    rendered.append(f"- {tname}: ERROR={item.get('error', 'unknown')}")
            if rendered:
                prompt += "\n\nTOOL RESULTS (latest):\n" + "\n".join(rendered) + "\n"
        if tools_enabled:
            prompt += (
                "\nTOOL MODE ENABLED.\n"
                "Доступ к данным: readTableListFromContentNodes (в ответе есть table_id для каждой таблицы); "
                "для строк таблицы — readTableData с jsonDecl.table_id. Если задача требует значений из строк, "
                "вызови readTableData.\n"
                "Если данных недостаточно, верни JSON:\n"
                "{\n"
                '  "tool_requests": [\n'
                "    {\n"
                '      "tool_name": "readTableListFromContentNodes",\n'
                '      "arguments": {"nodeIds": ["<uuid1>", "<uuid2>"]},\n'
                '      "reason": "optional"\n'
                "    },\n"
                "    {\n"
                '      "tool_name": "readTableData",\n'
                '      "arguments": {"jsonDecl": {"contentNodeId":"<uuid>","table_id":"<id_or_name>","offset":0,"limit":50}},\n'
                '      "reason": "optional"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "Иначе верни обычный JSON со structured tables."
            )
        return prompt

    @staticmethod
    def _extract_tool_requests(raw: Any) -> List[ToolRequest]:
        if not isinstance(raw, dict):
            return []
        items = raw.get("tool_requests")
        if not isinstance(items, list):
            return []
        out: List[ToolRequest] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name") or item.get("name") or "").strip()
            if not tool_name:
                continue
            args = item.get("arguments") or item.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            try:
                out.append(
                    ToolRequest(
                        tool_name=tool_name,
                        arguments=args,
                        reason=item.get("reason"),
                    )
                )
            except Exception:
                continue
        return out
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Парсит ответ LLM. Несколько попыток: markdown → извлечение по скобкам → repair."""
        raw = response.strip()

        # Ответ без JSON (blacklist/модерация GigaChat — обрезанный или текстовый ответ)
        if not raw or "{" not in raw:
            preview = (raw[:300] + "...") if len(raw) > 300 else raw
            self.logger.warning(
                "Structurizer: LLM returned non-JSON (possible blacklist/truncation). "
                "Response: %s",
                preview,
            )
            return self._empty_result(
                "LLM returned non-JSON (possible content filter/blacklist). Try simpler query or other content."
            )
        if len(raw) < 300:
            self.logger.warning(
                "Structurizer: very short LLM response (%s chars), may be truncated: %s",
                len(raw),
                raw[:200],
            )

        # 1) Извлечь фрагмент для парсинга (вложенный JSON — по балансу скобок)
        candidate = ""
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if md_match:
            block = md_match.group(1).strip()
            start = block.find("{")
            if start >= 0:
                candidate = self._extract_json_by_braces(block, start) or block[start:]
        if not candidate:
            start = raw.find("{")
            if start >= 0:
                candidate = self._extract_json_by_braces(raw, start) or raw[start:]
        if not candidate:
            candidate = raw

        # 2) Парсинг
        try:
            result = json.loads(candidate)
            return self._normalize_parse_result(result)
        except json.JSONDecodeError as e:
            self._log_parse_failure(raw, candidate, e)
        except Exception as e:
            self.logger.error(f"Structurizer parse unexpected error: {e}", exc_info=True)
            return self._empty_result(f"Parse error: {e}")

        # 3) Попытка починить JSON
        repaired = self._repair_json(candidate)
        try:
            result = json.loads(repaired)
            self.logger.info("✅ Structurizer: parsed after JSON repair")
            return self._normalize_parse_result(result)
        except json.JSONDecodeError as e2:
            self.logger.warning(f"Structurizer: repair did not help: {e2}")
            return self._empty_result(f"JSON parse error: {str(e2)}")
    
    def _extract_json_by_braces(self, text: str, start: int) -> Optional[str]:
        """Извлекает подстроку от start до сбалансированной закрывающей }."""
        depth_curly = 0
        depth_square = 0
        in_string = False
        escape_next = False
        i = start
        while i < len(text):
            c = text[i]
            if escape_next:
                escape_next = False
                i += 1
                continue
            if c == '\\' and in_string:
                escape_next = True
                i += 1
                continue
            if c == '"':
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue
            if c == '{':
                depth_curly += 1
            elif c == '}':
                depth_curly -= 1
            elif c == '[':
                depth_square += 1
            elif c == ']':
                depth_square -= 1
            i += 1
            if depth_curly == 0 and depth_square == 0:
                return text[start:i]
        return None

    def _normalize_parse_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
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
        # Модель иногда кладёт текст в narrative вместо notes
        nar = result.get("narrative")
        if isinstance(nar, str) and nar.strip() and (
            not str(result.get("notes", "")).strip()
        ):
            result["notes"] = nar
        elif isinstance(nar, dict) and isinstance(nar.get("text"), str):
            if not str(result.get("notes", "")).strip():
                result["notes"] = nar["text"]
        return result

    def _empty_result(self, notes: str) -> Dict[str, Any]:
        return {
            "tables": [],
            "entities": [],
            "key_value_pairs": {},
            "extraction_confidence": 0.0,
            "notes": notes,
        }

    def _log_parse_failure(
        self, raw: str, candidate: str, e: json.JSONDecodeError
    ) -> None:
        """Логирует сырой ответ при ошибке парсинга для отладки."""
        self.logger.error(f"JSON parse error: {e}")
        preview = candidate[:500] + "..." if len(candidate) > 500 else candidate
        if len(raw) <= 600:
            self.logger.info(
                "Structurizer LLM raw response (parse failed): %s",
                raw,
            )
        self.logger.debug(f"Structurizer candidate (first 500): {preview}")
        if len(candidate) > 2000:
            self.logger.debug(
                f"Structurizer candidate (around error line {getattr(e, 'lineno', '?')}): "
                f"...{candidate[max(0, (e.pos or 0) - 200):(e.pos or 0) + 200]}..."
            )
        # Опционально: запись в файл для разбора (включается через DEBUG)
        if logger.isEnabledFor(logging.DEBUG):
            try:
                import os
                log_dir = os.path.join(
                    os.path.dirname(__file__), "..", "..", "..", "..", "logs"
                )
                os.makedirs(log_dir, exist_ok=True)
                path = os.path.join(log_dir, "structurizer_last_response.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("=== RAW ===\n")
                    f.write(raw[:50000])
                    f.write("\n\n=== CANDIDATE ===\n")
                    f.write(candidate[:50000])
                    f.write(f"\n\n=== ERROR: {e} ===\n")
                self.logger.debug(f"Structurizer debug dump: {path}")
            except Exception as ex:
                self.logger.warning(f"Could not write structurizer debug file: {ex}")

    def _repair_json(self, content: str) -> str:
        """Типичные исправления JSON от LLM: висячие запятые, баланс скобок."""
        repaired = content.strip()
        # Убрать висячие запятые перед ] или }
        repaired = re.sub(r",\s*]", "]", repaired)
        repaired = re.sub(r",\s*}", "}", repaired)
        open_curly = repaired.count("{") - repaired.count("}")
        open_square = repaired.count("[") - repaired.count("]")
        if open_curly > 0 or open_square > 0:
            repaired = repaired.rstrip().rstrip(",")
            repaired += "}" * open_curly + "]" * open_square
        if open_curly < 0 or open_square < 0:
            for _ in range(-open_curly):
                pos = repaired.rfind("}")
                if pos >= 0:
                    repaired = repaired[:pos] + repaired[pos + 1:]
            for _ in range(-open_square):
                pos = repaired.rfind("]")
                if pos >= 0:
                    repaired = repaired[:pos] + repaired[pos + 1:]
        return repaired

    @staticmethod
    def _align_row_dicts_to_column_names(
        rows: List[Dict[str, Any]], names: List[str]
    ) -> List[Dict[str, Any]]:
        """Ключи в строках совпадают с `names` (exact / trim / регистр / порядок значений).

        LLM нередко отдаёт rows как list[list] (уже обработано выше) или dict с «чужими» ключами.
        """
        if not names:
            return rows
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                out.append({})
                continue
            rebuilt: Dict[str, Any] = {}
            matched_all = True
            for n in names:
                if n in row:
                    rebuilt[n] = row[n]
                elif (sk := next((k for k in row if str(k).strip() == n.strip()), None)) is not None:
                    rebuilt[n] = row[sk]
                elif (sk2 := next((k for k in row if str(k).strip().lower() == n.lower()), None)) is not None:
                    rebuilt[n] = row[sk2]
                else:
                    matched_all = False
                    break
            if matched_all and len(rebuilt) == len(names):
                out.append(rebuilt)
                continue
            vals = list(row.values())
            if len(vals) == len(names):
                out.append({names[i]: vals[i] for i in range(len(names))})
            else:
                out.append(row)
        return out
    
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

            # Стабильные имена колонок (пустое имя ломает dict и UI)
            names_for_keys: List[str] = []
            for idx, c in enumerate(typed_columns):
                raw_n = str(c.get("name", "")).strip() if isinstance(c, dict) else str(c).strip()
                stable = raw_n or f"col_{idx}"
                names_for_keys.append(stable)
                if isinstance(c, dict) and not raw_n:
                    c["name"] = stable
            
            # Ensure rows are dicts (LLM иногда отдаёт одну колонку списком строк — иначе строки терялись)
            rows = table.get("rows", [])
            new_rows: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    new_rows.append(row)
                elif isinstance(row, list):
                    new_rows.append(
                        {
                            names_for_keys[j]: row[j]
                            for j in range(min(len(row), len(names_for_keys)))
                        }
                    )
                elif isinstance(row, str) and names_for_keys:
                    rdict = {names_for_keys[0]: row}
                    for c in names_for_keys[1:]:
                        rdict[c] = None
                    new_rows.append(rdict)
                else:
                    new_rows.append({})

            # Ключи в dict-строках должны совпадать с columns[].name (LLM часто отдаёт другие имена)
            new_rows = StructurizerAgent._align_row_dicts_to_column_names(
                new_rows, names_for_keys
            )

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
