# Контекстное меню SourceNode

> **⚠️ LEGACY ДОКУМЕНТ**: Данный документ описывает устаревшую **DataNode** архитектуру.  
> 🆕 **См. Source-Content Node Architecture**: [NODE_MANAGEMENT_SYSTEM.md](./NODE_MANAGEMENT_SYSTEM.md), [CONNECTION_TYPES.md](./CONNECTION_TYPES.md)  
> 📝 Документ будет обновлён под новую архитектуру (SourceNode/ContentNode) в ближайшее время.

**Статус**: 🚧 В разработке  
**Приоритет**: Must Have (Phase 2)  
**Дата создания**: 26 января 2026

---

## Обзор

При активации (выделении) **SourceNode** на канвасе рядом с узлом появляется контекстное меню с перечнем доступных операций. Меню группирует операции по категориям и предоставляет быстрый доступ к ключевым функциям работы с данными.

---

## Структура меню

### **📊 1. ПРОСМОТР ДАННЫХ**

#### **Предварительный просмотр**
- **Табличные данные** (CSV, JSON, SQL результаты):
  - Отображение первых 100 строк в модальном окне
  - Показ schema (названия колонок, типы данных)
  - Row count, column count
  
- **Файлы** (PDF, XLSX, DOCX, изображения):
  - Встроенный viewer для PDF
  - Excel preview для XLSX
  - Image preview для изображений (PNG, JPG, SVG)
  - Document preview для DOCX
  
- **API responses** (JSON, XML):
  - Форматированное отображение структуры
  - Collapsible tree view для вложенных объектов
  
- **Бинарные данные**:
  - Метаданные: размер файла, MIME type, последнее изменение
  - Hex viewer (первые N байт)
  - Download опция

**Метаданные**:
- Источник данных (тип, конфигурация)
- Размер данных (bytes, rows)
- Последнее обновление
- Статус (актуальность)

#### **AI-инсайты** *(Analyst Agent)*
- Запросить у Analyst Agent анализ данных
- Автоматическое обнаружение паттернов, аномалий, трендов
- Создание CommentNode с результатами анализа
- Примеры инсайтов:
  - "Обнаружен spike в продажах 15 декабря (+350%)"
  - "Пропущены данные за 25 декабря"
  - "Сильная корреляция с email-кампанией (+0.82)"

---

### **🎨 2. ВИЗУАЛИЗАЦИЯ** *(Reporter Agent)*

#### **Создать визуализацию**
- **С подсказкой AI**: 
  - Пользователь вводит prompt: "создай линейный график продаж по времени"
  - Reporter Agent анализирует данные и генерирует HTML/CSS/JS код
  
- **Авто-визуализация**: 
  - Reporter Agent автоматически определяет оптимальный тип визуализации
  - Анализирует schema, типы данных, row count
  - Генерирует подходящую визуализацию без user prompt
  
- **Множественные виджеты**:
  - Создать несколько визуализаций одновременно
  - Например: график + таблица + KPI метрика
  - Все виджеты размещаются рядом с SourceNode

**Результат**: 
- Создаётся WidgetNode с `parent_data_node_id`
- Создаётся VISUALIZATION edge: SourceNode → WidgetNode
- WidgetNode размещается на канвасе справа от SourceNode

#### **Управление виджетами**
- Список всех связанных WidgetNode (через VISUALIZATION edges)
- Открыть/перейти к виджету (focus на канвасе)
- Обновить все виджеты (refresh)
- Удалить виджет (с каскадным удалением edge)
- Настроить авто-обновление:
  - При изменении SourceNode все виджеты обновляются автоматически
  - Toggle on/off для каждого виджета

---

### **⚙️ 3. ТРАНСФОРМАЦИИ** *(Transformation Agent)*

#### **Создать трансформацию**

**Одиночная трансформация** (SourceNode → новый ContentNode):
- Пользователь вводит prompt: "отфильтруй продажи > 1000"
- Transformation Agent генерирует Python код
- Executor Agent выполняет код в sandbox
- Создаётся новый ContentNode с результатом
- Создаётся TRANSFORMATION edge: source SourceNode → target ContentNode

