# 🔬 GigaBoard: Детальный анализ кода и реального состояния проекта

**Дата анализа:** 26 января 2026  
**Анализ:** Полный код review backend + frontend  
**Метод:** Сравнение документации vs реальной реализации

---

## 📊 EXECUTIVE SUMMARY

### Общая готовность проекта: **55%**

| Компонент                    | Документация | Реализация | Готовность |
| ---------------------------- | ------------ | ---------- | ---------- |
| **Backend Infrastructure**   | ✅ 100%       | ✅ 95%      | **95%**    |
| **Backend Models**           | ✅ 100%       | ✅ 100%     | **100%**   |
| **Backend API Routes**       | ✅ 100%       | ✅ 85%      | **85%**    |
| **Backend Services**         | ✅ 100%       | ✅ 80%      | **80%**    |
| **Socket.IO Server**         | ✅ 100%       | ⚠️ 60%      | **60%**    |
| **Frontend Infrastructure**  | ✅ 100%       | ✅ 100%     | **100%**   |
| **Frontend State (Zustand)** | ✅ 100%       | ✅ 95%      | **95%**    |
| **Frontend Canvas**          | ✅ 100%       | ⚠️ 50%      | **50%**    |
| **Frontend Node Components** | ✅ 100%       | ⚠️ 40%      | **40%**    |
| **Socket.IO Client**         | ✅ 100%       | ✅ 80%      | **80%**    |
| **AI Integration**           | ✅ 100%       | ❌ 0%       | **0%**     |
| **Multi-Agent System**       | ✅ 100%       | ❌ 0%       | **0%**     |

**Главный вывод:** Базовая инфраструктура и CRUD операции работают. Отсутствует AI-интеграция и расширенные UI компоненты.

---

## 🎯 BACKEND: Детальный анализ

### ✅ ЧТО РЕАЛЬНО РАБОТАЕТ

#### 1. Infrastructure (95% ✅)

**Файл:** `apps/backend/app/main.py`

```python
# ✅ РЕАЛИЗОВАНО:
- FastAPI app с lifespan management
- CORS middleware настроен
- PostgreSQL + SQLAlchemy async engine (init_db/close_db)
- Redis connection (init_redis/close_redis)
- Socket.IO интеграция через CombinedASGI router
- Логирование
- Health checks

# ⚠️ ЧАСТИЧНО:
- Socket.IO роутинг работает, но debugging логи избыточны (нужна настройка уровней)

# ❌ НЕ РЕАЛИЗОВАНО:
- Rate limiting middleware
- Monitoring/metrics (Prometheus)
```

#### 2. Database Models (100% ✅)

**Файлы проверены:**
- `app/models/user.py` ✅
- `app/models/project.py` ✅
- `app/models/board.py` ✅
- `app/models/data_node.py` ✅
- `app/models/widget_node.py` ✅
- `app/models/comment_node.py` ✅
- `app/models/edge.py` ✅

**Статус:** Все модели полностью реализованы согласно документации.

**Особенности:**
- WidgetNode обновлен под AI-генерацию (description вместо widget_type) ✅
- Edge поддерживает 5 типов (TRANSFORMATION, VISUALIZATION, COMMENT, DRILL_DOWN, REFERENCE) ✅
- Polymorphic references в Edge (source_node_id/type, target_node_id/type) ✅

#### 3. API Routes (85% ✅)

**Реализованные routes:**

```
✅ /health - Health check
✅ /api/v1/health - Extended health (DB + Redis)

✅ /api/v1/auth/register - Регистрация
✅ /api/v1/auth/login - Вход
✅ /api/v1/auth/logout - Выход
✅ /api/v1/auth/me - Текущий юзер

✅ /api/v1/projects - CRUD проектов (5 endpoints)

✅ /api/v1/boards - CRUD досок (5 endpoints)

✅ /api/v1/boards/{boardId}/data-nodes - CRUD DataNode (5 endpoints)
   - POST create ✅ (с broadcast через Socket.IO)
   - GET list ✅
   - GET by ID ✅
   - PATCH update ✅ (с broadcast)
   - DELETE ✅ (с broadcast)

✅ /api/v1/boards/{boardId}/widget-nodes - CRUD WidgetNode (5 endpoints)
   - POST create ✅ (с broadcast)
   - GET list ✅
   - GET by ID ✅
   - PATCH update ✅ (с broadcast)
   - DELETE ✅ (с broadcast)

✅ /api/v1/boards/{boardId}/comment-nodes - CRUD CommentNode (6 endpoints)
   - POST create ✅
   - GET list ✅
   - GET by ID ✅
   - PATCH update ✅
   - DELETE ✅
   - POST resolve ✅

✅ /api/v1/boards/{boardId}/edges - CRUD Edges (5 endpoints)
   - POST create ✅
   - GET list ✅
   - GET by ID ✅
   - PATCH update ✅ (частично)
   - DELETE ✅
```

