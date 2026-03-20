# План реализации источника AI Research

**Статус**: ✅ Реализовано (март 2026)  
**Дата обновления**: 11 марта 2026  
**Связь**: [SOURCE_NODE_CONCEPT.md](./SOURCE_NODE_CONCEPT.md) (раздел 7), [MULTI_AGENT.md](./MULTI_AGENT.md), [API.md](./API.md) (Research Chat), [ADMIN_AND_SYSTEM_LLM.md](./ADMIN_AND_SYSTEM_LLM.md) (Playground)

---

## Executive Summary

Источник **AI Research** работает на базе мультиагентного пайплайна (Deep search → контент и таблицы). Реализовано:

1. **Backend**: `ResearchController` → `Orchestrator.process_request`; `ResearchSource` делегирует в контроллер; `SourceNodeService` поддерживает создание/refresh и предзаполнение `content` из диалога (`data` в create).
2. **API**: `POST /api/v1/research/chat` — narrative, tables, sources, session_id.
3. **Frontend**: `ResearchSourceDialog` — чат слева (Markdown), превью справа; единый плейсхолдер при отсутствии данных; «Создать источник» передаёт последний результат в `data`.

---

## 1. Текущее состояние (актуально)

| Компонент | Статус |
|-----------|--------|
| ResearchAgent (multi-agent) | ✅ Пайплайн Discovery → Research → Structurizer → Analyst → Reporter |
| SourceType.RESEARCH, ResearchSourceConfig | ✅ Модели и схемы |
| ResearchSource (`app.sources.research`) | ✅ Вызов `ResearchController`, `ExtractionResult` с narrative/tables/sources |
| SourceNodeService | ✅ RESEARCH в create (extract + опционально `data` без повторного исследования), в `_get_extractor` / `extract_data` |
| ResearchSourceDialog | ✅ Две колонки, `researchAPI.chat`, превью, создание ноды с `data` |
| Playground (admin) vs Research Chat | ✅ Один и тот же Orchestrator; отличие — форма `user_request` (см. §2.0.1) |

---

## 2. План реализации (Backend)

### 2.0. ResearchController (Satellite Controller)

**Назначение**: единая точка извлечения результатов мультиагента (narrative, tables, sources) для сценариев «чат исследования» и «создание/refresh источника». Контроллер вызывает Orchestrator и парсит `results`, чтобы не дублировать логику в роуте и в ResearchSource.

**Файл**: `apps/backend/app/services/controllers/research_controller.py`.

**Роль** (по аналогии с [MULTI_AGENT.md](./MULTI_AGENT.md) — Satellite Controllers):

#### 2.0.1. Форма `user_request`: Research Chat и Playground

Оба сценария вызывают **один** `Orchestrator.process_request` и те же агенты. Разница — в том, что попадает в **`user_request`** (Planner видит блок `USER REQUEST: …`).

| Сценарий | Как формируется `user_request` |
|----------|--------------------------------|
| **Playground** (`POST /api/v1/admin/llm-playground/run`) | При наличии истории — «История диалога…», затем «Текущий вопрос пользователя:» и **сырой** вопрос. |
| **Research Chat** (`ResearchController._build_research_request`) | **Сначала** сообщение пользователя, **в конце** короткий форматный хинт в квадратных скобках (таблицы + краткий итог). |

Если подставлять длинную инструкцию про таблицы **в начало**, Planner и Discovery получают искажённый фокус и худшие результаты по сравнению с Playground. Форматный акцент вынесен в **хвост** запроса.

**Контекст**: в Orchestrator передаются `controller: "research"`, `mode: "research"`, при необходимости `chat_history` (Planner добавляет историю отдельным блоком в промпте).

---

- Принимает запрос пользователя (`message`) и опционально `session_id`, `chat_history`.
- Строит контекст без доски (или с placeholder `board_id`), чтобы Planner направил в research-пайплайн (discovery → research → structurizer → analyst → reporter).
- Вызывает `orchestrator.process_request(user_request=_build_research_request(message), board_id=RESEARCH_PLACEHOLDER_BOARD_ID, context={"controller": "research", "mode": "research", "chat_history": chat_history})`. См. §2.0.1.
- Из ответа `result["results"]` извлекает:
  - **narrative** — через `BaseController._extract_narrative(results)` (последний текст от Reporter/Structurizer/Analyst).
  - **tables** — через `BaseController._extract_tables(results)` (все таблицы из payload агентов, дедупликация по имени).
  - **sources** — из payload агента `research` (или `research_2`, …): поле `sources` — список `{url, title, snippet?}` с загруженными страницами.
