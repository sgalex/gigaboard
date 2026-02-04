# Manual Data Source Selection - Feature Addition

**Дата**: 23 января 2026 | **Тип**: Feature Addition to Dynamic Form Generation

---

## 🎯 Обзор

Система **Dynamic Form Generation** теперь поддерживает **ручной ввод источников данных** помимо автоматического сканирования. Это позволяет пользователям явно указывать, где находятся их данные, если они уже это знают.

---

## 📊 Два режима работы

### Режим 1: АВТОПОИСК (Auto-detect) ✨
Система автоматически:
- 🔍 Сканирует доступные источники (БД, файлы, облако)
- 🧠 Анализирует превью и предлагает опции
- ✅ Пользователь выбирает из найденных

**Когда использовать**: 
- Пользователь не знает где его данные
- Быстрый анализ, minimal friction
- "Проанализируй продажи"

### Режим 2: РУЧНОЙ ВВОД (Manual) 🎛️
Пользователь явно указывает:
- 📝 Тип БД (PostgreSQL, MySQL, MongoDB, CSV, Excel, Google Sheets)
- 🔗 Параметры подключения (host, port, database, credentials)
- 📋 Имя таблицы/файла
- Система валидирует и загружает данные

**Когда использовать**:
- Пользователь точно знает где его данные
- Специфичное подключение (нестандартный порт, VPN, custom schema)
- "Подключись к таблице sales на db.company.com"

---

## 🔄 How It Works

### Step 1: Intent Analysis

```python
# Система анализирует сообщение пользователя
message = "Используй таблицу 'sales' из PostgreSQL на хосте db.company.com"

# Intent Analyzer определяет:
{
    'mode': 'manual',  # Явное указание источника
    'confidence': 0.85,
    'source_hints': {
        'database_type': 'postgresql',
        'host': 'db.company.com',
        'table_name': 'sales'
    }
}

# Если source_hints заполнены → Ручной режим
# Если нет намёков → Автопоиск
```

### Step 2: Form Generation

#### Auto-detect Mode
```
AI анализирует намерение
   ↓
Data Source Scanner находит источники (БД, файлы, API)
   ↓
Генерируется форма с найденными опциями
   ↓
Форма со списком источников
```

#### Manual Mode
```
User указывает источник
   ↓
Intent Analyzer распознаёт указание
   ↓
Генерируется форма с полями ввода:
  - Database Type selector
  - Connection parameters (host, port, DB, user, pass)
  - Table/file selector
  - Advanced options
   ↓
Форма с input fields для ввода деталей
```

### Step 3: Validation & Testing

```python
# Для Manual Mode - проверка подключения:

async def validate_connection(config):
    """
    1. Проверяет доступность хоста
    2. Проверяет учётные данные
    3. Проверяет существование таблицы
    4. Загружает preview данных (100 строк)
    5. Анализирует schema (типы колонок)
    """
    
    # Connection attempt
    try:
        conn = await connect(config)
    except ConnectionRefusedError:
        return {'error': 'Хост недоступен', 'suggestion': 'Проверь host и port'}
    except AuthenticationError:
        return {'error': 'Неверные учётные данные', 'suggestion': 'Проверь username/password'}
    except Exception as e:
        return {'error': str(e), 'suggestion': '...'}
    
    # Get tables
    tables = await conn.get_table_list()
    
    # Validate table exists
    if config.table not in tables:
        return {'error': f'Таблица не найдена. Доступны: {tables[:10]}'}
    
    # Load preview
    preview = await conn.execute(f"SELECT * FROM {config.table} LIMIT 100")
    
    return {
        'valid': True,
        'preview': preview,
        'schema': {...},
        'row_count': 1500000
    }
```

---

## 📋 Form Schemas

### Manual Mode: PostgreSQL/MySQL Form

