# Template Marketplace — SourceNode & Transformation Templates

**Статус**: 🚧 Планируется  
**Приоритет**: Must Have (Phase 3)  
**Дата создания**: 24 января 2026  
**Обновлено**: 24 января 2026 (Source-Content architecture)

---

## 📋 Обзор

**Template Marketplace** — открытая библиотека готовых шаблонов для ускорения аналитической работы. Включает шаблоны для **SourceNode/ContentNode**, **WidgetNode**, **трансформаций** и полных **Board Templates**.

### 🆕 Новая архитектура: Data-Centric Canvas

Marketplace теперь поддерживает три типа узлов:
- **SourceNode** — шаблоны источников данных (SQL, API, CSV)
- **WidgetNode** — шаблоны визуализаций (созданные AI из ContentNode)
- **TransformationNode** — переиспользуемые трансформации (Python pandas код)

### Ключевые возможности
- 📚 **Публичная библиотека**: Тысячи готовых шаблонов SourceNode, ContentNode, WidgetNode, Transformations
- ⚡ **One-click import**: Импорт шаблона в свою доску одним кликом
- 🎨 **Категории**: 
  - **Data Sources**: PostgreSQL, MySQL, MongoDB, API, CSV
  - **Transformations**: Join, Filter, Aggregate, Pivot, Time-series
  - **Visualizations**: Charts, Tables, Maps, Dashboards
  - **Industries**: Finance, Marketing, Product, Operations, Sales, HR
- ⭐ **Рейтинги и отзывы**: Социальное доказательство качества
- 🔍 **Умный поиск**: AI-powered рекомендации шаблонов
- 💎 **Premium шаблоны**: Монетизация для создателей
- 🏆 **Конкурсы и награды**: Gamification для активных создателей
- 🔄 **Версионирование**: Шаблоны обновляются, пользователи получают уведомления

---

## 🏗️ Архитектура

### Database Schema