- Возвращает `ControllerResult` с полями `narrative`, `tables`, `sources`, `session_id`, `plan`, `status`, `execution_time_ms`, при ошибке — `error`.

**Извлечение sources**: в `results` ищем payload с ключом, начинающимся с `"research"` (например `"research"`, `"research_2"`), берём `payload.get("sources", [])`. Каждый элемент — dict с `url`, `title`, при наличии `fetched=True` и `content` не передаём большие поля на фронт, только url/title для блока «Источники».

**Наследование**: от `BaseController` (переиспользование `_call_orchestrator`, `_extract_narrative`, `_extract_tables`). Метод `process_request(message, session_id=None, chat_history=None)` → возврат результата с narrative/tables/sources.

**Использование**:

1. **Роут** `POST /api/v1/research/chat` — создаёт `ResearchController(orchestrator)`, вызывает `process_request`, отдаёт клиенту narrative, tables, sources, session_id.
2. **ResearchSource.extract()** — получает `orchestrator` из kwargs, создаёт тот же контроллер, вызывает `process_request(initial_prompt, chat_history=config.get("conversation_history", []))`, по возвращённому результату строит `ExtractionResult(text=narrative, tables=..., metadata={"sources": ...})`. Таким образом логика «что забрать из мультиагента» живёт только в контроллере.

### 2.1. ResearchSource: делегирование в ResearchController

**Файл**: `apps/backend/app/sources/research/extractor.py`

- В `extract()` получать `orchestrator` из `kwargs` (передаётся из SourceNodeService/роута).
- В `_run_research()`:
  - Создать `ResearchController(orchestrator)`.
  - Вызвать `controller.process_request(message=initial_prompt, chat_history=config.get("conversation_history", []))`.
  - По результату контроллера: при успехе — собрать `ExtractionResult(success=True, text=result.narrative, tables=..., metadata={"sources": result.sources})`; при ошибке — `ExtractionResult.failure(result.error)`.
- Таблицы из контроллера уже в формате list[dict] (ContentTable-like); конвертировать в `TableData` / формат `ExtractionResult.tables` при необходимости в самом extractor.
- Обработка ошибок: при `status == "error"` у контроллера возвращать `ExtractionResult.failure(error)`.

**Зависимости**: Orchestrator передаётся в `extract(..., orchestrator=...)` из SourceNodeService; ResearchController инкапсулирует вызов Orchestrator и извлечение narrative/tables/sources.

### 2.2. Совместимость ExtractionResult с существующим API

**Файл**: `apps/backend/app/sources/base.py`

- Добавить свойство `is_success` → `self.success` (для совместимости с `extraction.py` и `source_node_service.extract_data`).
- Добавить метод `to_content_dict()` → то же, что `to_content()`, чтобы вызывающий код мог использовать единый интерфейс.
- При необходимости добавить `errors: list[str]` (при `success=False` заполнять из `error`).

Тогда и `routes/extraction.py`, и `SourceNodeService.extract_data` смогут работать с результатом из `app.sources` без смены контракта.

### 2.3. SourceNodeService: поддержка RESEARCH

**Файл**: `apps/backend/app/services/source_node_service.py`

**Создание источника (create_source_node):**

- Для `SourceType.RESEARCH`:
  - Получить orchestrator (`get_orchestrator()`).
  - Вызвать `get_source_handler("research")` → `ResearchSource`.
  - Вызвать `extractor.extract(config, orchestrator=orchestrator)`.
  - По результату: при успехе — `content, lineage = result.to_content(), lineage_research`; при ошибке — логировать, создавать ноду с пустым `content` или с `content.text` = сообщение об ошибке (на усмотрение продукта).

**Refresh / extract_data:**

- В `_get_extractor()` добавить ветку для `SourceType.RESEARCH`: возвращать экземпляр из `get_source_handler("research")` (или фабрику, создающую ResearchSource).
- В `extract_data()` для `source_type == SourceType.RESEARCH`:
  - Подготавливать `extraction_params`: `orchestrator=get_orchestrator()`, при необходимости `db`, `source`.
  - Вызывать `extractor.extract(source.config, **extraction_params)`.
  - Результат приводить к формату ответа: `success=result.is_success` (или `result.success`), `content=result.to_content_dict()` (или `result.to_content()`), `errors=...`.

Учесть, что сейчас `extract_data` использует старые экстракторы с сигнатурой `extract(config, params)` и полями `is_success`, `to_content_dict()`. После введения совместимости в `ExtractionResult` вызов для RESEARCH может выглядеть так: `result = await extractor.extract(source.config, **extraction_params)` с проверкой `result.is_success` и `result.to_content_dict()`.

