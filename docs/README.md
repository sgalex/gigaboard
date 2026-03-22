# GigaBoard — Документация проекта

## 📖 Что это?

**GigaBoard** — **инструмент для аналитики и обработки данных с помощью ИИ** на **доске-пайплайне**: узлы и связи задают путь данных от **источников** (файлы, БД, API, streaming, research и др.) через **трансформации** до **виджетов** и текстовых выводов; **ассистент и мультиагент** (см. [MULTI_AGENT.md](./MULTI_AGENT.md)) отвечают на естественном языке, генерируют код трансформаций и визуализаций и работают в контексте графа и таблиц. Рядом — **дашборды** как презентационный слой, **глобальные фильтры** по доске/дашборду, **совместное редактирование** в реальном времени, явный **lineage** и **replay** при обновлении данных.

По типу это **рабочее приложение** с прямым назначением (как табличный редактор к таблицам), а не «платформа» в смысле **инфраструктуры или экосистемы под сторонние продукты**. **Data-Centric Canvas** — бесконечное полотно (React Flow), на котором этот пайплайн **наглядно закреплён**.

### Ключевые возможности
- 🤖 **ИИ как рабочий инструмент** — AI Assistant Panel, мультиагент (Orchestrator), генерация трансформаций и виджетов; стрим и прогресс через Socket.IO (см. [AI_ASSISTANT.md](./AI_ASSISTANT.md))
- 🎨 **Доска-пайплайн** — 4 типа узлов, 5 типов связей; воспроизводимые операции и граф зависимостей
- 📊 **Дашборды и фильтры** — редактор дашбордов; Cross-Filter по измерениям и пресетам (см. [DASHBOARD_SYSTEM.md](./DASHBOARD_SYSTEM.md), [CROSS_FILTER_SYSTEM.md](./CROSS_FILTER_SYSTEM.md))
- 🧠 **Multi-Agent System** — 9 core агентов + satellite-контроллеры (Transform, Widget, Assistant, Research и др.)
- 👥 **Real-time коллаборация** — Socket.IO + Redis pub/sub
- 🎨 **AI-виджеты** — **WidgetCodexAgent** / **WidgetController**; **Reporter** — итоговый narrative (см. [`MULTI_AGENT.md`](./MULTI_AGENT.md))
- 🔄 **Replay** — обновление источника запускает перепросчёт downstream-пайплайна

---

## 🏗️ Стек технологий

```
Frontend:  React, React Flow (@xyflow/react), ShadCN UI, Zustand, Socket.IO client
Backend:   Python 3.13+, FastAPI, SQLAlchemy, PostgreSQL, Redis
AI:        GigaChat API (Sberbank), langchain-gigachat
Realtime:  Socket.IO, Redis pub/sub
Package:   uv (Python), npm (Frontend)
```

---

## 📚 Навигация по документации

### Основа (обязательно)

| Документ                                 | Описание                                                       |
| ---------------------------------------- | -------------------------------------------------------------- |
| [SPECIFICATIONS.md](./SPECIFICATIONS.md) | Функциональные и нефункциональные требования (FR-1..FR-23)     |
| [ARCHITECTURE.md](./ARCHITECTURE.md)     | Архитектура: 4 типа узлов, Multi-Agent System, Data-Centric Canvas |
| [API.md](./API.md)                       | REST и WebSocket endpoints                                     |

### Архитектура узлов и связей

| Документ                                                 | Описание                                                                                                   |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| [BOARD_SYSTEM.md](./BOARD_SYSTEM.md)                     | **⭐ Документ доски:** 4 типа узлов, 5 типов связей, 9 источников, правила размещения — всё в одном месте** |
| [DASHBOARD_SYSTEM.md](./DASHBOARD_SYSTEM.md)             | **⭐ Dashboard System:** редактор дашбордов — виджеты, текст, изображения, линии, snap, z-order, rotation** |
| [DATA_NODE_SYSTEM.md](./DATA_NODE_SYSTEM.md)             | Pipeline и трансформации: процесс, replay, sandbox                                                         |
| [SOURCE_NODE_CONCEPT.md](./SOURCE_NODE_CONCEPT.md) | Диалоги настройки источников: CSV, API, DB, Research — полные UX-сценарии                                  |
| [CONNECTION_TYPES.md](./CONNECTION_TYPES.md)             | Полная спецификация 5 типов связей с метаданными                                                           |
| [SMART_NODE_PLACEMENT.md](./SMART_NODE_PLACEMENT.md)     | Алгоритм AABB, спиральный поиск, листинг кода                                                              |
| [DRILL_DOWN_SYSTEM.md](./DRILL_DOWN_SYSTEM.md)           | Interactive drill-down по DRILL_DOWN edges (Phase 2)                                                       |
| [CROSS_FILTER_SYSTEM.md](./CROSS_FILTER_SYSTEM.md)       | **⭐ Cross-Filter:** глобальные фильтры, измерения, click-to-filter, пресеты для ЛПР                        |
| [COLLABORATIVE_FEATURES.md](./COLLABORATIVE_FEATURES.md) | CommentNode, COMMENT edges, real-time совместная работа (Phase 2)                                          |

