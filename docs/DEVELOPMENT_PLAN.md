# 📋 ПЛАН РАБОТ: GigaBoard Development (Feature-Driven)

**Создано**: 2026-01-23  
**Обновлено**: 2026-01-26 (актуализировано после code review)  
**Статус**: 🟡 Активная разработка  
**Целевой Release**: 2026-03-31 (скорректировано)  
**Подход**: ✨ Feature-Driven Development

---

## 🎯 КОНТЕКСТ ПРОЕКТА

**GigaBoard** — интеллектуальная аналитическая доска с:
- Бесконечным канвасом (React Flow)
- AI-ассистентом (GigaChat)
- Мультиагентной системой (8 агентов)
- Dynamic tool generation (Python/SQL/JS)
- Real-time совместным редактированием (Socket.IO)

**Реальное состояние (после детального code review 26.01.2026):**
- ✅ Документация: 100% готова (12000+ строк)
- ✅ Архитектура: Спроектирована и реализована
- ✅ Backend Infrastructure: 95% (FastAPI, PostgreSQL, Redis, Socket.IO)
- ✅ Backend Models: 100% (все 7 моделей реализованы)
- ✅ Backend API: 85% (42 CRUD endpoints работают)
- ✅ Frontend Infrastructure: 100% (React + Vite + TypeScript)
- ⚠️ Frontend Canvas: 50% (работает, но нет dialogs)
- ⚠️ Socket.IO: 60% (работает, нужен рефакторинг)
- ❌ AI Integration: 0% (полностью отсутствует)

**Общая готовность проекта: 55%**

---

## 📚 СИСТЕМА РАЗРАБОТКИ ПО ФИЧАМ

Каждая фича полностью реализуется за спринт:
- ✅ Backend (models + API endpoints + logic)
- ✅ Frontend (components + state management + hooks)
- ✅ Database (migrations + schemas)
- ✅ Tests (unit + integration)
- ✅ Documentation

**Фичи реализуются последовательно**, каждая строит на предыдущей.

---

## 💾 АРХИТЕКТУРА ХРАНИЛИЩА ДАННЫХ

### Обзор

GigaBoard использует **двухуровневый подход** к хранилищу данных:

| Хранилище        | Назначение                                             | Тип         |
| ---------------- | ------------------------------------------------------ | ----------- |
| **PostgreSQL**   | Основная БД (доски, виджеты, связи, чаты, инструменты) | Реляционное |
| **Redis**        | Кэш, сессии, pub/sub, rate limiting                    | Key-Value   |
| **File Storage** | Экспорты, ассеты (опционально)                         | Файлы       |

### Таблицы БД (по фичам):

**Инфраструктура (FR-Setup):**
- `users` — пользователи (id, email, password_hash, created_at)
- `user_sessions` — сеансы (id, user_id, token_hash, expires_at)

**FR-1, FR-2: Доски и виджеты**
- `boards` — доски (id, user_id, name, description, created_at, updated_at)
- `widgets` — виджеты (id, board_id, type, x, y, width, height, config, data, created_at)

**FR-11: Связи между виджетами**
- `edges` — связи (id, board_id, source_id, target_id, type, metadata, created_at)

**FR-5: История**
- `board_history` — снимки досок (id, board_id, action_type, snapshot, created_at)

**FR-6, FR-4: AI Assistant**
- `chat_messages` — сообщения (id, board_id, session_id, user_id, role, content, created_at)
- `chat_sessions` — сеансы диалога (id, board_id, user_id, created_at)

**FR-7, FR-8: Multi-Agent + Tools**
- `tool_registry` — инструменты (id, name, code, version, language, created_at)
- `tool_executions` — логи выполнения (id, tool_id, status, input_data, output_data, created_at)

**Аудит:**
- `audit_logs` — все действия (id, user_id, resource_type, action, created_at)

---

## 🚀 ФИЧИ ПО ОЧЕРЕДНОСТИ

### ФИЧА 1️⃣: FR-Setup — Инфраструктура и аутентификация
**Время**: 3-4 дня  
**Статус**: ⏳ Не начато  
**Блокирует**: Все остальное

#### Описание
Базовая инфраструктура: БД, модели пользователя, JWT аутентификация, конфигурация.

#### Backend
- [ ] Структура проекта
  - [ ] Создать `apps/backend/app/models/`, `routes/`, `schemas/`, `services/`, `middleware/`
  - [ ] Настроить SQLAlchemy + async engine
  - [ ] Настроить Redis connection
  - [ ] Создать environment файл (`.env`, `.env.example`)

- [ ] Database models
  - [ ] Model `User` (id, email, username, password_hash, created_at, updated_at)
  - [ ] Model `UserSession` (id, user_id, token_hash, expires_at, created_at)
  - [ ] Alembic миграции для инициализации

- [ ] Authentication
  - [ ] JWT token generation и validation
  - [ ] Password hashing (bcrypt)
  - [ ] Auth middleware для проверки токена
  - [ ] Endpoints: POST `/api/v1/auth/register`, POST `/api/v1/auth/login`, POST `/api/v1/auth/logout`

- [ ] Health checks
  - [ ] GET `/health` — проверка сервера
  - [ ] GET `/api/v1/health` — проверка БД, Redis

#### Frontend
- [ ] React + Vite настройка
  - [ ] React Router для навигации
  - [ ] Zustand store для auth state (user, token, isLoading)

- [ ] Authentication pages
  - [ ] LoginPage компонент (email, password, submit button)
  - [ ] RegisterPage компонент (email, username, password, confirm)
  - [ ] Auth guard (redirect to login if no token)

#### Database
- [ ] Alembic `001_initial_users.py` миграция
- [ ] Create `users` table
- [ ] Create `user_sessions` table
- [ ] Индексы: `users(email)`, `user_sessions(user_id)`

#### Tests
- [ ] Тесты для JWT token generation
- [ ] Тесты для password hashing
- [ ] API тесты для auth endpoints (register, login)
- [ ] DB тесты для user creation

#### Docs
- [ ] `.env.example` файл с переменными
- [ ] Setup инструкции (PostgreSQL, Redis, Python venv)
- [ ] Примеры curl для auth endpoints

