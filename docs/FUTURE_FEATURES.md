# Планируемые функции (Future Features)

Сводный документ планируемых, но ещё не реализованных функций GigaBoard. Организован по фазам из [ROADMAP.md](./ROADMAP.md).

---

## Фаза 2: MVP (в работе)

### FR-8: Dynamic Tool System

AI-агенты создают, тестируют и выполняют инструменты (Python-скрипты) по запросу. Sandbox-исполнение с валидацией безопасности. Частично покрыто TransformCodexAgent и WidgetCodexAgent.

### FR-12: Dynamic Form Generation

AI автоматически генерирует интерактивные формы ввода в процессе диалога — обнаруживает источники данных (БД, файлы, API), создаёт форму подключения с условной логикой полей. Включает ручной режим выбора источника данных (Manual Data Source Selection).

### User Onboarding

AI-first онбординг: 3 клика до первой визуализации, <1 мин до результата. Пустой canvas с направляющими действиями (загрузить файл, подключить API/БД, спросить AI). Прогрессивное раскрытие от простого к сложному.

### Project Structure & Navigation

Организация вокруг сущности "Проект": несколько досок, общие источники данных, артефакты (запросы, датасеты, шаблоны виджетов), роли пользователей, версионирование с diff и rollback.

---

## Фаза 5: Collaborative Features & Marketplace

### FR-14: Collaborative Annotations & Comments

CommentNode как полноценный узел на канвасе с COMMENT edges. @mentions пользователей и @AI, thread discussions, visual annotations (стрелки, выделения, круги), real-time синхронизация через Socket.IO.

### FR-15: Template Marketplace

Публичная библиотека шаблонов SourceNode, ContentNode, WidgetNode, трансформаций и досок. One-click import, рейтинги и отзывы, AI-рекомендации, premium шаблоны для монетизации.

### FR-16: Interactive Widget Drill-Down

Click-to-drill на элементах графиков для генерации отфильтрованных дочерних виджетов. Breadcrumb навигация, многоуровневые пути (категория → продукт → транзакция), AI-предложения по drill-down.

---

## Фаза 6: Enterprise Features

### FR-17: Smart Data Lineage & Impact Analysis

DAG-визуализация потоков данных (SourceNode → ContentNode → WidgetNode). Impact analysis "что сломается, если изменить этот узел?", исторический трекинг, AI root-cause debugging.

### FR-18: Export & Embedding System

Экспорт досок/виджетов в PDF, PowerPoint, PNG, SVG, HTML, JSON. Iframe-встраивание виджетов с публичным/приватным/парольным доступом, live обновления данных, аналитика встраиваний.

### FR-19: Voice Input & Natural Language

Voice-to-text через Web Speech API (+ Whisper fallback), мультиязычность (RU/EN/ZH/ES), hands-free режим презентации, text-to-speech для ответов AI, понимание голосовых команд.

---

## Фаза 7: AI & Automation

### FR-20: Automated Report Generation & Scheduling

AI Report Writer для executive summaries. Запланированные отчёты (ежедневно/еженедельно/ежемесячно) в PDF, PPTX, HTML Email. Мультиканальная доставка: Email, Slack, Teams, Telegram.

### FR-21: AI-Powered Data Quality Monitor

Автоматическое обнаружение проблем с данными по 5 измерениям (completeness, accuracy, consistency, timeliness, validity). Real-time алерты, AI рекомендации по исправлению, auto-fix для простых проблем.

---

## Post-MVP улучшения

### Performance & Scale
- CDN для статических ассетов
- Redis caching layer
- Horizontal scaling

### Security & Compliance
- Row-level security, data masking
- Audit logs, GDPR compliance
- SSO (SAML, OAuth)

### Mobile
- React Native приложение
- Touch-optimized UI
- Offline mode + sync

### Advanced Analytics
- Predictive analytics
- Anomaly detection
- What-if scenarios
- ML model integration

### Integration Hub
- Google Analytics, Mixpanel, Amplitude
- Stripe, PayPal
- Shopify, WooCommerce
- Salesforce, HubSpot
- AWS CloudWatch, Azure Monitor

---

> **Примечание**: Подробные спецификации исходных документов (DB schemas, UI mockups, API designs) сохранены в `docs/history/`.