### 2.4. API для чата исследования (Research Dialog)

Чтобы диалог мог вести полноценный чат и показывать таблицы/источники без обязательной привязки к доске, нужен отдельный endpoint.

**Вариант A — отдельный endpoint (рекомендуется)**

- `POST /api/v1/research/chat` (или `POST /api/v1/boards/{board_id}/research/chat` при желании привязки к доске).
- **Request**: `ResearchChatRequest { message: str, session_id?: str, chat_history?: list[{role, content}] }`.
- **Response**: `ResearchChatResponse { narrative: str, tables: list[ContentTable], sources: list[{url, title}], session_id: str, plan?: object }`.
- Внутри: тот же AIAssistantController или выделенный ResearchChatController, который вызывает `orchestrator.process_request()` с контекстом `controller: "research"`, без/с минимальным board_context. Из `results` извлекать narrative, tables, sources и возвращать в ответе.

**Вариант B — переиспользовать `/boards/{board_id}/ai/chat`**

- Добавить в контекст флаг `mode: "research"` и при нём возвращать в ответе дополнительно `tables` и `sources` (расширить схему AIChatResponse).
- Минус: чат привязан к доске, нужен board_id даже для «чистого» исследования.

Рекомендация: **Вариант A** — отдельный `POST /api/v1/research/chat` для гибкости (диалог источника можно открыть без выбора доски; при создании ноды board_id известен и передаётся в create payload).

**Реализация Варианта A:**

- Роут: `apps/backend/app/routes/research.py` с префиксом `/api/v1/research`.
- Контроллер: **ResearchController** (см. п. 2.0). Роут получает orchestrator, создаёт `ResearchController(orchestrator)`, вызывает `controller.process_request(message=request.message, session_id=request.session_id, chat_history=request.chat_history)` и формирует ответ из полей результата: `narrative`, `tables`, `sources`, `session_id`.
- Схемы: `ResearchChatRequest`, `ResearchChatResponse` в `app/schemas/` (например `research.py`). В `ResearchChatResponse` — поля `narrative`, `tables`, `sources`, `session_id`, при необходимости `plan`, `execution_time_ms`.

---

## 3. План реализации (Frontend): ResearchSourceDialog

### 3.1. Целевой UX (по SOURCE_NODE_CONCEPT_V2, раздел 7)

- **Слева**: полноценный чат с AI (как в AIAssistantPanel): приветствие, история сообщений, индикация «AI думает…», поле ввода и кнопка «Отправить».
- **Справа**: блок «Результат исследования»:
  - Текст (narrative) с возможностью «Показать полностью».
  - Таблицы: табы по именам таблиц, под каждым табом — превью таблицы (колонки + несколько строк).
  - Блок «Источники»: список ссылок (url + title).
- **Футер**: «Отмена» и «🔍 Создать источник» (активна, когда есть хотя бы один ответ с контентом или таблицами; по желанию — всегда активна с сохранением последнего результата в ноду).

### 3.2. Структура компонентов

- **ResearchSourceDialog** — корневой диалог с layout «две колонки» (как в макете из SOURCE_NODE_CONCEPT_V2).
- **Левая колонка**: компонент чата (можно вынести общую часть с AIAssistantPanel в переиспользуемый `ChatPanel` или реализовать локально):
  - Список сообщений (user / assistant).
  - Состояние загрузки/стриминга (если позже добавим стриминг для research).
  - Textarea + кнопка отправки.
  - При открытии диалога — при необходимости отправить приветственное сообщение или первый запрос из `initial_prompt` (если перешли из «создать с промптом»).
- **Правая колонка**: `ResearchResultPreview`:
  - Секция «Текст»: narrative, сворачиваемый блок при длинном тексте.
  - Секция «Таблицы»: табы по `tables[].name`, для выбранной таблицы — таблица (колонки + строки), например через существующий компонент превью таблиц, если есть.
  - Секция «Источники»: список ссылок (открытие в новой вкладке).

### 3.3. Состояние и API

- **Состояние диалога** (useState или zustand slice):
  - `messages: { role, content }[]`
  - `sessionId: string | null`
  - `researchResult: { narrative, tables, sources } | null` — последний ответ от research/chat.
  - `isLoading: boolean`
