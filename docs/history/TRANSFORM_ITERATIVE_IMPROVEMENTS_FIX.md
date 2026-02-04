# Fix: TransformationAgent Iterative Improvements

**Дата**: 2024
**Статус**: ✅ Исправлено

## Проблема

TransformationAgent получал параметры `existing_code` и `chat_history` в task dict, но **НЕ использовал их** в промптах для GigaChat. В результате итеративные улучшения работали как генерация с нуля, игнорируя:

- Предыдущий код пользователя
- Контекст переписки
- Просьбы об улучшениях ("добавь фильтр", "исправь ошибку")

## Решение

### 1. Обновлён метод `_generate_transformation()`

```python
# apps/backend/app/services/multi_agent/agents/transformation.py

existing_code = task.get("existing_code")  # ✅ Извлекаем из task
chat_history = task.get("chat_history", [])  # ✅ Извлекаем из task

# Логируем для отладки
if existing_code:
    self.logger.info(f"🔁 Iterative mode: improving existing code ({len(existing_code)} chars)")
if chat_history:
    self.logger.info(f"💬 Chat history provided: {len(chat_history)} messages")

# Передаём в prompt builder
transformation_prompt = self._build_transformation_prompt(
    description=description,
    input_schemas=input_schemas,
    multiple_sources=multiple_sources,
    previous_errors=previous_errors,
    existing_code=existing_code,  # ✅
    chat_history=chat_history      # ✅
)
```

### 2. Обновлён метод `_build_transformation_prompt()`

Добавлена поддержка **двух режимов** работы:

#### Режим 1: Новая генерация (без existing_code)

```python
TASK: Generate pandas transformation code
DESCRIPTION: Отфильтруй строки где возраст > 30

INPUT SCHEMAS:
df: {"name": "string", "age": "int64", ...}
```

#### Режим 2: Итеративное улучшение (с existing_code)

```python
MODE: ITERATIVE IMPROVEMENT

CURRENT CODE:
```python
df_result = df[df['age'] > 18]
```

CONVERSATION HISTORY:
USER: Отфильтруй строки где возраст > 18
ASSISTANT: Код создан и выполнен успешно
USER: Измени фильтр на возраст > 30

NEW REQUEST: Измени фильтр на возраст > 30

TASK:
- MODIFY the existing code above to fulfill the new request
- PRESERVE working functionality unless explicitly asked to change it
- ADD new features or improvements as requested
- FIX any bugs or issues if mentioned
- Keep code clean and maintain consistent style
```

### 3. Используется контекст переписки

- Последние **5 сообщений** из chat_history включаются в промпт
- GigaChat видит, что было сказано раньше
- Пользователь может ссылаться на "предыдущий код" или "то, что мы делали"

## Результат

### До исправления ❌

```python
# Сообщение 1
USER: "Отфильтруй строки где возраст > 18"
AI: df_result = df[df['age'] > 18]  ✅

# Сообщение 2
USER: "Измени фильтр на возраст > 30"
AI: df_result = df[df['age'] > 18]  ❌ (игнорирует existing_code, генерирует с нуля)
```

### После исправления ✅

```python
# Сообщение 1
USER: "Отфильтруй строки где возраст > 18"
AI: df_result = df[df['age'] > 18]  ✅

# Сообщение 2
USER: "Измени фильтр на возраст > 30"
AI: df_result = df[df['age'] > 30]  ✅ (модифицирует existing_code)
```

## Затронутые файлы

- `apps/backend/app/services/multi_agent/agents/transformation.py`:
  - `_generate_transformation()` — извлечение existing_code и chat_history
  - `_build_transformation_prompt()` — формирование промптов с учётом режима

## Проверка

```bash
# Запустить backend
uv run python apps/backend/main.py

# В TransformDialog:
# 1. Отправить: "Отфильтруй строки где возраст > 18"
# 2. Дождаться кода
# 3. Отправить: "Измени фильтр на возраст > 30"
# 4. Проверить, что код ИЗМЕНИЛСЯ (а не сгенерировался заново)
```

## Ссылки

- [docs/TRANSFORM_DIALOG_CHAT_SYSTEM.md](../TRANSFORM_DIALOG_CHAT_SYSTEM.md) — архитектура Transform Dialog
- [docs/TRANSFORM_MULTIAGENT_DATA_FLOW.md](../TRANSFORM_MULTIAGENT_DATA_FLOW.md) — поток данных через multi-agent
- [docs/MULTI_AGENT_SYSTEM.md](../MULTI_AGENT_SYSTEM.md) — общая архитектура Multi-Agent
