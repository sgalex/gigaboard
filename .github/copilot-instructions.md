# GitHub Copilot Instructions для GigaBoard

## 🎯 Контекст проекта

**GigaBoard** — AI-powered платформа для создания data pipelines с концепцией Data-Centric Canvas.

**Стек:**
- Backend: FastAPI + SQLAlchemy + PostgreSQL + Redis + Socket.IO
- Frontend: React + TypeScript + Vite + React Flow + Zustand
- AI: Multi-Agent система (планируется GigaChat)

## 📚 Документация - ОБЯЗАТЕЛЬНО проверять

Перед любым изменением кода:

### 1. Проверь актуальное состояние
- `docs/README.md` - обзор проекта и текущее состояние
- `.vscode/CURRENT_FOCUS.md` - текущая фаза разработки
- `docs/ROADMAP.md` - план развития

### 2. Архитектура и спецификации
- `docs/ARCHITECTURE.md` - архитектура системы
- `docs/SPECIFICATIONS.md` - требования и спецификации
- `docs/API.md` - API endpoints и схемы

### 3. Специфичная документация (по контексту)
- `docs/DATA_NODE_SYSTEM.md` - работа с DataNode
- `docs/MULTI_AGENT_SYSTEM.md` - Multi-Agent архитектура
- `docs/BOARD_CONSTRUCTION_SYSTEM.md` - система досок
- `docs/CONNECTION_TYPES.md` - типы связей между нодами
- Другие файлы в `docs/` - проверяй по мере необходимости

### 4. История изменений
- `docs/history/` - завершённые фичи и анализы

## 🔄 Алгоритм работы

```
1. Получил задачу
   ↓
2. Проверил docs/README.md + .vscode/CURRENT_FOCUS.md
   ↓
3. Прочитал соответствующую специфичную документацию
   ↓
4. Понял архитектуру и зависимости
   ↓
5. Реализовал код в соответствии с документацией
   ↓
6. Если появились расхождения - предупредил пользователя
```

## 💡 Правила кодирования

### Backend (Python/FastAPI)
- **Используй `uv` для всех Python команд** — `uv run python`, `uv pip install`, `uv run alembic`
  - Проект настроен на использование корневого `.venv` через `uv.toml`
  - Можно вызывать `uv` из любой директории проекта
- Используй async/await для всех I/O операций
- SQLAlchemy models в `apps/backend/app/models/`
- Pydantic schemas в `apps/backend/app/schemas/`
- Routes в `apps/backend/app/routes/`
- Business logic в `apps/backend/app/services/`
- Следуй существующим паттернам (смотри похожие файлы)

### Frontend (React/TypeScript)
- Используй Zustand для state management
- Компоненты в `apps/web/src/components/`
- Hooks в `apps/web/src/hooks/`
- API calls через `apps/web/src/lib/api.ts`
- Типы в `apps/web/src/types/`
- Следуй существующей структуре

### Общие правила
- **НЕ придумывай** - если не уверен, спроси или проверь документацию
- **Ссылайся на документацию** в комментариях: `// См. docs/API.md`
- **Предупреждай о расхождениях** между кодом и документацией
- **Используй существующие паттерны** - смотри на похожие реализации

### Документация и диаграммы
- **Язык документации: русский** — вся техническая документация в `docs/` пишется на русском языке
  - Executive Summary — на русском
  - Описания, комментарии, тезисы — на русском
  - Исключения: код (Python/TypeScript), команды CLI, технические термины (SourceNode, ContentNode, API, etc.)
- **Используй Mermaid** для всех диаграмм и схем (вместо ASCII-графики)
- Типы диаграмм: `flowchart`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `stateDiagram`
- Пример:
  ````markdown
  ```mermaid
  flowchart LR
      A[SourceNode] -->|EXTRACT| B[ContentNode]
      B -->|VISUALIZATION| C[WidgetNode]
  ```
  ````
- **НЕ используй** ASCII-диаграммы типа `[A] --> [B]` в документации

### Структура технической документации
- **Executive Summary** вверху — краткий обзор для всех (что, зачем, ключевые концепции)
- **Тезисы перед кодом** — краткое описание структур данных, API, компонентов
- **Код в `<details>`** — длинные блоки кода (>30 строк) сворачивать:
  ```markdown
  <details>
  <summary>📄 Полная Database Schema (развернуть)</summary>
  
  ```python
  # код...
  ```
  </details>
  ```
- **Оставлять примеры** — короткие примеры использования (API calls, workflows) не сворачивать
- **Диаграммы открыто** — Mermaid диаграммы всегда видимы, не в `<details>`
- **Целевая аудитория** — документ должен быть полезен и PM (высокоуровневое понимание), и разработчикам (технические детали)

## ⚠️ Критические моменты

1. **Наследование нод**: Все ноды наследуются от `Node` (см. `docs/ARCHITECTURE.md`)
2. **Socket.IO события**: Проверяй существующие события в документации
3. **Database миграции**: Используй Alembic через `uv run alembic`, не меняй схему напрямую
4. **API версионирование**: Все endpoints под `/api/v1/`
5. **Python commands**: Всегда используй `uv` — `uv run python script.py`, `uv pip install package`

## 🚫 Что НЕ делать

- ❌ Не создавай новые модели без проверки ARCHITECTURE.md
- ❌ Не меняй существующую схему БД без миграции
- ❌ Не дублируй код - ищи существующие решения
- ❌ Не игнорируй существующие типы и интерфейсы
- ❌ Не предлагай решения, противоречащие документации

## ✅ Что делать, если документация устарела

1. Сообщи пользователю о расхождении
2. Предложи варианты:
   - Обновить документацию
   - Изменить код в соответствии с документацией
   - Обсудить новый подход

---

**Помни**: Документация - источник истины. Код должен соответствовать документации, а не наоборот.
