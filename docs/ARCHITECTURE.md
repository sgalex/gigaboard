# Архитектура проекта GigaBoard

## 🎯 Executive Summary

**GigaBoard** — клиент-серверное **рабочее приложение** для **аналитики и обработки данных с помощью ИИ**: на **Data-Centric Canvas** задан **граф пайплайна** (источники → трансформации → виджеты и выводы), а **LLM и мультиагентная оркестрация** выполняют пользовательские запросы, генерируют код и ведут диалог в контексте доски; дополнительно — **дашборды**, **фильтрация** по измерениям, **real-time** коллаборация. Ключевая модель данных: явное разделение **SourceNode** и **ContentNode**, что даёт **lineage**, streaming и **replay** при пересчёте.

### Ключевые архитектурные решения
- **4 типа узлов**: SourceNode (источники) → ContentNode (данные) → WidgetNode (визуализации) + CommentNode (аннотации)
- **5 типов связей**: TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN
- **Multi-Agent система**: единый Orchestrator, **9 ролей в плане** (planner … reporter) плюс служебные шаги (`context_filter` и др.); финальная проверка качества — **QualityGateAgent** под ключом плана `validator` (см. [`MULTI_AGENT.md`](MULTI_AGENT.md))
- **Real-time first**: Socket.IO + Redis pub/sub для мгновенной синхронизации
- **Streaming support**: WebSocket/SSE источники с аккумуляцией и архивированием

---

## Общий обзор

GigaBoard — клиент-серверное **приложение-инструмент**: визуальный канвас, REST и Socket.IO связывают пользователя, **граф пайплайна** и слой **ИИ** (ассистент, оркестратор агентов, контроллеры сценариев).

### Ключевая концепция: манипуляция данными через ИИ на Data-Centric Canvas

Пользователь управляет данными **через ИИ-инструменты** (ассистент, генерация кода трансформаций и виджетов, исследовательские сценарии и т.д.) и через явный граф на доске. **Data-Centric Canvas** — это полотно, на котором **закреплены** результаты: узлы и рёбра показывают, **что** произошло с данными и **в каком порядке**.

UI представляет бесконечное полотно (React Flow), где на канвасе размещаются **узлы четырёх типов**:

1. **SourceNode** 🆕 - точки входа данных: файлы, подключения к СУБД, API endpoints, **тип `research`** (чат исследования → Orchestrator), прочие AI-промпты, streaming источники
2. **ContentNode** 🆕 - результаты обработки данных: текстовые резюме + структурированные таблицы (N tables)
3. **WidgetNode** - визуализации ContentNode, HTML/CSS/JS код, сгенерированный AI-агентом
4. **CommentNode** - комментарии и аннотации к любым узлам

**Связи между узлами** означают преобразования и отношения:
- **TRANSFORMATION** - преобразование данных (ContentNode(s) → ContentNode) через произвольный Python код
- **VISUALIZATION** - визуализация данных (ContentNode → WidgetNode)
- **COMMENT** - комментирование (CommentNode → любой узел)
- **REFERENCE**, **DRILL_DOWN** - ссылки и детализация

> **Архитектура Source-Content**: SourceNode **наследует** ContentNode и содержит как конфигурацию источника, так и извлечённые данные. Отдельный тип связи EXTRACT не нужен — данные хранятся непосредственно в SourceNode. См. [SOURCE_NODE_CONCEPT.md](SOURCE_NODE_CONCEPT.md) для деталей.

Сервер обеспечивает API для управления узлами и связями, real-time обновления через Socket.IO, мультиагентную оркестрацию через GigaChat (langchain-gigachat) и безопасное выполнение трансформаций в sandbox.

## Компоненты системы

### 1. Frontend (React)
**Назначение**: UI-полотно, редактирование и взаимодействие с SourceNode/ContentNode/WidgetNode/CommentNode, чат с AI.
**Ответственность**: 
- Рендер бесконечного канваса (React Flow) с четырьмя типами узлов: SourceNode, ContentNode, WidgetNode, CommentNode
- Визуализация связей: TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN
- Локальное состояние доски (Zustand) + кэш запросов (TanStack Query)
- Real-time синхронизация по Socket.IO client
- UI-кит ShadCN (формы, панели, модальные окна)
- **AI Assistant Panel** в правом боковом панеле с историей диалога и рекомендациями
- Отображение графа зависимостей и data lineage
- **Streaming indicators** 🔴 LIVE badges для real-time источников
**Интерфейсы**: REST/JSON к FastAPI, Socket.IO events.

