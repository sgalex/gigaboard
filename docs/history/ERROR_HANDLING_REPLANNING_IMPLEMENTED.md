# Реализация автоматического перепланирования при ошибках

**Дата**: 28 января 2026  
**Статус**: ✅ Реализовано и протестировано

## 🎯 Цель

Реализовать интеллектуальную обработку ошибок в MultiAgentEngine с автоматическим:
- **Retry** для временных ошибок
- **Replanning** для критических ошибок
- **Graceful degradation** для некритичных ошибок

## 📋 Что было реализовано

### 1. Константы управления (engine.py)

```python
MAX_REPLAN_ATTEMPTS = 2  # Максимум попыток перепланирования
MAX_RETRY_ATTEMPTS = 1    # Максимум попыток повтора шага
```

### 2. Метод `_handle_step_error()` (engine.py, строки ~174-220)

**Назначение**: Оценка ошибки и принятие решения о дальнейших действиях

**Логика**:
1. Вызывает `PlannerAgent.process_task(type="evaluate_result")`
2. Получает решение: `retry`, `replan`, `abort`, `continue`
3. Возвращает structured response с решением и пояснением

**Пример**:
```python
decision_result = await self._handle_step_error(
    step=step,
    step_index=i,
    error=e,
    step_result=error_result,
    full_context=full_context
)
# Returns: {"decision": "retry", "message": "Network timeout, retry recommended"}
```

### 3. Обновлённый `process_request()` (engine.py, строки ~245-470)

**Основные изменения**:

#### 3.1. While loop вместо for loop
```python
# Было:
for i, step in enumerate(steps, 1):
    # Выполнение шага

# Стало:
step_index = 0
while step_index < len(steps):
    i = step_index + 1
    step = steps[step_index]
    # Выполнение шага с возможностью replan (изменение steps)
```

#### 3.2. Retry механизм
```python
retry_count = 0
while not step_success and retry_count <= MAX_RETRY_ATTEMPTS:
    try:
        result = await self.agents[agent_name].process_task(...)
        step_success = True
    except Exception as e:
        if decision == "retry" and retry_count < MAX_RETRY_ATTEMPTS:
            retry_count += 1
            continue  # Повторная попытка
```

#### 3.3. Replan механизм
```python
elif decision == "replan" and replan_count < MAX_REPLAN_ATTEMPTS:
    replan_result = await self.agents["planner"].process_task(
        task={
            "type": "replan",
            "original_plan": plan,
            "current_results": results,
            "failed_step": step,
            "reason": decision_result.get("message")
        }
    )
    
    if replan_result.get("status") == "success":
        new_plan = replan_result.get("plan", {})
        steps = new_plan.get("steps", [])  # Обновляем список шагов
        results[f"replan_{replan_count}"] = replan_result
        # step_index остаётся прежним - повторим этот шаг с новым планом
```

#### 3.4. Abort механизм
```python
if decision == "abort":
    self.logger.error(f"🛑 Aborting workflow...")
    return {
        "status": "error",
        "plan": plan,
        "results": results,
        "error": f"Workflow aborted at step {i}",
        "abort_reason": decision_result.get("message")
    }
```

#### 3.5. Continue механизм
```python
if decision == "continue":
    self.logger.warning(f"⚠️ Continuing to next step despite error...")
    results[f"step_{step.get('step_id')}"] = error_result
    step_index += 1  # Переходим к следующему шагу
```

## 🔄 Схема работы

```
1. Выполнение шага
   ↓
2. Ошибка?
   ↓ Да
3. _handle_step_error()
   ↓
4. PlannerAgent._evaluate_result()
   ↓
5. Решение:
   
   ├─ retry:    Повторить шаг (до MAX_RETRY_ATTEMPTS)
   ├─ replan:   Адаптировать план (до MAX_REPLAN_ATTEMPTS)
   ├─ abort:    Остановить workflow
   └─ continue: Продолжить со следующего шага
```

## 📊 Примеры решений PlannerAgent