**Анализ routes/data_nodes.py:**
```python
# ✅ Broadcast events работают:
await sio.emit("data_node_created", {...}, room=f"board:{board_id}")
await sio.emit("data_node_updated", {...}, room=f"board:{board_id}")
await sio.emit("data_node_deleted", {...}, room=f"board:{board_id}")

# ⚠️ НО: emit идет из routes, а не из service layer (плохая практика)
# Решение: Переместить broadcast в service или использовать event bus
```

**❌ НЕ РЕАЛИЗОВАНО:**

```
❌ /api/v1/boards/{boardId}/ai/chat - AI Assistant endpoints
❌ /api/v1/boards/{boardId}/ai/chat/history
❌ /api/v1/boards/{boardId}/ai/chat/actions/{actionId}/apply

❌ /api/v1/boards/{boardId}/transformations - Transformation management
❌ /api/v1/boards/{boardId}/transformations/generate
❌ /api/v1/boards/{boardId}/transformations/{transformationId}/replay

❌ /api/v1/boards/{boardId}/widget-nodes/generate - AI widget generation
❌ /api/v1/boards/{boardId}/data-nodes/{dataNodeId}/refresh - Data refresh
```

#### 4. Services (80% ✅)

**Реализованные services:**

`BoardService` (100% ✅):
```python
✅ create_board() - с проверкой project ownership
✅ get_board() - с user authorization
✅ list_boards() - с фильтрацией по project
✅ list_boards_with_counts() - с подсчетом узлов (JOIN queries)
✅ update_board()
✅ delete_board()
```

`DataNodeService` (100% ✅):
```python
✅ create_data_node() - с board validation
✅ get_data_node() - с user authorization (JOIN Board)
✅ list_data_nodes()
✅ update_data_node()
✅ delete_data_node()
```

`WidgetNodeService` (100% ✅):
```python
✅ create_widget_node()
✅ get_widget_node()
✅ list_widget_nodes()
✅ update_widget_node()
✅ delete_widget_node()
```

`CommentNodeService` (100% ✅):
```python
✅ create_comment_node()
✅ get_comment_node()
✅ list_comment_nodes()
✅ update_comment_node()
✅ delete_comment_node()
✅ resolve_comment_node()
```

`EdgeService` (90% ✅):
```python
✅ create_edge() - с валидацией node types
✅ get_edge()
✅ list_edges()
⚠️ update_edge() - частичная реализация (нет валидации transformation_code)
✅ delete_edge()

❌ validate_transformation_code() - не реализовано
❌ replay_transformation() - не реализовано
```

`AuthService` (100% ✅):
```python
✅ register_user() - с password hashing (bcrypt)
✅ login_user() - JWT token generation
✅ get_current_user() - token validation
```

**❌ НЕ РЕАЛИЗОВАННЫЕ SERVICES:**

```python
❌ AIAssistantService - главный сервис для AI
   - process_message()
   - _build_system_prompt()
   - _call_gigachat()
   - _parse_response()
   - apply_action()

❌ Multi-Agent Services:
   - PlannerAgent
   - AnalystAgent
   - DeveloperAgent
   - ResearcherAgent
   - TransformationAgent
   - ExecutorAgent
   - ReporterAgent
   - DataDiscoveryAgent
   - FormGeneratorAgent

❌ BoardContextProvider - сборка контекста доски для AI

❌ ToolRegistry - управление инструментами

❌ TransformationExecutor - выполнение трансформаций в sandbox

❌ CodeValidator - валидация генерируемого кода

❌ DataLineageTracker - отслеживание data lineage
```

#### 5. Socket.IO Server (60% ⚠️)

**Файл:** `apps/backend/app/socketio_events.py`

**✅ РЕАЛИЗОВАНО:**

```python
# Core events:
✅ connect(sid, environ)
✅ disconnect(sid)
✅ join_board(sid, data)
✅ leave_board(sid, data)

# DataNode events (server → client broadcast):
✅ data_node_created
✅ data_node_updated
✅ data_node_deleted

# WidgetNode events:
✅ widget_node_created
✅ widget_node_updated
✅ widget_node_deleted

# CommentNode events:
✅ comment_node_created
✅ comment_node_updated
✅ comment_node_deleted
✅ comment_node_resolved

# Edge events:
✅ edge_created
✅ edge_updated
✅ edge_deleted
```

**⚠️ ПРОБЛЕМЫ:**

1. **Дублирование логики broadcast:**
   - Events регистрируются в `socketio_events.py`
   - НО broadcast идет из routes (data_nodes.py, widget_nodes.py)
   - Нужно централизовать: либо все в events, либо использовать event bus

2. **События от client → server:**
   - Реализованы handlers для broadcast (data_node_created и т.д.)
   - НО они ожидают `data` от клиента, а клиент их не использует
   - Клиент создает ноды через REST API, broadcast идет из routes
   - Логика запутана

3. **Отсутствуют events:**
   ```python
   ❌ user_joined_board - показать кого в комнате
   ❌ user_left_board - уведомление об уходе
   ❌ active_users - список активных пользователей
   ❌ transformation_executed - результат трансформации
   ❌ ai_message_received - сообщение от AI
   ```

**✅ ЧТО РАБОТАЕТ ХОРОШО:**