### Multi-Agent System

| Документ                                                 | Описание                                                    |
| -------------------------------------------------------- | ----------------------------------------------------------- |
| [MULTI_AGENT.md](./MULTI_AGENT.md)                       | Orchestrator, AgentPayload, 9 агентов, satellite-контроллеры (в т.ч. ResearchController); тулы таблиц через `_compute_filtered_pipeline` (см. также `CROSS_FILTER_SYSTEM.md` §3.5); history/2026-03-18, 2026-03-20 |
| [CONTEXT_ENGINEERING.md](./CONTEXT_ENGINEERING.md)       | **Context engineering:** план внедрения бюджетов, селекции контекста, рабочей памяти, метрик по шагам пайплайна |
| [TASK_TYPES_REFERENCE.md](./TASK_TYPES_REFERENCE.md)     | Типы задач для каждого агента (task types)                  |
| [ADAPTIVE_PLANNING.md](./ADAPTIVE_PLANNING.md)           | Full Replan — адаптивное планирование на основе результатов |
| [AI_RESOLVER_SYSTEM.md](./AI_RESOLVER_SYSTEM.md)         | Batch AI resolution (пол, sentiment, категоризация)         |
| [MESSAGE_BUS_QUICKSTART.md](./MESSAGE_BUS_QUICKSTART.md) | Redis Message Bus — быстрый старт                           |
| [SEARCH_AGENT.md](./SEARCH_AGENT.md)                     | SearchAgent — веб-поиск через DuckDuckGo                    |

### Визуализации и трансформации

| Документ                                                                 | Описание                                                      |
| ------------------------------------------------------------------------ | ------------------------------------------------------------- |
| [WIDGET_GENERATION_SYSTEM.md](./WIDGET_GENERATION_SYSTEM.md)             | WidgetCodex / виджеты: AI-генерация HTML/CSS/JS (Reporter — итоговый narrative) |
| [WIDGET_SUGGESTIONS_SYSTEM.md](./WIDGET_SUGGESTIONS_SYSTEM.md)           | AI-рекомендации по улучшению виджетов                         |
| [TRANSFORM_SYSTEM.md](./TRANSFORM_SYSTEM.md)                             | Transform Dialog: итеративный чат, preview, Monaco Editor     |
| [TRANSFORM_DIALOG_CHAT_SYSTEM.md](./TRANSFORM_DIALOG_CHAT_SYSTEM.md)     | Dual-panel layout, итеративный чат, suggestions (реализовано) |
| [TRANSFORM_DISCUSSION_MODE.md](./TRANSFORM_DISCUSSION_MODE.md)           | Discussion mode vs Transformation mode в TransformDialog      |
| [TRANSFORM_MULTIAGENT_DATA_FLOW.md](./TRANSFORM_MULTIAGENT_DATA_FLOW.md) | Поток данных Frontend→Backend для `/transform/iterative`      |
| [TRANSFORM_SUGGESTIONS_AGENT.md](./TRANSFORM_SUGGESTIONS_AGENT.md)       | TransformSuggestionsAgent — контекстные рекомендации          |
| [ECHARTS_WIDGET_REFERENCE.md](./ECHARTS_WIDGET_REFERENCE.md)             | Справочник ECharts для генерации визуализаций                 |

### AI Assistant и UX

