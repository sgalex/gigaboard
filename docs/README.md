# GigaBoard — AI-Powered Analytics Dashboard

**Последнее обновление**: 4 февраля 2026 | **Статус**: 🚀 Multi-Agent System + 🆕 Source-Content + 🎨 Widget Generation + 💬 Transform Dialog + ✅ Extraction Complete + 🔧 **Transform Logic Fixed!**

---

## 📖 Что это?

**GigaBoard** — умная аналитическая доска с бесконечным полотном. Пользователи создают интерактивные дашборды из виджетов (графики, таблицы, текст), связывают их между собой, а **AI-ассистент** помогает генерировать визуализации и отвечает на вопросы на естественном языке.

### Ключевые возможности
- 🎨 Бесконечное полотно с любыми виджетами (React Flow)
- 🤖 AI Assistant Panel для диалога в контексте доски
- 🔗 6 типов связей между узлами (EXTRACT, TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN)
- 👥 Real-time совместная работа
- 🔄 **Мульти-агентная система с интеллектуальным поиском данных** (работает! ✅)
- ⚙️ Динамическая генерация инструментов (Python/SQL/JS)
- 🆕 **Source-Content Node Architecture** — чёткое разделение источников и данных
- 🎨 **AI-генерация визуализаций** — Reporter Agent создаёт виджеты из данных (работает! ✅)
- ✅ **Extraction Logic** — 6 extractors реализованы и протестированы! (NEW! 01.02.2026)

---

## 🎯 Текущий статус (2026-02-01)

### ✅ Завершено
- **Backend Restructuring**: Создана папка `core/` для инфраструктуры
- **Multi-Agent Infrastructure**: Message Bus, BaseAgent, 8+ специализированных агентов
- **🆕 Search → Research → Analyze Pattern** (КРИТИЧЕСКИЙ ПАТТЕРН):
  - SearchAgent находит URL в интернете
  - ResearcherAgent загружает полное содержимое страниц (HTML→текст)
  - AnalystAgent анализирует реальные данные (40x больше чем snippets)
  - **Протестировано**: 4/5 страниц загружено, 20KB данных, 28 секунд
- **MultiAgentEngine**: Единый фасад для управления всей системой
- **Graceful Shutdown**: Корректная остановка сервера
- **🆕 Adaptive Planning с Full Replan**:
  - GigaChat анализирует результаты после каждого успешного шага
  - Полное перепланирование с передачей всех накопленных знаний
  - AI-powered error evaluation (интеллектуальная классификация ошибок)
  - Консервативные решения для оптимального баланса (temperature=0.3)
  - **Протестировано**: Механизм работает, логирование решений в реальном времени
- **🆕 AI Resolver System** (31.01.2026):
  - ResolverAgent для batch AI resolution в трансформациях
  - `gb.ai_resolve_batch()` доступен в сгенерированном коде
  - Прямой вызов агента (без HTTP) через nest_asyncio
  - Chunking (50 значений), graceful error handling
  - Context-aware routing (direct GigaChat vs MessageBus)
  - **Протестировано**: "добавь столбец с полом человека" — работает!
- **🆕 WidgetNode Generation System** (01.02.2026):
  - Reporter Agent создаёт HTML/CSS/JS визуализации из ContentNode
  - Endpoint: `POST /api/v1/content-nodes/{id}/visualize`
  - AI-генерация: bar charts, line charts, tables, KPI cards, custom visualizations
  - Автоматическое создание VISUALIZATION edges
  - Валидация безопасности (только CDN, no eval/Function)
  - **Протестировано**: API работает, генерирует полный HTML код!
- **🆕 Source-Content Node Architecture** (Phase 1, 29-30.01.2026):
  - Database schema + models для SourceNode, ContentNode
  - Backend services с CRUD + lineage
  - API endpoints (12+ routes)
  - Frontend types + API client + Zustand store
  - React компоненты: SourceNodeCard, ContentNodeCard
  - 6 extractors структура (file, database, api, prompt, stream, manual)