- Room management (join/leave) работает корректно
- Broadcast в комнату `board:{boardId}` функционирует
- Session management через `sio.save_session()`

#### 6. Schemas (100% ✅)

Все Pydantic schemas реализованы:
- ✅ `BoardCreate`, `BoardUpdate`, `BoardResponse`, `BoardWithNodesResponse`
- ✅ `DataNodeCreate`, `DataNodeUpdate`, `DataNodeResponse`
- ✅ `WidgetNodeCreate`, `WidgetNodeUpdate`, `WidgetNodeResponse`
- ✅ `CommentNodeCreate`, `CommentNodeUpdate`, `CommentNodeResponse`
- ✅ `EdgeCreate`, `EdgeUpdate`, `EdgeResponse`
- ✅ `UserCreate`, `UserLogin`, `UserResponse`, `TokenResponse`

**Особенность:** `schema_` с alias `"schema"` для избежания конфликта с reserved keyword.

#### 7. Migrations (100% ✅)

**Файлы:** `apps/backend/migrations/versions/`

```
✅ 001_initial_users.py - Users + UserSessions
✅ 002_projects_boards_widgets.py - Projects + Boards + старые виджеты
✅ 003_edges.py - Edges таблица
✅ 004_datanode_architecture.py - DataNode + WidgetNode + CommentNode
✅ 005_update_edge_type_enum.py - Обновление EdgeType enum
```

Все миграции применены, база данных соответствует моделям.

---

## 🎨 FRONTEND: Детальный анализ

### ✅ ЧТО РЕАЛЬНО РАБОТАЕТ

#### 1. Infrastructure (100% ✅)

**React + Vite + TypeScript:**
```
✅ Vite config с hot reload
✅ TypeScript strict mode
✅ Path aliases (@/*)
✅ Environment variables (.env)
✅ Tailwind CSS + PostCSS
✅ shadcn/ui компоненты
```

**Routing (React Router v6):**
```tsx
✅ /login - LoginPage
✅ /register - RegisterPage
✅ / - LandingPage
✅ /welcome - WelcomePage
✅ /projects/:projectId - ProjectOverviewPage
✅ /projects/:projectId/boards/:boardId - BoardPage
✅ Protected routes (ProtectedRoute wrapper)
```

#### 2. State Management (95% ✅)

**Zustand Stores:**

`authStore.ts` (100% ✅):
```typescript
✅ State: user, token, isLoading, error
✅ Actions: login(), logout(), register(), checkAuth(), clearError()
✅ Token persistence (localStorage)
✅ Auto-logout on 401
```

`projectStore.ts` (100% ✅):
```typescript
✅ State: projects, currentProject, isLoading, error
✅ Actions: fetchProjects(), createProject(), updateProject(), deleteProject()
✅ API integration: projectsAPI.list/create/update/delete
```

`boardStore.ts` (100% ✅):
```typescript
✅ State: boards, currentBoard, dataNodes, widgetNodes, commentNodes, edges
✅ Actions (Boards): fetchBoards(), createBoard(), updateBoard(), deleteBoard()
✅ Actions (DataNodes): fetchDataNodes(), createDataNode(), updateDataNode(), deleteDataNode()
✅ Actions (WidgetNodes): fetchWidgetNodes(), createWidgetNode(), updateWidgetNode(), deleteWidgetNode()
✅ Actions (CommentNodes): fetchCommentNodes(), createCommentNode(), updateCommentNode(), deleteCommentNode(), resolveCommentNode()
✅ Actions (Edges): fetchEdges(), createEdge(), updateEdge(), deleteEdge()
✅ API integration: все CRUD операции
```

`notificationStore.ts` (100% ✅):
```typescript
✅ Toast notifications (success, error, warning, info)
✅ notify.success(), notify.error(), etc.
```

`uiStore.ts` (80% ✅):
```typescript
✅ State: createProjectDialogOpen, createBoardDialogOpen
✅ Actions: openCreateProjectDialog(), closeCreateProjectDialog()
⚠️ НЕТ: AI panel state, node creation dialogs state
```

**Анализ:** State management реализован отлично, но не хватает state для:
- AI Assistant Panel (открыт/закрыт, история чата)
- Node creation dialogs (DataNode, WidgetNode, CommentNode)
- Canvas UI state (выделенные ноды, zoom level, minimap visible)

#### 3. API Services (100% ✅)

**Файл:** `apps/web/src/services/api.ts`

```typescript
✅ authAPI: register, login, logout, me
✅ healthAPI: check
✅ projectsAPI: list, create, get, update, delete
✅ boardsAPI: list, create, get, update, delete
✅ dataNodesAPI: list, create, get, update, delete
✅ widgetNodesAPI: list, create, get, update, delete
✅ commentNodesAPI: list, create, get, update, delete, resolve
✅ edgesAPI: list, create, get, update, delete

✅ Auto-token injection (Authorization header)
✅ Error handling (401 → auto logout)
✅ Base URL от env variable
```

