# AI Assistant Panel — Developer Checklist

## 📋 Документация

- [x] Требования (FR-6 в SPECIFICATIONS.md)
- [x] API endpoints (в API.md)
- [x] Архитектура компонента (в ARCHITECTURE.md и AI_ASSISTANT.md)
- [x] UI дизайн и макеты (в UI_DESIGN.md)
- [x] Use cases и примеры (в USE_CASES.md)
- [x] Backend Service описание (в AI_ASSISTANT.md)
- [x] Frontend State Management (в AI_ASSISTANT.md)
- [ ] Database schema для chat history (требуется)
- [ ] Deployment guide (требуется)

---

## 🔧 Backend Development

### AI Orchestration Service

- [ ] Создать файл `backend/services/ai_assistant_service.py`
  - [ ] Класс `AIAssistantService`
  - [ ] Метод `process_message()` с контекстом доски
  - [ ] Метод `_build_system_prompt()` с описанием доски
  - [ ] Метод `_parse_response()` для выделения actions
  - [ ] Метод `apply_action()` для создания/обновления виджетов

- [ ] Создать файл `backend/services/board_context_provider.py`
  - [ ] Класс `BoardContextProvider`
  - [ ] Метод `get_board_context(board_id)` — собрать widgets, edges, data
  - [ ] Кэширование контекста в Redis (TTL 5 min)

### API Endpoints

- [ ] Добавить в `backend/routes/boards.py`:
  - [ ] `POST /api/v1/boards/{boardId}/ai/chat`
    - [ ] Валидация request (message не пусто)
    - [ ] Создание session_id если его нет
    - [ ] Вызов AIAssistantService.process_message()
    - [ ] Сохранение сообщения в Redis
    - [ ] Возврат response с suggested_actions
  
  - [ ] `GET /api/v1/boards/{boardId}/ai/chat/history`
    - [ ] Получение истории из Redis
    - [ ] Фильтрация по session_id (если передан)
    - [ ] Пагинация (limit, offset)
    - [ ] Возврат массива Message
  
  - [ ] `POST /api/v1/boards/{boardId}/ai/chat/actions/{actionId}/apply`
    - [ ] Получение action из Redis
    - [ ] Валидация action (существует, относится к этому boardId)
    - [ ] Если action.type == 'create_widget': вызвать WidgetService.create()
    - [ ] Отправить event 'widget_created' в Socket.IO room
    - [ ] Логировать action (для телеметрии)
    - [ ] Возврат применённого widget

### AI Integration (GigaChat)

- [ ] Интегрировать langchain-gigachat:
  - [ ] Инициализация GigaChatClient в main.py
  - [ ] Passing в AIAssistantService
  - [ ] Обработка errors (если GigaChat недоступен)
  - [ ] Retry логика (3 попытки с exponential backoff)

### Caching & Rate Limiting

- [ ] Redis интеграция:
  - [ ] Ключи для кэша: `ai:session:{session_id}`, `ai:board:{board_id}`
  - [ ] TTL: 4 часа для сессий, 24 часа для ответов

- [ ] Rate Limiting:
  - [ ] 10 сообщений в минуту на пользователя
  - [ ] 100 сообщений в час на пользователя
  - [ ] Возврат 429 Too Many Requests с retry-after
  - [ ] Реализация через redis (Redis-backed RateLimiter)

### Error Handling

- [ ] Обработка ошибок:
  - [ ] GigaChat недоступен → 503 Service Unavailable
  - [ ] Invalid widget spec → 400 Bad Request с описанием
  - [ ] Unauthorized → 401 Unauthorized
  - [ ] Board not found → 404 Not Found
  - [ ] Rate limit exceeded → 429 Too Many Requests

### Telemetry

- [ ] Логирование:
  - [ ] Каждое сообщение (user_id, board_id, message_length, timestamp)
  - [ ] Response time (время ответа от GigaChat)
  - [ ] Actions applied (какие actions были применены)
  - [ ] Errors (какие ошибки случились)

- [ ] Метрики (для Prometheus/CloudWatch):
  - [ ] Counter: `ai_chat_messages_total`
  - [ ] Histogram: `ai_chat_response_time_seconds`
  - [ ] Counter: `ai_chat_actions_applied`
  - [ ] Counter: `ai_chat_errors_total`

---

## 🎨 Frontend Development

### Component Structure