```json
{
  "form_id": "manual-sql-source",
  "type": "manual_data_source",
  "title": "Подключение к базе данных",
  
  "fields": [
    {
      "id": "database_type",
      "type": "select",
      "label": "Тип БД",
      "options": [
        {"value": "postgresql", "label": "PostgreSQL"},
        {"value": "mysql", "label": "MySQL"},
        {"value": "mongodb", "label": "MongoDB"},
        {"value": "csv", "label": "CSV файл"},
        {"value": "excel", "label": "Excel файл"}
      ],
      "pre_filled": "postgresql"  // Если распознано из intent
    },
    
    {
      "id": "connection_section",
      "type": "conditional",
      "condition": "database_type IN ['postgresql', 'mysql']",
      "fields": [
        {"id": "host", "type": "text", "label": "Хост", "pre_filled": "db.company.com"},
        {"id": "port", "type": "number", "label": "Порт", "default": 5432},
        {"id": "database_name", "type": "text", "label": "БД", "pre_filled": "analytics"},
        {"id": "username", "type": "text", "label": "Юзер", "required": true},
        {"id": "password", "type": "password", "label": "Пароль", "required": true},
        {"id": "schema", "type": "text", "label": "Schema", "default": "public"}
      ]
    },
    
    {
      "id": "table_section",
      "type": "conditional",
      "condition": "host && database_name",
      "fields": [
        {
          "id": "table_name",
          "type": "smart_select",
          "label": "Таблица",
          "load_from": "connected_database",  // Dynamically load list
          "pre_filled": "sales"
        }
      ]
    }
  ],
  
  "actions": [
    {
      "type": "validate",
      "label": "Проверить подключение",
      "endpoint": "/api/v1/ai/validate-source",
      "loading_text": "Проверяю подключение..."
    },
    {
      "type": "submit",
      "label": "Загрузить данные",
      "disabled_until": "connection_validated"
    }
  ]
}
```

### Manual Mode: File Upload Form

```json
{
  "fields": [
    {
      "id": "file_section",
      "type": "conditional",
      "condition": "database_type IN ['csv', 'excel']",
      "fields": [
        {
          "id": "file_upload",
          "type": "file",
          "label": "Загрузить файл",
          "accept": "{{database_type === 'csv' ? '.csv' : '.xlsx,.xls'}}",
          "help": "Максимум 100MB"
        },
        {
          "id": "sheet_name",
          "type": "text",
          "label": "Лист (для Excel)",
          "conditional_show": "database_type === 'excel'"
        }
      ]
    }
  ]
}
```

---

## 💬 Example Dialogues

### Example 1: User doesn't know where data is

```
User: "Проанализируй продажи за 2025"

System:
  - Intent: 'auto'  (No explicit source mentioned)
  - Scans local files, databases, cloud storage
  
AI: "Нашёл данные о продажах в 4 местах!
    
    ┌─────────────────────────────────┐
    │ ● Google Drive (свежий!)        │
    │   Sales_2025.xlsx               │
    │                                 │
    │ ○ PostgreSQL: table 'sales'     │
    │                                 │
    │ ○ CSV файлы в ~/Downloads       │
    │                                 │
    │ ○ Shopify API                   │
    │                                 │
    │ [Выбрать] [Все сразу]           │
    └─────────────────────────────────┘"

User: [Clicks "Google Drive"]
   → Spinner: "Загружаю данные..."
   → Data loaded and analyzed
```

### Example 2: User knows exactly where data is

```
User: "Подключись к PostgreSQL на db.company.com.
       БД: analytics, таблица: sales_daily.
       Нужна выручка за последние 3 месяца"

System:
  - Intent: 'manual' (confidence 0.92)
  - Detected: postgresql, db.company.com, analytics, sales_daily
  - Pre-fills form with these values

AI: "Подключаюсь к PostgreSQL.
    
    ┌──────────────────────────────┐
    │ БД тип: ● PostgreSQL         │
    ├──────────────────────────────┤
    │ Хост: [db.company.com    ]   │ ✓ Pre-filled
    │ Порт: [5432             ]    │
    │ БД:   [analytics        ]    │ ✓ Pre-filled
    │ Юзер: [_________________ ]   │
    │ Пароль: [______________ ]    │
    │ Таблица: [sales_daily   ]    │ ✓ Pre-filled
    │                              │
    │ [Проверить] [Загрузить]      │
    └──────────────────────────────┘"

User: [Enters username/password]
   → [Clicks "Проверить подключение"]
   → Spinner: "Проверяю подключение..."
   → ✓ "Успешно! Найдено 5.2M строк в sales_daily"
   → [Clicks "Загрузить"]
   → Spinner: "Загружаю и анализирую..."
   → Done! Board created with analysis

AI: "✨ Готово! 
    
    Добавил на доску:
    - Выручка по дням (3 месяца)
    - Среднее по дням недели
    - Топ-10 дней по продажам
    - Прогноз на следующую неделю
    
    💡 Интересное: вторник +35% выше среднего"
```

### Example 3: User provides partial info, system helps complete