---

### ФИЧА 2️⃣: FR-1, FR-2 — Доски и CRUD виджетов
**Время**: 4-5 дней  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-Setup  
**Блокирует**: FR-3, FR-11, FR-5

#### Backend ✅
- [x] Edge model с 5 типами (TRANSFORMATION, VISUALIZATION, COMMENT, DRILL_DOWN, REFERENCE)
- [x] Polymorphic references (source_node_id/type, target_node_id/type)
- [x] Edge CRUD API (5 endpoints)
- [x] EdgeService с validation
- [x] Миграция 003, 005 применены
- [x] Socket.IO events для edges

#### Frontend ✅
- [x] Edge types в TypeScript
- [x] Edge rendering на canvas с разными цветами
- [x] Edge creation через onConnect
- [x] Edge API integration

**Осталось (15%):**
- [ ] Edge type auto-detection (сейчас hardcoded VISUALIZATION)
- [ ] Edge creation dialog для выбора типа
- [ ] Transformation code editor для TRANSFORMATION edges
- [ ] Edge validation (циклические зависимости)

---

### ФИЧА 4️⃣: FR-3 — Real-time Socket.IO
**Время**: 2-3 дня  
**Статус**: ⚠️ ЧАСТИЧНО (60%)  
**Дата обновления**: 2026-01-26

#### Backend ✅
- [x] Socket.IO server инициализирован
- [x] CombinedASGI router (FastAPI + Socket.IO)
- [x] Room management (join_board, leave_board)
- [x] Event handlers зарегистрированы
- [x] Broadcast events:
  - data_node_created/updated/deleted
  - widget_node_created/updated/deleted
  - comment_node_created/updated/deleted
  - edge_created/updated/deleted

#### Frontend ✅
- [x] Socket.IO client (socket.io-client)
- [x] useBoardSocket hook
- [x] Join board при загрузке BoardPage
- [x] Event listeners для всех node types
- [x] State updates при получении events

**Критические проблемы (40%):**
- [ ] 🚨 Рефакторинг: broadcast логика дублируется (routes + events)
- [ ] 🚨 Event bus в service layer вместо emit из routes
- [ ] Optimistic updates (apply change before server response)
- [ ] Active users indicator (user_joined_board/user_left_board events)
- [ ] Connection status indicator (green/red dot)
- [ ] Conflict resolution при одновременных изменениях
- [ ] Rollback on error

---

## 🚨 КРИТИЧЕСКИЕ ЗАДАЧИ (БЛОКЕРЫ)

### ЗАДАЧА A: Security Fix — WidgetNode XSS Protection
**Приоритет**: 🔴 КРИТИЧНЫЙ  
**Время**: 1 день  
**Статус**: ❌ НЕ РЕШЕНО

**Проблема:**
```tsx
// apps/web/src/components/board/WidgetNodeCard.tsx
<div dangerouslySetInnerHTML={{ __html: node.html_code }} />
// ⚠️ XSS УЯЗВИМОСТЬ!
```

**Решение:**
- [ ] Создать iframe sandbox для widget rendering
- [ ] Implement CSP (Content Security Policy)
- [ ] Sanitize HTML/CSS/JS перед рендерингом
- [ ] Error boundary для ловли ошибок виджетов

**Код:**
```tsx
<iframe
    srcDoc={generateSecureHTML(node)}
    sandbox="allow-scripts allow-same-origin"
    style={{ width: '100%', height: '100%', border: 'none' }}
/>
```

---

### ЗАДАЧА B: Node Creation Dialogs
**Приоритет**: 🔴 КРИТИЧНЫЙ (блокирует использование UI)  
**Время**: 4-5 дней  
**Статус**: ❌ НЕ РЕШЕНО

**Проблема:**
Невозможно создать ноду с правильными данными через UI. Сейчас используются hardcoded placeholder values.

**Требуется создать:**

1. **CreateDataNodeDialog** (2-3 дня)
   - [ ] Форма: name, description, data_source_type (select dropdown)
   - [ ] Conditional fields по типу source:
     - SQL: query textarea, database select
     - API: endpoint, method, headers (JSON editor)
     - CSV/JSON: file upload
   - [ ] Preview данных (если возможно)
   - [ ] Position auto-calculate (viewport center)

2. **CreateWidgetNodeDialog** (1 день)
   - [ ] Форма: parent_data_node (select), user_prompt (textarea)
   - [ ] Position/size inputs
   - [ ] "Generate with AI" button (stub: returns empty widget)

3. **CreateCommentNodeDialog** (1 день)
   - [ ] Форма: target_node (select), content (textarea)
   - [ ] Markdown preview
   - [ ] Position near target node

4. **CreateEdgeDialog** (1-2 дня)
   - [ ] Auto-detect source/target types
   - [ ] Edge type select (TRANSFORMATION/VISUALIZATION/etc.)
   - [ ] Conditional: code editor для TRANSFORMATION

---

### ЗАДАЧА C: Edit/Delete Functionality
**Приоритет**: 🟡 ВЫСОКИЙ  
**Время**: 2-3 дня  
**Статус**: ❌ НЕ РЕШЕНО

**Требуется:**
- [ ] Context menu на node (right-click)
- [ ] Edit button → dialog с current values
- [ ] Delete button → confirmation + API call
- [ ] EditDataNodeDialog, EditWidgetNodeDialog, EditCommentNodeDialog
- [ ] Error handling

---

## 📅 АКТУАЛИЗИРОВАННЫЙ ПЛАН (Roadmap 2.0)

### 🎯 SPRINT 1: Functional UI (27 янв - 9 фев, 2 недели)
**Цель:** Сделать canvas полностью юзабельным без AI

#### Week 1: Critical Fixes & Dialogs (27 янв - 2 фев)

**День 1 (27.01):**
- [ ] 🔴 ЗАДАЧА A: WidgetNode iframe sandbox (XSS fix)
- [ ] Component: SecureWidgetRenderer с iframe
- [ ] Error boundary для widget errors

**День 2-3 (28-29.01):**
- [ ] 🔴 ЗАДАЧА B.1: CreateDataNodeDialog
- [ ] Форма с conditional fields
- [ ] File upload для CSV/JSON
- [ ] Integration с boardStore