**Множественная трансформация** (несколько SourceNode → один ContentNode):
- Выбрать другие SourceNode как дополнительные источники
- Prompt: "объедини эти данные с customer_data по customer_id и посчитай total_revenue"
- Transformation Agent генерирует код с множественными входами
- Создаются TRANSFORMATION edges от всех источников к результату

**Процесс**:
1. User prompt → Transformation Agent
2. Agent генерирует Python код
3. Executor Agent выполняет в sandbox
4. Создаётся новый ContentNode с результатом
5. Создаются TRANSFORMATION edges
6. Новый узел размещается на канвасе

#### **Переиспользовать трансформацию** *(Replay)*
- Просмотр списка downstream трансформаций (где этот SourceNode является источником)
- Выбрать трансформацию для replay
- Запустить снова с текущими данными
- Обновить target ContentNode новыми результатами
- Просмотр истории выполнения:
  - Timestamp
  - Duration
  - Status (success/failed)
  - Error messages (если были)

#### **Автоматизация**
- **Авто-replay**: 
  - При обновлении source SourceNode автоматически пересчитывать все downstream трансформации
  - Toggle on/off для каждой трансформации
  
- **Расписание** (опционально, если поддерживается):
  - Настроить периодическое выполнение
  - Например: каждый час, каждый день в 9:00

**Замечание**: Impact Analysis (какие узлы затронуты при изменении) встроен в функционал Transformation Agent. При создании/replay трансформации агент автоматически анализирует граф зависимостей и показывает затронутые узлы.

---

### **💬 4. КОММЕНТАРИИ И АННОТАЦИИ**

#### **Добавить комментарий**
- Текстовый комментарий пользователя
- Markdown поддержка
- Создаётся CommentNode с `target_node_id` = этот SourceNode
- Создаётся COMMENT edge: CommentNode → SourceNode
- CommentNode размещается рядом с SourceNode

#### **AI-инсайт** *(Analyst Agent)*
- Запросить автоматический анализ у Analyst Agent
- Agent анализирует данные и находит:
  - Аномалии (spikes, drops, missing data)
  - Паттерны (seasonality, trends, correlations)
  - Рекомендации (data quality issues, suggested transformations)
- Создаётся CommentNode с результатами
- Создаётся COMMENT edge: CommentNode → SourceNode

**Примеры AI-инсайтов**:
```
⚠️ Anomalies detected:
• Spike on Dec 15 (+350%) - likely Black Friday
• Missing data Dec 25 - Christmas holiday
• Strong correlation with email campaign (+0.82)
```

#### **Управление комментариями**
- Просмотр всех комментариев к этому узлу
- Треды (ответы на комментарии)
- Отметить resolved/unresolved
- Удалить комментарий (каскадно удаляется CommentNode и COMMENT edge)

---

### **🔗 5. НАВИГАЦИЯ И DRILL-DOWN**

#### **Настроить Drill-Down**
- Создать DRILL_DOWN edge к детализированным данным
- Процесс:
  1. Выбрать целевой SourceNode на канвасе (detail level)
  2. Настроить фильтрацию при переходе
  3. Создаётся DRILL_DOWN edge: summary SourceNode → detail SourceNode
  
**Для WidgetNode (drill-down в виджетах)**:
- Настроить click handler для элементов графика
- Пример: клик на "North" в pie chart → показать детали по North region
- При клике автоматически создаётся filtered ContentNode или открывается существующий detail node
- Breadcrumb navigation для возврата назад

#### **Создать справочную связь** *(REFERENCE)*
- Связать с другим узлом для документации контекста
- Примеры:
  - Связь к CommentNode с описанием источника данных
  - Связь к другому SourceNode с методологией
  - Связь к WidgetNode с reference documentation
- Создаётся REFERENCE edge: этот SourceNode → целевой узел
- Легковесная связь (не влияет на трансформации/обновления)

**Важно**: Edges (TRANSFORMATION, VISUALIZATION, COMMENT) создаются **автоматически** при выполнении соответствующих операций (создание трансформации, визуализации, комментария). Ручное создание edges доступно только для REFERENCE и DRILL_DOWN, где требуется явное указание связи пользователем.

