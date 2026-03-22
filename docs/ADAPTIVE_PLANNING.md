# Адаптивное планирование (replan / revise)

## Executive Summary

**Adaptive planning** в GigaBoard — это логика **повторного построения или доработки плана** после результатов шагов (ошибки, `suggested_replan` от Quality Gate, лимиты). Реализовано в **Orchestrator** (`process_request` / `process_user_request`), а не в отдельном документе-спецификации.

**Где читать подробно**:

- Поведение оркестратора и валидация: [`MULTI_AGENT.md`](./MULTI_AGENT.md) (Planner, QualityGate, разделы про replan).
- Стратегии декомпозиции запросов: [`PLANNING_DECOMPOSITION_STRATEGY.md`](./PLANNING_DECOMPOSITION_STRATEGY.md).
- Код: `apps/backend/app/services/multi_agent/orchestrator.py` (поиск по `replan`, `revise_remaining`, `adaptive`).

---

## Заметка

Исторические черновики с тем же названием могли лежать в `docs/history/`; для текущей модели опирайтесь на **`MULTI_AGENT.md`** и код оркестратора.