**❌ НЕ РЕАЛИЗОВАНО:**
```typescript
❌ aiAssistantAPI - AI chat endpoints
❌ transformationsAPI - трансформации
❌ toolsAPI - инструменты
```

#### 4. React Flow Canvas (50% ⚠️)

**Файл:** `apps/web/src/components/board/BoardCanvas.tsx`

**✅ РЕАЛИЗОВАНО:**

```tsx
// Core React Flow setup:
✅ ReactFlowProvider wrapper
✅ ReactFlow component с props (nodes, edges, onNodesChange, onEdgesChange, onConnect)
✅ Background, Controls, MiniMap
✅ Custom node types: dataNode, widgetNode, commentNode

// State management:
✅ Fetch nodes и edges при загрузке доски
✅ Конвертация DataNode/WidgetNode/CommentNode → ReactFlow Node
✅ Конвертация Edge → ReactFlow Edge

// Node updates:
✅ onNodesChange - обработка drag/select/remove
✅ Position updates (updateDataNode/updateWidgetNode/updateCommentNode с x, y)
✅ onEdgesChange - обработка edge changes

// Socket.IO:
✅ useBoardSocket hook подключен
✅ Real-time updates nodes/edges

// UI elements:
✅ "+ Create Node" button (показывает/скрывает меню)
✅ Node creation menu (Database, Chart, Comment icons)
```

**⚠️ ЧАСТИЧНО РЕАЛИЗОВАНО:**

```tsx
// Node creation flow:
⚠️ Button "+ Create Node" есть, но создание ноды идет прямо через store
⚠️ НЕТ диалогов для ввода данных (DataNode, WidgetNode, CommentNode)
⚠️ Создание ноды использует placeholder данные:

const handleCreateDataNode = async () => {
    await createDataNode(boardId, {
        name: 'New Data Node',
        data_source_type: DataSourceType.API_CALL,
        x: 100,
        y: 100,
        data: {},
    })
}

// Нужно: Dialog с формой (name, type, query/api_config, etc.)
```

```tsx
// Edge creation:
✅ onConnect handler есть
✅ createEdge() вызывается
⚠️ НО: не работает выбор типа edge (всегда VISUALIZATION)
⚠️ НЕТ: Dialog для выбора edge type + metadata

const handleConnect = useCallback(
    async (connection: Connection) => {
        await createEdge(boardId, {
            source_node_id: connection.source,
            target_node_id: connection.target,
            source_node_type: 'data_node', // Hardcoded!
            target_node_type: 'widget_node', // Hardcoded!
            edge_type: EdgeType.VISUALIZATION, // Всегда VISUALIZATION
        })
    },
    [boardId, createEdge]
)

// Нужно: Определять node type автоматически или через dialog
```

**❌ НЕ РЕАЛИЗОВАНО:**

```tsx
❌ Canvas toolbar (zoom controls, layout algorithms, minimap toggle)
❌ Node context menu (right-click → edit/delete/duplicate)
❌ Edge context menu (right-click → edit type/delete)
❌ Node resize handles (для WidgetNode работают, но не для CommentNode)
❌ Selection box (multi-select nodes)
❌ Undo/Redo buttons
❌ Save layout button
❌ Export canvas (PNG/SVG)
```

#### 5. Node Components (40% ⚠️)

**DataNodeCard** (80% ✅):

```tsx
✅ Icon по типу source (SQL/API/CSV/JSON/etc.)
✅ Label типа source
✅ Name + description display
✅ Data info (columns count, rows count)
✅ Query preview (truncated)
✅ Connection handles (left target, right source)
✅ Selected state (blue glow)

⚠️ НЕТ: Edit button
⚠️ НЕТ: Delete button
⚠️ НЕТ: Refresh data button
⚠️ НЕТ: Preview data modal
```

**WidgetNodeCard** (60% ✅):

```tsx
✅ Header с icon + name
✅ AI-generated indicator (Sparkles icon)
✅ Widget preview (dangerouslySetInnerHTML для html_code)
✅ CSS injection через <style>
✅ Auto-refresh indicator (если настроен)
✅ NodeResizer для изменения размера
✅ Connection handle (left target)
✅ Selected state (purple glow)

⚠️ НЕТ: Безопасный iframe sandbox (сейчас dangerouslySetInnerHTML)
⚠️ НЕТ: Error boundary для ловли ошибок рендеринга
⚠️ НЕТ: JS execution (js_code игнорируется)
⚠️ НЕТ: Edit button
⚠️ НЕТ: Delete button
⚠️ НЕТ: Regenerate widget button
⚠️ НЕТ: Fullscreen mode
```

**⚠️ КРИТИЧЕСКАЯ ПРОБЛЕМА:**
```tsx
// НЕБЕЗОПАСНО! XSS уязвимость:
<div dangerouslySetInnerHTML={{ __html: node.html_code }} />

// Нужно: Iframe sandbox
<iframe
    srcDoc={`
        <!DOCTYPE html>
        <html>
        <head><style>${css_code}</style></head>
        <body>${html_code}<script>${js_code}</script></body>
        </html>
    `}
    sandbox="allow-scripts"
    style={{ width: '100%', height: '100%', border: 'none' }}
/>
```