- [ ] Создать папку `src/components/AIAssistantPanel/`
  - [ ] `index.tsx` (главный компонент)
  - [ ] `MessageList.tsx` (список сообщений)
  - [ ] `Message.tsx` (одно сообщение)
  - [ ] `InputField.tsx` (поле ввода)
  - [ ] `SuggestedActions.tsx` (кнопки действий)
  - [ ] `Header.tsx` (заголовок панели)
  - [ ] `Footer.tsx` (подвал с ссылкой на GigaChat)

### State Management (Zustand)

- [ ] Создать `src/stores/ai_assistant_store.ts`
  - [ ] Interface `AssistantState`
  - [ ] Interface `Message` с fields: id, role, content, suggestedActions, timestamp
  - [ ] Interface `SuggestedAction`
  - [ ] Interface `BoardContext`
  
  - [ ] Actions:
    - [ ] `togglePanel()` — открыть/закрыть панель
    - [ ] `addMessage(role, content)` — добавить сообщение
    - [ ] `clearHistory()` — очистить историю
    - [ ] `setLoading(boolean)` — статус загрузки
    - [ ] `applyAction(actionId)` — применить рекомендацию

### API Integration

- [ ] Создать `src/api/ai_assistant_api.ts`
  - [ ] Function `sendMessage(boardId, message, sessionId?): Promise<Response>`
    - [ ] Вызов `POST /api/v1/boards/{boardId}/ai/chat`
    - [ ] Обработка ошибок
    - [ ] Возврат response с message и suggestedActions
  
  - [ ] Function `getHistory(boardId, sessionId?, limit?): Promise<Message[]>`
    - [ ] Вызов `GET /api/v1/boards/{boardId}/ai/chat/history`
    - [ ] Кэширование в TanStack Query
  
  - [ ] Function `applyAction(boardId, actionId): Promise<Widget>`
    - [ ] Вызов `POST /api/v1/boards/{boardId}/ai/chat/actions/{actionId}/apply`
    - [ ] Обновление state (добавить новый виджет)

### UI Components

- [ ] `MessageList.tsx`:
  - [ ] Auto-scroll вниз при новых сообщениях
  - [ ] Форматирование текста (markdown)
  - [ ] Code blocks с подсветкой синтаксиса
  - [ ] Timestamps для каждого сообщения
  - [ ] Loading indicator (typing dots)

- [ ] `InputField.tsx`:
  - [ ] Text input с multiline поддержкой
  - [ ] Send кнопка (или Enter для отправки)
  - [ ] Shift+Enter для новой строки
  - [ ] Placeholder text: "Введите вопрос о данных на доске..."
  - [ ] Disabled во время загрузки

- [ ] `SuggestedActions.tsx`:
  - [ ] Кнопки для каждого action
  - [ ] Loading state при применении
  - [ ] Success feedback "✓ Применено"
  - [ ] Error handling с retry опцией

### Layout Integration

- [ ] Обновить главный layout:
  - [ ] Добавить `<AIAssistantPanel />` в правую сторону
  - [ ] CSS: flex layout, ширина 380px (или responsive)
  - [ ] Z-index: выше canvas, но ниже модалей
  - [ ] Resizable panel (опционально)

### Styling

- [ ] Tailwind CSS классы (или ShadCN UI components):
  - [ ] Message bubbles (blue для user, gray для AI)
  - [ ] Buttons (primary для Send, secondary для Actions)
  - [ ] Input field (focus state)
  - [ ] Loading spinner
  - [ ] Error state (красный текст)

### Accessibility

- [ ] ARIA labels для всех элементов
- [ ] `role="dialog"` для панели
- [ ] `aria-live="polite"` для новых сообщений
- [ ] Keyboard navigation (Tab, Enter, Escape)
- [ ] Screen reader поддержка

---

## 🧪 Testing

### Backend Tests

- [ ] Unit tests для `AIAssistantService` (pytest):
  - [ ] test_process_message_basic()

---

## 🎨 Dynamic Form Generation (NEW)

### Form Generator Agent

- [ ] Создать `backend/agents/form_generator_agent.py`
  - [ ] Класс `FormGeneratorAgent`
  - [ ] Метод `generate_form(context)` — главный метод генерации
  - [ ] Метод `analyze_intent(context)` — анализ намерений пользователя
  - [ ] Метод `scan_data_sources(context)` — сканирование источников
  - [ ] Метод `create_form_schema()` — генерация JSON schema
  - [ ] Метод `get_smart_suggestions()` — умные подсказки на основе данных
  - [ ] Метод `rank_by_relevance()` — ранжирование источников

