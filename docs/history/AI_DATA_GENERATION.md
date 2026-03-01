# 🤖 AI Data Generation Feature (ARCHIVED)

**Дата реализации**: 27 января 2026  
**Статус**: ⚠️ АРХИВИРОВАН - заменён на Multi-Agent обработку промптов

---

## ⚠️ Важное изменение архитектуры

**Изначальная концепция**: Отдельная кнопка "Сгенерировать данные через AI" для генерации фейковых данных.

**Новая архитектура (актуально)**: 
- Все текстовые промпты в DataNode обрабатываются **Multi-Agent системой**
- Единая кнопка "Создать источник" для всех типов данных
- Multi-Agent анализирует характер промпта и выбирает стратегию:
  - Генерация синтетических данных (фейковые данные)
  - Сбор данных из открытых источников (Kaggle, OECD, World Bank)
  - Deep research (веб-скрапинг, агрегация из нескольких источников)
  - Трансформация существующих данных

См. актуальную документацию:
- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - архитектура Multi-Agent системы
- [INTEGRATION_MULTI_AGENT.md](INTEGRATION_MULTI_AGENT.md) - интеграция с GigaBoard

---

## 📋 Описание (историческая версия)

Функция AI-генерации синтетических данных позволяет пользователям создавать DataNode с реалистичными данными через естественный язык. Идеально для:
- Быстрого прототипирования дашбордов
- Демонстрации возможностей платформы
- Тестирования визуализаций без реальных данных
- Обучения и экспериментов

---

## 🎯 Кейс использования

### Сценарий: Создание дашборда продаж

```
1. User → "Создать DataNode"
2. Выбирает тип: "Текст / Промпт"
3. Название: "Sales Data"
4. Промпт: "Сгенерируй данные о продажах за последние 30 дней"
5. Кликает "Сгенерировать данные через AI" ✨
   ↓
6. AI (GigaChat) генерирует JSON:
   [
     {"date": "2026-01-01", "product": "Widget A", "quantity": 15, "revenue": 1499.50},
     {"date": "2026-01-02", "product": "Widget B", "quantity": 8, "revenue": 799.20},
     ...
   ]
   ↓
7. DataNode создаётся с данными
8. User → "Просмотр данных" → Видит таблицу с 30 записями
9. User → ПКМ → "Создать визуализацию" → AI создаёт line chart
```

---

## 🏗️ Архитектура

### Backend Stack

```
Frontend: CreateDataNodeDialog
    ↓
POST /api/v1/boards/{id}/data-nodes/generate-ai
    ↓
data_nodes.py: generate_ai_data_node()
    ↓
DataNodeService.generate_data_from_ai()
    ↓
AIDataGenerator.generate_data_from_prompt()
    ↓
GigaChatService.chat_completion()
    ↓
GigaChat API → JSON response
    ↓
Парсинг JSON + Type inference
    ↓
Сохранение в DataNode.data + DataNode.schema
    ↓
Socket.IO broadcast → Другие клиенты видят новый узел
```

### Компоненты

#### 1. AIDataGenerator ([ai_data_generator.py](../apps/backend/app/services/ai_data_generator.py))

**Ответственность:**
- Формирование промпта для GigaChat
- Парсинг JSON ответа
- Type inference
- Валидация структуры данных

**Ключевые методы:**
```python
async def generate_data_from_prompt(
    user_prompt: str,
    min_rows: int = 20,
    max_rows: int = 100
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Генерирует данные из промпта.
    
    Returns:
        (data, metadata)
    """
```

**System Prompt:**
```
Ты — генератор синтетических данных для GigaBoard.

Задача:
1. Понять запрос пользователя
2. Сгенерировать реалистичные данные в формате JSON
3. Формат: [{"column1": value1, ...}, ...]

Требования:
- Только валидный JSON (без markdown)
- Названия колонок на английском (snake_case)
- 20-100 записей
- Разнообразные типы: числа, строки, даты, булевы значения
```

#### 2. DataNodeService Extension

**Новый метод:**
```python
async def generate_data_from_ai(
    db: AsyncSession,
    board_id: UUID,
    user_id: UUID,
    name: str,
    prompt: str,
    x: float = 0,
    y: float = 0,
    description: str = None
) -> DataNode:
    """Создать DataNode с AI-генерированными данными."""
```

