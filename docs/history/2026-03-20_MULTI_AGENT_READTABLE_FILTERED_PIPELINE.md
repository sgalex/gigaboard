# Актуализация: тулы таблиц и `_compute_filtered_pipeline` (20.03.2026)

## Executive Summary

Зафиксировано выравнивание тулов оркестратора **`readTableData`** / **`readTableListFromContentNodes`** с тем же пересчётом пайплайна на бэке, что и UI доски/дашборда: **`_compute_filtered_pipeline`**. Это устраняет сценарии, когда аналитик видел «пустые» таблицы при ненулевом `row_count` или получал данные из сырого `ContentNode.content` без учёта цепочки и кросс-фильтра.

## Тезисы

- **Ленивый кэш** `pipeline_context["_raw_filtered_pipeline_result"]`: `_ensure_filtered_pipeline_raw_cache` больше не требует обязательного активного фильтра при известном `board_id` — выполняется пересчёт с `filters=None` (без кросс-фильтра по измерениям, с исполнением upstream-трансформаций).
- **Гидратация строк** при `row_count > 0` и пустом `rows`: сначала `_compute_filtered_pipeline_tables_for_node` + `_merge_filtered_pipeline_into_raw_cache`, затем при необходимости fallback на `_hydrate_table_rows_from_content_db` (чтение `content` из БД).
- **Документация**: `docs/MULTI_AGENT.md` (Executive Summary, «Кросс-фильтр и тулы», «Вызов `readTableData`»), `docs/CROSS_FILTER_SYSTEM.md` §3.5, `docs/API.md` §16, `docs/README.md`, `.vscode/CURRENT_FOCUS.md`.

## Код (ориентиры)

- `apps/backend/app/services/multi_agent/orchestrator.py` — `_compute_filtered_pipeline_tables_for_node`, `_merge_filtered_pipeline_into_raw_cache`, `_ensure_filtered_pipeline_raw_cache`, `_hydrate_table_rows_from_content_db`, `_tool_read_table_data`
- `apps/backend/app/routes/filters.py` — `_compute_filtered_pipeline`
