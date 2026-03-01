# Анализ: При каких обстоятельствах происходит перепланирование

**Дата**: 28 января 2026

# Анализ: При каких обстоятельствах происходит перепланирование

**Дата**: 28 января 2026  
**Статус**: ✅ Обновлено - AI-Powered Decision Logic Implemented

## 🎯 Новая реализация (28 января 2026)

### AI-Powered Error Evaluation + Full Replan After Success

Система теперь использует **два механизма** для адаптивного планирования:

1. **AI-Powered Error Evaluation** - При ошибках
2. **Full Replan After Success** - После успешных шагов

---

## ✅ 1. AI-Powered Error Evaluation (при ошибках)

### Новая цепочка принятия решений:

```
Ошибка в шаге
    ↓
Engine._handle_step_error()
    ↓
PlannerAgent._evaluate_result()
    ↓
    ├→ _ai_evaluate_error() (GigaChat анализ) ← НОВОЕ!
    │   └→ Решение: retry/replan/abort/continue + reasoning
    │
    └→ _heuristic_evaluate_error() (fallback) ← УЛУЧШЕНО!
        └→ Расширенные keywords для каждой категории
    ↓
Engine обрабатывает решение
```

### GigaChat Evaluation Prompt:

```python
prompt = f"""
Ты - AI планировщик. Агент {agent_name} вернул ошибку при выполнении шага.

ОШИБКА: {error_message}
ШАГ: {step_description}
КОНТЕКСТ: {step_context}

КРИТЕРИИ ДЛЯ RETRY:
- Временные проблемы (timeout, connection)
- Rate limit
- Случайные сбои

КРИТЕРИИ ДЛЯ REPLAN:
- Источник данных недоступен → можно найти альтернативный
- Доступ запрещён (403, 401) → можно использовать другой источник
- Формат не поддерживается → нужен шаг конвертации
- ВАЖНО: Предпочитай REPLAN если есть возможность обойти проблему!

КРИТЕРИИ ДЛЯ CONTINUE:
- Warning (не критично)
- Partial success (часть данных получена)

КРИТЕРИИ ДЛЯ ABORT:
- Фундаментальная ошибка
- Невозможно обойти

Ответ: {{"decision": "retry/replan/abort/continue", "reason": "..."}}
"""
```

### Enhanced Heuristic Fallback:

```python
# Расширенные keywords для каждой категории
if any(keyword in error_lower for keyword in [
    "timeout", "connection", "rate limit", "too many requests"
]):
    return "retry", "Temporary issue detected"

elif any(keyword in error_lower for keyword in [
    "not found", "404", "403", "missing", "unavailable",
    "access denied", "forbidden", "invalid format"
]):
    return "replan", "Resource unavailable, need alternative approach"

elif any(keyword in error_lower for keyword in [
    "warning", "partial"
]):
    return "continue", "Non-critical issue, can continue"

else:
    return "abort", "Unknown error"
```

---

## ✅ 2. Full Replan After Success (после успешных шагов)

### Новый механизм адаптивного планирования:

```
Шаг успешно выполнен
    ↓
Результаты добавлены в пул знаний (all_results)
    ↓
_should_replan_after_step() ← НОВЫЙ МЕТОД!
    ↓
GigaChat анализирует:
  - Результат текущего шага
  - ВСЕ накопленные результаты
  - Оставшиеся шаги в плане
    ↓
Решение: replan=true/false + reason + key_insights
    ↓
Если replan=true:
    PlannerAgent.replan() с full context
    └→ Полное перепланирование стратегии
```

### GigaChat Replan Analysis Prompt:

```python
prompt = f"""
Ты - AI планировщик, анализирующий результаты выполнения шагов.

ТЕКУЩАЯ СИТУАЦИЯ:
Только что успешно выполнен шаг #{step_index + 1}
Агент: {agent_name}
Статус: {status}

ОБЩИЙ КОНТЕКСТ:
Всего шагов в плане: {total_steps}
Выполнено шагов: {completed_steps}
Накопленные результаты: {results_count} результатов

ОСТАВШИЕСЯ ШАГИ: {remaining_steps}

КРИТЕРИИ ДЛЯ REPLAN:
1. Результат содержит СУЩЕСТВЕННО НОВУЮ информацию
2. Обнаружены НОВЫЕ источники данных
3. Текущий план НЕ ОПТИМАЛЕН для достижения цели
4. Нужно изменить ПОСЛЕДОВАТЕЛЬНОСТЬ шагов
5. Некоторые шаги можно ПРОПУСТИТЬ или ОБЪЕДИНИТЬ

НЕ НУЖЕН REPLAN если:
- План работает как ожидалось
- Результаты предсказуемы
- Оставшиеся шаги корректны

Ответ: {{"replan": true/false, "reason": "...", "key_insights": "..."}}
"""
```

### Ключевые преимущества:

- **Передача ВСЕХ результатов**: `current_results` содержит все накопленные знания
- **Полное перепланирование**: Используется `PlannerAgent.replan()`, а не частичная оптимизация
- **Консервативный подход**: temperature=0.3 для баланса между адаптацией и стабильностью
- **Ограничения**: MAX_REPLAN_ATTEMPTS=2 для предотвращения циклов

---

## 🔍 Старая реализация (до 28 января 2026)

## ✅ Рекомендации по улучшению