- **Вызов API**: при отправке сообщения вызывать `POST /api/v1/research/chat` с `message` и при наличии `sessionId`/`chat_history`. В ответ класть narrative, tables, sources в `researchResult` и добавлять ответ ассистента в `messages`.
- **Создание источника**: по кнопке «Создать источник» вызывать существующий `createSourceNode` с типом RESEARCH и config:
  - `initial_prompt`: первый запрос пользователя (или объединённый контекст первого сообщения).
  - `conversation_history`: массив `messages` (для воспроизведения диалога при refresh).
  - При наличии — сохранить в content ноды последний `researchResult` (text + tables), чтобы нода сразу имела данные без повторного запуска (опционально, можно оставить только config и при первом открытии/refresh запускать исследование по `initial_prompt`/history).

### 3.4. Детали UI

- Заголовок диалога: «🔍 AI Research — [имя/превью]» или «🔍 AI Research» до именования.
- Имя ноды при создании: из первого предложения запроса (как сейчас) или редактируемое поле в футере.
- Адаптивность: на узких экранах можно показывать чат и превью табами (Чат | Результат) вместо двух колонок.
- Доступность: фокус в поле ввода при открытии, корректные aria-labels для списка сообщений и таблиц.

### 3.5. Порядок внедрения (Frontend)

1. Добавить API-метод и типы для `POST /api/v1/research/chat` и ответа (narrative, tables, sources).
2. Реализовать layout ResearchSourceDialog: две колонки (слева чат, справа превью).
3. Реализовать левую часть: список сообщений + ввод + вызов research/chat, обновление `researchResult`.
4. Реализовать правую часть: отображение narrative, табы таблиц, превью таблицы, блок источников.
5. Подключить кнопку «Создать источник» и сохранение config (+ при необходимости content) через существующий create flow.
6. При необходимости — начальная подстановка `initial_prompt` (например при открытии из витрины с предзаполненным промптом).

---

## 3.6. Детальная проработка ResearchSourceDialog (UX-спецификация)

### Layout (десктоп)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 🔍 AI Research — [Название / «Новое исследование»]                         [✕]  │
├──────────────────────────────────────┬──────────────────────────────────────────┤
│                                      │                                          │
│  ┌─ AI Ассистент ───────────────────┐│  ┌─ Результат исследования ──────────────┐│
│  │                                   ││  │                                        ││
│  │  🤖 Привет! Я помогу найти и      ││  │  📝 Текст                               ││
│  │  структурировать данные из        ││  │  ─────────────────────────────────────  ││
│  │  открытых источников.             ││  │  [narrative или «Задайте вопрос»]       ││
│  │  Задайте вопрос или опишите       ││  │  [Показать полностью] (если длинный)     ││
│  │  задачу.                          ││  │                                        ││
│  │  ─────────────────────────────────  ││  │  📊 Таблицы                             ││
│  │  👤 Найди статистику продаж       ││  │  [Таб: by_brand] [by_region] [monthly]  ││
│  │  электромобилей в России 2024     ││  │  ┌──────────────────────────────────┐  ││
│  │  ─────────────────────────────────  ││  │  │ brand  │ 2023  │ 2024  │ +%     │  ││
│  │  🤖 Запускаю исследование...       ││  │  │--------|-------|-------|--------|  ││
│  │  ✅ Найдено 12 источников         ││  │  │ LIVAN  │ 5200  │ 12100 │ +133   │  ││
│  │  ✅ Загружено 8 страниц            ││  │  │ ...    │       │       │        │  ││
│  │  ✅ Готово!                        ││  │  └──────────────────────────────────┘  ││
│  │  ─────────────────────────────────  ││  │                                        ││
│  │  👤 Уточни по регионам              ││  │  🔗 Источники                           ││
│  │  ─────────────────────────────────  ││  │  • autostat.ru                           ││
│  │  🤖 [ответ]                         ││  │  • rbc.ru                                ││
│  │  ─────────────────────────────────  ││  │                                        ││
│  │  ┌────────────────────────────────┐ ││  └────────────────────────────────────────┘│
│  │  │ Введите сообщение...           │ ││                                          │
│  │  └────────────────────────────────┘ ││                                          │
│  │  [Отправить]                        ││                                          │
│  └─────────────────────────────────────┘│                                          │
│                                      │                                          │
├──────────────────────────────────────┴──────────────────────────────────────────┤
│                              [Отмена]              [🔍 Создать источник]        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Левая панель (чат)

