# Концепция настройки LLM: пресеты, модель по умолчанию, привязка к агентам

## Executive Summary

Настройки LLM строятся так:

1. **Перечень LLM-пресетов** — администратор заранее настраивает несколько «профилей» (GigaChat, внешний OpenAI-совместимый и т.д.) с реквизитами (ключи, base URL, модель). Реквизиты вводятся один раз на пресет.
2. **Модель по умолчанию** — одна из сконфигурированных пресетов выбирается как системная по умолчанию для всех агентов.
3. **Выбор LLM по агенту** — для каждого агента (planner, discovery, analyst, codex и т.д.) можно опционально указать пресет из списка; если не указан — используется модель по умолчанию.
4. **Служебные привязки** — для механизмов, не совпадающих с именем агента шага, используются отдельные ключи в той же таблице `agent_llm_override`. Сейчас: **`context_graph_compression`** — опциональная модель для LLM-сжатия уровней контекстного графа (L1/L2). **Если отдельной привязки нет** — применяется **та же системная модель по умолчанию** (`system_llm_settings.default_llm_config_id`), что и для агентов без персонального пресета (planner, analyst и т.д.); отдельный fallback не задаётся.

Так мы избегаем дублирования реквизитов по агентам и даём гибкость: тяжёлые задачи можно вести на одной модели, лёгкие — на другой.

---

## Термины

| Термин | Описание |
|--------|----------|
| **LLM-пресет** | Одна сконфигурированная «модель»: имя, провайдер (GigaChat / external OpenAI-compatible), все реквизиты (ключ, base URL, модель, temperature, max_tokens). Хранится в таблице `llm_config`. |
| **Модель по умолчанию** | Один из пресетов, выбранный как системный default. Используется для всех агентов, у которых нет персональной привязки. |
| **Привязка агента к LLM** | Опциональная связь «ключ → пресет». Ключ — строка из реестра агентов (`planner`, `discovery`, …) **или** служебный ключ (`context_graph_compression` и др.). |
| **Runtime policy агента** | Дополнительные runtime-параметры в `agent_llm_override.runtime_options`: `timeout_sec`, `max_retries`, `context_ladder`, `max_items`, `max_total_chars`, `task_overrides`. |

---

## Модель данных

### 1. Таблица `llm_config` (перечень пресетов)

Один пресет = одна запись. Администратор создаёт/редактирует/удаляет пресеты.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `name` | string | Отображаемое имя (например «GigaChat Prod», «OpenAI GPT-4») |
| `provider` | string | `gigachat` \| `external_openai_compat` |
| `sort_order` | int | Порядок отображения в списке (меньше — выше) |
| **GigaChat** | | |
| `gigachat_model` | string, nullable | Идентификатор модели |
| `gigachat_scope` | string, nullable | Scope |
| `gigachat_api_key_encrypted` | string, nullable | Зашифрованный ключ (или null, тогда из env) |
| **External OpenAI-compatible** | | |
| `external_base_url` | string, nullable | Base URL API |
| `external_default_model` | string, nullable | Имя модели |
| `external_timeout_seconds` | int, nullable | Таймаут запроса |
| `external_api_key_encrypted` | string, nullable | Зашифрованный API-ключ |
| **Параметры генерации** | | |
| `temperature` | float, nullable | 0.0–1.0 |
| `max_tokens` | int, nullable | Лимит токенов |
| `created_at`, `updated_at` | datetime | |

Ограничение: для `provider=gigachat` должны быть заполнены поля GigaChat (или ключ в env); для `external_openai_compat` — external_*.

### 2. Системные настройки и привязки агентов (вариант B — отдельная таблица)

Принят **вариант B**: отдельная таблица привязок агентов для нормализации и явных FK.

**`system_llm_settings`** (одна запись на инстанс):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `default_llm_config_id` | UUID, FK → llm_config.id, nullable | Пресет по умолчанию (если null — fallback на GigaChat из env) |
| `created_at`, `updated_at` | datetime | |

**`agent_llm_override`** (привязка агента к пресету):

| Поле | Тип | Описание |
|------|-----|----------|
| `agent_key` | string | PK, ключ агента из реестра (planner, discovery, …) |
| `llm_config_id` | UUID, FK → llm_config.id | Пресет для этого агента |
| `runtime_options` | JSON, nullable | Runtime-политика выполнения для агента: timeout/retries/context budgets и task-specific overrides |
| `created_at`, `updated_at` | datetime | |

Уникальность по `agent_key`: у каждого агента не более одной привязки. При удалении пресета нужно проверять, что он не используется как default и не указан в `agent_llm_override`.

### 3. Миграция с текущей таблицы `system_llm_settings`

Сейчас в ней хранится одна «монолитная» запись со всеми полями провайдера. При переходе на пресеты (вариант B):

- Создаём таблицу `llm_config` и таблицу `agent_llm_override`.
- Переносим данные из текущей записи `system_llm_settings` в первую запись `llm_config` (пресет «По умолчанию» или по имени из конфига).
- Добавляем в `system_llm_settings` колонку `default_llm_config_id` (FK на `llm_config.id`), проставляем её в id созданного пресета, затем удаляем старые колонки (provider, gigachat_*, external_*, temperature, max_tokens).

---

## Логика выбора LLM при вызове

При запросе к LLM от агента (в `LLMRouter.chat_completion` или аналоге):

