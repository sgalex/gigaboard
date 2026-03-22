# Message Bus — краткий ориентир

## Executive Summary

**AgentMessageBus** в GigaBoard используется оркестратором для **согласованного** взаимодействия с агентами (паттерн pub/sub поверх Redis в типичной конфигурации). Детали протокола и жизненного цикла описаны в архитектурном документе по мультиагентной системе; здесь — **быстрый вход** без дублирования длинных разделов.

**Источник истины**:

- Концепция и диаграммы: [`MULTI_AGENT.md`](./MULTI_AGENT.md) (раздел «Архитектура», MessageBus).
- Реализация: `apps/backend/app/services/multi_agent/message_bus.py`.
- Оркестратор: `apps/backend/app/services/multi_agent/orchestrator.py`.

---

## Минимальная схема

1. Оркестратор инициализирует шину и агентов (`Orchestrator.initialize`).
2. Запрос пользователя проходит **Single Path**: план → шаги → агенты; результаты накапливаются в `pipeline_context` / `agent_results`.
3. Для отладки смотрите трейсы (`MULTI_AGENT_TRACE_*` в окружении и документации `MULTI_AGENT.md`).