#### **Просмотр связей**
- Список всех edges связанных с этим SourceNode:
  - **Входящие** (upstream): откуда приходят данные
    - TRANSFORMATION edges (source → this node)
  - **Исходящие** (downstream): куда идут данные
    - TRANSFORMATION edges (this node → targets)
    - VISUALIZATION edges (this node → widgets)
  - **Комментарии**:
    - COMMENT edges (comments → this node)
  - **Справочные**:
    - REFERENCE edges
    - DRILL_DOWN edges
- Переход к связанному узлу (focus на канвасе)
- Показ metadata edge (label, visual_config, transformation code)

---

### **🔄 6. ИСТОЧНИКИ ДАННЫХ**

#### **Обновить данные** *(Refresh)*
- Принудительно перезагрузить данные из источника
- **Для SQL**: re-execute query
- **Для API**: re-fetch данные (новый API call)
- **Для файлов**: re-read файл (если изменился)
- API endpoint: `POST /api/v1/boards/{boardId}/data-nodes/{nodeId}/refresh`

**После обновления**:
- Обновляется content SourceNode
- Обновляется schema (если изменилась)
- Обновляется metadata (size, row_count, last_updated)
- Опционально: trigger авто-replay downstream трансформаций
- Опционально: trigger авто-refresh связанных WidgetNodes

#### **Редактировать источник**
- **SQL SourceNode**: 
  - Открыть SQL editor
  - Изменить query
  - Re-execute и обновить SourceNode
  
- **API SourceNode**:
  - Изменить API config (endpoint, headers, params)
  - Re-fetch данные
  
- **File SourceNode**:
  - Replace файл (upload новый)

#### **Настроить параметры**
- Редактировать `parameters` для query templates
- Пример: 
  ```sql
  SELECT * FROM sales WHERE region = {{region_param}} AND date > {{start_date}}
  ```
- Изменить `region_param`, `start_date`
- Refresh SourceNode с новыми параметрами

#### **Планировщик обновлений** *(опционально)*
- Настроить авто-refresh по расписанию:
  - Каждый час
  - Каждый день в определённое время
  - По cron expression
- Trigger-based updates:
  - Webhook (внешнее событие → refresh)
  - Event-based (изменение другого SourceNode → refresh)

---

### **📤 7. ЭКСПОРТ И СОВМЕСТНАЯ РАБОТА**

#### **Экспорт данных**
- **CSV**: скачать данные в CSV формате
- **JSON**: скачать в JSON формате
- **Excel**: экспорт в .xlsx (если табличные данные)
- **Копировать в буфер**: копировать sample (первые N строк)
- **Original format**: скачать в оригинальном формате (PDF, XLSX, изображение)

#### **Поделиться**
- **Public link**: создать публичную ссылку на SourceNode
  - View-only режим
  - Опционально: password protection
  - Expiration date
  
- **Embed link**: создать embed для виджетов (связанных WidgetNodes)
  
- **Пригласить коллег**:
  - Share board с правами view/edit
  - Collaboration permissions

#### **Дублирование**
- **Shallow copy**: клонировать узел без данных
  - Копируется конфигурация источника (query, API config)
  - Данные не копируются (нужен refresh для загрузки)
  
- **Deep copy**: клонировать узел с данными
  - Полная копия content
  - Новый независимый узел
  
- **Clone with transformations**:
  - Клонировать узел + все downstream трансформации
  - Воссоздать весь pipeline

---

### **⚙️ 8. УПРАВЛЕНИЕ УЗЛОМ**

#### **Редактирование**
- **Name/Description**: изменить название и описание
- **Position**: переместить узел (x, y координаты)
- **Size**: изменить размер (width, height)
- API: `PATCH /api/v1/boards/{boardId}/data-nodes/{nodeId}`

#### **Layout**
- **Auto-layout**: автоматически расположить узел и его связи
- **Snap to grid**: привязка к сетке канваса
- **Align with nodes**: выравнивание с соседними узлами
- **Group nodes**: создать группу узлов (визуальная группировка)

#### **Права доступа**
- **Permissions**: 
  - View only: только просмотр
  - Edit: полные права
  - Restrict specific users
  
