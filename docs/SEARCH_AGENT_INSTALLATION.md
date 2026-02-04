# 🔍 Search Agent - Installation Guide

## Быстрая установка

### Шаг 1: Установите зависимость

```bash
cd apps/backend
pip install duckduckgo-search
```

Или установите все зависимости из `pyproject.toml`:

```bash
pip install -e .
```

### Шаг 2: Проверьте установку

```bash
python -c "from duckduckgo_search import DDGS; print('✅ duckduckgo-search installed')"
```

### Шаг 3: Проверьте, что SearchAgent импортируется

```bash
python -c "from app.services.multi_agent import SearchAgent; print('✅ SearchAgent imported')"
```

### Шаг 4: Запустите тест

```bash
cd apps/backend
python tests/example_search_agent.py
```

## Ожидаемый вывод

```
🔧 Инициализация...
✅ SearchAgent готов

============================================================
🔍 Пример 1: Веб-поиск 'Python FastAPI'
============================================================

📊 Найдено результатов: 5

📝 Краткое резюме:
FastAPI - современный веб-фреймворк для создания API на Python...

🔗 Топ-3 результата:
  1. FastAPI - Official Documentation
     https://fastapi.tiangolo.com

  2. FastAPI on GitHub
     https://github.com/tiangolo/fastapi

  3. FastAPI Tutorial
     https://fastapi.tiangolo.com/tutorial/

============================================================
📰 Пример 2: Новости об 'искусственный интеллект'
============================================================

📊 Найдено новостей: 3

📰 Последние новости:
  1. Новые достижения в области ИИ
     Дата: 2024-01-20
     Источник: TechNews

============================================================
⚡ Пример 3: Быстрый ответ 'What is FastAPI?'
============================================================

💡 Ответ: FastAPI is a modern web framework for building APIs...

============================================================
✅ Все примеры выполнены успешно!
============================================================
```

## Troubleshooting

### Проблема: ImportError: No module named 'duckduckgo_search'

**Решение**:
```bash
pip install duckduckgo-search
```

### Проблема: SSL Certificate Error

**Решение**: Отключите проверку SSL сертификатов (только для разработки):
```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

### Проблема: Connection Timeout

**Решение**: Проверьте интернет-соединение или увеличьте timeout:
```python
task = {
    "type": "web_search",
    "query": "Python",
    "timeout": 60  # Увеличить до 60 секунд
}
```

## Следующие шаги

1. ✅ Установка завершена
2. ⏭️ Прочитайте [SEARCH_AGENT_QUICKSTART.md](SEARCH_AGENT_QUICKSTART.md)
3. ⏭️ Изучите [SEARCH_AGENT.md](SEARCH_AGENT.md) для полной документации
4. ⏭️ Попробуйте примеры в [example_search_agent.py](../apps/backend/tests/example_search_agent.py)

## Версии

- **duckduckgo-search**: >= 5.0.0
- **Python**: >= 3.11
- **GigaBoard Backend**: >= 0.1.0

## Поддержка

Если у вас возникли проблемы:
1. Проверьте версию Python: `python --version`
2. Проверьте установленные пакеты: `pip list | grep duckduckgo`
3. Проверьте логи: `tail -f logs/backend.log`

---

**Готово!** 🎉 SearchAgent установлен и готов к использованию.
