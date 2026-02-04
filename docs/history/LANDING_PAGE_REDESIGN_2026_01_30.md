# Landing Page Redesign — 30 января 2026

**Статус**: ✅ Завершено  
**Дата**: 30 января 2026  
**Цель**: Переработка landing page в соответствии с новой Source-Content Node Architecture

---

## 🎯 Что изменилось

### 1. Hero Section — новая концепция
**Было**: "Создавайте дашборды за минуты, а не за часы"  
**Стало**: "От источников к инсайтам одним промптом"

**Ключевые изменения**:
- Подзаголовок изменён на "AI-powered Data-Centric Canvas"
- Feature highlights обновлены:
  - `Layout` → `Network` (Data Pipeline Canvas)
  - `Users` → `Radio` (Real-time Streaming)
- Акцент на явном data lineage и streaming

---

### 2. Core Features — Source-Content Architecture
**Было**: 4 фичи (Бесконечное полотно, AI Assistant, Real-time, Связи)  
**Стало**: 4 фичи (SourceNode, ContentNode, WidgetNode, Прозрачный Pipeline)

**Новые фичи**:
1. **SourceNode — Источники данных**
   - 6 типов источников (prompt, file, database, api, stream, manual)
   - Auto-refresh расписания
   - Streaming поддержка
   - Архивирование данных

2. **ContentNode — Обработанные данные**
   - Результаты извлечения и трансформаций
   - Текст + N таблиц в одном узле
   - Полный data lineage от источника
   - 5 режимов replay

3. **WidgetNode — Визуализации**
   - AI генерирует HTML/CSS/JS код
   - Автообновление при изменении данных
   - 6 типов виджетов
   - Адаптивный дизайн + тёмная тема

4. **Прозрачный Data Pipeline**
   - EXTRACT → TRANSFORMATION → VISUALIZATION
   - Граф зависимостей всегда актуален
   - Автотрансформации
   - Impact Analysis

---

### 3. Connection Types — новая семантика
**Было**: 7 типов связей (DATA_FLOW, DEPENDENCY, CAUSALITY, DRILL_DOWN, REFERENCE, ANNOTATION, CUSTOM)  
**Стало**: 6 типов связей с явной семантикой data pipeline

**Новые типы связей**:
- `EXTRACT`: SourceNode → ContentNode (извлечение данных)
- `TRANSFORMATION`: ContentNode(s) → ContentNode (обработка данных)
- `VISUALIZATION`: ContentNode → WidgetNode (визуализация)
- `COMMENT`: CommentNode → любой узел (аннотации)
- `REFERENCE`: Ссылки между узлами
- `DRILL_DOWN`: Детализация данных

**Пример pipeline**:
```
SourceNode (DB) →EXTRACT→ ContentNode (sales data) 
→TRANSFORMATION→ ContentNode (aggregated) 
→VISUALIZATION→ WidgetNode (chart)
```

---

### 4. 🆕 Streaming Section — Real-time данные
**Новая секция**: Real-time Streaming с WebSocket/SSE/Kafka

**Ключевые возможности**:
1. **Streaming SourceNode**
   - Подключение WebSocket, SSE, Kafka
   - Аккумуляция в реальном времени
   - Автоматическое архивирование
   - Replay всей истории данных

2. **5 режимов Replay**
   - Throttled: обновление не чаще N секунд
   - Batched: накопление + batch обработка
   - Manual: только по команде пользователя
   - Intelligent: AI решает когда обновлять
   - Selective: только изменённые части

**Пример использования**:
IoT сенсоры → WebSocket SourceNode → ContentNode (10K записей/мин) → WidgetNode с real-time графиком

---

### 5. Use Cases — новые примеры с Source-Content
**Было**: 4 use case с метриками и AI suggestions  
**Стало**: 4 use case с пошаговым pipeline

**Новый формат**:
- Пошаговое описание работы агентов
- Явное указание создаваемых узлов (SourceNode/ContentNode/WidgetNode/CommentNode)
- Data lineage граф
- Badges: "Zero SQL", "Автокод", "Root Cause", "No Data? No Problem!"

**Примеры**:
1. **Product Manager**: "Покажи метрики продукта за неделю"
   - Researcher создаёт SourceNode (БД)
   - Extraction → ContentNode
   - Transformation → новый ContentNode
   - Reporter генерирует 3 WidgetNode

2. **Data Scientist**: "Проанализируй корреляцию email-кампаний и конверсии"
   - Analyst анализирует 2 ContentNode
   - Transformation создаёт lag-анализ (Python код)
   - Новый ContentNode с корреляциями
   - Reporter генерирует WidgetNode

3. **DevOps Engineer**: "Почему вчера ночью были ошибки?"
   - Researcher создаёт SourceNode (логи + deploy history)
   - ContentNode с timestamp correlation
   - Analyst находит регрессию
   - AI рекомендация: откат

