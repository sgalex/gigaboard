# Data-Centric Canvas: Система узлов и трансформаций

## Обзор концепции

GigaBoard построен на парадигме **Data-Centric Canvas** — вместо размещения виджетов на канвасе, система работает с **узлами данных** и их **трансформациями**. Это выводит продукт за рамки чистой визуализации к **инструменту создания и автоматизации data pipelines** с AI-ассистентом.

### Ключевая идея

**Данные первичны, визуализация вторична.** Каждый объект на канвасе либо содержит данные (DataNode), либо визуализирует их (WidgetNode), либо аннотирует (CommentNode). Связи между узлами описывают трансформации, зависимости и отношения.

#### Правила создания узлов

- Самостоятельно создаётся только **DataNode** (загрузка файла, API, SQL, трансформация и т.п.).
- **WidgetNode** является производным от DataNode: его создание всегда требует указания `parent_data_node` (VISUALIZATION edge). WidgetNode не может существовать без связанного DataNode.
- **CommentNode** также производен от данных: он всегда привязан к целевому узлу, который должен быть **либо DataNode**, **либо WidgetNode**, связанный с DataNode (`target_node`). CommentNode не создаётся «в воздухе».
- Удаление родительского **DataNode** приводит к каскадному удалению/деактивации всех связанных **WidgetNode** и **CommentNode** на доске.

## Типы узлов на канвасе

### 1. DataNode (узел данных)

**Назначение**: Хранение и представление любого контента, подлежащего обработке.

**Типы контента**:
- Файлы (CSV, JSON, Excel, PDF, изображения)
- Таблицы из БД (результаты SQL запросов)
- API responses (REST, GraphQL)
- Результаты вычислений (Python, JS)
- Текстовые данные (логи, документы)
- Бинарные данные (изображения, видео)
- Stream данные (real-time feeds)

**Метаданные DataNode**:
```json
{
  "id": "uuid",
  "type": "data_node",
  "content_type": "csv|json|table|api_response|file|binary|text",
  "content": "raw content or reference to storage",
  "schema": {
    "columns": ["name", "age", "city"],
    "types": ["string", "integer", "string"]
  },
  "statistics": {
    "row_count": 1000,
    "size_bytes": 45000,
    "last_updated": "2026-01-24T10:30:00Z"
  },
  "sample": "first 10 rows or preview",
  "source": {
    "type": "file_upload|api|transformation|database",
    "details": "connection string or file path"
  },
  "position": {"x": 100, "y": 200},
  "created_by": "user_id or agent_id",
  "created_at": "2026-01-24T10:30:00Z"
}
```

**Операции с DataNode**:
- **Upload**: пользователь загружает файл → создается DataNode
- **API fetch**: агент получает данные из API → создается DataNode
- **Database query**: выполнение SQL → результат в DataNode
- **Transformation**: один или несколько DataNode → новый DataNode через код
- **Visualization**: DataNode → WidgetNode через генерацию HTML/CSS/JS

### 2. WidgetNode (узел визуализации)

**Назначение**: Визуализация DataNode с помощью HTML/CSS/JS кода.

**Характеристики**:
- Создается **Reporter Agent** на основе анализа DataNode
- Содержит сгенерированный HTML/CSS/JS код
- Связан с родительским DataNode через edge типа VISUALIZATION
- Множественные WidgetNode могут визуализировать один DataNode (график, таблица, метрика)

**Метаданные WidgetNode**:
```json
{
  "id": "uuid",
  "type": "widget_node",
  "description": "Line chart showing revenue over time",
  "html_code": "<div>...</div>",
  "css_code": "...",
  "js_code": "...",
  "config": {
    "chart_type": "line",
    "x_axis": "date",
    "y_axis": "revenue"
  },
  "parent_data_node": "data_node_id",
  "position": {"x": 400, "y": 200},
  "size": {"width": 600, "height": 400},
  "generated_by": "reporter_agent",
  "created_at": "2026-01-24T10:35:00Z"
}
```

**Типы виджетов**:
- **Metric**: KPI с трендом
- **Chart**: линейные, столбчатые, круговые диаграммы
- **Table**: сортируемые таблицы с фильтрацией
- **Heatmap**: 2D матрицы для корреляций
- **Gauge**: индикаторы прогресса
- **Custom HTML**: произвольный код пользователя