- [ ] Создать `backend/services/data_source_scanner.py`
  - [ ] Класс `DataSourceScanner`
  - [ ] Метод `scan_local_files(user_intent)` — поиск CSV/Excel файлов
  - [ ] Метод `scan_databases()` — проверка подключенных БД
  - [ ] Метод `scan_cloud_storage()` — Google Drive, Dropbox, S3
  - [ ] Метод `scan_api_integrations()` — Stripe, Shopify и др.
  - [ ] Метод `get_user_history_sources(user_id)` — ранее использованные
  - [ ] Кэширование результатов в Redis (TTL 10 min)

- [ ] Создать `backend/services/smart_suggestion_engine.py`
  - [ ] Класс `SmartSuggestionEngine`
  - [ ] Метод `suggest_analysis_options(data_preview)` — анализ структуры
  - [ ] Метод `detect_seasonality(data)` — детекция сезонности
  - [ ] Метод `detect_anomalies(data)` — поиск аномалий
  - [ ] Метод `suggest_metrics(columns)` — рекомендации метрик

### API Endpoints

- [ ] Добавить в `backend/routes/ai.py`:
  - [ ] `POST /api/v1/boards/{boardId}/ai/generate-form`
    - [ ] Input: `{user_message, conversation_id}`
    - [ ] Вызов FormGeneratorAgent.generate_form()
    - [ ] Возврат: `{form_id, schema, component_code}`
  
  - [ ] `POST /api/v1/boards/{boardId}/ai/forms/{formId}/submit`
    - [ ] Input: form data (выбранные опции)
    - [ ] Валидация данных
    - [ ] Загрузка данных из выбранного источника
    - [ ] Передача данных Analyst Agent
    - [ ] Возврат: `{status, data_preview}`

### Frontend Components

- [ ] Создать `src/components/AIAssistantPanel/DynamicForm/`
  - [ ] `DynamicForm.tsx` — главный компонент
  - [ ] `FormField.tsx` — универсальный рендерер полей
  - [ ] `RadioGroup.tsx` — radio buttons с иконками
  - [ ] `ConditionalField.tsx` — условные поля
  - [ ] `SmartSelect.tsx` — select с поиском и умными подсказками
  - [ ] `LoadingSpinner.tsx` — спиннер для загрузки

- [ ] Обновить `src/stores/ai_assistant_store.ts`:
  - [ ] Добавить state для форм: `currentForm`, `formLoading`
  - [ ] Action: `setCurrentForm(form)`
  - [ ] Action: `submitForm(formData)`
  - [ ] Action: `clearForm()`

### Form Schema Validation

- [ ] Создать `backend/schemas/form_schema.py`
  - [ ] Pydantic models для form validation
  - [ ] `FormSchema`, `FormField`, `FormAction`
  - [ ] Валидация conditional logic
  - [ ] Валидация типов полей (radio, select, date, etc.)

### Security & Sandboxing

- [ ] Sandbox для выполнения генерированных компонентов:
  - [ ] React component sandbox с ограничениями
  - [ ] Валидация кода перед компиляцией
  - [ ] Ограничение доступа к window/document
  - [ ] Timeout для рендеринга (5 сек max)

### Testing

- [ ] Backend tests:
  - [ ] test_form_generator_agent()
  - [ ] test_data_source_scanner()
  - [ ] test_smart_suggestions()
  - [ ] test_form_schema_validation()
  - [ ] test_conditional_logic()

- [ ] Frontend tests:
  - [ ] test_dynamic_form_render()
  - [ ] test_conditional_fields()
  - [ ] test_form_submission()
  - [ ] test_loading_states()

---

## 🧪 Testing (Continued)

### Backend Tests (Continued)

- [ ] Unit tests для `AIAssistantService` (pytest):
  - [ ] test_process_message_basic()
  - [ ] test_build_system_prompt_with_context()
  - [ ] test_parse_response_with_actions()
  - [ ] test_apply_action_create_widget()
  - [ ] test_rate_limiting()
  - [ ] test_cache_hit()
  - [ ] test_error_handling_gigachat_unavailable()

- [ ] Integration tests:
  - [ ] test_full_dialog_flow() — от сообщения до widget creation
  - [ ] test_multi_turn_conversation() — контекст между вопросами
  - [ ] test_real_time_sync() — виджет видно на других клиентах