```python
class SourceNodeTemplate(Base):
    """Шаблон SourceNode в Marketplace"""
    __tablename__ = 'data_node_templates'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # Content
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(Enum(
        'sql_query', 'api_call', 'csv_upload', 'json_upload',
        'web_scraping', 'file_system', 'streaming'
    ))
    industry = Column(Enum(
        'finance', 'marketing', 'product', 'operations', 
        'sales', 'hr', 'engineering', 'analytics', 'other'
    ))
    
    # SourceNode configuration
    data_source_type = Column(String(50))  # 'postgresql', 'mysql', 'api', etc.
    query_template = Column(Text)  # SQL query with placeholders
    api_config = Column(JSONB)  # API endpoint, method, headers, etc.
    sample_data = Column(JSONB)  # Sample data for preview
    schema = Column(JSONB)  # Expected data schema
    
    # Parameters (placeholders in query)
    parameters = Column(JSONB)  # [{"name": "start_date", "type": "date", "default": "2024-01-01"}]
    
    # Metadata
    creator_id = Column(UUID, ForeignKey('users.id'))
    is_official = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    price = Column(Numeric(10, 2), nullable=True)
    
    # Engagement
    downloads_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    
    # Tags
    tags = Column(ARRAY(String))  # ['revenue', 'stripe', 'saas']
    
    # Requirements
    required_integrations = Column(ARRAY(String))  # ['stripe', 'google_analytics']
    required_permissions = Column(ARRAY(String))  # ['read:payments', 'write:customers']
    
    # Status
    status = Column(Enum('draft', 'published', 'archived'))
    published_at = Column(DateTime)
    
    # Versioning
    version = Column(String(20), default='1.0.0')
    changelog = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


class TransformationTemplate(Base):
    """Шаблон трансформации (TRANSFORMATION edge с Python кодом)"""
    __tablename__ = 'transformation_templates'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # Content
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(Enum(
        'join', 'filter', 'aggregate', 'pivot', 'unpivot',
        'time_series', 'window_function', 'custom'
    ))
    
    # Transformation code
    python_code = Column(Text, nullable=False)  # Pandas transformation
    input_schema = Column(JSONB)  # Expected input ContentNode schema
    output_schema = Column(JSONB)  # Expected output ContentNode schema
    
    # Parameters
    parameters = Column(JSONB)  # [{"name": "window_size", "type": "int", "default": 7}]
    
    # Example usage
    example_input = Column(JSONB)  # Sample input data
    example_output = Column(JSONB)  # Expected output data
    
    # Same engagement/metadata fields
    creator_id = Column(UUID, ForeignKey('users.id'))
    is_official = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    price = Column(Numeric(10, 2))
    
    downloads_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    
    tags = Column(ARRAY(String))
    status = Column(Enum('draft', 'published', 'archived'))
    version = Column(String(20), default='1.0.0')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


class WidgetNodeTemplate(Base):
    """Шаблон WidgetNode в Marketplace"""
    __tablename__ = 'widget_node_templates'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # Content
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(Enum(
        'chart_line', 'chart_bar', 'chart_pie', 'chart_scatter',
        'table', 'metric_card', 'map', 'heatmap', 'custom'
    ))
    industry = Column(Enum(
        'finance', 'marketing', 'product', 'operations', 
        'sales', 'hr', 'engineering', 'analytics', 'other'
    ))
    
    # WidgetNode config
    html_template = Column(Text)  # HTML with template variables
    css_template = Column(Text)  # CSS styling
    js_template = Column(Text)  # JavaScript for interactivity
    required_data_schema = Column(JSONB)  # Expected ContentNode schema
    
    # Preview
    thumbnail_url = Column(String(500))
    sample_data = Column(JSONB)  # For preview rendering
    
    # Same engagement/metadata fields
    creator_id = Column(UUID, ForeignKey('users.id'))
    is_official = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    price = Column(Numeric(10, 2))
    
    downloads_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    
    tags = Column(ARRAY(String))
    status = Column(Enum('draft', 'published', 'archived'))
    version = Column(String(20), default='1.0.0')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


class BoardTemplate(Base):
    """Шаблон доски (полный граф: SourceNode → Transformation → ContentNode → WidgetNode)"""
    __tablename__ = 'board_templates'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    industry = Column(String(100))
    
    # Configuration
    nodes = Column(JSONB)  # Array of SourceNode, ContentNode, WidgetNode, CommentNode configs
    edges = Column(JSONB)  # TRANSFORMATION, VISUALIZATION, COMMENT edges
    layout = Column(JSONB)  # Node positions on canvas
    
    # Preview
    thumbnail_url = Column(String(500))
    preview_images = Column(ARRAY(String))
    demo_url = Column(String(500))
    
    # Requirements
    required_integrations = Column(ARRAY(String))  # ['stripe', 'google_analytics']
    required_permissions = Column(ARRAY(String))
    
    # Same engagement/metadata fields
    creator_id = Column(UUID, ForeignKey('users.id'))
    is_official = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    price = Column(Numeric(10, 2))
    
    downloads_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    
    tags = Column(ARRAY(String))
    status = Column(Enum('draft', 'published', 'archived'))
    
    created_at = Column(DateTime, default=datetime.utcnow)


class TemplateReview(Base):
    """Отзыв на шаблон"""
    __tablename__ = 'template_reviews'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    template_id = Column(UUID)
    template_type = Column(Enum('data_node', 'transformation', 'widget_node', 'board'))
    user_id = Column(UUID, ForeignKey('users.id'))
    
    rating = Column(Integer)  # 1-5 stars
    review_text = Column(Text)
    
    # Helpfulness voting
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class TemplateDownload(Base):
    """Отслеживание скачиваний"""
    __tablename__ = 'template_downloads'
    
    id = Column(UUID, primary_key=True, default=uuid4)
    template_id = Column(UUID)
    template_type = Column(Enum('data_node', 'transformation', 'widget_node', 'board'))
    user_id = Column(UUID, ForeignKey('users.id'))
    board_id = Column(UUID, ForeignKey('boards.id'))
    
    downloaded_at = Column(DateTime, default=datetime.utcnow)
```

---

