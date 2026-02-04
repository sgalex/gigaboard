# GigaBoard with AI Assistant — System Diagrams

> **📌 Совет:** Диаграммы переведены в Mermaid — Markdown Preview Enhanced рендерит их прямо в превью, без доп. плагинов.

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph Platform["GIGABOARD PLATFORM"]
        subgraph Frontend["Frontend (Browser)\nReact + React Flow"]
            Canvas["Canvas (Infinite Board)\nWidgets, Edges, Undo/Redo,\nCollaborative Editing"]
            Panel["AI Assistant Panel (NEW)\nMessages, Input, Actions, History"]
            State["State: Zustand\nCache: TanStack Query"]
        end

        subgraph Backend["Backend (FastAPI + Python)"]
            REST["REST API\nAuth, CRUD Boards/Widgets/Edges"]
            Gateway["Real-time Gateway\nSocket.IO, Rooms, Redis pub/sub"]
            AIService["AI Orchestration Service\nContext Provider, Prompt Builder,\nGigaChat Integration, Action Parser,\nRate limiting & caching"]
            Middleware["Middleware\nAuth, Logging, Error Handling"]
        end

        subgraph Data["DATA LAYER"]
            PG["PostgreSQL\nUsers, Boards, Widgets, Edges, Assets, Chat History"]
            Redis["Redis\nCache, Sessions, Pub/Sub, Rate Limiter"]
            GigaChat["GigaChat\nAPI, Models, LangChain"]
        end
    end

    Canvas --> Panel
    Panel --> State
    State --> REST
    State --> Gateway
    State --> AIService

    Frontend -->|"REST/HTTPS\nJSON"| REST
    Frontend -->|"Socket.IO\nEvents"| Gateway
    Frontend -->|"Chat API"| AIService

    Backend --> PG
    Backend --> Redis
    AIService --> GigaChat
    Gateway --> Redis
```

---

## 2. AI Assistant Component Architecture

```mermaid
flowchart LR
    subgraph Frontend["Frontend: AI Assistant Panel"]
        Header["Header + Context Indicator"]
        Messages["Message List\nUser/AI messages"]
        Input["Input: 'Введите вопрос...'\n[Send] Shift+Enter"]
        Footer["Footer: v0.1 Powered by GigaChat"]
        State["State (Zustand)\nmessages, isPanelOpen, isLoading,\nsessionId, suggestedActions"]
        Client["API Client (TanStack Query + Fetch)\nsendMessage / getHistory / applyAction"]
        Messages --> Client
        Input --> Client
        State --> Client
    end

    subgraph Backend["Backend: AI Assistant Service"]
        ChatAPI["POST /api/v1/boards/{boardId}/ai/chat\nLoad BoardContext → Build SystemPrompt\nCall GigaChat → Cache results (Redis)"]
        ApplyAPI["POST /api/v1/boards/{boardId}/ai/chat/actions/{id}/apply\nValidate action → WidgetService.create\nSave to DB → Broadcast via Socket.IO"]
        SocketIO["Socket.IO broadcast\nroom: board_id\nevent: widget_created"]
        RTUpdate["Frontend real-time update\nupdateCanvas → addWidget → render"]
    end

    Client --> ChatAPI
    ChatAPI --> ApplyAPI
    ApplyAPI --> SocketIO
    SocketIO --> RTUpdate
    RTUpdate --> State
```

**Дополнительно:** rate limiting 10 msg/min (Redis counter), cache TTL 24h, session history TTL 4h.

---

## 3. Message Flow Sequence Diagram

```mermaid
sequenceDiagram
     participant U as User
     participant F as Frontend (React)
     participant B as Backend (FastAPI)
     participant G as GigaChat
     participant D as Database (PostgreSQL/Redis)

     U->>F: Open board / ask question
     F->>B: POST /ai/chat {message, session}
     B->>D: Load BoardContext (widgets, edges, data)
     B->>G: System prompt + user msg + history
     G-->>B: Response + suggested actions
     B-->>F: 200 OK {response, actions}
     U->>F: Click action (+Add chart)
     F->>B: POST /ai/chat/actions/{id}/apply
     B->>D: Create widget (WidgetService)
     B-->>F: 200 OK {applied, widget_id}
     B-->>F: Socket.IO widget_created
     F->>U: Real-time render widget
```

---

## 4. Context Awareness Architecture

```mermaid
flowchart LR
     PG[(PostgreSQL)] --> Context["Load Board Context\nwidgets, edges, data, metadata"]
     Sources["Data sources\nSQL / API / Sheets"] --> Context
     Redis[(Redis cache)] --> Context
     Context --> Prompt["System Prompt Builder"]
     Prompt --> GigaChat
     GigaChat --> Actions["AI Response\nanswers + suggested actions"]
     Actions --> Board["Board updates & actions"]
```

---

## 5. Data Flow for Widget Creation

```mermaid
flowchart TB
     Click["User clicks 'Add chart' action"] --> ApplyAPI["POST /ai/chat/actions/{id}/apply"]
     ApplyAPI --> Validate["Validate: board_id / user_id / action_id\nRate limit"]
     Validate --> Create["WidgetService.create(widget_spec)"]
     Create --> SaveDB["Save widget → PostgreSQL\nreturn widget_id"]
     SaveDB --> Broadcast["Socket.IO emit widget_created\nroom: board_id"]
     Broadcast --> UpdateFE["Frontend updates Zustand + React rerender"]
     UpdateFE --> Done["Widget appears on board 🎉"]
```

---

## 6. Error Handling Flow

```mermaid
flowchart TB
     Start["AI chat request"]
     API503["503 GigaChat unavailable\nWarn user, retry x3 backoff"]
     Rate429["429 Too Many Requests\nRetry-After; disable send 60s"]
     Spec400["400 Invalid widget spec\nShow details; user edits"]
     Auth401["401 Unauthorized\nRedirect to login; retry"]
     NotFound404["404 Board not found\nReturn to boards list"]
     Forbidden403["403 No access\nAsk owner for access"]
     Log["Log context\nuser_id, board_id, error_type, timestamp, request_id, stack"]

     Start --> API503 --> Log
     Start --> Rate429 --> Log
     Start --> Spec400 --> Log
     Start --> Auth401 --> Log
     Start --> NotFound404 --> Log
     Start --> Forbidden403 --> Log
```

---

**Status**: Diagrams Complete ✅  
**Date**: 2026-01-23  
**Format**: Embedded Draw.io diagrams (editable inline)