**CommentNodeCard** (50% ✅):

```tsx
✅ Author info
✅ Content display
✅ Timestamp
✅ Resolved state toggle
✅ NodeResizer для изменения размера
✅ Connection handle (left target)

⚠️ НЕТ: Edit button
⚠️ НЕТ: Delete button
⚠️ НЕТ: Reply button
⚠️ НЕТ: @mentions rendering
⚠️ НЕТ: Markdown support
```

#### 6. Socket.IO Client (80% ✅)

**Файл:** `apps/web/src/hooks/useBoardSocket.ts`

**✅ РЕАЛИЗОВАНО:**

```typescript
// Connection:
✅ io() client initialization
✅ Path: '/socket.io'
✅ Transports: ['polling', 'websocket']
✅ Reconnection logic
✅ Auto-connect

// Events от server:
✅ connect - логирование
✅ disconnect - логирование
✅ data_node_created - добавление в store
✅ data_node_updated - обновление в store
✅ data_node_deleted - удаление из store
✅ widget_node_created
✅ widget_node_updated
✅ widget_node_deleted
✅ comment_node_created
✅ comment_node_updated
✅ comment_node_deleted
✅ edge_created
✅ edge_updated
✅ edge_deleted

// Room management:
✅ join_board emit при подключении
✅ leave_board emit при отключении

// State sync:
✅ Обновление boardStore при получении events
```

**⚠️ ПРОБЛЕМЫ:**

1. **Нет оптимистичных обновлений:**
   - Клиент ждет ответа от server, потом обновляет UI
   - Нужно: Apply change immediately, rollback on error

2. **Нет обработки конфликтов:**
   - Два юзера двигают один node одновременно → последний wins
   - Нужно: Conflict resolution strategy

3. **Нет индикатора активных пользователей:**
   - Клиент не показывает кто еще смотрит доску
   - Нужно: Active users indicator с avatars

**❌ НЕ РЕАЛИЗОВАНО:**

```typescript
❌ user_joined_board event handler
❌ user_left_board event handler
❌ active_users state management
❌ transformation_executed event handler
❌ ai_message_received event handler
❌ Optimistic updates
❌ Conflict resolution
❌ Connection status indicator UI
```

#### 7. Dialogs (20% ✅)

**Реализованные:**
- ✅ `CreateProjectDialog` - создание проекта
- ✅ `CreateBoardDialog` - создание доски

**❌ НЕ РЕАЛИЗОВАННЫЕ (критично для функциональности):**

```tsx
❌ CreateDataNodeDialog - форма для создания DataNode
   - Выбор типа source (SQL/API/CSV/JSON/etc.)
   - Ввод name, description
   - SQL query input / API endpoint / file upload
   - Position (x, y)
   - Preview данных

❌ CreateWidgetNodeDialog - форма для создания WidgetNode
   - Выбор parent DataNode (dropdown)
   - User prompt (описание желаемого виджета)
   - Position (x, y)
   - Size (width, height)
   - Submit → вызов AI (stub пока)

❌ CreateCommentNodeDialog - форма для комментария
   - Выбор target node (dropdown)
   - Markdown editor
   - @mentions autocomplete
   - Position

❌ CreateEdgeDialog - выбор типа связи
   - Source/target nodes (auto-detected or manual)
   - Edge type (TRANSFORMATION/VISUALIZATION/COMMENT/etc.)
   - Transformation code editor (для TRANSFORMATION)
   - Metadata (label, description)

❌ EditDataNodeDialog - редактирование DataNode
❌ EditWidgetNodeDialog - редактирование WidgetNode
❌ EditCommentNodeDialog - редактирование CommentNode
❌ EditEdgeDialog - редактирование Edge

❌ DataPreviewDialog - просмотр данных DataNode (таблица)
❌ WidgetFullscreenDialog - полноэкранный просмотр виджета
```

**Анализ:**
Отсутствие dialogs делает UI неюзабельным. Сейчас ноды создаются с placeholder данными через прямой вызов API, что недопустимо для production.

---

## 🤖 AI INTEGRATION: Анализ

### ❌ ПОЛНОСТЬЮ ОТСУТСТВУЕТ (0%)

**НЕ НАЙДЕНО в кодовой базе:**

```python
# Backend:
❌ apps/backend/app/services/ai_assistant_service.py
❌ apps/backend/app/agents/ (папка с агентами)
❌ apps/backend/app/tools/ (инструменты)
❌ apps/backend/app/sandbox/ (code execution)
❌ Зависимости: langchain, langchain-gigachat отсутствуют в requirements

# Frontend:
❌ apps/web/src/components/AIAssistantPanel/ (правая панель)
❌ apps/web/src/store/aiAssistantStore.ts
❌ apps/web/src/api/aiAssistantAPI.ts

# Config:
❌ GIGACHAT_API_KEY в .env
❌ AI settings в config.py
```

**Что нужно:**

1. **GigaChat Integration:**
   ```bash
   pip install langchain langchain-gigachat tiktoken
   ```