**День 4 (30.01):**
- [ ] 🔴 ЗАДАЧА B.2: CreateWidgetNodeDialog (stub)
- [ ] Parent DataNode select
- [ ] User prompt textarea
- [ ] Placeholder: "AI coming soon"

**День 5 (31.01):**
- [ ] 🔴 ЗАДАЧА B.3: CreateCommentNodeDialog
- [ ] Target node select
- [ ] Markdown editor
- [ ] Position near target

**День 6-7 (1-2.02):**
- [ ] 🔴 ЗАДАЧА B.4: CreateEdgeDialog
- [ ] Auto-detect node types
- [ ] Edge type select
- [ ] Code editor для TRANSFORMATION

#### Week 2: Edit/Delete & Toolbar (3-9 фев)

**День 1-2 (3-4.02):**
- [ ] 🟡 ЗАДАЧА C: Edit/Delete functionality
- [ ] Context menu на nodes (right-click)
- [ ] EditDataNodeDialog, EditWidgetNodeDialog, EditCommentNodeDialog
- [ ] Delete confirmation dialogs

**День 3-4 (5-6.02):**
- [ ] Canvas Toolbar component
- [ ] Zoom controls (+/-, fit, 100%)
- [ ] Minimap toggle
- [ ] Grid toggle
- [ ] Node count indicator

**День 5-6 (7-8.02):**
- [ ] Node improvements:
  - DataNode: Preview data button → modal
  - WidgetNode: Fullscreen button
  - CommentNode: Reply button (stub)
- [ ] Keyboard shortcuts (Delete key, Ctrl+Z stub)

**День 7 (9.02):**
- [ ] Bug fixes & polish
- [ ] Testing with multiple nodes
- [ ] Performance optimization

**Deliverable:** Полностью функциональный UI для ручного создания досок

---

### 🎯 SPRINT 2: Real-time Perfection (10-16 фев, 1 неделя)
**Цель:** Довести Socket.IO до production quality

#### День 1-2 (10-11.02):
- [ ] 🚨 Refactor: Event bus в service layer
- [ ] Remove duplicate broadcast logic
- [ ] Centralize Socket.IO emit в services

#### День 3-4 (12-13.02):
- [ ] Active users tracking
- [ ] user_joined_board/user_left_board events
- [ ] ActiveUsersIndicator component (avatars)
- [ ] Connection status indicator

#### День 5-6 (14-15.02):
- [ ] Optimistic updates на клиенте
- [ ] Rollback on error
- [ ] Conflict resolution strategy
- [ ] Debounce position updates

#### День 7 (16.02):
- [ ] Multi-user testing (2+ clients)
- [ ] Performance testing
- [ ] Bug fixes

**Deliverable:** Production-ready real-time collaboration

---

### 🎯 SPRINT 3: AI Integration Phase 1 (17 фев - 9 мар, 3 недели)
**Цель:** GigaChat + Chat System + Reporter Agent

#### Week 1: Infrastructure (17-23 фев)

**День 1-2:**
- [ ] Install: `langchain`, `langchain-gigachat`, `tiktoken`
- [ ] Get GigaChat API key
- [ ] Config: GIGACHAT_API_KEY в .env
- [ ] Test connection

**День 3-4:**
- [ ] Create `ai_assistant_service.py`
- [ ] AIAssistantService class
- [ ] process_message() method
- [ ] _call_gigachat() integration
- [ ] Rate limiting (10 msg/min)

**День 5-7:**
- [ ] Create `board_context_provider.py`
- [ ] get_board_context() - собрать все узлы
- [ ] Format context для prompt
- [ ] Cache в Redis (TTL 5 min)

#### Week 2: Chat System (24 фев - 2 мар)

**День 1-3:**
- [ ] ChatMessage, ChatSession models
- [ ] Alembic migration
- [ ] API endpoints:
  - POST /api/v1/boards/{boardId}/ai/chat
  - GET /api/v1/boards/{boardId}/ai/chat/history
- [ ] Socket.IO: ai_message_sent/ai_response_received

**День 4-7:**
- [ ] AIAssistantPanel component (правая панель)
- [ ] aiAssistantStore (Zustand)
- [ ] aiAssistantAPI
- [ ] MessageList, Message, InputField
- [ ] Markdown rendering
- [ ] Typing indicator
- [ ] Socket.IO integration

#### Week 3: Reporter Agent (3-9 мар)

**День 1-3:**
- [ ] Create `reporter_agent.py`
- [ ] ReporterAgent class
- [ ] analyze_data_node() method
- [ ] generate_widget_code() с GigaChat
- [ ] Prompts для генерации HTML/CSS/JS

**День 4-5:**
- [ ] API: POST /api/v1/boards/{boardId}/widget-nodes/generate
- [ ] Input: parent_data_node_id, user_prompt
- [ ] Output: WidgetNode с HTML/CSS/JS
- [ ] Auto-create VISUALIZATION edge

**День 6-7:**
- [ ] Update CreateWidgetNodeDialog
- [ ] "Generate with AI" button → API call
- [ ] Loading state (spinner)
- [ ] Preview + Apply
- [ ] Error handling

**Deliverable:** AI может генерировать виджеты из DataNode

---

### 🎯 SPRINT 4: Transformation Agent (10-23 мар, 2 недели)
**Цель:** DataNode → DataNode трансформации

#### Week 1: Agent & Sandbox

**День 1-3:**
- [ ] Create `transformation_agent.py`
- [ ] TransformationAgent class
- [ ] generate_transformation_code()
- [ ] Prompts для Python pandas генерации

**День 4-7:**
- [ ] Create `transformation_executor.py`
- [ ] Python sandbox (RestrictedPython OR Docker)
- [ ] Code validation (syntax, safe imports)
- [ ] Execute transformation
- [ ] Error handling

#### Week 2: API & UI

**День 1-3:**
- [ ] API: POST /api/v1/boards/{boardId}/transformations/generate
- [ ] Create target DataNode с результатом
- [ ] Create TRANSFORMATION edge
- [ ] Store transformation code