### 3. CommentNode (узел комментария)

**Назначение**: Аннотации, заметки, инсайты пользователей или AI.

**Характеристики**:
- Текстовые комментарии пользователя
- AI-сгенерированные инсайты (аномалии, паттерны, рекомендации)
- Привязаны к DataNode или WidgetNode через edge типа COMMENT

**Метаданные CommentNode**:
```json
{
  "id": "uuid",
  "type": "comment_node",
  "text": "This data shows anomaly on 2026-01-15",
  "author": "user_id or analyst_agent",
  "target_node": "data_node_id or widget_node_id",
  "position": {"x": 700, "y": 300},
  "created_at": "2026-01-24T10:40:00Z"
}
```

## Типы связей (Edges)

Связи определяют отношения между узлами и поведение данных на канвасе.

### 1. TRANSFORMATION (трансформация данных)

**Назначение**: DataNode → DataNode через выполнение произвольного Python кода.

**Характеристики**:
- **Множественные источники**: может принимать 1+ source DataNode
- **Единственная цель**: создает 1 target DataNode
- **Произвольный код**: Python код генерируется Transformation Agent
- **Автоматизация**: может автоматически переиспользоваться при обновлении source

**Метаданные TRANSFORMATION edge**:
```json
{
  "id": "uuid",
  "type": "TRANSFORMATION",
  "source_nodes": ["data_node_123", "data_node_456"],
  "target_node": "data_node_789",
  "transformation_id": "transformation_uuid",
  "created_at": "2026-01-24T10:30:00Z"
}
```

**Метаданные трансформации**:
```json
{
  "transformation_id": "uuid",
  "prompt": "Join orders with customers by customer_id and calculate total revenue",
  "generated_code": "def transform_data(orders, customers):\n    import pandas as pd\n    ...",
  "source_nodes": ["data_node_123", "data_node_456"],
  "target_node": "data_node_789",
  "input_mapping": {
    "data_node_123": "orders",
    "data_node_456": "customers"
  },
  "execution_metadata": {
    "status": "success",
    "duration_ms": 2340,
    "memory_mb": 85,
    "executed_at": "2026-01-24T10:30:15Z"
  },
  "replay_enabled": true,
  "schedule": null,
  "version": 1,
  "created_by": "transformation_agent",
  "created_at": "2026-01-24T10:30:00Z"
}
```

**Примеры трансформаций**:

```python
# Пример 1: Фильтрация данных
def transform_data(source_data):
    import pandas as pd
    df = pd.read_csv(source_data)
    filtered = df[df['price'] > 1000]
    return filtered.to_csv(index=False)

# Пример 2: Join двух таблиц
def transform_data(orders, customers):
    import pandas as pd
    orders_df = pd.read_csv(orders)
    customers_df = pd.read_csv(customers)
    result = orders_df.merge(customers_df, on='customer_id')
    return result.to_csv(index=False)

# Пример 3: ML предсказание
def transform_data(historical_data):
    import pandas as pd
    from sklearn.ensemble import RandomForestRegressor
    
    df = pd.read_csv(historical_data)
    X = df[['feature1', 'feature2', 'feature3']]
    y = df['target']
    
    model = RandomForestRegressor()
    model.fit(X, y)
    
    predictions = model.predict(X)
    df['predictions'] = predictions
    
    return df.to_csv(index=False)

# Пример 4: Web scraping
def transform_data():
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    
    response = requests.get('https://example.com/data')
    soup = BeautifulSoup(response.content, 'html.parser')
    
    data = []
    for row in soup.find_all('tr'):
        cols = [td.text for td in row.find_all('td')]
        data.append(cols)
    
    df = pd.DataFrame(data, columns=['col1', 'col2', 'col3'])
    return df.to_csv(index=False)
```

### 2. VISUALIZATION (визуализация данных)

**Назначение**: DataNode → WidgetNode

**Характеристики**:
- Один DataNode может иметь множественные визуализации
- Reporter Agent анализирует схему и контент DataNode
- Генерирует оптимальный HTML/CSS/JS код для визуализации

### 3. COMMENT (комментирование)

**Назначение**: CommentNode → DataNode/WidgetNode

**Характеристики**:
- Пользовательские аннотации
- AI-сгенерированные инсайты

### 4. REFERENCE (ссылка)