| Документ                                                   | Описание                                                    |
| ---------------------------------------------------------- | ----------------------------------------------------------- |
| [AI_ASSISTANT.md](./AI_ASSISTANT.md)                       | AI Assistant Panel — спецификация, API, примеры             |
| [AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md](./AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md) | Источник AI Research: ResearchController, `/research/chat`, диалог, сравнение с Playground |
| [ADMIN_AND_SYSTEM_LLM.md](./ADMIN_AND_SYSTEM_LLM.md)       | Администратор, системные настройки LLM, Playground мультиагента |
| [LLM_CONFIGURATION_CONCEPT.md](./LLM_CONFIGURATION_CONCEPT.md) | Концепция: пресеты LLM, модель по умолчанию, привязка к агентам |
| [UI_DESIGN.md](./UI_DESIGN.md)                             | Макеты UI, компоненты, дизайн                               |
| [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)                     | Дизайн-система: цвета, типографика, компоненты              |
| [USE_CASES.md](./USE_CASES.md)                             | 7+ сценариев использования                                  |
| [USER_ONBOARDING.md](./USER_ONBOARDING.md)                 | User journey: первый запуск, 3 клика до первой визуализации |
| [DYNAMIC_FORM_GENERATION.md](./DYNAMIC_FORM_GENERATION.md) | AI-генерация форм подключения данных в диалоге              |
| [VOICE_INPUT_SYSTEM.md](./VOICE_INPUT_SYSTEM.md)           | Голосовое управление и Natural Language Query (Phase 3)     |
| [FAQ.md](./FAQ.md)                                         | 30+ вопросов и ответов                                      |

### Форматы данных и хранение

| Документ                                               | Описание                                        |
| ------------------------------------------------------ | ----------------------------------------------- |
| [DATA_FORMATS.md](./DATA_FORMATS.md)                   | Форматы данных: CSV, JSON, Excel, Parquet и др. |
| [JSON_SOURCE_PARSING.md](./JSON_SOURCE_PARSING.md) | JSON Source: автоизвлечение схемы, нормализация в таблицы, редактор мэппинга |
| [FILE_STORAGE_STRATEGY.md](./FILE_STORAGE_STRATEGY.md) | Стратегия хранения файлов                       |

**JSON Source (актуализация 2026-03-20):**
- Единый полноэкранный диалог для `create/edit`.
- Левая секция: upload JSON + collapsible preview исходного JSON.
- Правая секция: табы таблиц мэппинга (rename/delete/add), редактор столбцов и встроенный preview.
- Контракт хранения: `schema_snapshot`, `mapping_spec`, `generation_meta` в `SourceNode.config`.

### Планирование и развитие

| Документ                                                   | Описание                                               |
| ---------------------------------------------------------- | ------------------------------------------------------ |
| [ROADMAP.md](./ROADMAP.md)                                 | План развития по фазам                                 |
| [FUTURE_FEATURES.md](./FUTURE_FEATURES.md)                 | Концепции незавершённых фич (13 проектов)              |
| [TEMPLATE_MARKETPLACE.md](./TEMPLATE_MARKETPLACE.md)       | Маркетплейс шаблонов SourceNode / WidgetNode (Phase 3) |
| [EXPORT_EMBEDDING_SYSTEM.md](./EXPORT_EMBEDDING_SYSTEM.md) | Экспорт досок и iframe-embed виджетов (Phase 3)        |
| [AUTOMATED_REPORTING.md](./AUTOMATED_REPORTING.md)         | Автоматические отчёты по расписанию (Phase 4)          |
| [DATA_QUALITY_MONITOR.md](./DATA_QUALITY_MONITOR.md)       | AI-мониторинг качества данных (Phase 4)                |
| [COMMANDS.md](./COMMANDS.md)                               | Команды разработки                                     |

### Развёртывание (Docker)

| Документ | Описание |
| -------- | -------- |
| [DOCKER_VM_DEPLOYMENT.md](./DOCKER_VM_DEPLOYMENT.md) | Пошаговое развёртывание на виртуальной машине (Linux, Docker Compose) |
| [res/README.md](../res/README.md) | Вспомогательные ресурсы репозитория (демо-данные, шаблоны nginx для ВМ) |

### История и служебные каталоги

| Каталог | Описание |
| ------- | -------- |
| [history/README.md](./history/README.md) | **Архив**: снимки решений, V1-документы; актуальность — по корню `docs/` |
| [history/](./history/) | Файлы архива (не считать спецификацией без сверки с кодом) |
| [workflow_logs/README.md](./workflow_logs/README.md) | **Логи прогонов** (демо), не нормативная документация |
| [workflow_logs/](./workflow_logs/) | Сохранённые логи сессий |

---

## 📂 Структура проекта

