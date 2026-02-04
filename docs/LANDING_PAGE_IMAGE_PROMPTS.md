# Landing Page Image Generation Prompts для NanoBanana

**Проект**: GigaBoard — AI-Powered Analytics Platform  
**Дата**: 30 января 2026  
**Назначение**: Детальные промпты для генерации декоративных иллюстраций лендинга

---

## 🎯 Общий контекст проекта

**GigaBoard** — это платформа для создания data pipelines с AI-ассистентом на бесконечном полотне (canvas). Ключевые концепции:

### Архитектура узлов (Source-Content Node Architecture)
- **SourceNode** — источники данных (файлы, БД, API, AI-промпты, streaming данные)
- **ContentNode** — результаты обработки (текстовые резюме + структурированные таблицы)
- **WidgetNode** — интерактивные визуализации (HTML/CSS/JS, генерируются AI)
- **CommentNode** — аннотации и комментарии

### Типы связей (Edges)
- **EXTRACT** — извлечение данных из источника (SourceNode → ContentNode)
- **TRANSFORMATION** — преобразование данных (ContentNode → ContentNode)
- **VISUALIZATION** — визуализация данных (ContentNode → WidgetNode)
- **COMMENT** — комментирование любых узлов
- **REFERENCE**, **DRILL_DOWN** — ссылки и детализация

### Multi-Agent System
9 специализированных AI агентов, работающих через Redis Message Bus:
1. **Orchestrator** — координация и приоритизация
2. **Planner Agent** — создание и адаптация планов выполнения
3. **Search Agent** — поиск данных в интернете (Google/Bing API)
4. **Researcher Agent** — загрузка и извлечение контента из веб-страниц
5. **Analyst Agent** — анализ данных и генерация инсайтов
6. **Transformation Agent** — создание Python/SQL трансформаций
7. **Reporter Agent** — генерация WidgetNode визуализаций (HTML/CSS/JS с нуля)
8. **Developer Agent** — создание custom инструментов для агентов
9. **Critic Agent** — валидация результатов и выявление проблем

### Уникальные возможности
- **Natural Language Interface** — формулируйте запросы на естественном языке
- **Adaptive Planning** — GigaChat перепланирует выполнение на основе результатов
- **Search → Research → Analyze Pattern** — глубокий анализ данных из интернета (40x больше данных чем snippets)
- **Real-time Streaming** — поддержка WebSocket/SSE источников с аккумуляцией и архивированием
- **Automated Data Pipeline** — от источника до готовой визуализации за минуты
- **No-Code Analytics** — визуальный интерфейс для сложных трансформаций

---

## 🎨 Промпты для генерации изображений

### 1. Hero Section Background Illustration

**Назначение**: Фоновое изображение для главной секции лендинга, создающее атмосферу современной AI-powered data analytics платформы.

**Композиция**: Горизонтальный формат (16:9 или 21:9), центральная композиция с фокусом в центре и расходящимися элементами.

**Prompt для NanoBanana**:

```
Abstract data analytics platform illustration, futuristic and professional style.

Central focus: Large holographic AI brain with glowing neural network connections, 
floating in the center, emitting bright Sber Green (#21A038) light rays.

Surrounding elements flowing from center outward:
- Data source icons (database cylinders, file folders, API endpoints, cloud storage)
  positioned in left third, connected with glowing green data streams
- Flowing particle streams (#21A038 green) moving from sources through transformation nodes
- Abstract geometric nodes (hexagons, circles) representing data processing pipeline
- Interactive dashboard widgets floating in right third: 
  * Line charts with animated curves
  * Data tables with glowing rows
  * KPI metrics cards with numbers
  * Pie charts with segments
- Connection lines between all elements (thin, glowing, #21A038 with gradient fade)

Visual style:
- Dark gradient background (from #0a0a0a at edges to #1a1a1a in center)
- Sber Green (#21A038) as primary color for all glowing elements
- Subtle secondary glow effects (#2ABB4A lighter green for highlights)
- Isometric 3D perspective with depth of field blur on distant elements
- Modern tech aesthetic with glass morphism and transparency effects
- Motion blur on data streams to suggest real-time flow
- Particle effects around nodes (small glowing dots)
- Professional and clean, not too busy, good negative space

Technical requirements:
- Resolution: 2400x1200px minimum for responsive web
- Format: PNG with transparency support for overlay effects
- Color mode: RGB for screen display
- Optimization: suitable for web (under 500KB compressed)

Mood: Innovative, powerful, intelligent, futuristic, professional, trustworthy
Atmosphere: High-tech data center meets AI innovation lab
Key feeling: "From question to insight with one prompt"
```