**День 4-7:**
- [ ] UI: CreateTransformationDialog
- [ ] Select source DataNodes (multi-select)
- [ ] Describe transformation (textarea)
- [ ] "Generate" button → AI создает код
- [ ] Review code → Execute
- [ ] Replay button на TRANSFORMATION edge

**Deliverable:** AI трансформирует данные между DataNode

---

### 🎯 SPRINT 5+: Multi-Agent System (24 мар+)
**Scope:** Оставшиеся 6 агентов

- Planner Agent (orchestration)
- Analyst Agent (insights)
- Developer Agent (tools)
- Researcher Agent (data fetching)
- Executor Agent (tool execution)
- Data Discovery Agent (public datasets)
- Form Generator Agent (dynamic forms)

---

## 🎯 MVP SCOPE (скорректированный)

**MVP Release Date:** 31 марта 2026

**Must Have:**
- ✅ Auth + Projects + Boards (done)
- ✅ DataNode/WidgetNode/CommentNode CRUD (done)
- ✅ Real-time collaboration (done, needs polish)
- 🔄 Node creation/edit dialogs (sprint 1)
- 🔄 AI Chat System (sprint 3)
- 🔄 Reporter Agent - widget generation (sprint 3)
- 🔄 Transformation Agent - data transforms (sprint 4)

**Nice to Have (post-MVP):**
- Full Multi-Agent System (7 агентов)
- Dynamic Form Generation
- Data Discovery
- Data Lineage visualization
- Undo/Redo
- Export canvas

---

## 📊 UPDATED METRICS

### Готовность по компонентам:

| Компонент               | Было | Сейчас   | Target MVP |
| ----------------------- | ---- | -------- | ---------- |
| Backend Infrastructure  | 50%  | **95%**  | 100%       |
| Backend Models          | 0%   | **100%** | 100%       |
| Backend API             | 0%   | **85%**  | 95%        |
| Frontend Infrastructure | 50%  | **100%** | 100%       |
| Frontend Canvas         | 0%   | **50%**  | 90%        |
| Socket.IO               | 0%   | **60%**  | 90%        |
| AI Integration          | 0%   | **0%**   | 70%        |

### Overall Progress:
- **Was:** ~10-15%
- **Now:** **55%**
- **MVP Target:** **85%** (к 31 марта)

---

## 🚀 IMMEDIATE NEXT STEPS (эта неделя 27 янв - 2 фев)

1. **Понедельник:** XSS fix (iframe sandbox)
2. **Вторник-Среда:** CreateDataNodeDialog
3. **Четверг:** CreateWidgetNodeDialog (stub)
4. **Пятница:** CreateCommentNodeDialog
5. **Выходные:** CreateEdgeDialog

**Goal:** К концу недели все dialogs готовы, UI юзабелен!

---

### ФИЧА 5️⃣: FR-5 — История и undo/redo
**Время**: 2-3 дня  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-1, FR-2, FR-11  
**Блокирует**: Ничего

#### Описание
Локальный undo/redo на клиенте. Опционально: история на сервере с возможностью версионирования.

#### Frontend (основное)
- [ ] History state in Zustand
  - [ ] `historyStack` (массив снимков состояния)
  - [ ] `historyIndex` (текущая позиция)

- [ ] Actions
  - [ ] `undo()` — откатить последнее действие
  - [ ] `redo()` — вернуть отменённое действие
  - [ ] `addToHistory(state)` — при изменении доски

- [ ] Keyboard shortcuts
  - [ ] Ctrl+Z — undo
  - [ ] Ctrl+Y или Ctrl+Shift+Z — redo

- [ ] Components
  - [ ] Undo/Redo buttons в toolbar
  - [ ] Disabled state когда history пуста

#### Backend (опционально)
- [ ] Database model
  - [ ] Model `BoardHistory` (id, board_id, snapshot, action_type, created_at)
  - [ ] Алембик миграция

- [ ] API endpoint
  - [ ] GET `/api/v1/boards/{boardId}/history` — получить историю

#### Tests
- [ ] Frontend: History store tests (add, undo, redo)
- [ ] Frontend: Keyboard shortcut tests

#### Docs
- [ ] Undo/redo behavior

---

### ФИЧА 6️⃣: FR-6, FR-4 — AI Assistant Panel + GigaChat
**Время**: 5-6 дней  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-1, FR-2, FR-Setup  
**Блокирует**: FR-7, FR-12

#### Описание
AI Assistant Panel в правой боковой панели. Интеграция с GigaChat для диалога в контексте доски.

#### Предварительные требования
- [ ] Установить зависимости AI:
  - `langchain` — фреймворк для работы с LLM
  - `langchain-gigachat` — интеграция с GigaChat API
  - `tiktoken` — токенизация для контроля длины промптов
- [ ] Получить API ключ GigaChat (Yandex Cloud)
- [ ] Добавить в `.env`: `GIGACHAT_API_KEY`, `GIGACHAT_MODEL` (default: GigaChat-Pro)

#### Backend
- [ ] Database models
  - [ ] Model `ChatMessage` (id, board_id, session_id, user_id, role, content, created_at)
  - [ ] Model `ChatSession` (id, board_id, user_id, created_at)
  - [ ] Alembic миграция `004_chat.py`

- [ ] Services
  - [ ] `AIAssistantService` класс
    - [ ] `process_message(board_id, message, user_id)` — основной метод
    - [ ] `_build_system_prompt(board_context)` — собрать контекст доски
    - [ ] `_call_gigachat(messages)` — вызвать GigaChat API
    - [ ] `_parse_response(response)` — парсинг (текст + actions)
  - [ ] `BoardContextProvider` — собрать контекст (widgets, edges, data)
  - [ ] `RateLimiter` service — лимиты (10 msg/min, 100 msg/hour)

- [ ] API endpoints
  - [ ] POST `/api/v1/boards/{boardId}/ai/chat` — отправить сообщение
    - Параметры: message (string, max 2000 chars)
    - Возврат: { message, suggested_actions, session_id }
  - [ ] GET `/api/v1/boards/{boardId}/ai/chat/history` — история
    - Параметры: session_id (опц), limit (default 50), offset
    - Возврат: массив ChatMessage
  - [ ] POST `/api/v1/boards/{boardId}/ai/chat/actions/{actionId}/apply` — применить действие
    - Параметры: action_id
    - Возврат: обновленный widget или список widget