```
User: "Анализируй данные из MySQL хоста 192.168.1.100"

System:
  - Intent: 'manual' (confidence 0.70)
  - Detected: mysql, host: 192.168.1.100
  - Missing: port, database, table, credentials

AI: "Получил! Подключаюсь к MySQL.
    
    Нужно ещё несколько деталей:
    
    ┌──────────────────────────────┐
    │ Хост: [192.168.1.100    ]    │ ✓ (detected)
    │ Порт: [3306            ]     │ (default)
    │ БД:   [____________     ]    │ ?
    │ Юзер: [____________     ]    │ ?
    │ Пароль: [__________ ]        │ ?
    │                              │
    │ [Проверить подключение]      │
    └──────────────────────────────┘"

User: [Fills in missing fields]
   → [Checks connection]
   → System returns list of available databases/tables
   
AI: "Найдено 5 БД: production, staging, analytics, test, backup
    
    Какую использовать?"

User: "analytics"

AI: "В 'analytics' найдено 15 таблиц.
    Какие анализируем?
    
    💡 Рекомендую: customers, orders, products"

User: "Используй orders"

AI: "Готово! Загружаю orders..." [spinner]
```

---

## 🔐 Security Considerations

### Never expose credentials in logs/UI

```python
# ❌ DANGEROUS
log.info(f"Connecting to {config['password']}")

# ✅ SAFE
log.info(f"Connecting to {config['host']}:{config['port']}")
config['password'] = '***'  # Mask in logs
```

### Validate & sanitize inputs

```python
# Check for SQL injection attempts
def validate_table_name(table_name: str) -> bool:
    # Only allow alphanumeric, underscore, dot
    if not re.match(r'^[\w.]+$', table_name):
        return False
    return True

# Whitelist allowed operations
ALLOWED_OPERATIONS = ['SELECT']  # Never allow ALTER, DROP, etc.
```

### Store credentials securely

```python
# ✅ Use environment variables or secure vaults
credentials = {
    'password': os.getenv('DB_PASSWORD')  # From secure vault
}

# NOT in config files!
```

---

## 🚀 Implementation Checklist

### Backend
- [ ] Intent Analyzer (auto vs manual detection)
- [ ] Manual Form Schema generator
- [ ] DataSourceValidator (test connections)
- [ ] API endpoint: POST /api/v1/ai/validate-source
- [ ] Support multiple DB types (PostgreSQL, MySQL, MongoDB, CSV, Excel, Google Sheets)
- [ ] Secure credential handling
- [ ] Table/collection list loading dynamically
- [ ] Preview data loading

### Frontend
- [ ] Manual Mode form component
- [ ] Conditional field rendering
- [ ] Database type selector with icons
- [ ] Connection validation button with spinner
- [ ] Error messages with suggestions
- [ ] Pre-filled values from intent analysis
- [ ] Smart field focus & tab order

### Testing
- [ ] Valid PostgreSQL connection
- [ ] Invalid credentials error
- [ ] Network timeout handling
- [ ] Table not found error
- [ ] Large file handling (CSV/Excel)
- [ ] Concurrent connections
- [ ] Timeout after 30 seconds

---

## 📈 User Experience Flow

```
┌─────────────────────────────────────────┐
│   User writes message to AI             │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│   Intent Analyzer                        │
│   Auto-detect or Manual?                │
└────────────┬────────────────────────────┘
             │
      ┌──────┴──────┐
      │             │
      ↓             ↓
   AUTO         MANUAL
   │             │
   ↓             ↓
 Scan &       Form with
 Suggest     Input Fields
   │             │
   ↓             ↓
 Show      Validate
 Options   Connection
   │             │
   ↓             ↓
 User      Load
 Selects   Preview
   │             │
   └──────┬──────┘
          ↓
    Load Data &
    Analyze
          ↓
    ✨ Done!
```

---

## ✅ Summary

**Dynamic Form Generation now supports:**
1. ✨ **Auto-detect mode**: System finds data for you
2. 🎛️ **Manual mode**: You tell system where data is
3. 🧠 **Smart pre-filling**: If you partially specify source
4. ✔️ **Validation**: System checks connection before loading
5. 🔍 **Preview**: Shows sample data before full analysis
6. 🔐 **Security**: Credentials never exposed, inputs validated

**When to use each:**
- Auto-detect: "Анализируй продажи" → Minimal friction
- Manual: "Подключись к PostgreSQL на db.company.com" → Full control
- Hybrid: "MySQL хоста 192.168.1.100" → System asks for missing pieces