- **✅ Extraction Logic COMPLETE** (01.02.2026) 🎉:
  - **FileExtractor**: CSV, JSON, Excel, Parquet, TXT — полная реализация
  - **ManualExtractor**: text, json, table, CSV parsing
  - **APIExtractor**: GET/POST/PUT/DELETE, auth, retry logic, JSON parsing
  - **DatabaseExtractor**: PostgreSQL, MySQL, SQLite — async queries
  - **PromptExtractor**: GigaChat интеграция, AI-generated data
  - **StreamExtractor**: Stub для Phase 4 (как планировалось)
  - **SourceNodeService**: `extract_data()` с передачей db/gigachat
  - **API Routes**: `/extract` и `/refresh` работают end-to-end
  - **Frontend**: extractFromSource() + UI кнопка "Извлечь данные"
  - **Tests**: 10/10 unit tests passed ✅
  - См. [EXTRACTION_LOGIC_COMPLETED_20260201.md](./history/EXTRACTION_LOGIC_COMPLETED_20260201.md)
- **📚 Документация актуализирована** (30.01-01.02.2026):
  - ARCHITECTURE.md — обновлён под Source-Content
  - CONNECTION_TYPES.md — добавлен EXTRACT edge
  - NODE_MANAGEMENT_SYSTEM.md — полная актуализация
  - WIDGETNODE_GENERATION_SYSTEM.md — ContentNode integration
  - API.md — новые endpoints (SourceNode, ContentNode, visualize, AI Resolver)
  - AI_RESOLVER_SYSTEM.md — полная документация AI Resolver
  - WIDGET_GENERATION_QUICKSTART.md — примеры использования (NEW!)
- **🆕 Extract Dialog System** (01.02.2026) ✅:
  - Унификация UX с Transform — кнопка на toolbar вместо card
  - ExtractDialog с tabs (Config + Params)
  - Адаптивные подсказки для 6 типов источников
  - Preview rows для File/Database
  - См. [EXTRACT_DIALOG_UNIFIED_UX_20260201.md](./history/EXTRACT_DIALOG_UNIFIED_UX_20260201.md)
- **🆕 Smart Node Placement System** (02.2026):
  - Автоматическое размещение нод без наложения друг на друга
  - `findOptimalNodePosition()` для создания новых нод (WidgetDialog, Backend API)
  - `findNearestFreePosition()` для коррекции ручного drag & drop (BoardCanvas)
  - AABB collision detection с padding 40px
  - Frontend: `apps/web/src/lib/nodePositioning.ts`
  - Backend: `apps/backend/app/utils/node_positioning.py`
  - См. [SMART_NODE_PLACEMENT.md](./SMART_NODE_PLACEMENT.md)
- **🆕 Reporter Agent CDN Loading Fix** (02.2026):
  - Обновлены версии CDN библиотек (Chart.js@4, Plotly 2.35.2, D3@7, ECharts@5)
  - Паттерн `waitForLibrary()` для асинхронной загрузки
  - Исправлены DOM selector инструкции (без `#` для Plotly)
- **🆕 Canvas UI Polish** (02.2026):
  - Скрыта атрибуция React Flow
  - Подсказки отцентрированы внизу с полупрозрачностью
  - Исправлен resize capture для iframe-нод
- **🆕 Widget Suggestions System** (02.2026):
  - WidgetSuggestionAgent для AI-powered рекомендаций по улучшению виджетов
  - Анализ данных (column types, cardinality) + анализ кода (libraries, interactivity)
  - 5 типов рекомендаций: improvement, alternative, insight, library, style
  - HTTP endpoint: `POST /content-nodes/{id}/analyze-suggestions`
  - Singleton MultiAgentEngine с full Message Bus integration
  - Frontend: SuggestionsPanel в WidgetDialog (левая панель)
  - Backend + Frontend готовы ✅
  - См. [WIDGET_SUGGESTIONS_SYSTEM.md](./WIDGET_SUGGESTIONS_SYSTEM.md)
- **🆕 Transform Dialog Chat System** (02.2026):
  - Dual-panel layout: 40% chat + 60% preview/code
  - Итеративный AI-powered чат для создания трансформаций
  - TransformSuggestionsPanel с 5 категориями рекомендаций
  - Live preview результатов трансформации
  - Monaco Editor для ручного редактирования кода
  - Edit mode — возобновление существующих трансформаций
  - `crypto.randomUUID()` для уникальных ID сообщений
  - См. [TRANSFORM_DIALOG_CHAT_SYSTEM.md](./TRANSFORM_DIALOG_CHAT_SYSTEM.md)
