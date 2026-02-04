# Дорожная карта разработки

## Фаза 1: Планирование и документация ✓

**Статус**: В процессе

**Задачи**:
- [x] Определить требования
- [x] Спроектировать архитектуру
- [ ] Утвердить документацию (README/ARCHITECTURE/SPECIFICATIONS/API)
- [ ] Подготовить окружение разработки (.venv, базовые requirements/lockfiles)

**Дата завершения**: 2026-02-15

---

## Фаза 2: Разработка MVP

**Статус**: В процессе

**Задачи**:
- [ ] Frontend: канвас на React Flow, Zustand state, Socket.IO клиент
- [ ] Backend: FastAPI + Socket.IO сервер, CRUD бордов/виджетов
- [x] Настроить PostgreSQL + SQLAlchemy, Redis для pub/sub
- [x] **AI Multi-Agent System**: Planner, Analyst, Developer, Researcher, Executor, Reporter, Transformation, Data Discovery
- [x] **Adaptive Planning**: Интеллектуальное перепланирование с GigaChat после каждого успешного шага
- [x] **AI-Powered Error Evaluation**: Умная классификация ошибок для retry/replan/abort/continue
- [ ] **🆕 Source-Content Node Architecture**: Разделение источников данных и результатов обработки
  - [ ] SourceNode (file, database, api, prompt, stream)
  - [ ] ContentNode (text + N tables)
  - [ ] Streaming support с архивированием
  - [ ] Migration с DataNode
- [ ] **Form Generator Agent**: динамическая генерация форм ввода
- [ ] **Data Discovery Agent**: поиск публичных датасетов (Kaggle, OECD, World Bank)
- [ ] **Data Source Scanner**: автопоиск данных (БД, файлы, API, Cloud)
- [ ] **Smart Suggestions Engine**: умные подсказки на основе анализа данных
- [ ] **Dynamic Form Components**: React компоненты с conditional logic
- [ ] **Public Data Connectors**: интеграция с Kaggle, OECD, World Bank, Yahoo Finance
- [ ] Интеграция с GigaChat API
- [ ] Написать юнит- и интеграционные тесты (pytest, Vitest)

**Ключевые фичи MVP**:
- ✅ FR-1 до FR-6: Базовая доска + AI Assistant Panel
- ✅ FR-7: Multi-Agent System (8 агентов включая Data Discovery)
- ✅ FR-8: Dynamic Tool Development
- ✅ FR-12: Dynamic Form Generation
- ✅ FR-13: Public Data Discovery & Integration
- 🆕 **FR-14: Source-Content Node System** (10-15 дней разработки)

**Дата завершения**: 2026-04-15 (обновлено с учётом новой фичи)

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

**Последнее обновление**: 2026-01-24