- [ ] Error handling
  - [ ] Graceful degradation если GigaChat недоступен
  - [ ] Retry logic (3 попытки, exponential backoff)
  - [ ] Rate limit error responses (429)

- [ ] Middleware
  - [ ] Rate limiting middleware для chat endpoint

#### Frontend
- [ ] Zustand store (chatStore)
  - [ ] messages (array of ChatMessage)
  - [ ] currentSession
  - [ ] isLoading
  - [ ] error
  - [ ] suggestedActions

- [ ] Components
  - [ ] AIAssistantPanel (боковая панель справа)
    - [ ] Resizable, collapsible
  - [ ] ChatMessage компонент
    - [ ] User message (right, blue background)
    - [ ] Assistant message (left, gray background)
    - [ ] Markdown support (bold, italic, code blocks)
    - [ ] Timestamps
  - [ ] ChatInput компонент
    - [ ] Textarea с auto-height
    - [ ] Send button
    - [ ] Loading indicator
    - [ ] Character counter (max 2000)
  - [ ] SuggestedActions компонент
    - [ ] List of action recommendations
    - [ ] "Apply" button для каждого
    - [ ] Preview что будет создано
  - [ ] ChatHistory компонент
    - [ ] Scrollable message list
    - [ ] Infinite scroll (load older)
    - [ ] Clear history button

- [ ] Hooks
  - [ ] `useAIChat()` — fetch и state management
  - [ ] `useAIChatHistory()` — получить историю

#### Socket.IO
- [ ] Опционально: broadcast когда один юзер получает ответ от AI (для сообщности)

#### Tests
- [ ] Backend: AIAssistantService tests (mock GigaChat)
- [ ] Backend: API endpoint tests
- [ ] Backend: RateLimiter tests
- [ ] Frontend: ChatMessage component tests
- [ ] Frontend: AIAssistantPanel component tests
- [ ] Frontend: Store tests

#### Docs
- [ ] GigaChat API setup guide
- [ ] Environment variable: GIGACHAT_API_KEY
- [ ] Example prompts и responses

---

### ФИЧА 7️⃣: FR-12 — Dynamic Form Generation
**Время**: 3-4 дня  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-6  
**Блокирует**: FR-7 (частично)

#### Описание
Динамическая генерация форм для ввода параметров инструментов и данных источников. JSON schema → React компоненты.

#### Backend
- [ ] Services
  - [ ] `FormGeneratorAgent` (часть агентов, FR-7)
    - [ ] Генерация JSON schema на основе требований
    - [ ] Определение типов полей
    - [ ] Conditional logic (show_if, dependencies)
    - [ ] Validation rules

- [ ] API endpoint (опционально)
  - [ ] POST `/api/v1/boards/{boardId}/generate-form` — генерировать форму
    - Параметры: requirements (string описание)
    - Возврат: { form_schema, default_values }

#### Frontend
- [ ] Components
  - [ ] FormBuilder компонент
    - [ ] Render fields based on JSON schema
    - [ ] Error messages under fields
    - [ ] Validation feedback

- [ ] Field components
  - [ ] TextInput
  - [ ] NumberInput
  - [ ] Select (dropdown)
  - [ ] MultiSelect (checkbox group)
  - [ ] DatePicker
  - [ ] Toggle (boolean)
  - [ ] Textarea

- [ ] Form features
  - [ ] Conditional rendering (show_if logic)
  - [ ] Cascading selects
  - [ ] Required field validation
  - [ ] Min/max validation
  - [ ] Pattern validation (regex)
  - [ ] Custom validators

- [ ] Hooks
  - [ ] `useFormBuilder(schema)` — управление форма state

#### Tests
- [ ] Frontend: FormBuilder component tests
- [ ] Frontend: Field validation tests
- [ ] Frontend: Conditional rendering tests

#### Docs
- [ ] JSON schema format documentation
- [ ] Examples of form schemas

---

### ФИЧА 8️⃣: FR-7, FR-8 — Multi-Agent System + Dynamic Tools
**Время**: 7-8 дней  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-6, FR-12  
**Блокирует**: FR-9, FR-10

#### Описание
Мультиагентная система (7 агентов) с динамической генерацией и выполнением инструментов (Python/SQL/JS) в sandbox.

#### Backend
- [ ] Database models
  - [ ] Model `ToolRegistry` (id, name, code, language, version, category, created_at)
  - [ ] Model `ToolExecution` (id, tool_id, status, input_data, output_data, error, created_at)
  - [ ] Alembic миграция `005_tools_agents.py`

- [ ] Services
  - [ ] `CodeValidator` класс
    - [ ] AST parsing для Python/SQL/JS
    - [ ] Проверка на опасные операции
    - [ ] Syntax validation

  - [ ] `SandboxExecutor` класс
    - [ ] Docker container OR Process isolation
    - [ ] Timeout management (30s default)
    - [ ] Memory limits (512MB default)
    - [ ] Capture stdout/stderr

  - [ ] `ToolRegistry` service
    - [ ] CRUD операции
    - [ ] Версионирование
    - [ ] Redis кэш

  - [ ] Agent framework
    - [ ] `BaseAgent` абстрактный класс
    - [ ] `MessageBus` (Redis pub/sub)
    - [ ] Logging + Telemetry

- [ ] Реализация 7 агентов
  - [ ] `PlannerAgent` — разбор запроса на подзадачи
  - [ ] `ResearcherAgent` — получение данных
  - [ ] `AnalystAgent` — анализ данных
  - [ ] `DeveloperAgent` — генерация кода инструментов
  - [ ] `ExecutorAgent` — выполнение инструментов
  - [ ] `ReporterAgent` — создание виджетов
  - [ ] `FormGeneratorAgent` — генерация форм

- [ ] Orchestrator
  - [ ] `AgentOrchestrator` класс
    - [ ] `orchestrate(user_message, board_id)` — точка входа
    - [ ] Маршрутизация между агентами
    - [ ] Управление состоянием conversation
    - [ ] Progress updates в Socket.IO