### 2. Backend API (FastAPI)
**Назначение**: CRUD для бордов, узлов (SourceNode/ContentNode/WidgetNode/CommentNode), трансформаций, аутентификация, управление сессиями.
**Ответственность**:
- REST API для бордов, узлов всех типов, связей (edges), трансформаций, ассетов
- **Управление источниками данных**: извлечение (extract), валидация, refresh, архивирование
- **Управление трансформациями**: создание, выполнение, версионирование, replay (5 режимов)
- **Streaming support**: WebSocket/SSE/Kafka handlers, аккумуляция + архивирование
- Аутентификация и авторизация (JWT)
- Валидация контрактов (Pydantic v2)
**Интерфейсы**: HTTP/JSON, OpenAPI/Swagger UI.

### 3. Real-time Gateway (FastAPI + Socket.IO)
**Назначение**: События совместного редактирования и обновлений состояния узлов.
**Ответственность**:
- Комнаты по boardId, события добавления/перемещения/удаления узлов (SourceNode/ContentNode/WidgetNode/CommentNode)
- События создания/удаления связей (TRANSFORMATION, VISUALIZATION, COMMENT)
- **Streaming events**: real-time обновления ContentNode от streaming источников
- События выполнения трансформаций и обновления данных
- Транзит событий через Redis pub/sub для масштабирования по инстансам
**Интерфейсы**: Socket.IO (ws + fallback), Redis pub/sub.

### 4. Multi-Agent Orchestration Layer (GigaChat + Redis MessageBus)
**Назначение**: Интерпретация естественного языка, управление командой специализированных AI агентов через единый Orchestrator, генерация кода трансформаций и виджетов, анализ данных.

**Статус**: ✅ Реализовано (Multi-Agent). См. [`docs/MULTI_AGENT.md`](MULTI_AGENT.md) для полной спецификации.

#### Архитектура

```mermaid
flowchart TB
    subgraph Routes["FastAPI Routes"]
        R1["content_nodes.py"]
        R2["ai_assistant.py"]
        R3["research.py"]
        R4["admin.py Playground"]
    end

    subgraph Controllers["Satellite Controllers"]
        C1["TransformationController"]
        C2["WidgetController"]
        C3["AIAssistantController"]
        C4["TransformSuggestionsController"]
        C5["WidgetSuggestionsController"]
        C6["ResearchController"]
    end

    subgraph Orchestrator["Orchestrator (Single Path)"]
        O["process_request()"]
        P["PlannerAgent → Plan"]
        E["Execute Steps"]
        V["QualityGateAgent\n(plan key: validator)"]
        O --> P --> E --> V
    end

    subgraph Agents["Core (реестр оркестратора)"]
        A1["PlannerAgent"]
        A2["StructurizerAgent"]
        A3["AnalystAgent"]
        A4["TransformCodexAgent"]
        A4b["WidgetCodexAgent"]
        A5["ReporterAgent"]
        A6["DiscoveryAgent"]
        A7["ResearchAgent"]
        A8["ContextFilterAgent"]
        A9["QualityGateAgent\n(→ ключ validator)"]
    end

    R1 --> C1 & C2
    R2 --> C3
    R3 --> C6
    R4 --> C6
    C1 & C2 & C3 & C4 & C5 & C6 --> O
    E --> A1 & A2 & A3 & A4 & A4b & A5 & A6 & A7 & A8 & A9
```

#### Ключевые компоненты

**AgentPayload** — универсальный формат данных для всех агентов:
- `narrative` — текстовый ответ (markdown)
- `tables` — структурированные таблицы (PayloadContentTable)
- `code_blocks` — блоки кода (CodeBlock с purpose: transformation/widget/analysis)
- `findings` — инсайты, предупреждения, рекомендации
- `plan` — план выполнения (Plan + PlanStep)
- `validation` — результат валидации (ValidationResult)
- `sources` — источники данных
- `suggestions` — предложения пользователю