---

### 2. Core Features — Data Pipeline Flow Illustration

**Назначение**: Концептуальная визуализация data pipeline для секции Core Features, демонстрирующая путь данных от источника до визуализации.

**Композиция**: Горизонтальный flow слева направо, показывающий этапы трансформации данных.

**Prompt для NanoBanana**:

```
Conceptual illustration of automated data pipeline, modern tech illustration style.

Left to right flow visualization:

Left section (Data Sources):
- Stack of 3-4 source icons: database cylinder (#21A038 outline), 
  CSV file folder, API cloud symbol, streaming wave icon
- Each icon has soft glow and subtle animation lines
- Icons arranged vertically with slight offset for depth

Middle section (Transformation):
- Flowing green (#21A038) particle stream from sources
- Abstract transformation nodes (geometric shapes):
  * Hexagonal node labeled "EXTRACT" with data extraction symbols
  * Circular node labeled "TRANSFORM" with Python/SQL code snippets visible
  * Diamond node labeled "ANALYZE" with AI brain icon
- Particles morph and multiply as they pass through nodes
- Glowing connection lines between nodes (bezier curves)
- Small floating icons around nodes: Python logo, SQL symbol, AI chip

Right section (Visualizations):
- Three floating widget cards showing final results:
  * Top card: Line chart with upward trend, animated green line
  * Middle card: Data table with glowing highlighted rows
  * Bottom card: KPI metrics dashboard with large numbers
- Cards have glass morphism effect (semi-transparent with backdrop blur)
- Subtle shadow and glow around cards

Visual effects:
- Data particles: small glowing dots (#21A038) flowing along streams
- Motion blur on particles to show movement direction
- Gradient fade on connection lines (bright at nodes, dim between)
- Pulsing glow effect on transformation nodes (breathing animation feel)

Background:
- Dark gradient (from #0d0d0d at top to #1a1a1a at bottom)
- Subtle grid pattern overlay (very faint, #21A038 at 5% opacity)
- Depth of field: sharp focus on pipeline, slight blur on background elements

Color palette:
- Primary: Sber Green #21A038 for all active elements
- Secondary: Lighter green #2ABB4A for highlights and glow effects
- Accent: White #FFFFFF for text and icons (80% opacity)
- Background: Dark grays #0d0d0d to #1a1a1a

Technical style:
- Isometric 3D perspective with 30-degree angle
- Clean geometric shapes with rounded corners
- Professional tech illustration (not cartoony)
- Balance between abstract and recognizable elements

Resolution: 1600x900px minimum
Format: PNG with transparency
Mood: Automated, intelligent, seamless, efficient
```

---

### 3. Streaming Data — Real-Time Flow Visualization

**Назначение**: Иллюстрация real-time streaming данных для секции Streaming, показывающая динамичность и live-характер обновлений.

**Композиция**: Энергичная композиция с эффектом движения и пульсации.

**Prompt для NanoBanana**:

```
Dynamic real-time data streaming visualization, futuristic cyberpunk aesthetic.

Main composition:

Left side (IoT Sources):
- 5-6 small IoT sensor icons arranged in arc:
  * Temperature sensor (thermometer icon)
  * Network router (wifi symbol)
  * Server rack (stacked rectangles)
  * Mobile device (smartphone outline)
  * Industrial machine (gear icon)
- Each sensor emits pulsing green (#21A038) signal waves
- Animated concentric circles radiating from sensors (like sonar)

Center (Data Stream):
- Massive flowing river of data particles:
  * Thousands of small glowing dots (#21A038 green)
  * Particles of varying sizes creating depth
  * Flow speed indicated by motion blur trails
  * Particles converge from multiple sensors into single stream
- Glowing data packets (small rectangular shapes) with binary code visible
- WebSocket connection visualization: pulsing line connecting sensors to dashboard
- Lightning bolt accents showing high-speed transmission (#2ABB4A bright green)

Right side (Live Dashboard):
- Large animated chart showing real-time updates:
  * Line graph with newest data point highlighted and glowing
  * Graph line pulses with each new data point
  * Time axis shows "LIVE" indicator badge (red dot)
  * Y-axis values updating with smooth animation
- Floating counter displays:
  * "Messages/sec: 1,247" with incrementing numbers
  * "Active Streams: 5" with pulsing badge
  * "Latency: 23ms" with green checkmark
- Replay controls UI at bottom:
  * Play/Pause button (glowing green when active)
  * Timeline scrubber with playhead
  * Speed control (1x, 2x, 5x options)

Visual effects:
- Heavy use of neon glow (#21A038 primary, #2ABB4A highlights)
- Motion blur on fast-moving particles (horizontal trails)
- Pulsing animation on all "live" elements (breathing effect)
- Scan line effect across dashboard (subtle horizontal lines moving down)
- Chromatic aberration on brightest elements (slight RGB split)
- Particle trails fading from bright to transparent

Background:
- Very dark gradient (from #050505 at edges to #0d0d0d at center)
- Faint hexagonal grid pattern in background (cyberpunk aesthetic)
- Atmospheric fog/haze effect adding depth
- Subtle green glow emanating from data stream illuminating surroundings

Technical style:
- Cyberpunk/futuristic aesthetic (think Blade Runner meets data center)
- High contrast: very bright glowing elements on very dark background
- Lots of energy and movement
- Professional yet exciting, not too chaotic

Color scheme:
- Primary: Neon Sber Green #21A038
- Highlight: Bright Green #2ABB4A (almost electric)
- Accent: Cyan #00FFFF for secondary indicators (5% usage)
- Warning: Subtle Orange #FF6B35 for latency/alerts (minimal)
- Background: Deep Black #050505 to #0d0d0d

Resolution: 1400x1000px
Format: PNG
Mood: Real-time, high-speed, live, dynamic, powerful, cutting-edge
Key impression: "Data flows at the speed of light"
```

---

### 4. Use Cases — Professional Character Scenarios

**Назначение**: Концептуальные иллюстрации профессионалов, работающих с данными, для секции Use Cases. Всего 4 персонажа для разных ролей.

**Общие параметры для всех персонажей**:
- Формат: квадратный или 4:3 портретный
- Стиль: профессиональная tech-иллюстрация, не фотореалистичная, но узнаваемая
- Цветовая схема: Sber Green акценты на всех элементах
- Композиция: персонаж в центре, аналитические элементы вокруг
- Настроение: уверенность, профессионализм, сосредоточенность

#### 4.1. Product Manager Scenario

**Prompt для NanoBanana**:

```
Professional Product Manager character working with data analytics, modern tech illustration.

Character (central focus):
- Young professional (25-35 years old), confident expression
- Business casual attire: shirt/blouse, smart appearance
- Standing pose with hand gesturing towards floating data visualization
- Diverse appearance (can be any ethnicity/gender, inclusive representation)
- Stylized illustration style (not photorealistic, clean vector-like)

Surrounding analytics elements:
- Floating dashboard to character's right:
  * Product metrics cards (MAU, Retention, Conversion)
  * Small line chart showing growth trend (green upward line)
  * Funnel visualization (stages with percentages)
- Data nodes connected with lines (mind map style):
  * "User Feedback" node with star ratings
  * "A/B Test Results" node with split icons
  * "Feature Adoption" node with percentage
- Glowing Sber Green (#21A038) connection lines between elements
- Small floating icons: lightbulb (ideas), target (goals), chart (metrics)

Visual style:
- Modern office setting suggested in background (blurred glass walls, minimal)
- Professional tech illustration (similar to SaaS product marketing materials)
- Clean lines, geometric shapes, organized composition
- Sber Green (#21A038) used for all data elements and accents
- Neutral clothing colors (grays, blues) to not distract from data elements
- Confident body language: open stance, engaged with data

Color palette:
- Character: Neutral tones (light skin, blue/gray clothing)
- Data elements: Sber Green #21A038 primary
- Highlights: Lighter green #2ABB4A for emphasis
- Background: Light gradient #f5f5f5 to #ffffff (minimal, not distracting)
- Text on cards: Dark gray #2d2d2d

Resolution: 800x1000px (portrait)
Format: PNG with transparency
Mood: Strategic, data-driven, professional, confident
Character archetype: Modern product leader making informed decisions
```

#### 4.2. Data Scientist Scenario

**Prompt для NanoBanana**:

```
Professional Data Scientist character analyzing data, tech illustration style.

Character:
- Professional (28-40 years old), focused analytical expression
- Casual tech attire: hoodie or casual shirt, glasses (optional)
- Seated pose or standing with arms crossed, looking at visualizations
- Confident technical expert appearance
- Diverse, inclusive representation

Analytics environment:
- Large code editor window floating to one side:
  * Python code snippets visible (pandas, matplotlib)
  * Syntax highlighting with green accents
- Statistical visualizations:
  * Scatter plot with regression line (green)
  * Distribution histogram
  * Correlation matrix heatmap (green gradient)
- Machine learning elements:
  * Neural network diagram (nodes and connections)
  * Model accuracy metrics (95.2% in large green text)
  * Feature importance bar chart
- Jupyter notebook interface elements in background
- Floating formula/equation symbols (mathematical notation)

Tech lab atmosphere:
- Dark theme aesthetic (data science preference)
- Multiple monitors suggested in background (blurred)
- Coffee cup or water bottle detail (relatable touch)
- Organized chaos of a data scientist workspace

Visual style:
- Professional tech illustration with slight personality
- More technical details than Product Manager version
- Darker overall palette (data scientists prefer dark mode)
- Sber Green highlights on all active/important data elements
- Glowing screen effects illuminating character's face subtly

Color palette:
- Character: Neutral casual tones
- Code/data: Sber Green #21A038 for active elements
- Background: Dark gradient #1a1a1a to #2d2d2d
- Screen glow: Soft green illumination
- Accent: Lighter green #2ABB4A for highlights

Resolution: 800x1000px
Format: PNG
Mood: Analytical, deep-thinking, technical expert, methodical
Character archetype: Data scientist uncovering insights from complex data
```

#### 4.3. DevOps Engineer Scenario

**Prompt для NanoBanana**:

```
DevOps Engineer character monitoring system performance, professional tech illustration.

Character:
- Technical professional (25-40 years old), alert focused expression
- Casual tech attire: t-shirt or polo, practical appearance
- Standing pose monitoring multiple data streams
- Confident technical operator appearance
- Diverse representation

Monitoring environment:
- Multiple monitoring dashboards floating around:
  * Server health status grid (green checkmarks, one yellow warning)
  * CPU/Memory usage graphs (real-time lines)
  * Network traffic visualization (flowing data)
  * Docker container status list
  * Kubernetes cluster diagram
- Alert notification badges (mostly green, one amber)
- Deployment pipeline visualization:
  * Git → Build → Test → Deploy stages
  * Green checkmarks at each completed stage
- System architecture diagram in background:
  * Load balancer icon
  * Multiple server icons in grid
  * Database cluster
  * All connected with green network lines

Technical aesthetic:
- Dark theme (ops room/NOC atmosphere)
- Multiple glowing screens creating ambient green light
- Terminal windows with green text in background
- System logs scrolling (matrix-style effect, subtle)
- Uptime percentage displayed prominently: "99.9%"

Visual style:
- Professional operations center feel
- More dynamic than other scenarios (sense of real-time monitoring)
- Glowing screens and panels
- Sber Green for "healthy" status indicators
- Slight amber/yellow for warnings (minimal, not alarming)

Color palette:
- Character: Practical neutral tones
- Healthy status: Sber Green #21A038
- Warning status: Amber #FFA500 (sparingly)
- Background: Very dark #0d0d0d to #1a1a1a
- Screen glow: Green ambient light
- Network lines: Glowing green connections

Resolution: 800x1000px
Format: PNG
Mood: Vigilant, reliable, technical mastery, 24/7 readiness
Character archetype: DevOps engineer keeping systems running smoothly
```

#### 4.4. Student/Researcher Scenario

**Prompt для NanoBanana**:

```
Student or Academic Researcher analyzing data for study, educational tech illustration.

Character:
- Young student/researcher (20-30 years old), curious engaged expression
- Casual academic attire: sweater or casual shirt, comfortable style
- Seated at desk or leaning forward examining data with interest
- Eager learning body language
- Diverse representation

Academic data analysis environment:
- Research paper elements:
  * Floating document pages with charts
  * Academic journal article excerpts
  * Citation connections (network of references)
- Study data visualizations:
  * Survey results bar chart (green bars)
  * Research timeline Gantt chart
  * Sample size statistics
  * P-value and statistical significance indicators
- Study materials:
  * Notebook with handwritten notes
  * Textbook or tablet device
  * Scientific calculator or statistics software UI
- Learning resources:
  * Video tutorial playing in corner
  * Stack of data science books (subtle background)
  * Online course interface

Academic workspace:
- Bright, optimistic atmosphere (learning environment)
- Library or study space suggested in background
- Natural light feel (unlike dark DevOps environment)
- Organized study materials
- Motivational vibe (discovery and learning)

Visual style:
- Most approachable and friendly of all scenarios
- Lighter, more optimistic color palette
- Educational tech illustration style
- Sber Green for data insights and "aha moments"
- Warmer overall tone than corporate scenarios

Color palette:
- Character: Warm casual tones, friendly appearance
- Data elements: Sber Green #21A038 for insights
- Background: Light gradient #fafafa to #f0f0f0
- Accent: Warm yellow #FFC107 for "discovery" moments (10%)
- Text: Medium gray #424242
- Highlights: Lighter green #2ABB4A

Resolution: 800x1000px
Format: PNG
Mood: Curious, learning, discovery, accessible, empowering
Character archetype: Student conducting research and learning data skills
Key message: "Data analytics accessible to everyone, including students"
```

---

## 🎨 Стилистические guidelines для всех изображений

### Общие принципы
1. **Sber Green (#21A038) как ключевой цвет** — используется для всех активных элементов, связей, подсветок
2. **Профессиональный tech стиль** — современные SaaS продукты, не игровая графика
3. **Баланс абстракции и узнаваемости** — элементы должны быть понятны, но стилизованы
4. **Глубина через слои** — передний, средний, задний план с blur для глубины
5. **Движение и энергия** — motion blur, particle effects для создания ощущения "живой" системы

### Цветовая палитра (строгое соблюдение)
- **Primary**: Sber Green #21A038 (60-70% использования в активных элементах)
- **Secondary**: Light Green #2ABB4A (20-30% для highlights и glow)
- **Neutral**: Темные градиенты #050505 - #1a1a1a для фонов
- **Accent**: Белый #FFFFFF для текста (80% opacity), минимальные touches других цветов

### Технические требования
- **Разрешение**: Минимум 1200px по наименьшей стороне для качества
- **Формат**: PNG с поддержкой прозрачности
- **Оптимизация**: Сжатие для веб (под 500KB где возможно)
- **Адаптивность**: Композиция должна читаться при масштабировании

### Ключевые визуальные эффекты
- **Glow effects** — мягкое свечение вокруг активных элементов (#21A038 с blur)
- **Motion blur** — на движущихся частицах для передачи скорости
- **Glass morphism** — прозрачные панели с backdrop blur для modern UI
- **Particle systems** — маленькие светящиеся точки для data streams
- **Depth of field** — размытие дальних элементов для фокуса на главном

---

## 📋 Чек-лист перед генерацией

Перед отправкой промпта в NanoBanana проверьте:

- [ ] Промпт содержит точный hex код Sber Green (#21A038)
- [ ] Указано разрешение и формат изображения
- [ ] Описана композиция (расположение элементов)
- [ ] Указан желаемый mood/atmosphere
- [ ] Перечислены ключевые визуальные эффекты
- [ ] Указаны технические требования (размер файла, оптимизация)
- [ ] Промпт на английском языке (NanoBanana лучше понимает English)
- [ ] Избегайте слишком сложных композиций (лучше несколько простых элементов чем десятки мелких)

---

## 🔄 Итерации и корректировки

После генерации первой версии возможны корректировки:

### Типичные корректировки
1. **Цветовой баланс** — если зелёного слишком много или мало
2. **Детализация** — упрощение перегруженных композиций
3. **Контраст** — усиление различия между передним и задним планами
4. **Glow intensity** — уменьшение/усиление эффектов свечения
5. **Композиционный баланс** — перераспределение visual weight

### Feedback template для корректировок
```
[Image name] - Iteration 2

Changes needed:
- Reduce glow intensity by 30% (too bright)
- Move AI brain element 20% higher in composition
- Add more negative space in right third
- Darken background gradient (currently too light)
- Increase particle density in data stream by 50%

Keep as is:
- Sber Green color tone (perfect)
- Overall composition structure
- Character pose and expression
```

---

**Конец документа**

*Для вопросов по промптам или корректировкам обращайтесь к документации GigaBoard:*
- `docs/ARCHITECTURE.md` — архитектура системы
- `docs/SOURCE_CONTENT_NODE_CONCEPT.md` — концепция узлов данных
- `docs/MULTI_AGENT_SYSTEM.md` — мультиагентная система
- `docs/WIDGETNODE_GENERATION_SYSTEM.md` — генерация визуализаций