- **🆕 Node Cards UI Polish** (02.2026):
  - **ContentNodeCard**: inline rename (double-click/menu), clickable table badges, компактный header
  - **WidgetNodeCard**: inline rename (double-click/menu), только верхний Handle (VISUALIZATION)
  - Единообразные размеры кнопок (h-8 w-8) в header обеих карточек
  - Edit2 иконка для rename в DropdownMenu
- **🔧 Transform Logic Fixed** (04.02.2026) ⭐:
  - **UPDATE вместо CREATE**: редактирование трансформации теперь обновляет существующую ноду
  - Backend: параметр `target_node_id` в `/transform/execute`
  - Frontend: различение CREATE vs UPDATE через флаг `updated`
  - Cascade deletion fix: полная замена массивов вместо merge
  - См. [history/SESSION_2026_02_04_UI_AND_TRANSFORM_FIXES.md](./history/SESSION_2026_02_04_UI_AND_TRANSFORM_FIXES.md)
- **🎨 Canvas & Widget UI Improvements** (04.02.2026):
  - **Zoom настройки**: minZoom=0.5, maxZoom=2, defaultZoom=1, убран auto-fitView
  - **Fullscreen виджеты**: кнопка Maximize, dialog 95vh, auto-reload
  - **Robust JSON parsing**: 4-step fallback для GigaChat responses, fix broken JSON
  - **Визуальная дифференциация**: синяя кнопка Трансформации, фиолетовая Визуализации
  - **Widget Suggestions**: увеличен max_tokens до 4000, улучшены инструкции промпта

### 🔥 В работе
- **🆕 Source-Content Extraction Logic** (Priority 1, 2-3 дня)
  - FileExtractor реализация (CSV, JSON, Excel)
  - ManualExtractor для пользовательского ввода
  - PromptExtractor для AI-генерации данных
  - APIExtractor для REST endpoints
  - DatabaseExtractor для SQL запросов
- **Frontend UI для виджетов** (Priority 2)
  - Кнопка "Visualize" на ContentNode
  - Modal с опциями визуализации
  - Iframe rendering с postMessage
- Интеграция Multi-Agent с AI Assistant Panel
- Расширение возможностей агентов

### 📋 Следующие задачи
- Source-Content Phase 3: React UI Components
- Source-Content Phase 4: Streaming Support
- Multi-Agent Phase 2: Orchestrator & Session Management
- Suggested Actions Execution
- Real-time прогресс в UI

---

## 📚 Документация (организована по ролям)

### 🎯 **Начните отсюда**

| Кто вы  | Прочитайте                               | Назначение                        |
| ------- | ---------------------------------------- | --------------------------------- |
| **Все** | [SPECIFICATIONS.md](./SPECIFICATIONS.md) | Требования системы (FR-1 до FR-8) |
| **Все** | [ARCHITECTURE.md](./ARCHITECTURE.md)     | Как устроена система              |
| **Все** | [API.md](./API.md)                       | REST и WebSocket endpoints        |

### 🤖 **AI Assistant Panel (FR-6)**

| Документ                                   | Содержание                                                 |
| ------------------------------------------ | ---------------------------------------------------------- |
| [AI_ASSISTANT.md](./AI_ASSISTANT.md)       | Полная спецификация компонента (сервис, API, примеры кода) |
| [UI_DESIGN.md](./UI_DESIGN.md)             | Макеты, компоненты, дизайн систем                          |
| [SYSTEM_DIAGRAMS.md](./SYSTEM_DIAGRAMS.md) | 6 диаграмм архитектуры и потоков данных                    |

### 🔄 **Multi-Agent System (FR-7, FR-8)**