**Orchestrator** — единый путь выполнения:
1. PlannerAgent создаёт план (список шагов с агентами)
2. Последовательное выполнение шагов: каждый агент получает `pipeline_context` (мутабельный dict) и `agent_results` (хронологический list всех предыдущих AgentPayload)
3. `execution_context` — отдельный канал для тяжёлых данных (DataFrame), не попадающих в промпты
4. **QualityGateAgent** (в реестре и плане под ключом `validator`) проверяет итог пайплайна; отдельный **`ValidatorAgent`** (`validator.py`) используется для проверки сгенерированного Python-кода в сценариях трансформаций, не как замена Quality Gate в оркестраторе
5. Adaptive replanning при необходимости

**Основные агенты оркестратора** (см. также [`MULTI_AGENT.md`](MULTI_AGENT.md)):
| Ключ плана   | Класс                 | Роль                                         |
| ------------ | --------------------- | -------------------------------------------- |
| planner      | `PlannerAgent`        | Декомпозиция запроса на план выполнения      |
| structurizer | `StructurizerAgent`   | Извлечение таблиц из текста/данных           |
| analyst      | `AnalystAgent`        | Анализ данных, инсайты, паттерны             |
| transform_codex | `TransformCodexAgent` | Генерация Python кода (трансформации данных) |
| widget_codex | `WidgetCodexAgent`    | Генерация HTML/CSS/JS виджетов               |
| reporter     | `ReporterAgent`       | Финальный отчёт в markdown                   |
| discovery    | `DiscoveryAgent`      | Поиск и каталогизация источников данных      |
| research     | `ResearchAgent`       | Загрузка контента по URL из результатов Discovery (не путать с типом SourceNode `research`) |
| context_filter | `ContextFilterAgent` | Подготовка контекста (в т.ч. для кросс-фильтра и тулов) |
| validator    | `QualityGateAgent`    | Финальная проверка качества ответа / `suggested_replan` |

**Satellite Controllers** (обёртки → Orchestrator; в таблице — основные сценарии мультиагента):
| Контроллер                       | Роль                                      |
| -------------------------------- | ----------------------------------------- |
| `TransformationController`       | Генерация/выполнение Python трансформаций |
| `WidgetController`               | Генерация HTML виджетов                   |
| `AIAssistantController`          | Чат-ассистент (панель AI)                 |
| `TransformSuggestionsController` | Предложения трансформаций                 |
| `WidgetSuggestionsController`    | Предложения виджетов                      |
| `ResearchController`             | Источник AI Research и `POST /api/v1/research/chat`: единый вызов Orchestrator, извлечение narrative/tables/sources |

Админский **Playground** мультиагента вызывает тот же Orchestrator напрямую из `admin.py` (см. [ADMIN_AND_SYSTEM_LLM.md](./ADMIN_AND_SYSTEM_LLM.md)).

**Ответственность**:
- Парсинг пользовательских запросов через PlannerAgent
- Управление межагентной коммуникацией через Redis MessageBus (pub/sub)
- Генерация Python кода для трансформаций (TransformCodexAgent)
- Генерация HTML/CSS/JS виджетов (WidgetCodexAgent)
- Анализ данных и генерация инсайтов (AnalystAgent)
- Структуризация данных в таблицы (StructurizerAgent)
- Валидация итога пайплайна (QualityGateAgent, ключ `validator`)
- Adaptive replanning при неудачных шагах
- Retry с exponential backoff для агентов
- Сохранение истории диалога, метрик выполнения

**Файловая структура**:
```
apps/backend/app/services/
├── multi_agent/
│   ├── orchestrator.py          # Orchestrator
│   ├── message_bus.py           # Redis pub/sub
│   ├── schemas/
│   │   └── agent_payload.py     # AgentPayload (универсальный формат)
│   └── agents/
│       ├── base.py              # BaseAgent
│       ├── planner.py           # PlannerAgent
│       ├── structurizer.py      # StructurizerAgent
│       ├── analyst.py           # AnalystAgent
│       ├── transform_codex.py   # TransformCodexAgent
│       ├── widget_codex.py      # WidgetCodexAgent
│       ├── reporter.py          # ReporterAgent
│       ├── discovery.py         # DiscoveryAgent
│       ├── research.py          # ResearchAgent
│       └── validator.py         # ValidatorAgent
├── controllers/
│   ├── base_controller.py       # BaseController + ControllerResult
│   ├── transformation_controller.py
│   ├── widget_controller.py
│   ├── ai_assistant_controller.py
│   ├── research_controller.py     # AI Research source + research/chat
│   ├── transform_suggestions_controller.py
│   └── widget_suggestions_controller.py
```

**Интерфейсы**: Controllers → Orchestrator → Agents → LLMRouter → GigaChat / внешний LLM, Redis MessageBus.

