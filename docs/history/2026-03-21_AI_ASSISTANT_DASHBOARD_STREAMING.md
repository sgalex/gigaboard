# История: ИИ-ассистент на дашборде и документация

**Дата**: 2026-03-21

## Суть

- На дашборде ответ ассистента и **прогресс мультиагента** приводят к тому же Socket.IO-потоку (`ai_chat_stream`, `ai:stream:progress`), что и на доске: для дашборда в payload передаются `scope=dashboard` и JWT; сокет для панели поднимается отдельно от `BoardCanvas`.
- Обработчик `connect` на сервере принимает третий аргумент `auth` (клиент `io({ auth: { token } })`).

## Документация

Обновлены: `docs/AI_ASSISTANT.md`, `docs/API.md` (разделы 11 и Real-time), `docs/DASHBOARD_SYSTEM.md`, `docs/README.md`, ссылка в `docs/MULTI_AGENT.md`.
