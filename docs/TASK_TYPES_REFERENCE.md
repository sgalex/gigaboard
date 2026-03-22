# Справочник типов задач агентов (task types)

## Executive Summary

Типы задач (`task.type` в шагах плана и вызовах агентов) описаны **в коде** агентов и в основном документе по мультиагентной системе. Этот файл — **навигационный указатель**, чтобы не дублировать длинные таблицы.

**Источник истины**:

- Реестр агентов и ролей: [`MULTI_AGENT.md`](./MULTI_AGENT.md) (разделы «Core Agents», «Реестр агентов»).
- Реализация: `apps/backend/app/services/multi_agent/agents/*.py` (поля `task["type"]` в `process_task`).

**Связанные документы**: [`PLANNING_DECOMPOSITION_STRATEGY.md`](./PLANNING_DECOMPOSITION_STRATEGY.md), [`CONTEXT_ENGINEERING.md`](./CONTEXT_ENGINEERING.md).

---

## Заметка

Конкретные строки `task.type` меняются вместе с эволюцией агентов; при добавлении нового типа обновляйте описание в **`MULTI_AGENT.md`** и при необходимости тесты в `tests/backend/`.