**Назначение**: Справочная информация или зависимость

### 5. DRILL_DOWN (детализация)

**Назначение**: Переход от сводных данных к детальным

## Процесс работы с трансформациями

### 1. Создание трансформации

**Входные данные**:
- Source DataNode(s): один или несколько узлов с данными
- Transformation Intent: текстовое описание задачи от пользователя или другого агента

**Пример запроса**:
```
Пользователь: "Отфильтруй продажи где сумма > 10000, сгруппируй по категориям и посчитай среднее"
```

**Процесс**:
1. **Transformation Agent** получает запрос
2. Анализирует source DataNode:
   - Тип контента (CSV, JSON, database table)
   - Схему данных (колонки, типы)
   - Размер данных
   - Примеры (sample)
3. Генерирует Python код для трансформации:
```python
def transform_data(sales_data):
    import pandas as pd
    
    # Load data
    df = pd.read_csv(sales_data)
    
    # Filter
    filtered = df[df['amount'] > 10000]
    
    # Group and aggregate
    result = filtered.groupby('category')['amount'].mean().reset_index()
    result.columns = ['category', 'average_amount']
    
    return result.to_csv(index=False)
```
4. Валидирует код (линтинг, security check)
5. Выполняет в sandbox с resource limits (timeout, memory)
6. Создает target DataNode с результатом
7. Создает TRANSFORMATION edge: source → target
8. Сохраняет код трансформации и метаданные

### 2. Автоматизация (replay трансформаций)

**Сценарий**: Source DataNode обновляется (новые данные)

**Процесс**:
1. Система детектирует изменение source DataNode
2. Находит все downstream трансформации
3. Предлагает пользователю или автоматически запускает replay:
   - Re-execute transformation с новыми данными
   - Update target DataNode
   - Update все downstream WidgetNode
4. Отправляет real-time события через Socket.IO

**Триггеры replay**:
- **Manual**: пользователь нажал "Re-run"
- **On source update**: автоматически при изменении source DataNode
- **Scheduled**: по расписанию (cron)
- **On demand**: через API/webhook

### 3. Граф зависимостей (Data Lineage)

**Визуализация потока данных**:
```
API Data → Clean → Filter → Aggregate → Prediction
(DataNode)   (Trans1) (Trans2)  (Trans3)    (DataNode)
                                                 ↓
                                           Visualization
                                           (WidgetNode)
```

**Возможности**:
- Отслеживание происхождения данных
- Понимание влияния изменений
- Откат к предыдущим версиям
- Аудит трансформаций

### 4. Версионирование

**При изменении трансформации**:
- Создается новая версия кода
- Старая версия сохраняется в истории
- Можно откатиться к предыдущей версии
- Сравнение результатов между версиями

## Примеры использования

### Пример 1: Простой data pipeline

**Задача**: Загрузить данные о продажах, отфильтровать по региону, визуализировать