- **Lock/Unlock**: 
  - Lock: защита от случайных изменений (move, delete)
  - Unlock: разрешить редактирование
  
- **Audit trail**: 
  - История изменений
  - Кто, когда, что изменил

#### **Метаданные**
- **Теги**: добавить теги для поиска и фильтрации
  - Примеры: "sales", "Q4", "cleaned", "production"
  
- **Категория/Группа**: 
  - Назначить узел в категорию
  - Примеры: "Raw Data", "Cleaned", "Aggregated", "Final"
  
- **Цвет**: 
  - Цветовая маркировка узла
  - Для визуальной организации и быстрого поиска

#### **Удаление**
- **Delete node**: удалить SourceNode
  
- **Cascade preview**: 
  - Показать все узлы, которые будут удалены:
    - WidgetNodes (VISUALIZATION edges)
    - CommentNodes (COMMENT edges)
    - Target ContentNodes (если это source для трансформаций с авто-удалением)
  - Confirmation dialog с полным списком affected nodes
  
- **Cascade options**:
  - **Hard delete**: полное удаление всех зависимых узлов
  - **Soft delete**: пометить как deleted, сохранить историю
  - **Detach**: удалить только этот узел, оставить dependent nodes (они станут "orphaned")

---

### **🔧 9. РАЗРАБОТКА И ОТЛАДКА**

#### **Открыть в редакторе**
- **SQL Editor**: для SQL SourceNodes
  - Syntax highlighting
  - Query execution
  - Results preview
  
- **API Explorer**: для API SourceNodes
  - Request builder (headers, params, body)
  - Response preview
  - Test API call
  
- **Python Sandbox**: для трансформаций
  - Code editor с syntax highlighting
  - Execute transformation
  - Debug output

#### **Отладка трансформаций** *(для downstream трансформаций)*
- Просмотр transformation code (Python)
- Execution logs:
  - stdout/stderr
  - Execution timestamp
  - Status (success/failed)
  
- Performance metrics:
  - Duration (ms)
  - Memory usage (MB)
  - CPU usage (%)
  
- Error traceback (если был сбой):
  - Full Python traceback
  - Error message
  - Suggested fixes (AI-powered)

#### **Версионирование** *(опционально)*
- История версий SourceNode:
  - Content changes
  - Schema changes
  - Configuration changes
  
- Diff между версиями:
  - Schema diff (added/removed/changed columns)
  - Data diff (row count, statistics)
  
- **Restore**: откатиться к предыдущей версии

---

## Приоритизация в UI

### **Основное меню** (всегда видимо, первый уровень)

```
📊 Предварительный просмотр
🎨 Создать визуализацию
⚙️ Создать трансформацию
💬 Добавить комментарий
🔄 Обновить данные
───────────────────────────
🔗 Просмотр связей
📤 Экспорт
⚙️ Дополнительно ▶
🗑️ Удалить узел
```

### **Подменю "Дополнительно"**

```
Управление виджетами ▶
  • Список виджетов
  • Обновить все
  • Настроить авто-обновление
  
Трансформации ▶
  • Переиспользовать (Replay)
  • Автоматизация
  • Отладка
  
Комментарии ▶
  • Просмотр всех
  • AI-инсайт
  
Drill-Down и навигация ▶
  • Настроить Drill-Down
  • Создать справочную связь
  
Источник данных ▶
  • Редактировать источник
  • Настроить параметры
  • Планировщик обновлений
  
Совместная работа ▶
  • Поделиться
  • Дублирование
  
Управление узлом ▶
  • Layout
  • Права доступа
  • Метаданные
  • Версионирование
  
Разработка ▶
  • Открыть в редакторе
  • Отладка
```

---

## Связь с агентами

| Агент                    | Операции                                                   |
| ------------------------ | ---------------------------------------------------------- |
| **Reporter Agent**       | Создание визуализаций (WidgetNode генерация)               |
| **Transformation Agent** | Создание и генерация кода трансформаций                    |
| **Analyst Agent**        | AI-инсайты, анализ паттернов, аномалий                     |
| **Executor Agent**       | Выполнение трансформаций, replay, sandbox execution        |
| **Planner Agent**        | Координация множественных операций, workflow orchestration |