**Что делает:**
1. Вызывает `AIDataGenerator.generate_data_from_prompt()`
2. Создаёт `DataNodeText` с:
   - `data_source_type = 'ai_generated'`
   - `text_content = prompt` (сохраняем промпт)
   - `data = {"rows": [...]}` (сгенерированные данные)
   - `schema = {"columns": [...], "column_types": {...}}`
3. Сохраняет в БД
4. Возвращает DataNode

#### 3. API Endpoint

```python
POST /api/v1/boards/{board_id}/data-nodes/generate-ai
```

**Query Parameters:**
```typescript
{
  name: string         // Название DataNode
  prompt: string       // Текстовый промпт
  x?: float           // Позиция X (опционально)
  y?: float           // Позиция Y (опционально)
  description?: string // Описание (опционально)
}
```

**Response:**
```typescript
DataNodeResponse {
  id: string
  name: string
  data_source_type: "ai_generated"
  data: {
    rows: Array<Record<string, any>>
  }
  schema: {
    columns: string[]
    column_types: Record<string, string>
  }
  ...
}
```

#### 4. Frontend UI

**CreateDataNodeDialog Updates:**

1. **Новая кнопка "Сгенерировать данные через AI"**
   - Градиентный фон (primary/5 to purple-500/5)
   - Иконка Sparkles ✨
   - Анимация при генерации
   - Disabled если поля пустые

2. **Метод handleGenerateAI():**
```typescript
const handleGenerateAI = async () => {
    // Валидация
    if (!name.trim() || !textContent.trim()) {
        notify.error('Заполните поля')
        return
    }
    
    // Вычисление позиции
    const { x, y } = findFreePosition(...)
    
    // API call
    await apiClient.post('/api/v1/boards/.../generate-ai', null, {
        params: { name, prompt, x, y, description }
    })
    
    // Refresh board
    await fetchDataNodes(boardId)
    
    // Close dialog
    handleClose()
}
```

3. **UX Flow:**
```
User вводит название → "Sales Data"
User вводит промпт → "Сгенерируй данные о продажах"
User кликает "Сгенерировать" ✨
  ↓ Loading state (кнопка: "Генерация данных...")
  ↓ AI генерирует (3-5 секунд)
  ↓ Success notification
  ↓ DataNode появляется на canvas
  ↓ Dialog закрывается
```

---

## 📊 Примеры промптов и результатов

### Пример 1: Данные о продажах

**Промпт:**
```
Сгенерируй данные о продажах за последние 30 дней
```

**Результат:**
```json
[
  {
    "date": "2026-01-01",
    "product": "Widget A",
    "quantity": 15,
    "revenue": 1499.50,
    "region": "North",
    "sales_rep": "John Doe"
  },
  {
    "date": "2026-01-02",
    "product": "Widget B",
    "quantity": 8,
    "revenue": 799.20,
    "region": "South",
    "sales_rep": "Jane Smith"
  },
  ...30 rows total
]
```

**Schema:**
```json
{
  "columns": ["date", "product", "quantity", "revenue", "region", "sales_rep"],
  "column_types": {
    "date": "date",
    "product": "string",
    "quantity": "integer",
    "revenue": "float",
    "region": "string",
    "sales_rep": "string"
  }
}
```

### Пример 2: Пользователи

**Промпт:**
```
Создай данные о пользователях платформы с их активностью
```

**Результат:**
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "age": 28,
    "is_active": true,
    "registered_at": "2025-06-15",
    "last_login": "2026-01-27 14:30:00",
    "total_sessions": 45
  },
  ...
]
```

### Пример 3: Веб-аналитика

**Промпт:**
```
Сгенерируй данные веб-аналитики для интернет-магазина
```

**Результат:**
```json
[
  {
    "date": "2026-01-20",
    "page_views": 1523,
    "unique_visitors": 847,
    "bounce_rate": 42.5,
    "avg_session_duration": "00:03:45",
    "conversion_rate": 3.2,
    "revenue": 4567.89
  },
  ...
]
```

---

## 🎨 Возможные визуализации

После создания DataNode с AI-генерированными данными, пользователь может:

### 1. Линейный график продаж
```
DataNode (Sales Data)
    ↓ ПКМ → "Создать визуализацию"
    ↓ AI Assistant: "Какую визуализацию создать?"
    ↓ User: "График продаж по дням"
    ↓ Reporter Agent генерирует:
        - Line chart (D3.js или Chart.js)
        - Ось X: date
        - Ось Y: revenue
        - Цвета по region
