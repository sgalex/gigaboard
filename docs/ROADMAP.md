# Дорожная карта разработки

## Фаза 1: Планирование и документация ✓

**Статус**: Завершена

**Задачи**:
- [x] Определить требования
- [x] Спроектировать архитектуру
- [x] Утвердить документацию (README/ARCHITECTURE/SPECIFICATIONS/API)
- [x] Подготовить окружение разработки (.venv, uv, pyproject.toml)

**Дата завершения**: 2026-02-15

---

## Фаза 2: Разработка MVP

**Статус**: В процессе

**Задачи**:
- [x] Frontend: канвас на React Flow (@xyflow/react), Zustand state, Socket.IO клиент
- [x] Backend: FastAPI + Socket.IO сервер, CRUD бордов/узлов
- [x] Настроить PostgreSQL + SQLAlchemy, Redis для pub/sub
- [x] **Multi-Agent System** (9 core agents + 5 controllers):
  - [x] AgentPayload — универсальный формат данных
  - [x] Orchestrator — Single Path (Planner → Steps → Validator)
  - [x] 9 Core Agents: Planner, Structurizer, Analyst, TransformCodex, WidgetCodex, Reporter, Discovery, Research, Validator
  - [x] Satellite Controllers: Transformation, Widget, AIAssistant, TransformSuggestions, WidgetSuggestions, **ResearchController** (источник AI Research + `research/chat`)
  - [x] Zero-mapping agent_results (хронологический list), adaptive replanning
  - [x] 112 unit + integration тестов (pytest) ✅
  - [x] Legacy V1 cleanup (12 файлов, ~145KB удалено)
- [x] **Adaptive Planning**: Интеллектуальное перепланирование с GigaChat после каждого шага
- [x] **AI-Powered Error Evaluation**: Умная классификация ошибок для retry/replan/abort/continue
- [x] **Source-Content Node Architecture**: SourceNode → ContentNode → WidgetNode
  - [x] SourceNode (csv, json, excel, document, api, database, research, manual, stream)
  - [x] ContentNode (text + N tables)
  - [x] PromptExtractor для text-to-table
  - [x] Extractors по типам источников: файловые (CSV/JSON/Excel/Document), API, Database, Manual, **Research** (`ResearchSource` → `ResearchController` / Orchestrator), Stream (stub)
- [x] **Интеграция с GigaChat API** (langchain-gigachat)
- [x] **Widget Generation System**: WidgetCodexAgent генерирует HTML/CSS/JS виджеты
- [x] **Transform Dialog Chat System**: итеративный AI-чат для трансформаций
- [x] **Dashboard System**: дашборды, элементы (виджет/таблица/текст/изображение/линия), библиотека виджетов и таблиц проекта
- [x] **Cross-Filter System**: измерения (Dimensions), активные фильтры досок/дашбордов, пресеты, click-to-filter из виджетов
- [ ] **E2E тестирование**: Проверка полного pipeline с реальным GigaChat
- [ ] **Frontend тесты**: Vitest для React компонентов
- [ ] **Form Generator Agent**: динамическая генерация форм ввода
- [ ] **Data Discovery Agent**: поиск публичных датасетов (Kaggle, OECD, World Bank)

**Ключевые фичи MVP**:
- ✅ FR-1 до FR-6: Базовая доска + AI Assistant Panel
- ✅ FR-7: Multi-Agent System (9 agents, Single Path Orchestrator, 5 controllers)
- ✅ FR-9: WidgetNode Generation (WidgetCodexAgent + WidgetController)
- ✅ FR-11: Connection Types (TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN)
- 🔄 FR-8: Dynamic Tool Development (частично — TransformCodexAgent/WidgetCodexAgent покрывает code generation)
- 🔄 FR-12: Dynamic Form Generation (концепт)
- ⏳ FR-13: Public Data Discovery & Integration (DiscoveryAgent — базовый, без внешних датасетов)

**Дата завершения**: 2026-04-15

---

## Фаза 3: Интеграция и тестирование