2. **AI Services структура:**
   ```
   apps/backend/app/
   ├── agents/
   │   ├── __init__.py
   │   ├── planner_agent.py
   │   ├── analyst_agent.py
   │   ├── developer_agent.py
   │   ├── researcher_agent.py
   │   ├── transformation_agent.py
   │   ├── executor_agent.py
   │   ├── reporter_agent.py
   │   ├── data_discovery_agent.py
   │   └── form_generator_agent.py
   ├── services/
   │   ├── ai_assistant_service.py
   │   ├── board_context_provider.py
   │   ├── tool_registry.py
   │   └── transformation_executor.py
   ├── tools/
   │   ├── __init__.py
   │   ├── sql_tool.py
   │   ├── api_tool.py
   │   ├── web_scraper_tool.py
   │   └── file_tool.py
   └── sandbox/
       ├── __init__.py
       ├── python_sandbox.py
       └── code_validator.py
   ```

3. **Frontend AI Panel:**
   ```
   apps/web/src/
   ├── components/
   │   └── AIAssistantPanel/
   │       ├── index.tsx
   │       ├── MessageList.tsx
   │       ├── Message.tsx
   │       ├── InputField.tsx
   │       ├── SuggestedActions.tsx
   │       ├── Header.tsx
   │       └── Footer.tsx
   ├── store/
   │   └── aiAssistantStore.ts
   └── api/
       └── aiAssistantAPI.ts
   ```

---

## 🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1. **Безопасность WidgetNode rendering** (HIGH PRIORITY)

**Проблема:**
```tsx
// apps/web/src/components/board/WidgetNodeCard.tsx
<div dangerouslySetInnerHTML={{ __html: node.html_code }} />
```

**Риск:** XSS уязвимость, выполнение вредоносного кода

**Решение:**
```tsx
// Использовать iframe sandbox
<iframe
    srcDoc={generateSecureHTML(node)}
    sandbox="allow-scripts allow-same-origin"
    style={{ width: '100%', height: '100%', border: 'none' }}
/>

function generateSecureHTML(node: WidgetNode): string {
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="Content-Security-Policy" content="
                default-src 'self'; 
                script-src 'unsafe-inline' 'unsafe-eval'; 
                style-src 'unsafe-inline';
            ">
            <style>${sanitizeCSS(node.css_code)}</style>
        </head>
        <body>
            ${sanitizeHTML(node.html_code)}
            <script>${sanitizeJS(node.js_code)}</script>
        </body>
        </html>
    `
}
```

### 2. **Socket.IO broadcast дублирование логики**

**Проблема:**
- Broadcast events идут из routes (data_nodes.py, widget_nodes.py)
- НО handlers для этих events регистрируются в socketio_events.py
- Логика запутана: клиент создает через REST, server broadcast из route

**Решение:**
Использовать event bus или переместить broadcast в service layer:

```python
# apps/backend/app/services/event_bus.py
class EventBus:
    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
    
    async def emit_data_node_created(self, board_id: UUID, node: DataNode):
        await self.sio.emit(
            "data_node_created",
            node.to_dict(),
            room=f"board:{board_id}"
        )

# В service:
class DataNodeService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def create_data_node(...):
        # ... create logic
        await self.event_bus.emit_data_node_created(board_id, data_node)
        return data_node