## 🎨 UI Components

### Marketplace Categories

```typescript
const MARKETPLACE_CATEGORIES = {
  dataSources: {
    name: 'Data Sources',
    icon: '🗄️',
    subcategories: [
      'SQL Queries',
      'API Calls',
      'CSV Import',
      'Web Scraping',
      'Streaming Data'
    ]
  },
  transformations: {
    name: 'Transformations',
    icon: '🔄',
    subcategories: [
      'Join & Merge',
      'Filter & Clean',
      'Aggregate',
      'Pivot & Unpivot',
      'Time Series',
      'Window Functions'
    ]
  },
  visualizations: {
    name: 'Visualizations',
    icon: '📊',
    subcategories: [
      'Line Charts',
      'Bar Charts',
      'Tables',
      'Maps',
      'Metrics Cards',
      'Custom HTML'
    ]
  },
  boards: {
    name: 'Complete Boards',
    icon: '🎨',
    subcategories: [
      'Finance Dashboards',
      'Marketing Analytics',
      'Product Metrics',
      'Sales Funnels',
      'HR Analytics'
    ]
  }
};
```

---

## 📦 Example Templates

### 1. SourceNode Template: Stripe Monthly Revenue

```json
{
  "name": "Stripe Monthly Revenue (MRR)",
  "description": "Fetch monthly recurring revenue from Stripe",
  "category": "api_call",
  "industry": "finance",
  "data_source_type": "stripe_api",
  "api_config": {
    "endpoint": "https://api.stripe.com/v1/subscriptions",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer ${STRIPE_API_KEY}"
    },
    "params": {
      "status": "active",
      "limit": 100
    }
  },
  "query_template": null,
  "parameters": [
    {
      "name": "start_date",
      "type": "date",
      "default": "2024-01-01",
      "description": "Start date for data"
    }
  ],
  "sample_data": {
    "columns": ["month", "mrr", "customer_count"],
    "rows": [
      ["2024-01", 45000, 120],
      ["2024-02", 48000, 125]
    ]
  },
  "schema": {
    "month": "string",
    "mrr": "number",
    "customer_count": "number"
  },
  "tags": ["stripe", "revenue", "saas", "mrr"],
  "required_integrations": ["stripe"],
  "is_official": true,
  "is_premium": false
}
```

### 2. Transformation Template: 7-Day Moving Average

```json
{
  "name": "7-Day Moving Average",
  "description": "Calculate rolling 7-day average for time series data",
  "category": "time_series",
  "python_code": "import pandas as pd\n\ndef transform(df, **params):\n    window_size = params.get('window_size', 7)\n    value_column = params.get('value_column', 'value')\n    \n    df_sorted = df.sort_values('date')\n    df_sorted['rolling_avg'] = df_sorted[value_column].rolling(window=window_size).mean()\n    \n    return df_sorted",
  "input_schema": {
    "required_columns": ["date", "value"],
    "date": "datetime",
    "value": "number"
  },
  "output_schema": {
    "columns": ["date", "value", "rolling_avg"],
    "date": "datetime",
    "value": "number",
    "rolling_avg": "number"
  },
  "parameters": [
    {
      "name": "window_size",
      "type": "int",
      "default": 7,
      "description": "Window size for rolling average"
    },
    {
      "name": "value_column",
      "type": "string",
      "default": "value",
      "description": "Column name to calculate average"
    }
  ],
  "example_input": {
    "rows": [
      {"date": "2024-01-01", "value": 100},
      {"date": "2024-01-02", "value": 110}
    ]
  },
  "example_output": {
    "rows": [
      {"date": "2024-01-01", "value": 100, "rolling_avg": null},
      {"date": "2024-01-07", "value": 110, "rolling_avg": 105}
    ]
  },
  "tags": ["time-series", "smoothing", "moving-average"],
  "is_official": true,
  "is_premium": false
}
```

### 3. Board Template: SaaS Metrics Dashboard