### 5. Data Layer
**Назначение**: Хранение бордов, узлов (SourceNode/ContentNode/WidgetNode/CommentNode), связей, трансформаций, дашбордов, фильтров, пользовательских профилей.
**Технологии**: PostgreSQL + SQLAlchemy.
**Ответственность**:
- Схемы БД:
  - **boards**, **projects**: каталог проектов и досок
  - **source_nodes**, **content_nodes**, **widget_nodes**, **comment_nodes**: узлы канваса (Source-Content архитектура)
  - **edges**: связи между узлами (TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN)
  - **uploaded_files**: загруженные файлы
  - **users**, **user_sessions**: пользователи и сессии
  - **user_ai_settings**, **user_secrets**: персональные AI/LLM-настройки и зашифрованные секреты
  - **agent_sessions**, **chat_messages**: сессии AI и чат
  - **dashboards**, **dashboard_items**: дашборды и элементы (виджет/таблица/текст/изображение/линия)
  - **dashboard_share**: шаринг дашбордов (публичный URL)
  - **project_widget**, **project_table**: библиотека виджетов и таблиц проекта
  - **dimensions**, **dimension_column_mappings**: измерения для Cross-Filter (см. [CROSS_FILTER_SYSTEM.md](CROSS_FILTER_SYSTEM.md))
  - **filter_presets**: сохраняемые наборы фильтров по проекту
- Миграции: Alembic

### 6. Tool Sandbox & Execution Environment
**Назначение**: Безопасное выполнение кода трансформаций (Python в sandbox; см. `PythonExecutor` и контроллеры трансформаций).
**Технологии**: Docker контейнеры OR процессная изоляция с resource limits.
**Ответственность**:
- Валидация и линтинг кода трансформаций перед выполнением
- Изоляция выполнения (timeout, memory limit, disk limit)
- Capture output/errors/logs
- Версионирование трансформаций
- Поддержка множественных входов (source ContentNodes) для трансформаций
- Автоматический replay трансформаций при обновлении source данных (5 режимов: throttled, batched, manual, intelligent, selective)

### 7. Tool Registry
**Назначение**: Хранилище встроенных и пользовательских инструментов.
**Технологии**: PostgreSQL + Redis cache.
**Ответственность**:
- Регистрация инструментов (встроенные: SQL, HTTP, file operations, web scraping)
- Версионирование кода инструментов
- Метрики использования и производительности
- Управление доступом и разрешениями

### 8. Node Management System
**Назначение**: Позволяет агентам и пользователям активно строить доски, размещая узлы (SourceNode/ContentNode/WidgetNode/CommentNode) и создавая связи между ними.
**Компоненты**:
- **SourceNode Manager**: 🆕 CRUD для источников данных (extract, validate, refresh, archive)
- **ContentNode Manager**: 🆕 CRUD для обработанных данных (text + N tables)
- **WidgetNode Manager**: Управление визуализациями (создание из ContentNode, обновление кода, удаление)
- **CommentNode Manager**: Управление комментариями (создание, редактирование, удаление)
- **Edge Manager**: Управление связями между узлами (типы: TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN)
- **Transformation Manager**: Управление трансформациями (создание, выполнение, replay, версионирование)
- **Layout Planner**: Генерирует оптимальные лэйауты узлов (flow, grid, hierarchy, freeform)
- **Board History**: Отслеживает изменения доски, поддерживает версионирование

**Ответственность**:
- Позволяет пользователю создавать SourceNode (в т.ч. тип **`research`** — данные из мультиагентного исследования через `ResearchController`)
- Позволяет пользователю и **TransformCodex** / pipeline создавать ContentNode с результатами трансформаций
- Позволяет **WidgetCodex** / **WidgetController** создавать WidgetNode с визуализациями ContentNode
- Валидирует создание связей (проверка типов, циклические зависимости)
- Управляет графом зависимостей (data lineage): SourceNode → ContentNode → WidgetNode
- Отслеживает изменения SourceNode и триггерит refresh ContentNode
- Отслеживает изменения source ContentNode и триггерит replay трансформаций
- Отправляет real-time обновления через Socket.IO
- Сохраняет историю редактирования и код трансформаций
- Поддерживает откат к предыдущим версиям