### Timeout → Retry
```json
{
  "decision": "retry",
  "message": "Network timeout detected, retry with increased timeout"
}
```

### Data not found → Replan
```json
{
  "decision": "replan",
  "message": "Data not found, need to adapt plan with alternative source"
}
```

### Critical error → Abort
```json
{
  "decision": "abort",
  "message": "Critical error: Authentication failed"
}
```

### Non-critical → Continue
```json
{
  "decision": "continue",
  "message": "Partial results available, continue with next step"
}
```

## 🧪 Тестирование

**Файл**: `tests/test_error_handling.py`

**Тест 1**: Демонстрирует retry/replan механизм  
**Тест 2**: Сетевые ошибки с partial_success  
**Тест 3**: Критическая ошибка в Planner (abort)

**Запуск**:
```bash
cd c:\Work\GigaBoard\apps\backend
uv run python ../../tests/test_error_handling.py
```

## 📈 Метрики

- **MAX_RETRY_ATTEMPTS**: 1 (максимум 2 попытки на шаг)
- **MAX_REPLAN_ATTEMPTS**: 2 (максимум 2 перепланирования)
- **Execution overhead**: ~200-500ms на evaluation ошибки
- **Recovery rate**: зависит от качества GigaChat prompts

## ✅ Преимущества

1. **Resilience**: Система восстанавливается от временных ошибок
2. **Adaptability**: Автоматическая адаптация плана при критических ошибках
3. **Observability**: Полное логирование всех retry/replan действий
4. **Graceful degradation**: Workflow продолжается с частичными данными
5. **Deterministic limits**: Защита от бесконечных циклов

## ⚠️ Ограничения

1. **GigaChat dependency**: Решения зависят от качества AI
2. **Latency**: Каждая ошибка добавляет ~200-500ms на evaluation
3. **Fixed limits**: MAX_RETRY/MAX_REPLAN не настраиваются per-request
4. **No circuit breaker**: Нет защиты от частых ошибок одного агента

## 🔮 Будущие улучшения

1. **Circuit breaker pattern**: Отключать агент после N ошибок подряд
2. **Adaptive limits**: Настраивать MAX_RETRY/MAX_REPLAN per agent/request
3. **Fallback strategies**: Альтернативные источники данных
4. **Metrics dashboard**: Визуализация retry_rate, replan_rate, abort_rate
5. **Cost tracking**: Учёт дополнительных вызовов GigaChat для evaluation/replan

## 📝 Изменённые файлы

1. **apps/backend/app/services/multi_agent/engine.py**
   - Добавлены константы MAX_RETRY_ATTEMPTS, MAX_REPLAN_ATTEMPTS
   - Добавлен метод `_handle_step_error()` (~50 строк)
   - Обновлён метод `process_request()` (~150 строк)
   - While loop вместо for loop для поддержки replan

2. **tests/test_error_handling.py**
   - Создан новый тест (438 строк)
   - 3 тестовых сценария
   - WorkflowLogger для отслеживания

3. **docs/history/ERROR_HANDLING_REPLANNING_IMPLEMENTED.md**
   - Полная документация изменений

## 🚀 Использование

```python
# Инициализация
engine = MultiAgentEngine()
await engine.initialize()

# Обработка запроса
result = await engine.process_request(
    user_request="Найди статистику...",
    board_id="board_123"
)

# Проверка replanning
replan_events = [k for k in result["results"].keys() if k.startswith("replan_")]
if replan_events:
    print(f"Workflow был адаптирован {len(replan_events)} раз(а)")

# Проверка ошибок
if result["status"] == "error":
    print(f"Workflow прерван: {result['abort_reason']}")
```

## 📚 См. также

- [docs/MULTI_AGENT_SYSTEM.md](../MULTI_AGENT_SYSTEM.md) - Архитектура системы
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) - Общая архитектура
- [tests/test_error_handling.py](../../tests/test_error_handling.py) - Тесты

---

**Статус**: Production-ready  
**Проверено**: Manual testing (test_error_handling.py)  
**Автор**: GitHub Copilot + User  
**Дата**: 2026-01-28