```
GigaBoard/
├── res/                           # Вспомогательные ресурсы (демо-данные, шаблоны nginx для ВМ)
├── docs/                          # 📚 Документация: корень — спецификации; history/ — архив; workflow_logs/ — логи прогонов (см. README в каждом каталоге)
│   ├── README.md                  # ⭐ Этот файл — навигация
│   ├── SPECIFICATIONS.md          # Требования (FR-1..FR-23)
│   ├── ARCHITECTURE.md            # Архитектура системы
│   ├── API.md                     # REST/WebSocket endpoints
│   ├── DATA_NODE_SYSTEM.md        # SourceNode/ContentNode архитектура
│   ├── SOURCE_NODE_CONCEPT.md  # 9 типов источников, витрина, диалоги
│   ├── CONNECTION_TYPES.md        # 5 типов связей
│   ├── MULTI_AGENT.md  # Multi-Agent архитектура
│   ├── WIDGET_GENERATION_SYSTEM.md # AI-генерация визуализаций
│   ├── TRANSFORM_SYSTEM.md        # Система трансформаций
│   ├── TRANSFORM_DIALOG_CHAT_SYSTEM.md  # TransformDialog с чатом
│   ├── COLLABORATIVE_FEATURES.md  # Совместная работа (Phase 2)
│   ├── DRILL_DOWN_SYSTEM.md       # Drill-down по виджетам (Phase 2)
│   ├── FUTURE_FEATURES.md         # Незавершённые концепции
│   ├── ROADMAP.md                 # План развития
│   ├── history/                   # Архив завершённых фич и V1 документов
│   └── ...                        # Остальные документы (см. навигацию выше)
├── apps/
│   ├── backend/                   # 🐍 FastAPI Backend
│   │   └── app/
│   │       ├── core/              # Инфраструктура (config, database, redis, socketio)
│   │       ├── models/            # SQLAlchemy models (board, project, source_node, content_node, widget_node, comment_node, edge, dashboard, dashboard_item, dashboard_share, dimension, dimension_column_mapping, filter_preset, project_widget, project_table, user, uploaded_file, agent_session, chat_message и др.)
│   │       ├── schemas/           # Pydantic schemas
│   │       ├── routes/            # API endpoints (auth, health, projects, boards, edges, source_nodes, content_nodes, widget_nodes, comment_nodes, extraction, ai_assistant, ai_resolver, database, files, dashboards, library, public, dimensions, filters)
│   │       ├── services/          # Business logic
│   │       │   ├── multi_agent/   # Multi-Agent
│   │       │   │   ├── agents/    # 9 core агентов + QualityGate
│   │       │   │   └── ...
│   │       │   ├── controllers/   # satellite-контроллеры (AI Assistant, Transform, Widget, Research, …)
│   │       │   └── extractors/    # Extractors (file, db, api, prompt, manual)
│   │       ├── middleware/        # Auth middleware
│   │       └── utils/             # Utilities
│   └── web/                       # ⚛️ React Frontend
│       └── src/
│           ├── components/        # React компоненты
│           │   └── board/         # Canvas компоненты
│           ├── store/             # Zustand stores (board, project, auth, ui, …)
│           ├── pages/             # Страницы
│           ├── hooks/             # Custom hooks
│           └── lib/               # Utilities
├── tests/                         # Интеграционные тесты
└── .vscode/
    └── CURRENT_FOCUS.md           # Текущая фаза разработки
```

---

## 🚀 Быстрый старт

### Требования
- Python 3.11+ (рекомендуется 3.13)
- Node.js 18+ LTS
- PostgreSQL 14+
- Redis 6+
- uv (Python package manager)

### Запуск

```bash
# Backend
cd apps/backend
uv sync
uv run python run_dev.py
# → http://localhost:8000 (docs: /docs)

# Frontend (в отдельном терминале)
cd apps/web
npm install
npm run dev
# → http://localhost:5173

# Или оба сразу (Windows)
./run-dev.ps1
```

---

## 📞 Быстрые ответы

**Архитектура системы?** → [ARCHITECTURE.md](./ARCHITECTURE.md)

**API endpoints?** → [API.md](./API.md)

**Как устроена доска?** → [BOARD_SYSTEM.md](./BOARD_SYSTEM.md) — всё в одном месте

**Типы узлов и связей (детально)?** → [DATA_NODE_SYSTEM.md](./DATA_NODE_SYSTEM.md) + [CONNECTION_TYPES.md](./CONNECTION_TYPES.md)

**Как работают агенты?** → [MULTI_AGENT.md](./MULTI_AGENT.md) + [TASK_TYPES_REFERENCE.md](./TASK_TYPES_REFERENCE.md)

**AI Assistant?** → [AI_ASSISTANT.md](./AI_ASSISTANT.md) + [USE_CASES.md](./USE_CASES.md)

**Ещё вопросы?** → [FAQ.md](./FAQ.md)