| Документ                                                                                                | Содержание                                                                   |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md)                                                        | 10-агентная архитектура + **Phase 1 Message Bus реализована** ⭐              |
| [AI_RESOLVER_SYSTEM.md](./AI_RESOLVER_SYSTEM.md) 🆕⭐                                                     | **AI Resolver System** — семантические трансформации через AI (реализовано!) |
| [apps/backend/app/services/multi_agent/README.md](../apps/backend/app/services/multi_agent/README.md) 🆕 | **Message Bus Quick Start** (реализация, примеры кода)                       |
| [ADAPTIVE_PLANNING.md](./ADAPTIVE_PLANNING.md) ⭐🆕                                                       | **Адаптивное планирование с Full Replan** (реализовано!)                     |
| [history/REPLAN_AFTER_SUCCESS_IMPLEMENTED.md](./history/REPLAN_AFTER_SUCCESS_IMPLEMENTED.md) 🆕          | Full Replan механизм: реализация, тестирование, примеры                      |
| [REPLAN_DECISION_LOGIC_ANALYSIS.md](./REPLAN_DECISION_LOGIC_ANALYSIS.md)                                | Логика принятия решений о перепланировании (AI-powered)                      |
| [history/BACKEND_RESTRUCTURING_2026_01_29.md](./history/BACKEND_RESTRUCTURING_2026_01_29.md) 🆕          | Backend рефакторинг: `core/` folder, deprecated cleanup                      |
| [DYNAMIC_TOOL_SYSTEM.md](./DYNAMIC_TOOL_SYSTEM.md)                                                      | Pipeline для генерации инструментов, sandbox, безопасность                   |
| [BOARD_CONSTRUCTION_SYSTEM.md](./BOARD_CONSTRUCTION_SYSTEM.md)                                          | Система построения виджетов и связей                                         |
| [SMART_NODE_PLACEMENT.md](./SMART_NODE_PLACEMENT.md) 🆕                                                  | Автоматическое размещение нод без коллизий                                   |
| [TRANSFORM_DIALOG_CHAT_SYSTEM.md](./TRANSFORM_DIALOG_CHAT_SYSTEM.md) 🆕                                  | AI-powered итеративный диалог для трансформаций                              |
| [TRANSFORM_SUGGESTIONS_AGENT.md](./TRANSFORM_SUGGESTIONS_AGENT.md) 🆕                                    | TransformSuggestionsAgent — рекомендации трансформаций                       |

**Обновлено 1 февраля 2026**:
- ✅ **Transform Dialog Chat System реализована**: итеративный чат, preview, Monaco Editor
- ✅ **Node Cards UI Polish**: inline rename, table badges, единообразные кнопки
- ✅ **AI Resolver System реализована**: ResolverAgent, gb module, nest_asyncio
- ✅ **Phase 1 Message Bus завершена**: 11 модулей, Redis Pub/Sub, retry logic, metrics
- ✅ Backend реструктурирован: `apps/backend/app/core/` folder
- ✅ Graceful shutdown исправлен
- ⏳ Phase 2 в работе: Orchestrator & Session Management

### 📝 **Dynamic Form Generation (FR-12 — NEW!)**

| Документ                                                             | Содержание                                           |
| -------------------------------------------------------------------- | ---------------------------------------------------- |
| [DYNAMIC_FORM_GENERATION.md](./DYNAMIC_FORM_GENERATION.md)           | Полная спецификация динамической генерации форм      |
| [MANUAL_DATA_SOURCE_SELECTION.md](./MANUAL_DATA_SOURCE_SELECTION.md) | Ручной ввод источников данных (Auto vs Manual modes) |

### 📊 **Node System Architecture**

| Документ                                                                           | Содержание                                                                           |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [SOURCE_CONTENT_NODE_CONCEPT.md](./SOURCE_CONTENT_NODE_CONCEPT.md) 🆕⭐              | **Source-Content Node Architecture** (FR-14) — полная спецификация новой архитектуры |
| [SOURCE_CONTENT_IMPLEMENTATION_PLAN.md](./SOURCE_CONTENT_IMPLEMENTATION_PLAN.md) 🆕 | План реализации: 6 фаз, 10-15 дней, детальные задачи                                 |
| [SOURCE_CONTENT_QUICK_REF.md](./SOURCE_CONTENT_QUICK_REF.md) 🆕                     | Краткий reference: типы нод, edges, streaming, решения                               |
| [DATA_NODE_SYSTEM.md](./DATA_NODE_SYSTEM.md) ⚠️                                     | Архитектура DataNode (LEGACY, будет мигрирована)                                     |
| [DATANODE_PROMPT_PROCESSING.md](./DATANODE_PROMPT_PROCESSING.md)                   | Multi-Agent обработка промптов текстовых нод                                         |
| [history/PRIORITY_1_COMPLETED.md](./history/PRIORITY_1_COMPLETED.md)               | Завершённая реализация preview и execution                                           |