4. **Студент**: "Проанализируй безработицу в России за 5 лет"
   - Data Discovery Agent ищет публичные датасеты
   - Создаёт 3 SourceNode (Росстат, ЦБ РФ, OECD)
   - Transformation объединяет данные
   - Reporter создаёт интерактивные графики

---

### 6. Tech Stack — обновлённые технологии
**Добавлено**:
- Socket.IO в Backend
- Adaptive Planning в AI
- SSE, Message Bus в Real-time
- Stream Archives в Database

**Новые badges**:
- Source-Content Architecture
- Multi-Agent System (9 агентов)
- Real-time First (latency < 150ms)

---

### 7. Header Navigation — обновлённая структура
**Было**: Возможности, AI-агенты, Виджеты, Примеры, Безопасность, Для кого  
**Стало**: Архитектура, Streaming, AI-агенты, Примеры, Безопасность

**Причина**: Фокус на ключевых инновациях:
- Архитектура (Source-Content)
- Streaming (новая фича)
- AI-агенты (мультиагентная система)
- Примеры (практическое применение)
- Безопасность (доверие)

---

### 8. CTA Section — обновлённое позиционирование
**Было**: "GigaBoard превращает аналитику из рутины в удовольствие"  
**Стало**: "Попрощайтесь с бесконечными SQL запросами и часами ручной работы"

**Новый месседж**:
- "Просто опишите задачу — AI построит весь pipeline"
- Акцент на автоматизацию и AI-первый подход
- Заголовок: "Готовы к революции в аналитике?"

---

## 📊 Ключевые концепции в новом дизайне

### 1. Data-Centric Canvas
Вместо "бесконечного полотна с виджетами" → **явный data pipeline**:
```
SourceNode → ContentNode → WidgetNode
```

### 2. Явный Data Lineage
Каждая связь имеет семантику:
- EXTRACT — из источника
- TRANSFORMATION — обработка
- VISUALIZATION — отображение

### 3. Real-time First
Streaming источники — первоклассные граждане:
- WebSocket, SSE, Kafka
- Аккумуляция + архивирование
- 5 режимов replay

### 4. AI-Powered Automation
9 специализированных агентов строят полный pipeline:
- Researcher → SourceNode
- Transformation Agent → ContentNode
- Reporter Agent → WidgetNode

---

## 🎨 Дизайн-система

### Новые иконки
- `Database` — SourceNode
- `Boxes` — ContentNode
- `Network` — Data Pipeline
- `Radio` — Real-time Streaming
- `Layers` — Replay режимы
- `FileCode` — Трансформации
- `PlayCircle` — SSE

### Новые цветовые акценты
- **Blue** (#4CAF50) — EXTRACT
- **Purple** (#9C27B0) — TRANSFORMATION / ContentNode
- **Green** (#2196F3) — VISUALIZATION / WidgetNode
- **Orange** (#FF9800) — COMMENT
- **Accent** — Streaming indicators

---

## 📄 Файлы изменены

1. `apps/web/src/pages/LandingPage.tsx` — полная переработка:
   - Hero Section
   - Core Features
   - Connection Types
   - **Streaming Section** (новая)
   - Use Cases
   - Tech Stack
   - Header Navigation
   - CTA Section

---

## 🚀 Что дальше?

1. **Проверить отображение**:
   ```bash
   npm run -w apps/web dev
   ```
   Открыть http://localhost:5173

2. **Тестирование**:
   - Проверить все секции
   - Тестировать навигацию
   - Проверить responsive дизайн
   - Протестировать тёмную тему

3. **Обновить screenshots**:
   - Создать новые скриншоты для README.md
   - Добавить в docs/assets/

4. **SEO оптимизация**:
   - Обновить meta tags в index.html
   - Добавить keywords: "Source-Content Node", "Data Pipeline Canvas", "Real-time Streaming"

---

## ✅ Checklist

- [x] Hero Section обновлён
- [x] Core Features переработаны под Source-Content
- [x] Connection Types с новой семантикой
- [x] Streaming Section добавлена
- [x] Use Cases обновлены с пошаговыми примерами
- [x] Tech Stack актуализирован
- [x] Header Navigation реструктурирован
- [x] CTA Section обновлён
- [x] Импорты новых иконок добавлены
- [x] Нет ошибок компиляции
- [ ] Тестирование в браузере
- [ ] Screenshots обновлены
- [ ] SEO оптимизация

---

## 💡 Ключевые улучшения

1. **Фокус на архитектуре**: Source-Content Node как ключевая инновация
2. **Streaming первым классом**: Новая секция для real-time данных
3. **Практические примеры**: Пошаговые use cases с явным pipeline
4. **Явная семантика**: EXTRACT → TRANSFORMATION → VISUALIZATION
5. **AI-автоматизация**: Агенты строят весь граф от источников до визуализаций

---

**Вывод**: Landing page теперь точно отражает концепцию GigaBoard как **AI-powered Data-Centric Canvas** с явным data lineage, real-time streaming и мультиагентной автоматизацией.