**Статус**: Планируется

**Задачи**:
- [ ] Интеграционное тестирование
- [ ] Тестирование производительности
- [ ] Устранение критических багов
- [ ] Подготовка документации для пользователей

**Дата завершения**: 2026-04-30

---

## Фаза 4: Развертывание и оптимизация

**Статус**: Планируется

**Задачи**:
- [ ] Подготовка production окружения
- [ ] Развертывание
- [ ] Мониторинг и логирование
- [ ] Оптимизация производительности

**Дата завершения**: 2026-05-31

---

## Фаза 5: Collaborative Features & Marketplace

**Статус**: Планируется  
**Приоритет**: Must Have  
**Дата начала**: 2026-06-01

**Задачи**:
- [ ] **FR-14: Collaborative Annotations & Comments**
  - Widget comments с @mentions
  - Thread discussions
  - AI участие в комментариях (@AI)
  - Visual annotations (arrows, highlights, circles)
  - Real-time notifications
- [ ] **FR-15: Widget Templates Marketplace**
  - Публичная библиотека шаблонов
  - One-click import
  - Рейтинги и отзывы
  - AI-powered recommendations
  - Premium templates (монетизация)
- [ ] **FR-16: Interactive Widget Drill-Downs**
  - Click-to-drill на элементах графиков
  - Auto-filter generation
  - Breadcrumb navigation
  - Multi-level drill-down paths
  - AI drill-down suggestions

**Дата завершения**: 2026-07-31

---

## Фаза 6: Enterprise Features

**Статус**: Планируется  
**Приоритет**: Should Have  
**Дата начала**: 2026-08-01

**Задачи**:
- [ ] **FR-17: Smart Data Lineage & Impact Analysis**
  - Визуализация data lineage (DAG)
  - Impact analysis для изменений
  - Historical tracking
  - AI root cause analyzer
  - Dependency mapping
- [ ] **FR-18: Export & Embedding System**
  - Multiple formats: PDF, PowerPoint, PNG, SVG, HTML
  - Web embedding (iframe, widget snippet)
  - Public share links
  - Access control (public/private/password)
  - Embed analytics
- [ ] **FR-19: Voice Input & Natural Language**
  - Voice-to-text (Web Speech API)
  - Multi-language support
  - Hands-free presentation mode
  - Voice commands для navigation
  - Text-to-speech responses

**Дата завершения**: 2026-09-30

---

## Фаза 7: AI & Automation

**Статус**: Планируется  
**Приоритет**: Should Have  
**Дата начала**: 2026-10-01

**Задачи**:
- [ ] **FR-20: Automated Report Generation & Scheduling**
  - AI report writer agent
  - Scheduled reports (daily/weekly/monthly)
  - Multiple formats (PDF, PPTX, Email)
  - Multi-channel delivery (Email, Slack, Teams)
  - Dynamic content generation
- [ ] **FR-21: AI-Powered Data Quality Monitor**
  - Auto-detection проблем с данными
  - Quality metrics (completeness, accuracy, consistency)
  - Real-time alerts
  - AI recommendations
  - Auto-fix для простых проблем

**Дата завершения**: 2026-11-30

---

## Будущие улучшения (Post-MVP)

### Performance & Scale
- CDN для статических ассетов
- Redis caching layer
- Database query optimization
- Horizontal scaling support

### Security & Compliance
- Row-level security
- Data masking для sensitive fields
- Audit logs
- GDPR compliance
- SSO integration (SAML, OAuth)

### Mobile Experience
- React Native приложение
- Touch-optimized UI
- Offline mode с sync
- Push notifications

### Advanced Analytics
- Predictive analytics agent
- Anomaly detection
- What-if scenarios
- ML model integration

### Integration Hub
- Pre-built connectors:
  - Google Analytics, Mixpanel, Amplitude
  - Stripe, PayPal
  - Shopify, WooCommerce
  - Salesforce, HubSpot
  - AWS CloudWatch, Azure Monitor

---

**Последнее обновление**: 2026-02-06
