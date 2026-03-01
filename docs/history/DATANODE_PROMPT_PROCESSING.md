# 🔄 SourceNode Prompt Processing via Multi-Agent System

> **⚠️ LEGACY ДОКУМЕНТ**: Данный документ описывает устаревшую **DataNode** архитектуру.  
> 🆕 **См. Source-Content Node Architecture**: [NODE_MANAGEMENT_SYSTEM.md](./NODE_MANAGEMENT_SYSTEM.md)  
> 📝 Документ будет обновлён под новую архитектуру (SourceNode prompt-тип с извлечением в ContentNode) в ближайшее время.

**Дата**: 2026-01-27  
**Статус**: Архитектура утверждена, реализация в Priority 3

---

## 🎯 Концепция

При создании **текстового SourceNode** пользователь вводит естественный промпт, который сохраняется в поле `text_content`. После создания узла, **Multi-Agent система** автоматически анализирует промпт и выполняет соответствующие действия.

### Примеры промптов и их обработка:

| Промпт пользователя                                 | Агент                | Действие                                                |
| --------------------------------------------------- | -------------------- | ------------------------------------------------------- |
| "Сгенерируй данные о продажах за последние 30 дней" | Developer Agent      | Генерирует синтетические данные с помощью AI (GigaChat) |
| "Найди публичные данные о населении городов России" | Data Discovery Agent | Ищет датасеты на Kaggle, Росстат, World Bank            |
| "Собери статистику по GitHub репозиторию GigaBoard" | Researcher Agent     | Использует GitHub API для сбора данных                  |
| "Загрузи курсы валют за последний месяц"            | Researcher Agent     | Парсит данные с ЦБ РФ или других источников             |
| "Объедини данные из узлов Sales и Customers"        | Transformation Agent | Создаёт трансформацию с JOIN операцией                  |

---

## 🏗️ Архитектура

### Текущая реализация (Jan 27, 2026)

```typescript
// Frontend: CreateSourceNodeDialog.tsx
case 'text':
    sourceNodeType = 'text'
    dataSourceType = DataSourceType.AI_GENERATED
    textContent_ = textContent
    data = {
        prompt: textContent,
        needs_multi_agent_processing: true,  // 🔴 Флаг для Multi-Agent системы
    }
    break
```

**Что происходит сейчас:**
1. Пользователь создаёт SourceNode с промптом
2. Узел сохраняется с флагом `needs_multi_agent_processing: true`
3. Узел отображается на canvas с промптом в `text_content`
4. ⚠️ **Multi-Agent обработка НЕ реализована** (Priority 3, срок: Feb 20)

---

## 🚀 Будущая реализация (Priority 3)

### Backend: Multi-Agent Orchestrator

```python
# apps/backend/app/services/multi_agent/orchestrator.py

class SourceNodePromptProcessor:
    """
    Обрабатывает промпты текстовых SourceNode через Multi-Agent систему.
    """
    
    def __init__(self):
        self.planner = PlannerAgent()
        self.developer = DeveloperAgent()
        self.researcher = ResearcherAgent()
        self.data_discovery = DataDiscoveryAgent()
        self.transformation = TransformationAgent()
    
    async def process_prompt(
        self, 
        source_node_id: UUID, 
        prompt: str,
        board_context: dict
    ) -> dict:
        """
        Анализирует промпт и делегирует задачу агентам.
        
        Workflow:
        1. Planner анализирует промпт и определяет тип задачи
        2. Делегирует задачу соответствующему агенту
        3. Агент выполняет задачу и возвращает данные
        4. Результат сохраняется в ContentNode.data
        5. Socket.IO broadcast обновления
        """
        
        # Шаг 1: Planner анализирует промпт
        analysis = await self.planner.analyze_prompt(prompt, board_context)
        
        task_type = analysis['task_type']  # 'generate', 'fetch', 'research', 'transform'
        
        # Шаг 2: Делегирование
        if task_type == 'generate':
            # Генерация синтетических данных
            result = await self.developer.generate_synthetic_data(prompt)
            
        elif task_type == 'fetch_public':
            # Поиск публичных датасетов
            result = await self.data_discovery.find_datasets(prompt)
            
        elif task_type == 'research':
            # Deep research: веб-скрапинг, API, агрегация
            result = await self.researcher.deep_research(prompt)
            
        elif task_type == 'transform':
            # Трансформация существующих данных
            result = await self.transformation.create_transformation(
                prompt, 
                board_context['source_nodes']
            )
        
        # Шаг 3: Сохранение результата
        await self.save_result_to_content_node(source_node_id, result)
        
        # Шаг 4: Broadcast через Socket.IO
        await self.broadcast_content_node_update(source_node_id)
        
        return result
```