### Frontend Tests

- [ ] Component tests (Vitest + React Testing Library):
  - [ ] test_panel_opens_and_closes()
  - [ ] test_message_sent_and_received()
  - [ ] test_action_button_applies_widget()
  - [ ] test_loading_state()
  - [ ] test_error_handling()
  - [ ] test_keyboard_shortcuts()

- [ ] E2E tests (Cypress или Playwright):
  - [ ] User opens board → AI panel available
  - [ ] User types question → gets response
  - [ ] User clicks action → widget appears on canvas
  - [ ] Other user sees widget in real-time

### Performance Tests

- [ ] Response time < 2 sec (P95)
- [ ] Message list scrolls smoothly (60fps)
- [ ] Memory usage stable при долгих диалогах

---

## 📊 Database & Schema

- [ ] (Опционально) Chat history в PostgreSQL:
  - [ ] Таблица `chat_messages`
    ```sql
    CREATE TABLE chat_messages (
      id UUID PRIMARY KEY,
      board_id UUID REFERENCES boards(id),
      user_id UUID REFERENCES users(id),
      role VARCHAR(20), -- 'user' или 'assistant'
      content TEXT,
      suggested_actions JSONB,
      session_id UUID,
      created_at TIMESTAMP,
      updated_at TIMESTAMP
    );
    ```
  - [ ] Index на (board_id, session_id) для быстрой выборки

- [ ] (Опционально) Actions applied логирование:
  - [ ] Таблица `ai_actions_log`
    ```sql
    CREATE TABLE ai_actions_log (
      id UUID PRIMARY KEY,
      board_id UUID,
      user_id UUID,
      action_type VARCHAR(50),
      action_data JSONB,
      widget_created_id UUID,
      applied_at TIMESTAMP
    );
    ```

---

## 🚀 Deployment & DevOps

- [ ] Environment variables:
  - [ ] `GIGACHAT_API_KEY`
  - [ ] `GIGACHAT_API_URL`
  - [ ] `REDIS_URL`
  - [ ] `AI_ASSISTANT_ENABLED` (feature flag)

- [ ] Docker:
  - [ ] Добавить в `backend/requirements.txt`: `langchain-gigachat`, `redis`
  - [ ] Обновить `docker-compose.yml` с Redis service

- [ ] CI/CD:
  - [ ] Lint: `mypy src/`, `eslint src/`
  - [ ] Tests: `pytest`, `vitest`
  - [ ] Coverage: > 70% для критичных модулей

---

## 📈 Monitoring & Observability

- [ ] Метрики (Prometheus):
  - [ ] `ai_chat_messages_total` counter
  - [ ] `ai_chat_response_time_seconds` histogram
  - [ ] `ai_chat_actions_applied` counter
  - [ ] `ai_chat_errors_total` counter

- [ ] Логирование:
  - [ ] Структурированные логи (JSON format)
  - [ ] Level: DEBUG, INFO, WARN, ERROR
  - [ ] Context: board_id, user_id, session_id

- [ ] Dashboards:
  - [ ] Messages/day, Average response time
  - [ ] Top questions (анонимизированные)
  - [ ] Success rate actions
  - [ ] Error trends

---

## 🔄 Rollout Plan

### Phase 1: Internal Testing (Week 1-2)
- [ ] Deploy на staging
- [ ] Internal team tests dialogs
- [ ] Collect feedback
- [ ] Fix critical bugs

### Phase 2: Beta (Week 3-4)
- [ ] Deploy на production с feature flag (disabled)
- [ ] Enable для 10% users
- [ ] Monitor metrics
- [ ] Collect feedback

### Phase 3: GA (Week 5+)
- [ ] Enable для всех users
- [ ] Monitor for issues
- [ ] Optimize based on usage patterns

---

## ✅ Definition of Done

- [x] Документация завершена
- [ ] Backend реализован и протестирован
- [ ] Frontend реализован и протестирован
- [ ] Integration тесты passed
- [ ] Performance тесты passed (response time < 2 sec)
- [ ] Code review approved
- [ ] Merged в main branch
- [ ] Deployed на staging
- [ ] Staging testing approved
- [ ] Deployed на production
- [ ] Monitoring и alerting настроены
- [ ] User documentation готова

---

**Статус**: Готов к разработке 🚀
**Дата**: 2026-01-23
**Приоритет**: HIGH (часть MVP)
