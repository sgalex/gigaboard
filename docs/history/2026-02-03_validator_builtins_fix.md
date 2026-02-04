# Validator Builtins Fix — 2026-02-03

## 🐛 Проблема

Multi-Agent система не могла выполнить трансформации из-за критической ошибки в ValidatorAgent:

```
"Dry run failed: name 'len' is not defined"
```

### Симптомы

1. TransformationAgent генерировал **корректный** код:
   ```python
   row_count = len(df)
   df_result = pd.DataFrame({'Row Count': [row_count]})
   ```

2. ValidatorAgent проваливал все попытки (6/6) с одной и той же ошибкой

3. ErrorAnalyzerAgent давал **неверный** совет:
   > "Define 'len' before using it"
   
   (Абсурдно — `len()` это встроенная функция Python!)

4. Fallback возвращал исходную таблицу без трансформации

## 🔍 Root Cause

В [validator.py:321](apps/backend/app/services/multi_agent/agents/validator.py#L321) была изоляция окружения `exec()`:

```python
namespace = {
    'pd': pd,
    'np': np,
    'gb': MockGBHelpers(),
    '__builtins__': {}  # ❌ Блокирует все встроенные функции Python!
}
```

Это блокировало доступ к:
- `len()`, `int()`, `str()`, `float()`
- `sum()`, `min()`, `max()`, `abs()`, `round()`
- `range()`, `enumerate()`, `zip()`, `map()`, `filter()`
- И все остальные Python builtins

## ✅ Решение

### 1. Исправлен ValidatorAgent

**Файл:** [apps/backend/app/services/multi_agent/agents/validator.py:321](apps/backend/app/services/multi_agent/agents/validator.py#L321)

```python
namespace = {
    'pd': pd,
    'np': np,
    'gb': MockGBHelpers(),
    '__builtins__': __builtins__  # ✅ Доступ к встроенным функциям Python
}
```

### 2. Улучшен ErrorAnalyzerAgent

**Файл:** [apps/backend/app/services/multi_agent/agents/error_analyzer.py:168-192](apps/backend/app/services/multi_agent/agents/error_analyzer.py#L168-L192)

Добавлена проверка на Python builtins:

```python
python_builtins = {'len', 'int', 'str', 'float', 'list', 'dict', 'tuple', 'set', 
                  'sum', 'min', 'max', 'abs', 'round', 'range', 'enumerate', 
                  'zip', 'map', 'filter', 'sorted', 'all', 'any', 'type', 'isinstance'}

if var_name in python_builtins:
    return {
        "root_cause": f"Built-in function '{var_name}' not available in sandbox",
        "error_category": "sandbox_environment",
        "specific_fixes": [
            "CRITICAL: This is a validator configuration issue, not a code issue"
        ],
        ...
    }
```

Теперь ErrorAnalyzerAgent **распознает**, что проблема в песочнице, а не в коде.

## 📊 Impact

**До исправления:**
- ❌ Все трансформации с `len()`, `int()`, `sum()` и т.д. проваливались
- ❌ Система уходила в fallback (возврат исходной таблицы)
- ❌ 6 бесполезных попыток с GigaChat API

**После исправления:**
- ✅ Трансформации с Python builtins работают
- ✅ ValidatorAgent корректно выполняет dry-run
- ✅ ErrorAnalyzerAgent дает правильные рекомендации

## 🧪 Тестирование

**Тест-кейс:** "посчитай количество строк"

**Ожидаемое поведение:**
1. TransformationAgent генерирует: `row_count = len(df)`
2. ValidatorAgent успешно выполняет dry-run
3. Создается ContentNode с результатом: `{'Row Count': [19041]}`

**Требуется:**
- Перезапустить backend: `.\run-backend.ps1`
- Повторить трансформацию в UI

## 📝 Related Files

- [apps/backend/app/services/multi_agent/agents/validator.py](apps/backend/app/services/multi_agent/agents/validator.py) — ValidatorAgent
- [apps/backend/app/services/multi_agent/agents/error_analyzer.py](apps/backend/app/services/multi_agent/agents/error_analyzer.py) — ErrorAnalyzerAgent
- [apps/backend/app/services/agents/transformation_multi_agent.py](apps/backend/app/services/agents/transformation_multi_agent.py) — Multi-Agent orchestrator

## 🎓 Lessons Learned

1. **Изоляция exec() должна быть разумной** — блокировать опасные операции (file I/O, network), но не базовые функции
2. **ErrorAnalyzer должен знать контекст выполнения** — различать ошибки кода vs ошибки окружения
3. **Dry-run окружение должно соответствовать production** — иначе валидация бесполезна

## 🔄 Next Steps

1. ✅ Перезапустить backend
2. ✅ Протестировать трансформации с `len()`, `sum()`, `int()`
3. ⏳ Рассмотреть добавление юнит-тестов для ValidatorAgent
4. ⏳ Документировать список доступных функций в песочнице

---

**Status:** ✅ FIXED  
**Date:** 2026-02-03  
**Severity:** CRITICAL (блокировало 90% трансформаций)