- [ ] Built-in tools
  - [ ] SQL Query Tool (`sql_query.py`)
  - [ ] HTTP Request Tool (`http_request.py`)
  - [ ] Web Scraper Tool (`web_scraper.py`)
  - [ ] File Operations Tool (`file_operations.py`)
  - [ ] Data Transform Tool (`data_transform.py`)

- [ ] API endpoints
  - [ ] GET `/api/v1/tools` — список всех инструментов
  - [ ] POST `/api/v1/tools` — создать/загрузить инструмент
  - [ ] POST `/api/v1/tools/{toolId}/execute` — запустить инструмент
  - [ ] GET `/api/v1/tools/{toolId}/executions` — логи выполнения

#### Frontend
- [ ] Agent reasoning display (опционально)
  - [ ] Show thinking process in chat (для отладки)
  - [ ] Progress bar для длительных операций

#### Tests
- [ ] Backend: CodeValidator тесты
- [ ] Backend: SandboxExecutor тесты (безопасность)
- [ ] Backend: ToolRegistry тесты
- [ ] Backend: Agent тесты (mock Message Bus)
- [ ] Backend: API endpoint тесты

#### Docs
- [ ] Agent communication architecture
- [ ] Tool development guide (как писать инструменты)
- [ ] Security guide (что опасно, что нет)

---

### ФИЧА 9️⃣: FR-9 — Widget Code Generation
**Время**: 3-4 дня  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-8 (для agent), FR-1, FR-2 (для widgets)  
**Блокирует**: Ничего критичного

#### Описание
Генерация HTML/CSS/JS кода для виджетов (6 типов) на основе данных. Reporter Agent может создавать красивые визуализации.

#### Backend
- [ ] Services
  - [ ] `WidgetCodeGenerator` класс
    - [ ] `generate_metric_widget(data, config)` → HTML/CSS/JS
    - [ ] `generate_chart_widget(data, config)` → Chart.js
    - [ ] `generate_table_widget(data, config)` → HTML table
    - [ ] `generate_heatmap_widget(data, config)` → D3/Plotly
    - [ ] `generate_gauge_widget(data, config)` → SVG gauge
    - [ ] `generate_custom_html_widget(code)` → HTML validation

  - [ ] Widget code templates (в папке `templates/`)

- [ ] Features
  - [ ] Dark mode support (CSS variables)
  - [ ] Responsive design (mobile/tablet/desktop)
  - [ ] Code validation (size, security, performance)

#### Frontend
- [ ] Components
  - [ ] Widget renderers (iframe для HTML виджетов)
  - [ ] Chart wrapper (для Chart.js)
  - [ ] Table wrapper (с сортировкой)

#### Tests
- [ ] Backend: Widget generation тесты (проверка HTML)

#### Docs
- [ ] Widget types documentation
- [ ] Code generation templates

---

### ФИЧА 🔟: FR-10 — Board Construction System
**Время**: 2-3 дня  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-9, FR-8  
**Блокирует**: Ничего

#### Описание
Reporter Agent активно строит доски, размещая виджеты оптимальными лэйаутами и создавая связи между ними.

#### Backend
- [ ] Services
  - [ ] `BoardConstructionService` класс
    - [ ] `layout_grid(widgets)` — сетка 3 колонки
    - [ ] `layout_flow(widgets)` — слева направо
    - [ ] `layout_hierarchy(widgets)` — иерархия
    - [ ] `layout_freeform(widgets)` — случайно
    - [ ] `validate_edge()` — проверка циклических зависимостей
    - [ ] `auto_arrange_widgets(board_id)` — автоматическое расположение

- [ ] Integration in ReporterAgent
  - [ ] Вызов Board Construction API при создании виджетов

#### Frontend
- [ ] Auto-layout visualization (опционально)
  - [ ] Показать как агент размещает виджеты

#### Tests
- [ ] Backend: Layout algorithm тесты
- [ ] Backend: Validation тесты

---

### ФИЧА 11: FR-13 — Public Data Discovery & Integration
**Время**: 4-5 дней  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-6, FR-7, FR-8  
**Блокирует**: Ничего (optional feature для MVP+)

#### Описание
Позволяет пользователям без собственных данных находить и анализировать публичные датасеты из различных источников (Kaggle, Open Data, APIs).

#### Backend
- [ ] Data Discovery Agent (8-й агент)
  - [ ] `DataDiscoveryAgent` класс
    - [ ] `search_datasets(query, sources)` — поиск по запросу
    - [ ] `rank_by_relevance(datasets, query)` — ранжирование
    - [ ] `fetch_dataset_preview(source, id)` — превью данных
    - [ ] `validate_data_quality(dataset)` — проверка качества
  - [ ] Интеграция с Planner Agent

- [ ] Public Data Connectors
  - [ ] `RosstatConnector` — интеграция с Росстатом
    - [ ] Поиск датасетов по категориям
    - [ ] Загрузка статистики в Excel/CSV
    - [ ] Метаданные (период, регион, источник)
  - [ ] `EMISSConnector` — fedstat.ru (ЕМИСС)
  - [ ] `DataGovRuConnector` — data.gov.ru, data.mos.ru
  - [ ] `MOEXConnector` — Московская биржа (котировки, облигации)
  - [ ] `CBRConnector` — ЦБ РФ (курсы валют, ключевая ставка)
  - [ ] `VKAPIConnector` — VK API (социальные тренды)
  - [ ] `YandexMapsConnector` — Яндекс.Карты API (геоданные)
  - [ ] `NewsRuConnector` — РИА Новости, ТАСС, Яндекс.Новости

- [ ] Dataset Registry & Cache
  - [ ] Database model `PublicDataset`
    - [ ] source, dataset_id, name, description, size, quality_score
    - [ ] last_updated, category, tags, download_count
  - [ ] Redis cache для популярных датасетов
  - [ ] Alembic миграция `006_public_datasets.py`

- [ ] API endpoints
  - [ ] POST `/api/v1/data/search` — поиск публичных данных
    - Request: `{ "query": "climate change data", "sources": ["kaggle", "world_bank"] }`
    - Response: список датасетов с рейтингами
  - [ ] GET `/api/v1/data/sources` — список доступных источников
  - [ ] POST `/api/v1/data/preview/{source}/{dataset_id}` — превью датасета
  - [ ] POST `/api/v1/data/load/{source}/{dataset_id}` — загрузить в борд