1. Входные параметры: `user_id` (для доступа к БД), **`agent_key`** (например `planner`, `analyst`, служебный `context_graph_compression`), `params` (messages, temperature, max_tokens).
2. Загрузить системные настройки: `default_llm_config_id`. Загрузить привязку из `agent_llm_override` по `agent_key` (если есть).
3. Определить `llm_config_id` (**одинаково для агентов и служебных ключей**):
   - если в `agent_llm_override` есть запись для `agent_key` → взять её `llm_config_id`;
   - иначе → взять **`default_llm_config_id`** (модель по умолчанию в системных настройках LLM).
4. Загрузить запись `llm_config` по `llm_config_id`.
5. По `provider` построить клиент (GigaChat или OpenAI-compatible) и выполнить запрос. Параметры `temperature`/`max_tokens` из запроса могут переопределять значения из пресета (или брать из пресета, если не переданы).

Дополнительно для исполнения шага в Orchestrator:

- из `agent_llm_override.runtime_options` читаются runtime-параметры для `ExecutionPolicy` и `context_selection`;
- поддерживаются task-specific overrides в `runtime_options.task_overrides[task_type]`.

Если `default_llm_config_id` не задан или пресет удалён — fallback на текущее поведение (например GigaChat из env), с логированием предупреждения.

---

## API (админ)

- `GET /api/v1/admin/llm-configs` — список пресетов (для выбора default и для привязки агентов).
- `POST /api/v1/admin/llm-configs` — создание пресета.
- `GET /api/v1/admin/llm-configs/{id}` — один пресет.
- `PATCH /api/v1/admin/llm-configs/{id}` — обновление пресета (в т.ч. реквизиты).
- `DELETE /api/v1/admin/llm-configs/{id}` — удаление пресета (проверка: не используется ли как default или в `agent_llm_override`).
- `GET /api/v1/admin/llm-settings` — текущие системные настройки: default_llm_config_id, список привязок из `agent_llm_override`, плюс для удобства список пресетов и реестр агентов.
- `PATCH /api/v1/admin/llm-settings` — установить default_llm_config_id.
- `GET /api/v1/admin/agent-llm-overrides` — список привязок агент → пресет.
- `PUT /api/v1/admin/agent-llm-overrides` — установить привязки (полная замена): список `{ agent_key, llm_config_id, runtime_options? }`.

### `runtime_options` (контракт)

Поддерживаемая структура:

```json
{
  "timeout_sec": 45,
  "max_retries": 1,
  "context_ladder": ["full", "compact", "minimal"],
  "max_items": 30,
  "max_total_chars": 100000,
  "task_overrides": {
    "create_plan": {
      "timeout_sec": 35,
      "max_retries": 1,
      "max_items": 20,
      "max_total_chars": 70000
    }
  }
}
```

Ограничения валидации:

- `context_ladder`: только `full`, `compact`, `minimal` (регистр не важен, нормализуется к lower-case);
- `timeout_sec`: `1..1800`;
- `max_retries`: `0..10`;
- `max_items`: `1..200`;
- `max_total_chars`: `1000..500000`.

Тест подключения и Playground мультиагента остаются; тест привязать к выбранному пресету или к default.

---

## Реестр агентов (для UI)

Список ключей агентов, для которых можно задать привязку к пресету (из `MULTI_AGENT.md` и кода Orchestrator):

| agent_key | Описание |
|-----------|----------|
| `planner` | Планировщик |
| `discovery` | Поиск (веб, датасеты) |
| `research` | Загрузка контента по URL |
| `structurizer` | Извлечение структурированных данных |
| `analyst` | Анализ данных |
| `transform_codex` | Генерация Python-трансформаций |
| `widget_codex` | Генерация виджетов |
| `reporter` | Формирование ответа |
| `context_filter` | Подготовка контекста / фильтрация для пайплайна |
| `validator` | Финальная проверка (Quality Gate; ключ плана) |

В UI: выпадающий список «Модель по умолчанию» (пресеты) + таблица/форма «Для агента X использовать пресет Y» (опционально, по умолчанию — «по умолчанию»).

---

## Изменения в коде (кратко)

1. **Backend**
   - Модели: `LLMConfig`, обновлённая `SystemLLMSettings` (default_llm_config_id, agent_overrides).
   - Миграции: создать `llm_config`, изменить `system_llm_settings` (перенос данных из текущей записи в первый пресет, затем упрощение таблицы).
   - Схемы и роуты: CRUD для `llm_config`, GET/PATCH для system-llm-settings с default и overrides.
   - `LLMRouter`: при `chat_completion(user_id, params, agent_key=...)` определять llm_config_id по default + agent_overrides, загружать пресет, строить клиент из пресета.
2. **Orchestrator / BaseAgent**
   - При вызове LLM передавать в роутер `agent_key` (имя агента из `self.agent_name` или из реестра).
3. **Frontend**
   - В настройках LLM: вкладка «Пресеты» (список, добавление, редактирование, удаление), блок «Модель по умолчанию» (выбор пресета), блок «Привязка к агентам» (таблица агент → пресет или «по умолчанию»). Тест и Playground — без изменений по смыслу, при необходимости привязка к выбранному пресету/default.

---

## Итог

- Один раз настраиваем **перечень LLM-пресетов** с реквизитами.
- Выбираем **одну модель по умолчанию** для всей системы.
- При необходимости задаём **для каждого агента** пресет из списка; иначе используется default.
- Реквизиты не дублируются по агентам; гибкость сохраняется за счёт выбора пресета по агенту.

После согласования концепции можно переходить к миграциям и реализации API и UI.