### Интеграция с существующей системой

**Endpoint для запуска обработки:**

```python
# apps/backend/app/routes/source_nodes.py

@router.post(
    "/boards/{board_id}/source-nodes/{node_id}/process",
    response_model=SourceNodeResponse,
)
async def process_source_node_prompt(
    board_id: UUID,
    node_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Запускает Multi-Agent обработку промпта SourceNode.
    Работает асинхронно в фоновом режиме.
    """
    
    # Проверяем что SourceNode существует
    source_node = await db.get(SourceNode, node_id)
    if not source_node or not source_node.needs_multi_agent_processing:
        raise HTTPException(status_code=400, detail="Node not found or already processed")
    
    # Получаем контекст доски
    board_context = await get_board_context(db, board_id)
    
    # Запускаем обработку в фоне
    background_tasks.add_task(
        process_prompt_background,
        node_id=node_id,
        prompt=source_node.text_content,
        board_context=board_context
    )
    
    return source_node
```

### Frontend: Автоматический запуск обработки

```typescript
// apps/web/src/components/canvas/SourceNodeCard.tsx

export function SourceNodeCard({ node }: { node: SourceNode }) {
    const [isProcessing, setIsProcessing] = useState(false)
    
    useEffect(() => {
        // Автоматически запускаем обработку для новых нод с промптами
        if (node.data?.needs_multi_agent_processing && !isProcessing) {
            processPrompt()
        }
    }, [node])
    
    const processPrompt = async () => {
        setIsProcessing(true)
        
        try {
            // Запускаем Multi-Agent обработку
            await api.post(`/api/v1/boards/${boardId}/data-nodes/${node.id}/process`)
            
            notify.info('Multi-Agent система обрабатывает ваш запрос...')
        } catch (error) {
            notify.error('Ошибка обработки промпта')
        } finally {
            setIsProcessing(false)
        }
    }
    
    // UI показывает прогресс обработки
    if (isProcessing) {
        return <SourceNodeProcessingIndicator prompt={node.text_content} />
    }
    
    return <SourceNodeCardContent node={node} />
}
```

---

## 🎨 UX Flow

### Пользовательский опыт

```
1. User создаёт SourceNode → тип "Текст / Промпт"
   ↓
2. Вводит промпт: "Сгенерируй данные о продажах за последние 30 дней"
   ↓
3. Кликает "Создать источник"
   ↓
4. Узел появляется на canvas с индикатором обработки:
   
   ┌─────────────────────────────────────┐
   │ 🔄 Обработка промпта...             │
   │                                     │
   │ "Сгенерируй данные о продажах..."   │
   │                                     │
   │ 💬 Planner Agent анализирует...     │
   │ ⏳ Примерно 5-10 секунд             │
   └─────────────────────────────────────┘
   
   ↓ (5-10 секунд)
   
5. Socket.IO получает событие `content_node:processed`
   ↓
6. Узел обновляется с данными:
   
   ┌─────────────────────────────────────┐
   │ ✅ Sales Data (30 rows)             │
   │                                     │
   │ 📊 Preview:                         │
   │ date       | product    | revenue   │
   │ 2026-01-01 | Widget A   | 1499.50  │
   │ 2026-01-02 | Widget B   | 799.20   │
   │ ...                                  │
   │                                     │
   │ [Просмотр] [Визуализировать]        │
   └─────────────────────────────────────┘
```

---

## 🧪 Тестовые сценарии

### 1. Генерация синтетических данных

**Промпт:**
```
Сгенерируй данные о продажах онлайн-магазина за последние 90 дней
```

**Ожидаемый результат:**
- Developer Agent генерирует ~90 записей
- Колонки: date, order_id, product_name, quantity, price, total_amount, customer_id, region
- Реалистичные значения с трендами

### 2. Поиск публичных датасетов

**Промпт:**
```
Найди данные о населении городов России с 2010 по 2023 год
```

**Ожидаемый результат:**
- Data Discovery Agent ищет на Росстат, Kaggle, World Bank
- Предлагает несколько вариантов датасетов
- Пользователь выбирает нужный → данные загружаются

### 3. Deep Research

**Промпт:**
```
Собери статистику по Python библиотекам для data science: количество звёзд на GitHub, последний релиз, количество контрибьюторов
```

**Ожидаемый результат:**
- Researcher Agent использует GitHub API
- Собирает данные по pandas, numpy, scikit-learn, matplotlib и т.д.
- Возвращает таблицу с метриками

### 4. Трансформация данных