- [ ] Data Quality Validator
  - [ ] `check_completeness()` — % пропущенных значений
  - [ ] `check_freshness()` — когда последнее обновление
  - [ ] `check_credibility()` — рейтинг источника

#### Frontend
- [ ] Zustand store (publicDataStore)
  - [ ] availableSources (список источников)
  - [ ] searchResults (найденные датасеты)
  - [ ] selectedDataset
  - [ ] isLoading, error

- [ ] Components
  - [ ] DataSearchPanel компонент
    - [ ] Input для поискового запроса
    - [ ] Фильтры по источникам, категориям
    - [ ] Результаты поиска с превью
  - [ ] DatasetCard компонент
    - [ ] Название, описание, источник
    - [ ] Метрики (размер, качество, свежесть)
    - [ ] Кнопка "Загрузить" / "Предпросмотр"
  - [ ] DatasetPreviewModal
    - [ ] Таблица с первыми 100 строками
    - [ ] Статистика (колонки, типы, missing values)
    - [ ] Кнопка "Загрузить на доску"
  - [ ] SampleProjectsGallery
    - [ ] Галерея готовых шаблонов досок
    - [ ] "COVID-19 Dashboard", "Stock Analysis", "Climate Trends"
    - [ ] One-click deploy с актуальными данными

- [ ] AI Assistant интеграция
  - [ ] Команда в чате: "Найди данные о [topic]"
  - [ ] Отображение результатов в чате
  - [ ] Quick actions для загрузки датасета

#### Database
- [ ] Alembic `006_public_datasets.py`
- [ ] Create `public_datasets` table
- [ ] Create `dataset_usage` table (для статистики)
- [ ] Индексы: `public_datasets(source, category)`, `dataset_usage(dataset_id, user_id)`

#### Tests
- [ ] Backend: DataDiscoveryAgent тесты
- [ ] Backend: Connectors тесты (mock API responses)
- [ ] Backend: Data quality validator тесты
- [ ] Frontend: DataSearchPanel тесты
- [ ] Frontend: Dataset selection flow тесты
- [ ] Integration: Full workflow test (search → preview → load)

#### Docs
- [ ] Документация по поддерживаемым источникам
- [ ] Примеры запросов к Public Data API
- [ ] Sample Projects Gallery описание
- [ ] Tutorial: "Как начать без своих данных"

#### Зависимости (внешние API keys)
- [ ] Московская биржа API key (для финансовых данных MOEX)
- [ ] ЦБ РФ API (для курсов валют - публичный, без ключа)
- [ ] VK API key (для анализа социальных трендов)
- [ ] Яндекс.Карты API key (для геоданных)
- [ ] data.gov.ru / data.mos.ru (публичные, без ключа)
- [ ] Росстат / ЕМИСС (публичные, возможна регистрация для расширенного доступа)
- [ ] Telegram Bot API (optional, для анализа каналов)

---

### ФИЧА 12: FR-14 — Widget Transformation System
**Время**: 5-6 дней  
**Статус**: ⏳ Не начато  
**Зависит от**: FR-6, FR-7, FR-8, FR-11  
**Блокирует**: Нет

#### Описание
Система интеллектуальных трансформаций виджетов. Пользователь выделяет виджеты, ИИ анализирует и предлагает операции (аналитические, композиционные, предиктивные). Новый виджет создаётся с графом зависимостей (data lineage).

#### Backend
- [ ] Services
  - [ ] `TransformationAgent` (9-й агент)
    - [ ] `analyze_selection()` — анализ выделенных виджетов
    - [ ] `suggest_operations()` — контекстные предложения
    - [ ] `execute_transform()` — выполнение трансформации
    - [ ] `preview_transform()` — превью результата
    - [ ] `track_lineage()` — сохранение графа зависимостей
  
  - [ ] TransformationService
    - [ ] Координирует работу Transformation + Developer + Executor + Reporter
    - [ ] Управление историей трансформаций
    - [ ] Template library (популярные трансформации)

- [ ] Models
  - [ ] `TransformationEdge` (extends Edge)
    - [ ] source_widget_ids: List[str]
    - [ ] target_widget_id: str
    - [ ] operation: str
    - [ ] code: str
    - [ ] timestamp
  - [ ] `TransformationTemplate`
    - [ ] name, description, category
    - [ ] required_input_types
    - [ ] code_template
    - [ ] usage_count (для рейтинга)

- [ ] API endpoints
  - [ ] POST `/api/v1/boards/{boardId}/transform`
    - Body: { widget_ids, custom_prompt? }
    - Returns: { suggestions: [TransformOperation] }
  - [ ] POST `/api/v1/boards/{boardId}/transform/preview`
    - Body: { operation_id, widget_ids }
    - Returns: { preview_data, estimated_size, warnings }
  - [ ] POST `/api/v1/boards/{boardId}/transform/execute`
    - Body: { operation_id, widget_ids, params? }
    - Returns: { new_widget_id, lineage_edges, execution_time }
  - [ ] GET `/api/v1/transform/templates`
    - Returns: { templates: [TransformationTemplate] }

- [ ] Operation Categories
  - [ ] Analytical: time series, statistics, correlation, anomalies
  - [ ] Compositional: combine charts, create dashboards
  - [ ] Data transformations: aggregate, pivot, join, filter
  - [ ] Generative: text summaries, reports
  - [ ] Predictive: ARIMA, ML models, anomaly detection

#### Frontend
- [ ] Zustand store (transformationStore)
  - [ ] selectedWidgets, suggestions, previewData
  - [ ] transformationHistory

- [ ] Components
  - [ ] WidgetSelectionManager (Shift+Click, Lasso)
  - [ ] TransformationMenu (Ctrl+T, context menu)
  - [ ] TransformationPreview (показ результата)
  - [ ] LineageVisualizer (граф зависимостей)
  - [ ] TransformationHistory panel

- [ ] Canvas integration
  - [ ] Multi-select UI
  - [ ] Lineage edges rendering
  - [ ] Keyboard shortcuts

