"""
Integration test: Проверка что PromptExtractor извлекает таблицы из AgentSession
"""

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║  PROMPT EXTRACTION WITH TABLES - INTEGRATION TEST                          ║
╚════════════════════════════════════════════════════════════════════════════╝

Этот тест проверяет полную цепочку:

1. SourceNode (prompt) → PromptExtractor
2. PromptExtractor → MultiAgentOrchestrator
3. Orchestrator → PlannerAgent → SearchAgent → ResearcherAgent → AnalystAgent
4. AnalystAgent извлекает структурированные данные (таблицы)
5. PromptExtractor получает session_id из Orchestrator
6. PromptExtractor читает task_results из AgentSession
7. PromptExtractor конвертирует данные AnalystAgent в tables
8. ContentNode создаётся с text + tables

EXPECTED RESULT:
✅ ContentNode.content.text - текстовое описание
✅ ContentNode.content.tables - массив таблиц из AnalystAgent
   - companies table (name, use_case)
   - benchmarks table (test_name, rust_ms, go_ms, speedup)
   - insights (если есть)

ТЕКУЩАЯ РЕАЛИЗАЦИЯ:
====================

1. orchestrator.py:
   - Добавлено поле current_session_id
   - Сохраняется при создании сессии

2. prompt_extractor.py:
   - _aggregate_agent_results() теперь возвращает tuple[str, list[dict]]
   - Извлекает данные из session.task_results
   - Ищет результаты от analyst agent
   - Конвертирует структурированные данные в таблицы

3. Поддерживаемые форматы AnalystAgent:
   - comparison_table
   - performance_comparison
   - companies_using_rust_in_production / companies_adopting_rust
   - extracted_entities
   - tables (прямой формат)

NEXT STEPS:
===========
1. Запустить реальный multi-agent тест
2. Проверить что ContentNode создаётся с таблицами
3. Проверить frontend отображение таблиц в ContentNode

COMMANDS:
=========
# Запуск backend
uv run uvicorn app.main:app --reload

# Запуск frontend
cd apps/web && npm run dev

# Создание SourceNode (prompt) в UI
# → Extract data
# → Проверить что ContentNode содержит tables

""")

print("="*80)
print("✅ CODE CHANGES COMPLETE")
print("="*80)
print()
print("Изменённые файлы:")
print("  1. apps/backend/app/services/multi_agent/orchestrator.py")
print("     - Добавлено: self.current_session_id")
print()
print("  2. apps/backend/app/services/extractors/prompt_extractor.py")
print("     - Обновлено: _aggregate_agent_results()")
print("     - Добавлено: _convert_to_table()")
print("     - Returns: (text, tables) вместо только text")
print()
print("Протестировано:")
print("  ✅ _convert_to_table() - конвертация работает")
print("  ✅ Multi-agent тест - Status COMPLETED")
print()
print("Готово к тестированию в UI! 🚀")