**Промпт:**
```
Объедини узлы "Sales 2023" и "Sales 2024" в один датасет и добавь колонку "year"
```

**Ожидаемый результат:**
- Transformation Agent создаёт Python трансформацию
- Код: `pd.concat([sales_2023, sales_2024], keys=['2023', '2024'])`
- Новый ContentNode с объединёнными данными

---

## 📊 Типы агентов и их задачи

| Агент              | Специализация                  | Примеры задач                                |
| ------------------ | ------------------------------ | -------------------------------------------- |
| **Planner**        | Анализ промпта, маршрутизация  | Определяет тип задачи и делегирует агенту    |
| **Developer**      | Генерация синтетических данных | "Сгенерируй фейковые данные о пользователях" |
| **Data Discovery** | Поиск публичных датасетов      | "Найди данные о погоде в Москве"             |
| **Researcher**     | Веб-скрапинг, API, агрегация   | "Собери цены на квартиры с Авито"            |
| **Transformation** | Обработка существующих данных  | "Объедини два датасета по ключу"             |
| **Reporter**       | Визуализация результатов       | Создаёт WidgetNode с графиками               |

---

## 🔐 Безопасность

### Sandbox для выполнения кода

Все агенты выполняют код в изолированном окружении:

```python
class CodeSandbox:
    """
    Песочница для безопасного выполнения Python кода.
    """
    
    def __init__(self):
        self.timeout = 30  # 30 секунд максимум
        self.max_memory = 512  # 512 MB
        self.allowed_imports = [
            'pandas', 'numpy', 'requests', 'json', 'datetime'
        ]
    
    async def execute(self, code: str) -> dict:
        """
        Выполняет код с ограничениями:
        - Timeout 30 секунд
        - Memory limit 512MB
        - Только разрешённые импорты
        - Нет доступа к файловой системе (кроме /tmp)
        - Нет сетевых запросов (кроме whitelist API)
        """
        # ... реализация ...
```

### Whitelist для внешних API

```python
ALLOWED_API_DOMAINS = [
    'api.github.com',
    'data.worldbank.org',
    'api.kaggle.com',
    'cbr.ru',  # ЦБ РФ
    'rosstat.gov.ru',
]
```

---

## 📈 Метрики и мониторинг

### Логирование обработки промптов

```python
class PromptProcessingLog(Base):
    __tablename__ = "prompt_processing_logs"
    
    id = Column(UUID, primary_key=True)
    source_node_id = Column(UUID, ForeignKey("source_nodes.id"))
    prompt = Column(Text)
    task_type = Column(String)  # 'generate', 'fetch', 'research', 'transform'
    agent_used = Column(String)  # 'developer', 'researcher', etc.
    execution_time_ms = Column(Integer)
    status = Column(String)  # 'success', 'error', 'timeout'
    error_message = Column(Text, nullable=True)
    result_size_bytes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Dashboard для администратора

- Количество обработанных промптов
- Средн время обработки
- Распределение по типам задач
- Ошибки и таймауты

---

## 🚧 Текущий статус

| Компонент                         | Статус                       | Срок         |
| --------------------------------- | ---------------------------- | ------------ |
| Backend Multi-Agent Orchestrator  | ❌ Не начато                  | Feb 20, 2026 |
| Planner Agent                     | ❌ Не начато                  | Feb 20, 2026 |
| Developer Agent (data generation) | ⚠️ Частично (AIDataGenerator) | Feb 20, 2026 |
| Data Discovery Agent              | ❌ Не начато                  | Feb 20, 2026 |
| Researcher Agent                  | ❌ Не начато                  | Feb 20, 2026 |
| Transformation Agent              | ❌ Не начато                  | Feb 20, 2026 |
| Frontend processing indicator     | ❌ Не начато                  | Feb 20, 2026 |
| Socket.IO events                  | ⚠️ Частично                   | Feb 20, 2026 |
| Code Sandbox                      | ❌ Не начато                  | Feb 20, 2026 |
| API Whitelist                     | ❌ Не начато                  | Feb 20, 2026 |

---

## 📚 Связанные документы

- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - полная спецификация Multi-Agent системы
- [INTEGRATION_MULTI_AGENT.md](INTEGRATION_MULTI_AGENT.md) - интеграция с GigaBoard
- [AI_DATA_GENERATION.md](AI_DATA_GENERATION.md) - историческая версия (AI generation кнопка)
- [DATA_NODE_SYSTEM.md](DATA_NODE_SYSTEM.md) - архитектура SourceNode/ContentNode

---

**Автор**: GitHub Copilot  
**Дата**: 2026-01-27  
**Статус**: 📝 АРХИТЕКТУРА УТВЕРЖДЕНА