#### Database
- [ ] Alembic `007_transformations.py`
- [ ] Extend `edges` table: operation, code, execution_time
- [ ] Create `transformation_templates` table
- [ ] Create `transformation_history` table

#### Tests
- [ ] Backend: TransformationAgent, operations
- [ ] Frontend: Menu, Lineage, History
- [ ] Integration: End-to-end transformation flow

#### Docs
- [ ] User guide: "How to Transform Widgets"
- [ ] Developer guide: "Adding Custom Transformations"
- [ ] API documentation
- [ ] Examples: Common patterns

---

## 📊 TIMELINE SUMMARY

| #   | Фича             | Задача                         | Дни | Статус | Конец       |
| --- | ---------------- | ------------------------------ | --- | ------ | ----------- |
| 1   | FR-Setup         | Инфраструктура, аутентификация | 3-4 | ⏳      | ~2026-01-26 |
| 2   | FR-1, FR-2       | Доски, виджеты, CRUD           | 4-5 | ⏳      | ~2026-02-02 |
| 3   | FR-3             | Real-time Socket.IO            | 3-4 | ⏳      | ~2026-02-06 |
| 4   | FR-11            | Связи между виджетами          | 3-4 | ⏳      | ~2026-02-10 |
| 5   | FR-5             | Undo/redo история              | 2-3 | ⏳      | ~2026-02-13 |
| 6   | FR-6, FR-4       | AI Assistant Panel + GigaChat  | 5-6 | ⏳      | ~2026-02-20 |
| 7   | FR-12            | Dynamic Form Generation        | 3-4 | ⏳      | ~2026-02-24 |
| 8   | FR-7, FR-8       | Multi-Agent + Tools            | 7-8 | ⏳      | ~2026-03-04 |
| 9   | FR-9             | Widget Code Generation         | 3-4 | ⏳      | ~2026-03-08 |
| 10  | FR-10            | Board Construction System      | 2-3 | ⏳      | ~2026-03-11 |
| 11  | FR-13            | Public Data Discovery          | 4-5 | ⏳      | ~2026-03-16 |
| 12  | FR-14            | Widget Transformation System   | 5-6 | ⏳      | ~2026-03-23 |
| -   | **Тестирование** | Unit + Integration + E2E       | 5-7 | ⏳      | ~2026-04-01 |
| -   | **Документация** | Docs + Deployment              | 3-5 | ⏳      | ~2026-04-08 |

**Итого**: 52-64 дня (11-13 недель)  
**Старт**: 2026-01-24  
**MVP релиз**: ~2026-04-08 (с небольшим резервом до 2026-04-25)

**ОБЩЕЕ ВРЕМЯ**: ~13-15 недель (2026-01-24 → 2026-04-25)

---

## 🎯 КРИТИЧЕСКИЕ ПУТИ

```
FR-Setup (инфраструктура)
  ↓
FR-1, FR-2 (доски, виджеты)
  ↓
FR-3 (real-time)
FR-11 (связи) ↓     ↓
            FR-5 (history)
              ↓
            FR-6, FR-4 (AI)
              ↓
            FR-12 (форма)
              ↓
            FR-7, FR-8 (агенты + инструменты)
              ↓
            FR-9 (генерация кода)
              ↓
            FR-10 (конструктор досок)
```

Параллельные потоки:
- FR-1 + FR-3 + FR-11 могут идти параллельно (после FR-2)
- FR-9 + FR-10 могут идти параллельно (после FR-8)
- Тестирование идёт параллельно со всеми фичами

---

## ✅ CHECKLIST ПО ФИЧЕ

Когда начинаете новую фичу:

```markdown
### ФИЧА N: FR-X
- [ ] Backend implementation
  - [ ] Models created
  - [ ] API endpoints working
  - [ ] Error handling complete
  - [ ] Validation working
  
- [ ] Frontend implementation
  - [ ] Components created
  - [ ] State management (Zustand)
  - [ ] Socket.IO integration (если нужна)
  - [ ] Styling complete
  
- [ ] Database
  - [ ] Alembic migration created
  - [ ] Migration tested (up/down)
  
- [ ] Tests
  - [ ] Backend unit tests (>80% coverage)
  - [ ] Backend integration tests
  - [ ] Frontend component tests
  - [ ] All tests passing
  
- [ ] Documentation
  - [ ] API docs updated
  - [ ] Examples added
  - [ ] Deployment notes
  
- [ ] Code Review
  - [ ] Code reviewed
  - [ ] No blockers
  - [ ] Merged to main
  
- [ ] Testing/QA
  - [ ] Manual testing done
  - [ ] No regressions
  - [ ] Ready to merge/deploy
```

---

## 🚀 КАК РАБОТАТЬ С ЭТИМ ПЛАНОМ

**Для каждой фичи:**

1. Скопируйте checklist выше в задачу
2. Начните с Backend implementation (обычно самое дальше)
3. Параллельно делайте Frontend
4. Database миграции идут с Backend
5. Tests идут параллельно
6. Documentation в конце
7. Отметьте чекбоксы по мере выполнения

**Примеры обновления:**

```markdown
### ФИЧА 1: FR-Setup ✅ ЗАВЕРШЕНО (2026-01-26)

### ФИЧА 2: FR-1, FR-2 🟡 В ПРОЦЕССЕ (Day 3/5)
- [x] Model Board создана
- [x] Model Widget создана
- [ ] API endpoints (50% готово)
  - [x] POST /boards
  - [x] GET /boards/{id}
  - [ ] PUT /boards/{id}
  - [ ] DELETE /boards/{id}
- [ ] Frontend Canvas (не начинался)
```

---

## 💡 РЕКОМЕНДАЦИИ

1. **Не пропускайте тесты** — они спасают позже
2. **Документируйте API** — даже примерами curl
3. **Делайте code reviews** — перед мержем в main
4. **Тестируйте интеграцию** — на реальных данных
5. **Коммитьте часто** — по завершении subtask
6. **Обновляйте план** — для отслеживания прогресса

---

**Последнее обновление**: 2026-01-24  
**Подход**: Feature-Driven Development  
**Целевой Release**: 2026-04-25