---

## API Endpoints

### Основные операции

```
GET    /api/v1/boards/{boardId}/data-nodes/{nodeId}
PATCH  /api/v1/boards/{boardId}/data-nodes/{nodeId}
DELETE /api/v1/boards/{boardId}/data-nodes/{nodeId}
POST   /api/v1/boards/{boardId}/data-nodes/{nodeId}/refresh

POST   /api/v1/boards/{boardId}/widget-nodes
GET    /api/v1/boards/{boardId}/widget-nodes?parent_data_node_id={nodeId}
DELETE /api/v1/boards/{boardId}/widget-nodes/{widgetId}

POST   /api/v1/boards/{boardId}/comment-nodes
GET    /api/v1/boards/{boardId}/comment-nodes?target_node_id={nodeId}

POST   /api/v1/boards/{boardId}/edges
GET    /api/v1/boards/{boardId}/edges?from_node_id={nodeId}
GET    /api/v1/boards/{boardId}/edges?to_node_id={nodeId}
DELETE /api/v1/boards/{boardId}/edges/{edgeId}

POST   /api/v1/boards/{boardId}/transformations
POST   /api/v1/boards/{boardId}/transformations/{transformationId}/replay
```

---

## UI/UX Рекомендации

### Позиционирование меню
- Меню появляется **справа от узла** при его выделении
- Floating panel с тенью
- Закрывается при клике вне меню или на другой узел

### Группировка действий
- Визуальные разделители между группами
- Иконки для каждого пункта (consistent icon set)
- Подменю открываются справа (›)

### Feedback и индикация
- Loading states для долгих операций (API calls, transformations)
- Success/Error toasts после выполнения
- Progress bars для multi-step операций
- Confirmation dialogs для destructive actions (delete, cascade)

### Keyboard shortcuts (опционально)
- `V` - Create Visualization
- `T` - Create Transformation
- `C` - Add Comment
- `R` - Refresh Data
- `E` - Export
- `Del` - Delete Node

---

## Примеры использования

### Сценарий 1: Анализ продаж

1. User выделяет SourceNode "Sales CSV"
2. Клик "📊 Предварительный просмотр" → видит первые 100 строк
3. Клик "🎨 Создать визуализацию" → вводит "создай график продаж по месяцам"
4. Reporter Agent создаёт WidgetNode с линейным графиком
5. User видит spike в декабре, клик "💬 AI-инсайт"
6. Analyst Agent создаёт CommentNode: "Spike в декабре связан с Black Friday"

### Сценарий 2: Трансформация данных

1. User выделяет SourceNode "Raw Orders"
2. Клик "⚙️ Создать трансформацию"
3. Вводит: "отфильтруй заказы > $1000 и добавь колонку revenue_category"
4. Transformation Agent генерирует Python код
5. Executor Agent выполняет трансформацию
6. Создаётся новый ContentNode "Filtered Orders" + TRANSFORMATION edge
7. User настраивает авто-replay: при обновлении Raw Orders автоматически пересчитывать Filtered

### Сценарий 3: Drill-Down

1. User создал WidgetNode "Sales by Region" (pie chart) из SourceNode "Sales Summary"
2. Выделяет SourceNode "Sales Summary"
3. Клик "🔗 Настроить Drill-Down"
4. Выбирает target SourceNode "Sales Details"
5. Настраивает фильтр: region = clicked_value
6. Создаётся DRILL_DOWN edge
7. Теперь при клике на "North" в pie chart открывается filtered view Sales Details для North

---

## Итоги

Контекстное меню SourceNode обеспечивает:
- ✅ Быстрый доступ ко всем операциям узла
- ✅ Интеграцию с AI-агентами (Reporter, Transformation, Analyst)
- ✅ Управление зависимостями (edges, cascade)
- ✅ Workflow automation (auto-replay, auto-refresh)
- ✅ Collaboration features (share, export, permissions)
- ✅ Developer tools (debugging, versioning, editors)

Меню является центральным интерфейсом для работы с данными на канвасе и реализует все ключевые возможности системы SourceNode → Transformation → WidgetNode.
