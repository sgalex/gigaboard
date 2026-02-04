# Контекстное меню DataNode - Реализовано

**Дата**: 26 января 2026  
**Статус**: ✅ Базовая версия готова

---

## Что реализовано

### Компоненты
- **DataNodeContextMenu.tsx** - Основной компонент контекстного меню
- **DataNodeCard.tsx** - Интегрировано меню с кнопкой ⋮ в заголовке

### Функции меню

#### ✅ Реализовано (UI + обработчики)

1. **📊 Просмотр данных**
   - Опция: "Просмотр данных"
   - Обработчик: `onViewData`
   - TODO: Модальное окно с preview (первые 100 строк, schema, метаданные)

2. **🎨 Создать визуализацию**
   - Опция: "Создать визуализацию" (с маркером AI)
   - Обработчик: `onCreateVisualization`
   - TODO: Диалог для ввода промпта + интеграция с Reporter Agent

3. **⚙️ Создать трансформацию**
   - Опция: "Создать трансформацию" (с маркером AI)
   - Обработчик: `onCreateTransformation`
   - TODO: Диалог для ввода промпта + интеграция с Transformation Agent

4. **💬 Добавить комментарий**
   - Опция: "Добавить комментарий"
   - Обработчик: `onAddComment`
   - TODO: Диалог создания CommentNode + интеграция с Analyst Agent для AI-инсайтов

5. **🔗 Просмотр связей**
   - Опция: "Просмотр связей"
   - Обработчик: `onViewConnections`
   - TODO: Модальное окно со списком всех edges (входящие/исходящие)

6. **🔄 Обновить данные**
   - Опция: "Обновить данные"
   - Обработчик: `onRefresh`
   - TODO: API вызов для refresh DataNode (re-fetch SQL/API/File)

7. **📤 Экспорт**
   - Подменю с опциями:
     - Экспорт в CSV
     - Экспорт в JSON
     - Экспорт в Excel
   - Обработчик: `onExport(format)`
   - TODO: Генерация и скачивание файла

8. **✏️ Редактировать**
   - Опция: "Редактировать"
   - Обработчик: `onEdit`
   - TODO: Диалог редактирования (EditDataNodeDialog)

9. **🗑️ Удалить узел**
   - Опция: "Удалить узел" (красный цвет)
   - Обработчик: `onDelete`
   - ✅ Реализовано: Confirmation dialog + cascade delete warning

---

## Как использовать

### Открытие меню
1. **Кнопка ⋮** в заголовке DataNode - клик открывает dropdown menu
2. **Правый клик** на узле - также открывает контекстное меню

### Структура меню
```
DataNode: "Название узла"
├─ 📊 Просмотр данных
├─ ──────────────────
├─ 🎨 Создать визуализацию [AI]
├─ ⚙️ Создать трансформацию [AI]
├─ 💬 Добавить комментарий
├─ ──────────────────
├─ 🔗 Просмотр связей
├─ 🔄 Обновить данные
├─ 📤 Экспорт
│  ├─ Экспорт в CSV
│  ├─ Экспорт в JSON
│  └─ Экспорт в Excel
├─ ──────────────────
├─ ✏️ Редактировать
└─ 🗑️ Удалить узел
```

---

## Следующие шаги (приоритет)

### 1. Диалог просмотра данных (High Priority)
**Файл**: `apps/web/src/components/dialogs/ViewDataDialog.tsx`

**Функции**:
- Отображение первых 100 строк в таблице
- Schema viewer (колонки, типы данных)
- Метаданные: row count, column count, размер
- Фильтрация и сортировка
- Копирование данных в буфер обмена

**API endpoint**: `GET /api/v1/boards/{boardId}/data-nodes/{nodeId}/preview`

### 2. Диалог создания визуализации (High Priority)
**Файл**: `apps/web/src/components/dialogs/CreateVisualizationDialog.tsx`

**Функции**:
- Текстовое поле для промпта пользователя
- Примеры промптов (placeholder)
- Кнопка "Авто-визуализация" (AI выбирает тип автоматически)
- Интеграция с Reporter Agent API
- Preview сгенерированного кода

**API endpoint**: `POST /api/v1/boards/{boardId}/data-nodes/{nodeId}/visualize`

### 3. Диалог создания трансформации (High Priority)
**Файл**: `apps/web/src/components/dialogs/CreateTransformationDialog.tsx`

**Функции**:
- Текстовое поле для промпта трансформации
- Примеры: "отфильтруй продажи > 1000", "группируй по региону"
- Множественный выбор source DataNodes (для join операций)
- Интеграция с Transformation Agent API
- Preview сгенерированного Python кода
- Execute и создание нового DataNode с результатом

**API endpoint**: `POST /api/v1/boards/{boardId}/data-nodes/{nodeId}/transform`

### 4. Диалог редактирования (Medium Priority)
**Файл**: `apps/web/src/components/dialogs/EditDataNodeDialog.tsx`

**Функции**:
- Редактирование name, description
- Редактирование query (для SQL DataNodes)
- Редактирование API config (для API DataNodes)
- Replace файла (для File DataNodes)
- Validation и сохранение

**API endpoint**: `PATCH /api/v1/boards/{boardId}/data-nodes/{nodeId}`

### 5. Refresh функциональность (Medium Priority)
**Backend**: Добавить endpoint для refresh