| Элемент | Поведение |
|--------|-----------|
| Заголовок секции | «AI Ассистент» или «Чат» |
| Приветствие | Одно сообщение от assistant при пустой истории: «Привет! Я помогу найти и структурировать данные из открытых источников. Задайте вопрос или опишите задачу.» |
| Список сообщений | Скролл, сообщения user — справа (или отдельный стиль), assistant — слева. Поддержка markdown в ответах (как в AIAssistantPanel). |
| Индикация выполнения | При `isLoading`: под последним сообщением блок «⏳ Запускаю исследование…» или пошаговый статус (Discovery → Research → …), если API будет отдавать шаги. |
| Поле ввода | Textarea, placeholder: «Опишите, какие данные найти…», Enter — отправка (Shift+Enter — новая строка). |
| Кнопка «Отправить» | Иконка Send, неактивна при пустом вводе или isLoading. |

### Правая панель (превью результата)

| Секция | Содержимое | Поведение |
|--------|------------|-----------|
| **Единый плейсхолдер** | Нет narrative, таблиц и источников | Одна строка: «Данные появятся по результатам исследования.» (вместо трёх отдельных плейсхолдеров по секциям). |
| **Текст** | `researchResult.narrative` | При наличии данных — отображение; при длинном тексте — по возможности «Показать полностью». Сообщения ассистента в чате — Markdown (remark-gfm). |
| **Таблицы** | `researchResult.tables` | Табы по `table.name`, превью строк и колонок. |
| **Источники** | `researchResult.sources` | Список ссылок (title / домен), открытие в новой вкладке. |

### Футер

- **Отмена** — закрытие диалога без сохранения.
- **Создать источник** — вызов `createSourceNode` с `source_type: research`, `config: { initial_prompt, conversation_history }`. Имя ноды: из первого сообщения пользователя (обрезать до 50 символов) или поле «Название источника» в футере. После успешного создания — закрыть диалог и показать ноду на доске. Кнопка активна всегда (источник можно создать и с пустым результатом — тогда при refresh запустится исследование по history).

### Состояния правой панели

1. **Нет ответа** — плейсхолдеры в каждой секции.
2. **Идёт запрос** — те же плейсхолдеры, опционально «Обновляю результат…» в шапке правой панели.
3. **Есть результат** — заполнены текст, табы таблиц, источники (какие есть).
4. **Ошибка** — в правой панели или под чатом показать сообщение об ошибке, предложить повторить.

### Переиспользование компонентов

- **Сообщения чата**: по возможности общий компонент `MessageBubble` (как в AIAssistantPanel) с поддержкой role и markdown.
- **Превью таблицы**: использовать существующий компонент таблицы из проекта (например для ContentNode preview) или простую `<table>` с заголовками и `rows.slice(0, 50)`.
- **Layout двух колонок**: фиксированное соотношение ширины (например 45% / 55% или 1fr 1fr), min-width для правой панели, чтобы таблицы не сжимались в нитку.

### Адаптивность

- **Узкий экран** (< 768px): переключение на табы «Чат» | «Результат» вместо двух колонок, чтобы не теснить чат и таблицы.

---

## 4. Порядок работ (сводка) — выполнено

| # | Задача | Файлы / зона |
|---|--------|---------------|
| 0 | **ResearchController** + `_build_research_request` (вопрос первым, формат в конце) | `app/services/controllers/research_controller.py` |
| 1 | `ControllerResult.tables/sources`, `ExtractionResult.is_success`, `to_content_dict()` | `base_controller.py`, `app/sources/base.py` |
| 2 | ResearchSource → ResearchController | `app/sources/research/extractor.py` |
| 3–4 | SourceNodeService: RESEARCH create/extract, `data` при create | `app/services/source_node_service.py` |
| 5 | `POST /api/v1/research/chat` | `app/routes/research.py`, `app/schemas/research.py` |
| 6–9 | Frontend: API, типы, диалог, create с `data` | `apps/web/src/...` |
| — | Discovery: off-topic фильтр (кино/сериалы при запросах про авто/данные и т.п.) | `app/services/multi_agent/agents/discovery.py`; см. [MULTI_AGENT.md](./MULTI_AGENT.md) |
| — | Structurizer: устойчивость к не-JSON ответам LLM, санитизация контента | `app/services/multi_agent/agents/structurizer.py` |

---

## 5. Связанные документы

- [SOURCE_NODE_CONCEPT.md](./SOURCE_NODE_CONCEPT.md) — раздел 7 (AI Research Dialog)
- [MULTI_AGENT.md](./MULTI_AGENT.md) — Research pipeline, форматы AgentPayload
- [API.md](./API.md) — актуализация после добавления `POST /api/v1/research/chat`
- [BOARD_SYSTEM.md](./BOARD_SYSTEM.md) — тип источника research, refresh