```

### 2. Гистограмма по продуктам
```
User: "Столбчатая диаграмма продаж по продуктам"
    ↓ Reporter Agent:
        - Bar chart
        - Группировка по product
        - SUM(revenue)
        - Сортировка по убыванию
```

### 3. Таблица с метриками
```
User: "Таблица с топ-10 продуктов"
    ↓ Reporter Agent:
        - Table widget
        - Фильтр: TOP 10 by revenue
        - Колонки: product, quantity, revenue
        - Форматирование: валюта для revenue
```

---

## 🔧 Технические детали

### Type Inference

Система автоматически определяет типы колонок:

```python
def _infer_column_types(data, columns):
    for col in columns:
        sample_value = find_first_non_empty(data[:10], col)
        
        if isinstance(sample_value, bool):
            return "boolean"
        elif isinstance(sample_value, int):
            return "integer"
        elif isinstance(sample_value, float):
            return "float"
        elif _looks_like_date(sample_value):
            return "date"
        else:
            return "string"
```

### JSON Cleaning

AI может вернуть ответ с markdown блоками:

```python
def _clean_json_response(response: str) -> str:
    # Удаляем ```json ... ```
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        response = response[start:end]
    
    # Ищем начало JSON массива
    if not response.startswith("["):
        bracket_index = response.find("[")
        if bracket_index != -1:
            response = response[bracket_index:]
    
    return response.strip()
```

### Валидация

```python
# Проверка структуры
if not isinstance(data, list):
    raise Exception("AI должен вернуть массив")

if len(data) == 0:
    raise Exception("Пустой массив")

if not all(isinstance(item, dict) for item in data):
    raise Exception("Все элементы должны быть объектами")

# Ограничение размера
if len(data) > max_rows:
    data = data[:max_rows]
```

---

## 🚀 Тестирование

### Сценарий тестирования:

1. **Запустить приложение**
```powershell
.\run-backend.ps1  # Terminal 1
.\run-frontend.ps1 # Terminal 2
```

2. **Создать DataNode**
   - Открыть доску
   - "Создать DataNode"
   - Тип: "Текст / Промпт"
   - Название: "Test Sales"
   - Промпт: "Сгенерируй данные о продажах"
   - Кликнуть "Сгенерировать данные через AI" ✨

3. **Проверить результат**
   - DataNode появился на canvas
   - ПКМ → "Просмотр данных"
   - Видна таблица с данными
   - Schema показывает колонки и типы

4. **Проверить интеграцию**
   - ПКМ → "Создать визуализацию"
   - AI должен видеть данные в контексте
   - Создать график

---

## 📈 Преимущества

✅ **Быстрое прототипирование** - данные за 5 секунд  
✅ **Реалистичные данные** - AI генерирует разнообразные значения  
✅ **Типизация** - автоматическое определение типов колонок  
✅ **Интеграция** - работает со всеми другими фичами (preview, visualizations)  
✅ **Гибкость** - любой промпт на естественном языке

---

## 🎯 Следующие шаги

### Улучшения (Future):

1. **Параметры генерации**
   - Настройка количества строк (UI slider)
   - Выбор языка данных (русский/английский)
   - Seed для воспроизводимости

2. **Кэширование промптов**
   - Сохранять популярные промпты
   - Template gallery: "Sales", "Users", "Analytics"

3. **Инкрементальная генерация**
   - "Добавить ещё 100 строк"
   - "Продлить период на следующий месяц"

4. **Связанные данные**
   - Генерация нескольких связанных таблиц
   - Foreign keys между DataNode

---

## 📚 Связанные документы

- [AI_ASSISTANT.md](AI_ASSISTANT.md) - Общая документация AI системы
- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - Multi-Agent архитектура
- [DATA_NODE_SYSTEM.md](DATA_NODE_SYSTEM.md) - DataNode система
- [PRIORITY_1_COMPLETED.md](history/PRIORITY_1_COMPLETED.md) - DataNode preview

---

**Автор**: GitHub Copilot  
**Дата**: 2026-01-27  
**Статус**: ✅ IMPLEMENTED & TESTED