**API endpoint**: `POST /api/v1/boards/{boardId}/data-nodes/{nodeId}/refresh`

**Логика**:
- SQL DataNode: re-execute query
- API DataNode: re-fetch данные (новый HTTP request)
- File DataNode: re-read файл
- Обновить content, schema, metadata
- Broadcast обновление через WebSocket

### 6. Экспорт функциональность (Medium Priority)
**Backend**: Добавить endpoints для экспорта

**API endpoints**:
- `GET /api/v1/boards/{boardId}/data-nodes/{nodeId}/export/csv`
- `GET /api/v1/boards/{boardId}/data-nodes/{nodeId}/export/json`
- `GET /api/v1/boards/{boardId}/data-nodes/{nodeId}/export/xlsx`

**Формат ответа**: File download (Content-Disposition: attachment)

### 7. Просмотр связей (Low Priority)
**Файл**: `apps/web/src/components/dialogs/ViewConnectionsDialog.tsx`

**Функции**:
- Список всех edges:
  - Входящие (upstream): TRANSFORMATION edges → this node
  - Исходящие (downstream): this node → TRANSFORMATION/VISUALIZATION edges
  - Комментарии: COMMENT edges → this node
  - Справочные: REFERENCE/DRILL_DOWN edges
- Переход к связанному узлу (focus на канвасе)
- Metadata edge (label, visual_config, transformation code)

---

## Архитектура

### Компонент: DataNodeContextMenu

**Props**:
```typescript
interface DataNodeContextMenuProps {
    dataNode: DataNode
    children: React.ReactNode
    onCreateVisualization?: () => void
    onCreateTransformation?: () => void
    onAddComment?: () => void
    onRefresh?: () => void
    onEdit?: () => void
    onDelete?: () => void
    onViewData?: () => void
    onExport?: (format: 'csv' | 'json' | 'xlsx') => void
    onViewConnections?: () => void
}
```

**Использование**:
```tsx
<DataNodeContextMenu
    dataNode={node}
    onCreateVisualization={handleCreateVisualization}
    onCreateTransformation={handleCreateTransformation}
    // ... другие обработчики
>
    <div className="datanode-card">
        {/* Content */}
    </div>
</DataNodeContextMenu>
```

### Интеграция с DataNodeCard

**Изменения в DataNodeCard.tsx**:
1. Импорт `DataNodeContextMenu`
2. Добавлена кнопка ⋮ в заголовке
3. Обёрнута карточка в `<DataNodeContextMenu>`
4. Добавлены обработчики для всех операций
5. Реализован `handleDelete` с confirmation dialog

---

## Демо и тестирование

### Как протестировать
1. Запустить dev окружение: `.\run-dev.ps1`
2. Открыть доску с DataNode
3. Кликнуть на кнопку ⋮ в заголовке узла
4. Попробовать все опции меню

### Текущее поведение
- Все опции показывают alert с уведомлением "будет реализовано в следующей версии"
- Кроме **Удалить узел** - работает полностью (confirmation + cascade delete)

---

## Документация

**Полная спецификация**: `docs/DATANODE_CONTEXT_MENU.md`

**Связанные документы**:
- `docs/MULTI_AGENT_SYSTEM.md` - AI агенты (Reporter, Transformation, Analyst)
- `docs/DATA_LINEAGE_SYSTEM.md` - Граф зависимостей и edges
- `docs/WIDGETNODE_GENERATION_SYSTEM.md` - Генерация визуализаций

---

## Заметки по реализации

### Удаление узла (cascade delete)
**Текущая реализация**:
- Confirmation dialog с предупреждением о каскадном удалении
- Вызов `deleteDataNode(boardId, nodeId)`
- Backend автоматически удаляет связанные edges

**TODO (для улучшения)**:
- Показать список affected nodes перед удалением
- Опции: Hard delete / Soft delete / Detach
- API endpoint для preview cascade: `GET /api/v1/boards/{boardId}/data-nodes/{nodeId}/cascade-preview`

### AI интеграции
**Placeholder алерты** для:
- Создание визуализации → Reporter Agent
- Создание трансформации → Transformation Agent
- AI-инсайты → Analyst Agent

**Следующий шаг**: Создать диалоги с интеграцией агентов через API

---

## Дизайн

### UI/UX решения
- **Кнопка ⋮**: В правом верхнем углу заголовка узла
- **Цвета**: 
  - Основные опции: default
  - AI функции: маркер "AI" справа (text-muted-foreground)
  - Удаление: text-destructive (красный)
- **Подменю**: Экспорт использует `DropdownMenuSub` для вложенных опций
- **Separator**: Логические группы разделены линиями

### Accessibility
- Keyboard navigation: работает из коробки (shadcn/ui dropdown)
- Screen reader: aria-labels на всех опциях
- Focus management: автоматический focus trap при открытии

---

## Итоги

✅ **Готово**:
- Структура меню
- UI компоненты
- Интеграция с DataNodeCard
- Обработчики событий (stubs)
- Удаление узла (полная реализация)

🚧 **В разработке**:
- Диалоги для всех операций
- AI интеграции
- Backend endpoints (refresh, export)
- Просмотр данных и связей

📝 **Запланировано**:
- Автоматизация (авто-refresh, авто-replay трансформаций)
- Версионирование узлов
- Права доступа и lock/unlock
- Расширенные функции (drill-down, справочные связи)