### 9. Cache/Queue
**Назначение**: Быстрый доступ к сессионным данным и pub/sub для real-time, межагентная коммуникация.
**Технологии**: Redis.
**Ответственность**: 
- Кэш подсказок AI, результатов запросов
- Message Bus для inter-agent communication (pub/sub)
- Throttle для частых операций
- WebSocket events broadcast

## Взаимодействие компонентов

```mermaid
flowchart TB
    FE[Frontend: React + React Flow]
    API[Backend: FastAPI]
    RT[Real-time Gateway: Socket.IO]
    MA[Multi-Agent Orchestration]
    DB[(PostgreSQL)]
    REDIS[(Redis)]
    
    FE -->|REST CRUD| API
    FE -->|Socket.IO events| RT
    FE -->|AI Chat| MA
    
    API --> DB
    RT --> REDIS
    MA --> REDIS
    
    MA --> PA[PlannerAgent]
    MA --> DA[DiscoveryAgent]
    MA --> RA[ResearchAgent]
    MA --> SA[StructurizerAgent]
    MA --> AA[AnalystAgent]
    MA --> CX[TransformCodexAgent]
    MA --> WC[WidgetCodexAgent]
    MA --> REP[ReporterAgent]
    MA --> QG[QualityGate\n(plan: validator)]
    
    MA -->|LangChain| GC[GigaChat API]
    
    style MA fill:#e1f5ff
    style FE fill:#fff4e6
    style DB fill:#f3e5f5
    style REDIS fill:#ffe0e0
```

## Поток данных (примеры)

### Пример 1: Простой запрос (упрощённо)
1) Пользователь: "Покажи продажи по регионам"
2) Orchestrator → Planner → шаги по плану (при необходимости Discovery → Research → Structurizer → Analyst → Reporter)
3) Результат → отчёт/таблицы/виджет на доске в зависимости от сценария

### Пример 2: Исследование с внешними источниками (соответствует текущему пайплайну)
1) Пользователь: "Найди публичные данные по теме X и сравни с нашими продажами"
2) Orchestration → Planner (разбивает на подзадачи)
3) **Discovery** → **Research** (загрузка страниц) → **Structurizer** → **Analyst** → **Reporter**
4) При необходимости — шаг **validator** (`QualityGateAgent`), **replan**
5) Результат — narrative, таблицы, при необходимости код виджета через **WidgetCodex** в отдельном сценарии

## Технологический стек

- Язык: TypeScript (FE), Python 3.11+ (BE)
- Фреймворк: React + Vite (FE), FastAPI (BE)
- Real-time: Socket.IO (client/server), Redis pub/sub
- AI: langchain-gigachat
- База данных: PostgreSQL + SQLAlchemy
- Инфраструктура: .venv для Python, npm для FE; Docker позже (не приоритет сейчас)
- Тестирование: Vitest + React Testing Library; pytest + pytest-asyncio
- Качество: mypy, ESLint + Prettier

## Требования к масштабируемости и производительности (MVP)
- Поддержка 50-100 одновременных пользователей на борд без ощутимых задержек
- Latency real-time событий < 150 мс при локальной сети, < 400 мс при WAN
- REST API P95 < 300 мс на CRUD-операции бордов/виджетов
- Горизонтальное масштабирование real-time через Redis pub/sub и несколько приложений FastAPI/Socket.IO

### 10. Cross-Filter System
**Назначение**: Глобальная фильтрация данных на досках и дашбордах по измерениям (Dimensions), click-to-filter из виджетов, пресеты фильтров.
**Компоненты**: DimensionService, FilterPresetService, FilterEngine; API: `/api/v1/boards/{id}/filters`, `/api/v1/dashboards/{id}/filters`, `/api/v1/projects/{id}/dimensions`, `/api/v1/projects/{id}/filter-presets`.
**Детали**: см. [CROSS_FILTER_SYSTEM.md](CROSS_FILTER_SYSTEM.md).

### 11. Dashboard System
**Назначение**: Презентационный слой — дашборды из виджетов/таблиц/текста/изображений/линий с свободным размещением, z-order, вращением.
**Компоненты**: DashboardService, ShareService; API: `/api/v1/dashboards`, `/api/v1/public/dashboards/{token}`.
**Детали**: см. [DASHBOARD_SYSTEM.md](DASHBOARD_SYSTEM.md).

---

**Состояние**: Актуализировано  
**Последнее обновление**: 2026-03-01 (Cross-Filter, Dashboard, Data Layer, диаграмма агентов)