```

### 3. **Отсутствие Node Creation Dialogs**

**Проблема:**
Невозможно создать ноду с правильными данными через UI.

**Текущий код:**
```tsx
const handleCreateDataNode = async () => {
    await createDataNode(boardId, {
        name: 'New Data Node', // Hardcoded!
        data_source_type: DataSourceType.API_CALL, // Hardcoded!
        x: 100,
        y: 100,
        data: {}, // Empty!
    })
}
```

**Решение:**
Создать полноценные dialogs (см. раздел "Dialogs" выше).

### 4. **Edge Type всегда VISUALIZATION**

**Проблема:**
```tsx
edge_type: EdgeType.VISUALIZATION, // Hardcoded!
source_node_type: 'data_node', // Hardcoded!
target_node_type: 'widget_node', // Hardcoded!
```

**Решение:**
- Auto-detect node types по ID (lookup в store)
- Dialog для выбора edge type при manual connection

### 5. **Нет AI Integration**

Весь AI функционал отсутствует, хотя он центральная часть проекта.

---

## 📋 АКТУАЛИЗИРОВАННЫЙ ПЛАН РАЗРАБОТКИ

### 🎯 MILESTONE 1: Функциональный UI (1-2 недели)

**Цель:** Сделать canvas полностью юзабельным без AI

#### Неделя 1: Node Creation & Editing

**День 1-2: DataNode Dialog**
- [ ] CreateDataNodeDialog компонент
- [ ] Форма: name, description, data_source_type (select)
- [ ] Conditional fields:
  - SQL: query textarea, database select
  - API: endpoint input, headers JSON editor
  - CSV/JSON: file upload
- [ ] Preview данных (если возможно)
- [ ] Position auto-calculate (center of viewport)
- [ ] Интеграция с boardStore.createDataNode()

**День 3-4: WidgetNode Dialog (stub для AI)**
- [ ] CreateWidgetNodeDialog компонент
- [ ] Форма: parent_data_node (select из dataNodes), user_prompt
- [ ] Position/size inputs
- [ ] Submit → вызов API endpoint (stub: возвращает empty widget)
- [ ] Placeholder: "AI generation coming soon"

**День 5: CommentNode Dialog**
- [ ] CreateCommentNodeDialog компонент
- [ ] Форма: target_node (select), content (textarea)
- [ ] Markdown preview
- [ ] @mentions autocomplete (future)
- [ ] Position auto-calculate (near target node)

**День 6-7: Edge Creation Dialog**
- [ ] CreateEdgeDialog компонент (optional modal после connect)
- [ ] Auto-detect source/target node types
- [ ] Edge type select (TRANSFORMATION/VISUALIZATION/etc.)
- [ ] Conditional fields:
  - TRANSFORMATION: code editor (CodeMirror/Monaco)
  - VISUALIZATION: auto (no extra fields)
  - COMMENT: auto (no extra fields)
- [ ] Label, description inputs

#### Неделя 2: Node Editing & Canvas Improvements

**День 1-2: Edit Dialogs**
- [ ] EditDataNodeDialog (copy of Create, pre-filled)
- [ ] EditWidgetNodeDialog (name, description, auto_refresh)
- [ ] EditCommentNodeDialog (content, resolved)
- [ ] EditEdgeDialog (type, label, transformation_code)

**День 3-4: Canvas Toolbar**
- [ ] Toolbar component (top of canvas)
- [ ] Zoom controls (+/-, fit, 100%)
- [ ] Minimap toggle
- [ ] Layout algorithms (future: auto-arrange)
- [ ] Undo/Redo buttons (future)
- [ ] Save/Export buttons (future)

**День 5-6: Node Context Menus**
- [ ] Right-click на node → context menu
- [ ] Edit, Delete, Duplicate actions
- [ ] DataNode: Refresh data, Preview data
- [ ] WidgetNode: Fullscreen, Regenerate (future AI)
- [ ] CommentNode: Resolve, Reply

**День 7: Security & Bug Fixes**
- [ ] WidgetNode iframe sandbox (КРИТИЧНО!)
- [ ] Error boundaries для widget rendering
- [ ] Edge type auto-detection fix
- [ ] Socket.IO optimistic updates

---

### 🎯 MILESTONE 2: Real-time Collaboration (1 неделя)

**День 1-2: Socket.IO Improvements**
- [ ] Refactor broadcast logic (event bus в services)
- [ ] Удалить дублирующие handlers в socketio_events.py
- [ ] Optimistic updates на клиенте
- [ ] Rollback on error

**День 3-4: Active Users**
- [ ] user_joined_board, user_left_board events
- [ ] active_users state в boardStore
- [ ] ActiveUsersIndicator component (avatars в TopBar)
- [ ] Connection status indicator (green/red dot)

**День 5-7: Testing & Polishing**
- [ ] Тесты для Socket.IO events (backend + frontend)
- [ ] Multi-user testing (2+ clients)
- [ ] Performance optimization (debounce position updates)
- [ ] Conflict resolution strategy

---

### 🎯 MILESTONE 3: AI Integration - Phase 1 (2-3 недели)

**Неделя 1: Infrastructure**

**День 1-2: GigaChat Setup**
- [ ] Install dependencies: `langchain`, `langchain-gigachat`, `tiktoken`
- [ ] Get GigaChat API key
- [ ] Config: GIGACHAT_API_KEY в .env
- [ ] Test connection: simple prompt → response

**День 3-4: AIAssistantService**
- [ ] Create `ai_assistant_service.py`
- [ ] `AIAssistantService` class
- [ ] `process_message(board_id, message)` method
- [ ] `_call_gigachat(messages)` - вызов GigaChat
- [ ] `_parse_response(response)` - парсинг ответа
- [ ] Rate limiting (10 msg/min)

**День 5-7: BoardContextProvider**
- [ ] Create `board_context_provider.py`
- [ ] `get_board_context(board_id)` - сбор контекста:
  - Все DataNodes (names, types, data samples)
  - Все WidgetNodes (descriptions)
  - Все Edges (types, transformations)
- [ ] Formatting context для prompt
- [ ] Caching в Redis (TTL 5 min)

**Неделя 2: Chat System**

**День 1-3: Backend Chat API**
- [ ] ChatMessage model (user_id, board_id, role, content)
- [ ] ChatSession model (board_id, user_id)
- [ ] API endpoints:
  - POST `/api/v1/boards/{boardId}/ai/chat`
  - GET `/api/v1/boards/{boardId}/ai/chat/history`
- [ ] Socket.IO events: `ai_message_sent`, `ai_response_received`
- [ ] Integration с AIAssistantService

**День 4-7: Frontend AI Panel**
- [ ] AIAssistantPanel component (правая панель)
- [ ] aiAssistantStore (messages, loading, error)
- [ ] aiAssistantAPI (sendMessage, getHistory)
- [ ] MessageList, Message, InputField components
- [ ] Markdown rendering для сообщений
- [ ] Typing indicator для AI
- [ ] Auto-scroll to bottom
- [ ] Socket.IO integration

**Неделя 3: Reporter Agent (Widget Generation)**

**День 1-3: Reporter Agent**
- [ ] `reporter_agent.py`
- [ ] `ReporterAgent` class
- [ ] `analyze_data_node(data_node)` - анализ данных
- [ ] `generate_widget_code(data_node, user_prompt)` - генерация HTML/CSS/JS
- [ ] Prompts для GigaChat (system prompt + data context + user prompt)
- [ ] Code validation и sanitization

**День 4-5: API Integration**
- [ ] POST `/api/v1/boards/{boardId}/widget-nodes/generate`
- [ ] Input: parent_data_node_id, user_prompt
- [ ] Output: WidgetNode с generated HTML/CSS/JS
- [ ] Auto-create VISUALIZATION edge

**День 6-7: Frontend Integration**
- [ ] Update CreateWidgetNodeDialog
- [ ] "Generate with AI" button
- [ ] Loading state (spinner)
- [ ] Preview generated widget в dialog
- [ ] Apply → create WidgetNode на canvas

---

### 🎯 MILESTONE 4: Transformation Agent (2 недели)

**Неделя 1: Transformation Agent**
- [ ] `transformation_agent.py`
- [ ] `TransformationAgent` class
- [ ] `generate_transformation_code(source_nodes, target_description)` - генерация Python pandas
- [ ] Code validation (syntax check, safe imports)
- [ ] Sandbox execution (RestrictedPython или Docker)
- [ ] API endpoint: POST `/api/v1/boards/{boardId}/transformations/generate`

**Неделя 2: Transformation Execution**
- [ ] `transformation_executor.py`
- [ ] Execute transformation в sandbox
- [ ] Create target DataNode с результатом
- [ ] Create TRANSFORMATION edge
- [ ] Replay logic (при изменении source DataNode)

---

### 🎯 MILESTONE 5: Multi-Agent System (3-4 недели)

Реализация оставшихся 7 агентов по одному в неделю:
- [ ] Planner Agent (orchestration)
- [ ] Analyst Agent (data analysis)
- [ ] Developer Agent (tool generation)
- [ ] Researcher Agent (data fetching)
- [ ] Executor Agent (tool execution)
- [ ] Data Discovery Agent (public datasets)
- [ ] Form Generator Agent (dynamic forms)

---

## 📊 МЕТРИКИ ГОТОВНОСТИ (обновлено после анализа кода)

### Backend: **72%** (было 70%)

| Компонент      | Готовность | Комментарий                         |
| -------------- | ---------- | ----------------------------------- |
| Infrastructure | 95%        | ✅ Почти готово, нужен rate limiting |
| Models         | 100%       | ✅ Все модели реализованы            |
| Migrations     | 100%       | ✅ 5 миграций применены              |
| API Routes     | 85%        | ✅ CRUD готов, нет AI endpoints      |
| Services       | 80%        | ✅ CRUD готов, нет AI services       |
| Socket.IO      | 60%        | ⚠️ Работает, но нужен рефакторинг    |
| Schemas        | 100%       | ✅ Pydantic schemas готовы           |
| AI Integration | 0%         | ❌ Отсутствует                       |

### Frontend: **58%** (было 60%)

| Компонент        | Готовность | Комментарий                     |
| ---------------- | ---------- | ------------------------------- |
| Infrastructure   | 100%       | ✅ React + Vite + TS готов       |
| State (Zustand)  | 95%        | ✅ Почти готово, нужен AI state  |
| API Services     | 100%       | ✅ Все CRUD API обернуты         |
| Canvas           | 50%        | ⚠️ Работает, но нет dialogs      |
| Node Components  | 40%        | ⚠️ Отображаются, нет edit/delete |
| Socket.IO Client | 80%        | ✅ Работает, нужен active users  |
| Dialogs          | 20%        | ⚠️ Только Project/Board          |
| AI Panel         | 0%         | ❌ Отсутствует                   |

### Общая готовность: **55%** (уточнено)

---

## 🎯 NEXT IMMEDIATE STEPS (на эту неделю)

### Приоритет 1: Security Fix (1 день)
**КРИТИЧНО:** WidgetNode iframe sandbox

### Приоритет 2: CreateDataNodeDialog (2-3 дня)
Полноценная форма создания DataNode

### Приоритет 3: Edit/Delete Buttons (2 дня)
Context menu для всех node types

### Приоритет 4: Canvas Toolbar (1-2 дня)
Zoom controls, minimap toggle

---

**Итого:** Реальное состояние проекта хуже, чем показывала документация. Много базовой UI функциональности отсутствует. AI integration на 0%. 

**Но:** Архитектура правильная, база данных и API работают, Socket.IO функционирует. Можно строить дальше.

**Рекомендация:** Сфокусироваться на Milestone 1 (Функциональный UI) перед началом AI интеграции.