```json
{
  "name": "SaaS Metrics Dashboard",
  "description": "Complete dashboard: MRR, Churn, LTV, CAC",
  "industry": "finance",
  "nodes": [
    {
      "id": "dn1",
      "type": "SourceNode",
      "name": "Stripe Subscriptions",
      "template_id": "stripe_mrr_template_id"
    },
    {
      "id": "dn2",
      "type": "SourceNode",
      "name": "Churned Customers",
      "template_id": "stripe_churn_template_id"
    },
    {
      "id": "tn1",
      "type": "TransformationNode",
      "name": "Calculate Churn Rate",
      "template_id": "churn_rate_calculation_template_id"
    },
    {
      "id": "wn1",
      "type": "WidgetNode",
      "name": "MRR Chart",
      "template_id": "line_chart_template_id"
    },
    {
      "id": "wn2",
      "type": "WidgetNode",
      "name": "Churn Rate Card",
      "template_id": "metric_card_template_id"
    }
  ],
  "edges": [
    {
      "source": "dn1",
      "target": "wn1",
      "type": "VISUALIZATION"
    },
    {
      "source": "dn2",
      "target": "tn1",
      "type": "TRANSFORMATION"
    },
    {
      "source": "tn1",
      "target": "wn2",
      "type": "VISUALIZATION"
    }
  ],
  "layout": {
    "dn1": {"x": 100, "y": 100},
    "wn1": {"x": 400, "y": 100},
    "dn2": {"x": 100, "y": 300},
    "tn1": {"x": 250, "y": 300},
    "wn2": {"x": 400, "y": 300}
  },
  "required_integrations": ["stripe"],
  "tags": ["saas", "finance", "mrr", "churn"],
  "is_official": true,
  "is_premium": false
}
```

---

## 🔥 Popular Templates

### Data Sources
1. **PostgreSQL Sales Query** ⭐ 4.8 (2.1K downloads)
2. **Google Analytics Traffic** ⭐ 4.7 (1.8K downloads)
3. **Stripe Revenue API** ⭐ 4.9 (3.2K downloads)
4. **CSV Product Catalog** ⭐ 4.6 (900 downloads)

### Transformations
1. **Join Orders + Customers** ⭐ 4.9 (4.5K downloads)
2. **Remove Outliers (IQR)** ⭐ 4.7 (2.3K downloads)
3. **Pivot Sales by Region** ⭐ 4.8 (1.9K downloads)
4. **7-Day Moving Average** ⭐ 4.6 (3.1K downloads)

### Visualizations
1. **Revenue Line Chart** ⭐ 4.9 (5.2K downloads)
2. **Top 10 Products Table** ⭐ 4.7 (4.1K downloads)
3. **Conversion Funnel** ⭐ 4.8 (2.8K downloads)
4. **Geographic Heatmap** ⭐ 4.6 (1.5K downloads)

### Complete Boards
1. **SaaS Metrics Dashboard** ⭐ 5.0 (1.2K downloads)
2. **Marketing Attribution** ⭐ 4.8 (890 downloads)
3. **Product Analytics** ⭐ 4.7 (670 downloads)

---

## 🚀 Implementation Roadmap

### Phase 1: MVP (Month 1-2)
- [ ] Database models для SourceNode/ContentNode/Transformation/WidgetNode templates
- [ ] Marketplace browse page (категории, поиск, фильтры)
- [ ] Template detail modal
- [ ] Import functionality
- [ ] 20 официальных templates (по 5 каждого типа)

### Phase 2: Community (Month 3-4)
- [ ] User-submitted templates
- [ ] Review system
- [ ] Rating system
- [ ] Template versioning

### Phase 3: Premium (Month 5-6)
- [ ] Premium templates
- [ ] Creator earnings
- [ ] Analytics dashboard для создателей
- [ ] Featured templates carousel

---

## ✅ Success Metrics

- **Adoption**: 70%+ пользователей используют хотя бы 1 template
- **Engagement**: Average 5 templates/user в первый месяц
- **Quality**: Average rating > 4.5 для official templates
- **Community**: 100+ user-submitted templates к концу Phase 2
- **Monetization**: $10K+ revenue от premium templates (Phase 3)