### Вариант 1: Расширенная эвристика

```python
async def _evaluate_result(self, task, context):
    error_msg = step_result.get("error", "").lower()
    agent = step_result.get("agent", "")
    
    # Условия для RETRY
    retry_keywords = ["timeout", "connection", "temporary", "rate limit"]
    if any(kw in error_msg for kw in retry_keywords):
        return {"decision": "retry", ...}
    
    # Условия для REPLAN
    replan_keywords = [
        "not found", "missing", "unavailable", "does not exist",
        "insufficient", "invalid format", "unsupported",
        "cannot parse", "failed to load", "access denied"
    ]
    if any(kw in error_msg for kw in replan_keywords):
        return {"decision": "replan", ...}
    
    # Специфичные для агента правила
    if agent == "search" and "no results" in error_msg:
        return {"decision": "replan", ...}  # Попробовать другой источник
    
    if agent == "analyst" and "insufficient data" in error_msg:
        return {"decision": "replan", ...}  # Расширить поиск
    
    # Всё остальное → ABORT
    return {"decision": "abort", ...}
```

### Вариант 2: AI-powered decision (РЕКОМЕНДУЕТСЯ)

```python
async def _evaluate_result(self, task, context):
    error_msg = step_result.get("error", "")
    agent = step_result.get("agent", "")
    step_id = step_result.get("step_id", "")
    
    # Вызываем GigaChat для анализа ошибки
    prompt = f"""
Analyze the error and decide on the best action:

ERROR: {error_msg}
AGENT: {agent}
STEP: {step_id}

AVAILABLE ACTIONS:
1. RETRY - temporary error, try again
2. REPLAN - error requires plan modification
3. ABORT - critical unrecoverable error
4. CONTINUE - non-critical, skip this step

Consider:
- Is error recoverable by retry?
- Can we adapt plan to work around error?
- Is this step critical for workflow?

Return JSON: {{"decision": "retry|replan|abort|continue", "reason": "..."}}
"""
    
    response = await self.gigachat.chat_completion([
        {"role": "system", "content": "You are error analysis expert."},
        {"role": "user", "content": prompt}
    ])
    
    # Parse и validate response
    decision_data = self._parse_decision_from_response(response)
    return decision_data
```

### Вариант 3: Hybrid (эвристика + AI fallback)

```python
async def _evaluate_result(self, task, context):
    # Сначала пробуем быструю эвристику
    quick_decision = self._quick_heuristic_decision(step_result)
    
    if quick_decision["confidence"] > 0.9:
        return quick_decision  # Уверены в решении
    
    # Если не уверены → спрашиваем AI
    ai_decision = await self._ai_powered_decision(step_result, context)
    return ai_decision
```

## 📊 Сравнение подходов

| Подход                    | Скорость    | Точность | Гибкость   | Стоимость     |
| ------------------------- | ----------- | -------- | ---------- | ------------- |
| **Текущий** (1 keyword)   | ⚡ 0ms       | ⚠️ 30%    | ❌ Низкая   | 💰 $0          |
| **Расширенная эвристика** | ⚡ 1ms       | ✅ 70%    | ⚠️ Средняя  | 💰 $0          |
| **AI-powered**            | 🐌 200-500ms | ✅✅ 90%   | ✅✅ Высокая | 💰💰 $0.01-0.05 |
| **Hybrid**                | ⚡ 1-500ms   | ✅✅ 85%   | ✅ Высокая  | 💰 $0.005-0.02 |

## 🎯 Конкретный ответ на вопрос

### **Когда происходит replan СЕЙЧАС:**

**ЕДИНСТВЕННОЕ условие**: Текст ошибки содержит подстроку `"not found"` (регистронезависимо)

**Примеры**:
- ✅ SearchAgent: "Resource not found at URL"
- ✅ ResearcherAgent: "Page not found (404)"
- ✅ TransformationAgent: "Column 'name' not found in data"
- ✅ AnalystAgent: "Required field not found"

**Дополнительное условие в Engine**:
```python
elif decision == "replan" and replan_count < MAX_REPLAN_ATTEMPTS:
    # Выполняем replan
```

Т.е. replan происходит **максимум 2 раза** (MAX_REPLAN_ATTEMPTS = 2)

### **Полная логика**:

```
1. Шаг завершился с ошибкой
2. Engine вызывает _handle_step_error()
3. PlannerAgent._evaluate_result() проверяет:
   IF "not found" in error.lower():
       decision = "replan"
4. Engine проверяет:
   IF decision == "replan" AND replan_count < 2:
       Вызывает PlannerAgent.replan()
       Обновляет список шагов (steps)
       Повторяет текущий шаг с новым планом
```

## 📝 Файлы для изменения

Если нужно улучшить логику:

1. **apps/backend/app/services/multi_agent/agents/planner.py**
   - Метод `_evaluate_result()` (строки 386-440)
   - Заменить простую эвристику на расширенную или AI-powered

2. **apps/backend/app/services/multi_agent/engine.py**
   - Можно добавить настраиваемые лимиты retry/replan
   - Добавить метрики: replan_reasons, decision_accuracy

---

**Вывод**: Текущая реализация использует **крайне упрощённую** эвристику для принятия решения о перепланировании. Рекомендуется внедрить **AI-powered decision making** для более интеллектуального анализа ошибок.