**Обновлено 1 февраля 2026**:
- ✅ **Node Cards UI**: ContentNodeCard и WidgetNodeCard обновлены
  - Inline rename (double-click на название или через меню)
  - Clickable table badges в ContentNodeCard
  - WidgetNodeCard: только верхний Handle (VISUALIZATION edge)
  - Единообразные размеры кнопок (h-8 w-8)
- 🆕 **Source-Content Node Architecture** (FR-14): новая концепция утверждена
  - SourceNode (источники: file, database, api, prompt, stream)
  - ContentNode (результаты: text + N tables)
  - Streaming с аккумуляцией и архивированием
  - 5 режимов replay трансформаций
  - План готов: 6 фаз, 10-15 дней разработки
- ⚠️ Текущая DataNode будет мигрирована на новую архитектуру

### 🌍 **Public Data Discovery (FR-13 — NEW!)**

| Документ                                       | Содержание                                                 |
| ---------------------------------------------- | ---------------------------------------------------------- |
| [SPECIFICATIONS.md](./SPECIFICATIONS.md#fr-13) | Полное описание функционала поиска публичных данных        |
| [USE_CASES.md](./USE_CASES.md#7)               | Use case: студент анализирует безработицу без своих данных |

**Ключевые возможности**:
- 🔍 AI-поиск датасетов по естественному запросу
- 📊 Интеграция с российскими источниками (data.gov.ru, Росстат, ЕМИСС, MOEX, ЦБ РФ)
- ⭐ Оценка качества данных (completeness, freshness, credibility)
- 📁 Sample Projects Gallery с готовыми шаблонами
- 🎓 Идеально для студентов, журналистов, стартапов

### 🔄 **Widget Transformation System (FR-14 — NEW!)**

| Документ                                                                | Содержание                                      |
| ----------------------------------------------------------------------- | ----------------------------------------------- |
| [SPECIFICATIONS.md](./SPECIFICATIONS.md#fr-14)                          | Полное описание системы трансформаций виджетов  |
| [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md#9-transformation-agent) | Transformation Agent (9-й агент) — спецификация |

**Ключевые возможности**:
- 🎯 Выделение виджетов → AI анализ → Контекстные предложения операций
- 📊 5 типов трансформаций: Analytical, Compositional, Data, Generative, Predictive
- 🔗 Data Lineage: граф зависимостей между исходными и производными виджетами
- 👁️ Preview Mode: просмотр результата до применения
- 📜 Template Library: популярные трансформации как шаблоны
- ♻️ Undo/History: откат к любому этапу цепочки трансформаций

### 💡 **Примеры и сценарии**

| Документ                                                           | Содержание                                         |
| ------------------------------------------------------------------ | -------------------------------------------------- |
| [USE_CASES.md](./USE_CASES.md)                                     | 7 real-world сценариев + 4 мульти-агентных примера |
| [MULTI_AGENT_USE_CASES.md](./MULTI_AGENT_USE_CASES.md)             | 4 детальных примера workflow с агентами            |
| [BOARD_CONSTRUCTION_EXAMPLES.md](./BOARD_CONSTRUCTION_EXAMPLES.md) | Примеры конструирования виджетов                   |

### ❓ **Вопросы и справка**

| Документ                                     | Содержание                                                       |
| -------------------------------------------- | ---------------------------------------------------------------- |
| [FAQ.md](./FAQ.md)                           | 30+ вопросов и ответов по архитектуре, безопасности, performance |
| [CONNECTION_TYPES.md](./CONNECTION_TYPES.md) | Описание 7 типов связей между виджетами                          |

### 👨‍💻 **Для разработчиков**

| Документ                                           | Содержание                           |
| -------------------------------------------------- | ------------------------------------ |
| [DEVELOPER_CHECKLIST.md](./DEVELOPER_CHECKLIST.md) | Полный чек-лист задач для разработки |
| [ROADMAP.md](./ROADMAP.md)                         | План разработки по фазам             |

---

## 🏗️ Стек технологий

```
Frontend:  React, React Flow, ShadCN UI, Zustand, Socket.IO client
Backend:   Python 3.13+, FastAPI, SQLAlchemy, PostgreSQL, Redis
AI:        GigaChat API (Yandex), LangChain (planned)
Realtime:  Socket.IO, Redis pub/sub
Testing:   pytest, pytest-asyncio, Vitest, RTL
```

---

## 📊 Статистика проекта

### Документация
- **Документов**: 25+ файлов (включая history/)
- **Строк**: 10000+ строк спецификаций и кода
- **Размер**: 350+ KB
- **Диаграмм**: 6 детальных
- **Use Cases**: 11 сценариев
- **FAQ**: 30+ ответов

### Backend (Python/FastAPI)
- **Файлов**: ~60 Python модулей
- **Строк кода**: ~6000+ (включая Multi-Agent Phase 1)
- **Models**: 11 SQLAlchemy models (User, Project, Board, Node types, Edge, ChatMessage, etc.)
- **API Endpoints**: ~35
- **Socket.IO Events**: 16
- **Миграций Alembic**: 8
- **Multi-Agent Modules**: 11 (Phase 1 реализована)

### Frontend (React/TypeScript)
- **Файлов**: ~80 TypeScript/TSX модулей
- **Строк кода**: ~8000+
- **Компонентов**: ~40 React компонентов
- **Zustand Stores**: 6
- **Pages**: 6

### Multi-Agent System
- **Phase 1 Status**: ✅ Завершена (2026-01-29)
- **Modules**: 11 (message_bus, retry_logic, timeout_monitor, metrics, etc.)
- **Lines of Code**: ~1500
- **Agents Planned**: 9 (Phase 3-5)
- **Message Types**: 11
- **Channel Types**: 5 (broadcast, agent inbox, ui_events, session_results, errors)

---

## 🚀 Быстрый старт

### Требования
- Python 3.11+ (текущая: 3.13.9 в .venv)
- Node.js 18+ LTS
- PostgreSQL 14+
- Redis 6+
- uv (Python package manager) — установлен ✅

### Запуск Backend

```bash
# Переход в папку backend
cd apps/backend

# Установка зависимостей (если нужно)
uv sync

# Запуск dev сервера
uv run python run_dev.py
# или через скрипт
../../run-backend.ps1

# Сервер доступен на http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Запуск Frontend

```bash
# В новом терминале
cd apps/web

# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev
# или через скрипт
../../run-frontend.ps1

# Frontend доступен на http://localhost:5173
```

### Запуск обоих одновременно

```bash
# В корне проекта
./run-dev.ps1  # Windows
# или
./run-dev.sh   # macOS/Linux

# Frontend
npm install
```

---

## 📋 Функциональные требования (Functional Requirements)

| ID    | Требование                     | Статус | Реализация                       |
| ----- | ------------------------------ | ------ | -------------------------------- |
| FR-1  | Infinite Canvas с виджетами    | ✅ 100% | React Flow + Socket.IO           |
| FR-2  | CRUD операции (Board/Widget)   | ✅ 100% | FastAPI + SQLAlchemy             |
| FR-3  | Real-time синхронизация        | ✅ 100% | Socket.IO + Redis Pub/Sub        |
| FR-4  | Типы связей между виджетами    | ✅ 100% | 7 типов Edge реализовано         |
| FR-5  | Rendering HTML/CSS/JS виджетов | ✅ 90%  | WidgetNode (iframe sandbox TODO) |
| FR-6  | AI Assistant Panel             | ✅ 85%  | GigaChat streaming работает      |
| FR-7  | Multi-Agent System             | ⚠️ 30%  | Phase 1 ✅, Phase 2 в работе      |
| FR-8  | Dynamic Tool Generation        | ⚠️ 15%  | Архитектура задокументирована    |
| FR-12 | Dynamic Form Generation        | ✅ 100% | Архитектура + документация       |
| FR-13 | Public Data Discovery          | ❌ 0%   | TODO Phase 5                     |

---

## 🔄 Текущая фаза разработки

### 🚀 Phase 1 Multi-Agent: Message Bus Infrastructure ✅ ЗАВЕРШЕНО

**Результаты** (2026-01-29):
- 11 модулей (~1500 строк)
- Redis Pub/Sub с 5 типами каналов
- AgentMessageBus (publish, subscribe, request_response)
- Retry logic + timeout monitoring
- Metrics & monitoring
- Tests + developer documentation

📖 [Детальная документация](../apps/backend/app/services/multi_agent/README.md)

### 🔥 Phase 2 Multi-Agent: Orchestrator & Session Management (В РАБОТЕ)

**Цель** (3-4 дня, до 2 февраля):
- AgentSession model + миграция
- AgentSessionManager service
- MultiAgentOrchestrator implementation
- AIService integration (через Orchestrator)

**Следующие фазы**:
- Phase 3: Core Agents (Planner, Researcher, Analyst, Transformation)
- Phase 4: Generation Agents (Reporter, Developer, Executor)
- Phase 5: Advanced Agents (FormGenerator, DataDiscovery)

---

## 🎯 Навигация по документам

### По типу работы

**Я хочу понять архитектуру**
1. [ARCHITECTURE.md](./ARCHITECTURE.md) — компоненты и интеграция
2. [SYSTEM_DIAGRAMS.md](./SYSTEM_DIAGRAMS.md) — 6 диаграмм

**Я хочу начать разработку**
1. [SPECIFICATIONS.md](./SPECIFICATIONS.md) — требования
2. [API.md](./API.md) — endpoints
3. [DEVELOPER_CHECKLIST.md](./DEVELOPER_CHECKLIST.md) — задачи

**Я хочу увидеть примеры**
1. [USE_CASES.md](./USE_CASES.md) — User scenarios
2. [MULTI_AGENT_USE_CASES.md](./MULTI_AGENT_USE_CASES.md) — Agent workflows
3. [BOARD_CONSTRUCTION_EXAMPLES.md](./BOARD_CONSTRUCTION_EXAMPLES.md) — Widgets примеры

**Я ищу ответы на вопросы**
1. [FAQ.md](./FAQ.md) — 30+ ответов
2. [CONNECTION_TYPES.md](./CONNECTION_TYPES.md) — Типы связей

---

## 📂 Структура папок проекта

```
GigaBoard/
├── docs/                          # 📚 Документация (25+ файлов)
│   ├── README.md                  # ⭐ Вы здесь (обновлён 2026-01-29)
│   ├── SPECIFICATIONS.md          # Требования (FR-1 до FR-13)
│   ├── ARCHITECTURE.md            # Архитектура системы
│   ├── API.md                     # REST/WebSocket endpoints
│   ├── AI_ASSISTANT.md            # FR-6 спецификация + Orchestrator
│   ├── UI_DESIGN.md               # Макеты и дизайн
│   ├── SYSTEM_DIAGRAMS.md         # 6 архитектурных диаграмм
│   ├── MULTI_AGENT_SYSTEM.md      # FR-7 архитектура (с Phase 1-5 roadmap)
│   ├── DYNAMIC_TOOL_SYSTEM.md     # FR-8 система инструментов
│   ├── DATA_NODE_SYSTEM.md        # DataNode архитектура
│   ├── USE_CASES.md               # 11 user scenarios
│   ├── MULTI_AGENT_USE_CASES.md   # 4 agent workflow примера
│   ├── CONNECTION_TYPES.md        # 7 типов связей
│   ├── BOARD_CONSTRUCTION_SYSTEM.md # Система конструирования
│   ├── BOARD_CONSTRUCTION_EXAMPLES.md # Примеры
│   ├── SMART_NODE_PLACEMENT.md    # 🆕 Автоматическое размещение нод
│   ├── DYNAMIC_FORM_GENERATION.md # FR-12 динамические формы
│   ├── FAQ.md                     # 30+ вопросов
│   ├── DEVELOPER_CHECKLIST.md     # Чек-лист разработки
│   ├── ROADMAP.md                 # План по фазам
│   ├── history/                   # История завершённых задач
│   │   ├── PRIORITY_1_COMPLETED.md         # DataNode preview & execute ✅
│   │   ├── BACKEND_RESTRUCTURING_2026_01_29.md # core/ folder ✅
│   │   └── [другие завершённые фичи]
│   └── diagrams/                  # Drawio диаграммы
├── apps/
│   ├── backend/                   # 🐍 FastAPI Backend (~60 модулей, ~6000 строк)
│   │   ├── app/
│   │   │   ├── core/              # 🆕 Инфраструктура (config, database, redis, socketio)
│   │   │   ├── models/            # SQLAlchemy models (11 моделей)
│   │   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── routes/            # API endpoints (~35 endpoints)
│   │   │   ├── services/          # Business logic
│   │   │   │   └── multi_agent/   # 🆕 Phase 1 Message Bus (11 модулей) ✅
│   │   │   │       ├── message_bus.py
│   │   │   │       ├── retry_logic.py
│   │   │   │       ├── timeout_monitor.py
│   │   │   │       ├── metrics.py
│   │   │   │       ├── README.md  # Developer guide
│   │   │   │       └── [другие модули]
│   │   │   ├── middleware/        # Auth middleware
│   │   │   ├── utils/             # 🆕 Utilities
│   │   │   │   └── node_positioning.py  # Smart node placement
│   │   │   └── main.py            # FastAPI app entry point
│   │   ├── migrations/            # Alembic (8 миграций)
│   │   └── tests/
│   └── web/                       # ⚛️ React Frontend (~80 модулей, ~8000 строк)
│       ├── src/
│       │   ├── components/        # React компоненты (~40)
│       │   ├── stores/            # Zustand stores (6 stores)
│       │   ├── pages/             # Pages (6 страниц)
│       │   ├── hooks/             # Custom hooks
│       │   └── lib/               # Utilities
│       │       └── nodePositioning.ts  # 🆕 Smart node placement
│       └── [config files]
├── tests/                         # ✅ Интеграционные тесты
├── .vscode/
│   └── CURRENT_FOCUS.md           # 📍 Текущая фаза (обновлён 2026-01-29)
└── [config files]
```

---

## � Поддержка и вопросы

- 📚 **Документация**: Начните с [SPECIFICATIONS.md](./SPECIFICATIONS.md)
- 🐛 **Проблемы**: Проверьте [FAQ.md](./FAQ.md)
- 💡 **Вопросы по архитектуре**: См. [ARCHITECTURE.md](./ARCHITECTURE.md)
- 🤖 **Multi-Agent System**: См. [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md) + [Phase 1 README](../apps/backend/app/services/multi_agent/README.md)

---

**Проект**: GigaBoard  
**Версия**: Phase 1 Multi-Agent Complete + Source-Content Architecture (2026-01-30)  
**Лицензия**: Proprietary  
**Разработчик**: Solo development  
**Статус**: 🚀 Active development — Phase 2 Orchestrator в работе + документация актуализирована
- Tool Registry & Sandbox
- Dynamic Tool Generation

**Текущий статус**: Готовы к Фазе 1 (архитектура завершена)

**Где начать?**
→ Прочитайте SPECIFICATIONS.md, затем ARCHITECTURE.md

**Как устроена API?**
→ Смотрите API.md (все endpoints перечислены)

**Что такое эти 6 типов связей?**
→ CONNECTION_TYPES.md подробно объясняет каждый (EXTRACT, TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN)

**Как работает AI Assistant?**
→ AI_ASSISTANT.md (спецификация) + USE_CASES.md (примеры)

**Как работают агенты?**
→ MULTI_AGENT_SYSTEM.md + MULTI_AGENT_USE_CASES.md (примеры)

**Где найти чек-лист разработки?**
→ DEVELOPER_CHECKLIST.md

**Есть ещё вопросы?**
→ FAQ.md (30+ ответов)

---

## 📞 Контакты и статус

- **Архитектура**: ✅ Завершена
- **Документация**: ✅ Завершена (7500+ строк)
- **Разработка**: ⏳ Готовы начинать

**Последнее обновление**: 30 января 2026