**Шаги**:
1. Пользователь загружает sales.csv → **DataNode #1**
2. Говорит AI: "Отфильтруй продажи по региону 'Europe'"
3. **Transformation Agent**:
   - Анализирует DataNode #1 (CSV с колонками: id, amount, region, date)
   - Генерирует код фильтрации
   - Выполняет → создает **DataNode #2**
   - Создает edge TRANSFORMATION (#1 → #2)
4. Говорит AI: "Визуализируй как график по датам"
5. **Reporter Agent**:
   - Анализирует DataNode #2
   - Генерирует HTML/CSS/JS код линейного графика
   - Создает **WidgetNode #1**
   - Создает edge VISUALIZATION (#2 → WidgetNode #1)

**Результат на канвасе**:
```
[DataNode #1: sales.csv] 
      ↓ TRANSFORMATION (filter region='Europe')
[DataNode #2: filtered_sales]
      ↓ VISUALIZATION
[WidgetNode #1: Line Chart]
```

### Пример 2: Многовходовая трансформация

**Задача**: Объединить данные заказов и клиентов, вычислить lifetime value

**Шаги**:
1. **DataNode #1**: orders.csv (order_id, customer_id, amount, date)
2. **DataNode #2**: customers.json (customer_id, name, email, registration_date)
3. Пользователь: "Join orders with customers and calculate lifetime value per customer"
4. **Transformation Agent**:
   - Анализирует оба DataNode
   - Генерирует код join + aggregation:
```python
def transform_data(orders, customers):
    import pandas as pd
    
    orders_df = pd.read_csv(orders)
    customers_df = pd.read_json(customers)
    
    # Join
    merged = orders_df.merge(customers_df, on='customer_id')
    
    # Calculate LTV
    ltv = merged.groupby(['customer_id', 'name', 'email'])['amount'].sum().reset_index()
    ltv.columns = ['customer_id', 'name', 'email', 'lifetime_value']
    ltv = ltv.sort_values('lifetime_value', ascending=False)
    
    return ltv.to_csv(index=False)
```
   - Выполняет → **DataNode #3** (customer LTV)
   - Создает edges TRANSFORMATION (#1, #2 → #3)

**Результат**:
```
[DataNode #1: orders] ──┐
                        │ TRANSFORMATION (join + LTV)
[DataNode #2: customers]──┘
                        ↓
          [DataNode #3: customer_ltv]
                        ↓ VISUALIZATION
              [WidgetNode: Table]
```

### Пример 3: Pipeline с ML

**Задача**: Построить модель предсказания оттока клиентов

**Шаги**:
1. **DataNode #1**: customer_features.csv
2. **Transformation #1**: "Clean data, handle missing values"
   - → **DataNode #2**: cleaned_features
3. **Transformation #2**: "Split into train/test"
   - → **DataNode #3**: train_data
   - → **DataNode #4**: test_data
4. **Transformation #3**: "Train RandomForest model on train_data"
   - → **DataNode #5**: trained_model (pickle)
5. **Transformation #4**: "Predict on test_data using trained_model"
   - Input: DataNode #4 + DataNode #5
   - → **DataNode #6**: predictions
6. **Visualization**: "Show confusion matrix"
   - → **WidgetNode #1**: Heatmap

**Граф**:
```
[DataNode #1: raw] → [Trans1: clean] → [DataNode #2: cleaned]
                                              ↓
                              [Trans2: split] ──┬── [DataNode #3: train]
                                                │        ↓
                                                │   [Trans3: train model]
                                                │        ↓
                                                │   [DataNode #5: model]
                                                │        ↓
                                                └── [DataNode #4: test] → [Trans4: predict] → [DataNode #6: predictions]
                                                                                                       ↓
                                                                                                [WidgetNode: Confusion Matrix]
```

## Преимущества концепции

### 1. Воспроизводимость
- Весь код трансформаций сохранен
- Можно replay на новых данных
- Версионирование кода

### 2. Прозрачность
- Граф зависимостей показывает откуда данные
- Понятно какие трансформации применялись
- Audit trail для compliance

### 3. Автоматизация
- Автоматический replay при обновлении источников
- Scheduled execution
- Webhook triggers

### 4. Гибкость
- Произвольный Python код
- Не ограничены шаблонными операциями
- Можно делать что угодно: ML, web scraping, API calls

### 5. Переиспользование
- Успешные трансформации можно сохранить как шаблоны
- Применить к похожим данным
- Библиотека трансформаций

### 6. Коллаборация
- Real-time синхронизация изменений
- Множественные пользователи на одной доске
- AI агенты работают совместно с пользователями

## Технические детали

### Безопасность выполнения кода

**Sandbox с ограничениями**:
- Timeout execution (max 60 seconds)
- Memory limit (max 512 MB)
- Disk limit (max 100 MB)
- Network restrictions (whitelist URLs only)
- No file system write access
- No subprocess execution

**Валидация кода**:
- Syntax check (Python AST parsing)
- Security scan (no eval, exec, __import__)
- Linting (flake8, pylint)
- Dependency check (only allowed packages)

### Масштабируемость

**Для больших данных**:
- Chunked processing (не загружать все в память)
- Streaming transformations
- Distributed execution (Spark, Dask)
- Caching intermediate results

**Для множественных трансформаций**:
- Task queue (Celery, RQ)
- Parallel execution
- Priority scheduling
- Resource allocation

### Мониторинг

**Метрики**:
- Execution time
- Memory usage
- Success/failure rate
- Data quality metrics

**Логирование**:
- Code executed
- Input/output sizes
- Errors and exceptions
- Performance bottlenecks

---

**Статус**: Draft  
**Версия**: 1.0  
**Последнее обновление**: 2026-01-24
