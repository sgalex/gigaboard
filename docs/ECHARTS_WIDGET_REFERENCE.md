# ECharts Widget Reference для WidgetController

## Executive Summary

Справочник по всем типам виджетов Apache ECharts v6, используемых в GigaBoard для генерации визуализаций через WidgetController → WidgetCodexAgent pipeline. Документ содержит минимальные воспроизводимые примеры для каждого типа графика, рекомендации по выбору и шаблоны кода для промпта WidgetCodexAgent.

**Контекст использования:** WidgetCodexAgent генерирует standalone HTML-виджеты с ECharts, загружая библиотеку из `/libs/echarts.min.js`. Данный документ описывает все доступные типы визуализаций и их option-конфигурации.

---

## Общая структура ECharts-виджета

Каждый виджет в GigaBoard — это standalone HTML с embedded ECharts:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body, #chart { width: 100%; height: 100%; margin: 0; padding: 0; }
  </style>
</head>
<body>
  <div id="chart"></div>
  <script src="/libs/echarts.min.js"></script>
  <script>
    const chart = echarts.init(document.getElementById('chart'));
    const option = { /* ... конфигурация ... */ };
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
  </script>
</body>
</html>
```

**Ключевые принципы:**
- Библиотека загружается локально: `/libs/echarts.min.js` (ECharts v6)
- Контейнер `#chart` занимает 100% доступного пространства
- Обработчик `resize` обеспечивает адаптивность внутри React Flow ноды
- Данные подставляются напрямую из ContentNode в `option`

---

## Категории виджетов

```mermaid
flowchart TB
    subgraph basic["Базовые (Cartesian)"]
        line[Line / Area]
        bar[Bar]
        scatter[Scatter]
        candlestick[Candlestick]
        boxplot[Boxplot]
        heatmap[Heatmap]
    end

    subgraph circular["Круговые / Радиальные"]
        pie[Pie / Doughnut]
        radar[Radar]
        sunburst[Sunburst]
        gauge[Gauge]
        chord[Chord]
    end

    subgraph hierarchy["Иерархические"]
        tree[Tree]
        treemap[Treemap]
    end

    subgraph relational["Связи и потоки"]
        graph[Graph / Network]
        sankey[Sankey]
        funnel[Funnel]
    end

    subgraph specialized["Специальные"]
        parallel[Parallel Coordinates]
        themeRiver[ThemeRiver]
        pictorialBar[PictorialBar]
        calendar[Calendar]
        matrix[Matrix]
        custom[Custom Series]
    end
```

---

## 1. Line Chart (Линейный график)

**Когда использовать:** Временные ряды, тренды, сравнение динамики нескольких показателей.

**Тип серии:** `type: 'line'`

### 1.1 Базовый Line

```javascript
option = {
  xAxis: {
    type: 'category',
    data: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      data: [150, 230, 224, 218, 135, 147, 260],
      type: 'line'
    }
  ]
};
```

### 1.2 Smoothed Line (Сглаженная линия)

```javascript
option = {
  xAxis: {
    type: 'category',
    data: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  },
  yAxis: { type: 'value' },
  series: [
    {
      data: [820, 932, 901, 934, 1290, 1330, 1320],
      type: 'line',
      smooth: true
    }
  ]
};
```

### 1.3 Area Chart (Область)

```javascript
option = {
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  },
  yAxis: { type: 'value' },
  series: [
    {
      data: [820, 932, 901, 934, 1290, 1330, 1320],
      type: 'line',
      areaStyle: {}
    }
  ]
};
```

### 1.4 Stacked Line / Stacked Area

```javascript
option = {
  title: { text: 'Stacked Line' },
  tooltip: { trigger: 'axis' },
  legend: { data: ['Email', 'Direct', 'Search'] },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  },
  yAxis: { type: 'value' },
  series: [
    { name: 'Email', type: 'line', stack: 'Total', data: [120, 132, 101, 134, 90, 230, 210] },
    { name: 'Direct', type: 'line', stack: 'Total', data: [220, 182, 191, 234, 290, 330, 310] },
    { name: 'Search', type: 'line', stack: 'Total', data: [150, 232, 201, 154, 190, 330, 410] }
  ]
};
```

**Для Stacked Area** — добавить `areaStyle: {}` в каждую серию.

### Ключевые параметры Line

| Параметр         | Описание           | Пример                                         |
| ---------------- | ------------------ | ---------------------------------------------- |
| `smooth`         | Сглаживание        | `true` / `0.5`                                 |
| `areaStyle`      | Заливка области    | `{}` или `{ opacity: 0.3 }`                    |
| `stack`          | Стекирование       | `'Total'` (одинаковый ключ)                    |
| `step`           | Ступенчатый        | `'start'` / `'middle'` / `'end'`               |
| `symbol`         | Форма точки        | `'circle'` / `'rect'` / `'none'`               |
| `lineStyle.type` | Тип линии          | `'solid'` / `'dashed'` / `'dotted'`            |
| `markPoint`      | Отметки на графике | `{ data: [{ type: 'max' }, { type: 'min' }] }` |
| `markLine`       | Линии-маркеры      | `{ data: [{ type: 'average' }] }`              |

---

## 2. Bar Chart (Столбчатый / Гистограмма)

**Когда использовать:** Сравнение категорий, рейтинги, распределения.

**Тип серии:** `type: 'bar'`

### 2.1 Базовый Bar

```javascript
option = {
  xAxis: {
    type: 'category',
    data: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  },
  yAxis: { type: 'value' },
  series: [
    {
      data: [120, 200, 150, 80, 70, 110, 130],
      type: 'bar'
    }
  ]
};
```

### 2.2 Horizontal Bar (Горизонтальные столбцы)

```javascript
option = {
  title: { text: 'Население стран' },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'value', boundaryGap: [0, 0.01] },
  yAxis: {
    type: 'category',
    data: ['Бразилия', 'Индонезия', 'США', 'Индия', 'Китай']
  },
  series: [
    {
      name: '2023',
      type: 'bar',
      data: [215313, 275501, 331893, 1428628, 1425671]
    }
  ]
};
```

### 2.3 Stacked Bar

```javascript
option = {
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: {},
  xAxis: { type: 'category', data: ['Q1', 'Q2', 'Q3', 'Q4'] },
  yAxis: { type: 'value' },
  series: [
    { name: 'Продукт A', type: 'bar', stack: 'total', data: [320, 302, 301, 334] },
    { name: 'Продукт B', type: 'bar', stack: 'total', data: [120, 132, 101, 134] },
    { name: 'Продукт C', type: 'bar', stack: 'total', data: [220, 182, 191, 234] }
  ]
};
```

### 2.4 Waterfall Chart (Каскадная диаграмма)

```javascript
option = {
  title: { text: 'Waterfall Chart' },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: ['Всего', 'Аренда', 'ЖКХ', 'Транспорт', 'Еда', 'Прочее'] },
  yAxis: { type: 'value' },
  series: [
    {
      name: 'Placeholder',
      type: 'bar',
      stack: 'Total',
      itemStyle: { borderColor: 'transparent', color: 'transparent' },
      emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
      data: [0, 1700, 1400, 1200, 300, 0]
    },
    {
      name: 'Расходы',
      type: 'bar',
      stack: 'Total',
      data: [2900, 1200, 300, 200, 900, 300]
    }
  ]
};
```

### Ключевые параметры Bar

| Параметр                 | Описание              | Пример                               |
| ------------------------ | --------------------- | ------------------------------------ |
| `barWidth`               | Ширина столбца        | `'60%'` / `40`                       |
| `barGap`                 | Отступ между группами | `'30%'` / `'-100%'` (перекрытие)     |
| `stack`                  | Стекирование          | `'total'`                            |
| `showBackground`         | Фоновый столбец       | `true`                               |
| `backgroundStyle`        | Стиль фона            | `{ color: 'rgba(180,180,180,0.2)' }` |
| `label.show`             | Подписи значений      | `true`                               |
| `itemStyle.borderRadius` | Скругление            | `[5, 5, 0, 0]`                       |

---

## 3. Pie Chart (Круговая диаграмма)

**Когда использовать:** Доли целого, процентное распределение, структура.

**Тип серии:** `type: 'pie'`

### 3.1 Базовый Pie

```javascript
option = {
  title: { text: 'Источники трафика', left: 'center' },
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', left: 'left' },
  series: [
    {
      name: 'Источник',
      type: 'pie',
      radius: '50%',
      data: [
        { value: 1048, name: 'Поиск' },
        { value: 735, name: 'Прямой' },
        { value: 580, name: 'Email' },
        { value: 484, name: 'Партнёры' },
        { value: 300, name: 'Видео' }
      ],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }
  ]
};
```

### 3.2 Doughnut Chart (Кольцевая)

```javascript
option = {
  tooltip: { trigger: 'item' },
  legend: { top: '5%', left: 'center' },
  series: [
    {
      name: 'Доступ',
      type: 'pie',
      radius: ['40%', '70%'],       // Внутренний и внешний радиус
      avoidLabelOverlap: false,
      label: { show: false, position: 'center' },
      emphasis: {
        label: { show: true, fontSize: 40, fontWeight: 'bold' }
      },
      labelLine: { show: false },
      data: [
        { value: 1048, name: 'Поиск' },
        { value: 735, name: 'Прямой' },
        { value: 580, name: 'Email' },
        { value: 484, name: 'Партнёры' },
        { value: 300, name: 'Видео' }
      ]
    }
  ]
};
```

### 3.3 Nightingale (Rose) Chart

```javascript
option = {
  series: [
    {
      type: 'pie',
      radius: [50, 250],
      roseType: 'area',           // 'radius' или 'area'
      itemStyle: { borderRadius: 8 },
      data: [
        { value: 40, name: 'Категория A' },
        { value: 38, name: 'Категория B' },
        { value: 32, name: 'Категория C' },
        { value: 30, name: 'Категория D' },
        { value: 28, name: 'Категория E' }
      ]
    }
  ]
};
```

### 3.4 Half Doughnut

```javascript
option = {
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '70%'],
      startAngle: 180,
      endAngle: 360,              // Полукруг
      data: [
        { value: 1048, name: 'A' },
        { value: 735, name: 'B' },
        { value: 580, name: 'C' }
      ]
    }
  ]
};
```

### Ключевые параметры Pie

| Параметр                  | Описание               | Пример                                |
| ------------------------- | ---------------------- | ------------------------------------- |
| `radius`                  | Радиус                 | `'50%'` / `['40%', '70%']` (doughnut) |
| `center`                  | Центр                  | `['50%', '50%']`                      |
| `roseType`                | Nightingale            | `'radius'` / `'area'`                 |
| `startAngle` / `endAngle` | Углы                   | `180` / `360` (полукруг)              |
| `padAngle`                | Отступ между секторами | `5`                                   |
| `itemStyle.borderRadius`  | Скругление             | `10`                                  |
| `label.formatter`         | Формат подписи         | `'{b}: {d}%'`                         |

---

## 4. Scatter Chart (Точечный график)

**Когда использовать:** Корреляции, распределения, кластеры, выбросы.

**Тип серии:** `type: 'scatter'` / `type: 'effectScatter'`

### 4.1 Базовый Scatter

```javascript
option = {
  xAxis: {},
  yAxis: {},
  series: [
    {
      symbolSize: 20,
      data: [
        [10.0, 8.04], [8.07, 6.95], [13.0, 7.58],
        [9.05, 8.81], [11.0, 8.33], [14.0, 7.66],
        [13.4, 6.81], [10.0, 6.33], [14.0, 8.96],
        [12.5, 6.82], [9.15, 7.20], [11.5, 7.20]
      ],
      type: 'scatter'
    }
  ]
};
```

### 4.2 Bubble Chart (Пузырьковый)

```javascript
option = {
  xAxis: {},
  yAxis: {},
  series: [
    {
      type: 'scatter',
      symbolSize: function (data) {
        return Math.sqrt(data[2]) * 5;  // Размер от 3-го параметра
      },
      data: [
        [10, 8, 100], [8, 7, 50], [13, 7.5, 200],
        [9, 8.8, 75], [11, 8.3, 150]
      ],
      emphasis: {
        focus: 'series',
        label: { show: true, formatter: '{b}', position: 'top' }
      }
    }
  ]
};
```

### 4.3 Effect Scatter (с анимацией)

```javascript
option = {
  xAxis: { scale: true },
  yAxis: { scale: true },
  series: [
    {
      type: 'effectScatter',
      symbolSize: 20,
      data: [[172.7, 105.2], [153.4, 42]],
      rippleEffect: { brushType: 'stroke' }
    },
    {
      type: 'scatter',
      data: [[161.2, 51.6], [167.5, 59.0], [159.5, 49.2]]
    }
  ]
};
```

---

## 5. Radar Chart (Радарный / Паутинный)

**Когда использовать:** Многомерное сравнение, профили, компетенции.

**Тип серии:** `type: 'radar'`

```javascript
option = {
  title: { text: 'Бюджет vs Расходы' },
  legend: { data: ['Бюджет', 'Расходы'] },
  radar: {
    indicator: [
      { name: 'Продажи', max: 6500 },
      { name: 'Администрация', max: 16000 },
      { name: 'IT', max: 30000 },
      { name: 'Поддержка', max: 38000 },
      { name: 'Разработка', max: 52000 },
      { name: 'Маркетинг', max: 25000 }
    ]
  },
  series: [
    {
      name: 'Бюджет vs Расходы',
      type: 'radar',
      data: [
        {
          value: [4200, 3000, 20000, 35000, 50000, 18000],
          name: 'Бюджет'
        },
        {
          value: [5000, 14000, 28000, 26000, 42000, 21000],
          name: 'Расходы'
        }
      ]
    }
  ]
};
```

### Ключевые параметры Radar

| Параметр          | Описание | Пример                                  |
| ----------------- | -------- | --------------------------------------- |
| `radar.shape`     | Форма    | `'polygon'` (по умолчанию) / `'circle'` |
| `radar.indicator` | Оси      | `[{ name: '...', max: N }]`             |
| `radar.radius`    | Радиус   | `'65%'`                                 |
| `areaStyle`       | Заливка  | `{ opacity: 0.3 }`                      |

---

## 6. Gauge Chart (Приборная панель / Спидометр)

**Когда использовать:** KPI, метрики, прогресс, одиночные значения.

**Тип серии:** `type: 'gauge'`

### 6.1 Simple Gauge

```javascript
option = {
  tooltip: { formatter: '{a} <br/>{b} : {c}%' },
  series: [
    {
      name: 'Давление',
      type: 'gauge',
      progress: { show: true },
      detail: { valueAnimation: true, formatter: '{value}' },
      data: [{ value: 50, name: 'SCORE' }]
    }
  ]
};
```

### 6.2 Progress Gauge (с полосой прогресса)

```javascript
option = {
  series: [
    {
      type: 'gauge',
      progress: { show: true, width: 18 },
      axisLine: { lineStyle: { width: 18 } },
      axisTick: { show: false },
      splitLine: { length: 15, lineStyle: { width: 2, color: '#999' } },
      axisLabel: { distance: 25, color: '#999', fontSize: 20 },
      anchor: { show: true, showAbove: true, size: 25, itemStyle: { borderWidth: 10 } },
      title: { show: false },
      detail: {
        valueAnimation: true,
        fontSize: 80,
        offsetCenter: [0, '70%']
      },
      data: [{ value: 70, name: 'Выполнение' }]
    }
  ]
};
```

### 6.3 Ring Gauge (без стрелки, кольцо)

```javascript
option = {
  series: [
    {
      type: 'gauge',
      startAngle: 90,
      endAngle: -270,
      pointer: { show: false },
      progress: {
        show: true,
        overlap: false,
        roundCap: true,
        clip: false
      },
      axisLine: { lineStyle: { width: 40 } },
      splitLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      data: [
        { value: 20, name: 'Идеально', title: { offsetCenter: ['0%', '-30%'] }, detail: { offsetCenter: ['0%', '-20%'] } },
        { value: 40, name: 'Хорошо', title: { offsetCenter: ['0%', '0%'] }, detail: { offsetCenter: ['0%', '10%'] } },
        { value: 60, name: 'Часто', title: { offsetCenter: ['0%', '30%'] }, detail: { offsetCenter: ['0%', '40%'] } }
      ],
      title: { fontSize: 14 },
      detail: { width: 50, height: 14, fontSize: 14, color: 'inherit', formatter: '{value}%' }
    }
  ]
};
```

---

## 7. Candlestick Chart (Свечной / Биржевой)

**Когда использовать:** Финансовые данные, OHLC, биржевые котировки.

**Тип серии:** `type: 'candlestick'`

```javascript
option = {
  xAxis: {
    data: ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
  },
  yAxis: {},
  series: [
    {
      type: 'candlestick',
      data: [
        [20, 34, 10, 38],   // [open, close, lowest, highest]
        [40, 35, 30, 50],
        [31, 38, 33, 44],
        [38, 15, 5, 42]
      ]
    }
  ]
};
```

### Ключевые параметры Candlestick

| Параметр                 | Описание        | Пример      |
| ------------------------ | --------------- | ----------- |
| `itemStyle.color`        | Цвет роста      | `'#ec0000'` |
| `itemStyle.color0`       | Цвет падения    | `'#00da3c'` |
| `itemStyle.borderColor`  | Граница роста   | `'#ec0000'` |
| `itemStyle.borderColor0` | Граница падения | `'#00da3c'` |

---

## 8. Boxplot (Ящик с усами)

**Когда использовать:** Статистическое распределение, квартили, выбросы.

**Тип серии:** `type: 'boxplot'`

```javascript
option = {
  title: { text: 'Распределение данных' },
  dataset: [
    {
      source: [
        [850, 740, 900, 1070, 930, 850, 950, 980, 980, 880, 1000, 980],
        [960, 940, 960, 940, 880, 800, 850, 880, 900, 840, 830, 790]
      ]
    },
    {
      transform: { type: 'boxplot', config: { itemNameFormatter: 'Эксп. {value}' } }
    },
    {
      fromDatasetIndex: 1,
      fromTransformResult: 1    // outliers
    }
  ],
  tooltip: { trigger: 'item' },
  xAxis: { type: 'category' },
  yAxis: { type: 'value' },
  series: [
    { name: 'boxplot', type: 'boxplot', datasetIndex: 1 },
    { name: 'outlier', type: 'scatter', datasetIndex: 2 }
  ]
};
```

---

## 9. Heatmap (Тепловая карта)

**Когда использовать:** Плотность, корреляции, временные паттерны, матрицы.

**Тип серии:** `type: 'heatmap'`

```javascript
const hours = ['12a', '1a', '2a', '3a', '4a', '5a', '6a', '7a', '8a', '9a', '10a', '11a',
  '12p', '1p', '2p', '3p', '4p', '5p', '6p', '7p', '8p', '9p', '10p', '11p'];
const days = ['Сб', 'Пт', 'Чт', 'Ср', 'Вт', 'Пн', 'Вс'];

// data: [xIndex, yIndex, value]
const data = [[0, 0, 5], [0, 1, 1], [1, 0, 3], [1, 1, 7] /* ... */];

option = {
  tooltip: { position: 'top' },
  grid: { height: '50%', top: '10%' },
  xAxis: { type: 'category', data: hours, splitArea: { show: true } },
  yAxis: { type: 'category', data: days, splitArea: { show: true } },
  visualMap: {
    min: 0,
    max: 10,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: '15%'
  },
  series: [
    {
      name: 'Активность',
      type: 'heatmap',
      data: data,
      label: { show: true },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }
      }
    }
  ]
};
```

### Ключевые параметры Heatmap

| Параметр             | Описание               | Пример                                                            |
| -------------------- | ---------------------- | ----------------------------------------------------------------- |
| `visualMap`          | Цветовая шкала         | `{ min: 0, max: 10, inRange: { color: ['#313695', '#d73027'] } }` |
| `label.show`         | Значения в ячейках     | `true`                                                            |
| координатная система | Может быть на calendar | `coordinateSystem: 'calendar'`                                    |

---

## 10. Graph (Сетевой / Граф)

**Когда использовать:** Связи, социальные сети, зависимости, топологии.

**Тип серии:** `type: 'graph'`

```javascript
option = {
  title: { text: 'Граф связей' },
  tooltip: {},
  series: [
    {
      type: 'graph',
      layout: 'force',          // 'none' | 'force' | 'circular'
      symbolSize: 50,
      roam: true,
      label: { show: true },
      edgeSymbol: ['circle', 'arrow'],
      edgeSymbolSize: [4, 10],
      data: [
        { name: 'Узел 1', x: 300, y: 300 },
        { name: 'Узел 2', x: 800, y: 300 },
        { name: 'Узел 3', x: 550, y: 100 },
        { name: 'Узел 4', x: 550, y: 500 }
      ],
      links: [
        { source: 'Узел 1', target: 'Узел 2' },
        { source: 'Узел 1', target: 'Узел 3' },
        { source: 'Узел 2', target: 'Узел 3' },
        { source: 'Узел 2', target: 'Узел 4' }
      ],
      force: {
        repulsion: 1000,
        edgeLength: [10, 50]
      }
    }
  ]
};
```

### Ключевые параметры Graph

| Параметр           | Описание            | Пример                                   |
| ------------------ | ------------------- | ---------------------------------------- |
| `layout`           | Алгоритм размещения | `'force'` / `'circular'` / `'none'`      |
| `roam`             | Zoom/Pan            | `true`                                   |
| `force.repulsion`  | Сила отталкивания   | `1000`                                   |
| `force.edgeLength` | Длина ребра         | `[10, 50]`                               |
| `categories`       | Группировка узлов   | `[{ name: 'Тип A' }, { name: 'Тип B' }]` |

---

## 11. Sankey (Санкей / Диаграмма потоков)

**Когда использовать:** Потоки ресурсов, перераспределение, миграция, энергия.

**Тип серии:** `type: 'sankey'`

```javascript
option = {
  series: {
    type: 'sankey',
    layout: 'none',
    emphasis: { focus: 'adjacency' },
    data: [
      { name: 'Источник A' },
      { name: 'Источник B' },
      { name: 'Процесс 1' },
      { name: 'Процесс 2' },
      { name: 'Результат X' },
      { name: 'Результат Y' }
    ],
    links: [
      { source: 'Источник A', target: 'Процесс 1', value: 5 },
      { source: 'Источник A', target: 'Процесс 2', value: 3 },
      { source: 'Источник B', target: 'Процесс 1', value: 8 },
      { source: 'Процесс 1', target: 'Результат X', value: 13 },
      { source: 'Процесс 2', target: 'Результат Y', value: 3 }
    ]
  }
};
```

### Ключевые параметры Sankey

| Параметр          | Описание            | Пример                                         |
| ----------------- | ------------------- | ---------------------------------------------- |
| `orient`          | Ориентация          | `'horizontal'` / `'vertical'`                  |
| `nodeAlign`       | Выравнивание        | `'justify'` / `'left'` / `'right'`             |
| `emphasis.focus`  | Фокус при наведении | `'adjacency'`                                  |
| `levels`          | Стили по уровням    | `[{ depth: 0, itemStyle: { color: '#fbb' } }]` |
| `lineStyle.color` | Цвет связи          | `'gradient'` / `'source'` / `'target'`         |

---

## 12. Funnel Chart (Воронка)

**Когда использовать:** Конверсия, воронка продаж, этапы процесса.

**Тип серии:** `type: 'funnel'`

```javascript
option = {
  title: { text: 'Воронка продаж' },
  tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c}%' },
  legend: { data: ['Показы', 'Клики', 'Визиты', 'Заявки', 'Покупки'] },
  series: [
    {
      name: 'Конверсия',
      type: 'funnel',
      left: '10%',
      top: 60,
      bottom: 60,
      width: '80%',
      min: 0,
      max: 100,
      minSize: '0%',
      maxSize: '100%',
      sort: 'descending',        // 'ascending' | 'descending' | 'none'
      gap: 2,
      label: { show: true, position: 'inside' },
      emphasis: { label: { fontSize: 20 } },
      data: [
        { value: 100, name: 'Показы' },
        { value: 80, name: 'Клики' },
        { value: 60, name: 'Визиты' },
        { value: 40, name: 'Заявки' },
        { value: 20, name: 'Покупки' }
      ]
    }
  ]
};
```

---

## 13. Tree (Дерево)

**Когда использовать:** Иерархии, оргструктуры, файловые системы, таксономии.

**Тип серии:** `type: 'tree'`

```javascript
option = {
  tooltip: { trigger: 'item', triggerOn: 'mousemove' },
  series: [
    {
      type: 'tree',
      data: [{
        name: 'Корень',
        children: [
          {
            name: 'Ветка A',
            children: [
              { name: 'Лист A1' },
              { name: 'Лист A2' }
            ]
          },
          {
            name: 'Ветка B',
            children: [
              { name: 'Лист B1' },
              {
                name: 'Подветка B2',
                children: [
                  { name: 'Лист B2a' },
                  { name: 'Лист B2b' }
                ]
              }
            ]
          }
        ]
      }],
      top: '1%',
      left: '7%',
      bottom: '1%',
      right: '20%',
      symbolSize: 7,
      label: {
        position: 'left',
        verticalAlign: 'middle',
        align: 'right',
        fontSize: 9
      },
      leaves: {
        label: { position: 'right', verticalAlign: 'middle', align: 'left' }
      },
      expandAndCollapse: true,
      animationDuration: 550,
      animationDurationUpdate: 750
    }
  ]
};
```

### Ключевые параметры Tree

| Параметр            | Описание          | Пример                            |
| ------------------- | ----------------- | --------------------------------- |
| `orient`            | Направление       | `'LR'` / `'RL'` / `'TB'` / `'BT'` |
| `layout`            | Алгоритм          | `'orthogonal'` / `'radial'`       |
| `edgeShape`         | Форма рёбер       | `'curve'` / `'polyline'`          |
| `expandAndCollapse` | Сворачивание      | `true`                            |
| `initialTreeDepth`  | Начальная глубина | `2`                               |

---

## 14. Treemap (Карта дерева)

**Когда использовать:** Иерархические пропорции, использование диска, бюджеты.

**Тип серии:** `type: 'treemap'`

```javascript
option = {
  series: [
    {
      type: 'treemap',
      data: [
        {
          name: 'Категория A',
          value: 10,
          children: [
            { name: 'A-1', value: 4 },
            { name: 'A-2', value: 6 }
          ]
        },
        {
          name: 'Категория B',
          value: 20,
          children: [
            {
              name: 'B-1',
              value: 20,
              children: [
                { name: 'B-1-a', value: 15 },
                { name: 'B-1-b', value: 5 }
              ]
            }
          ]
        }
      ]
    }
  ]
};
```

### Ключевые параметры Treemap

| Параметр     | Описание           | Пример                                |
| ------------ | ------------------ | ------------------------------------- |
| `leafDepth`  | Drill-down глубина | `1`                                   |
| `roam`       | Zoom/Pan           | `true`                                |
| `levels`     | Стили по уровням   | `[{ itemStyle: { borderWidth: 3 } }]` |
| `visibleMin` | Мин. размер        | `300`                                 |

---

## 15. Sunburst (Солнечная диаграмма)

**Когда использовать:** Многоуровневые иерархии с пропорциями, drill-down структуры.

**Тип серии:** `type: 'sunburst'`

```javascript
option = {
  series: [
    {
      type: 'sunburst',
      data: [
        {
          name: 'Дедушка',
          children: [
            {
              name: 'Дядя',
              value: 15,
              children: [
                { name: 'Кузен 1', value: 2 },
                { name: 'Кузен 2', value: 5 },
                { name: 'Кузен 3', value: 4 }
              ]
            },
            {
              name: 'Отец',
              value: 10,
              children: [
                { name: 'Я', value: 5 },
                { name: 'Брат', value: 3 }
              ]
            }
          ]
        }
      ],
      radius: [0, '90%'],
      label: { rotate: 'radial' }
    }
  ]
};
```

### Ключевые параметры Sunburst

| Параметр                 | Описание          | Пример                          |
| ------------------------ | ----------------- | ------------------------------- |
| `radius`                 | Радиус            | `[0, '90%']` / `['15%', '80%']` |
| `label.rotate`           | Вращение подписей | `'radial'` / `'tangential'`     |
| `itemStyle.borderRadius` | Скругление        | `7`                             |
| `emphasis.focus`         | Фокус             | `'ancestor'` / `'descendant'`   |

---

## 16. Parallel Coordinates (Параллельные координаты)

**Когда использовать:** Многомерный анализ, сравнение по множеству параметров.

**Тип серии:** `type: 'parallel'`

```javascript
option = {
  parallelAxis: [
    { dim: 0, name: 'Цена' },
    { dim: 1, name: 'Вес' },
    { dim: 2, name: 'Количество' },
    {
      dim: 3,
      name: 'Оценка',
      type: 'category',
      data: ['Отл.', 'Хор.', 'Удв.', 'Неуд.']
    }
  ],
  series: {
    type: 'parallel',
    lineStyle: { width: 4 },
    data: [
      [12.99, 100, 82, 'Хор.'],
      [9.99, 80, 77, 'Удв.'],
      [20, 120, 60, 'Отл.']
    ]
  }
};
```

---

## 17. ThemeRiver (Тематическая река)

**Когда использовать:** Изменение долей во времени, трендовые потоки.

**Тип серии:** `type: 'themeRiver'`

```javascript
option = {
  tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
  legend: { data: ['Тема A', 'Тема B', 'Тема C'] },
  singleAxis: { top: 50, bottom: 50, type: 'time' },
  series: [
    {
      type: 'themeRiver',
      emphasis: { itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.8)' } },
      data: [
        ['2024/01/01', 10, 'Тема A'],
        ['2024/01/01', 20, 'Тема B'],
        ['2024/01/01', 30, 'Тема C'],
        ['2024/02/01', 25, 'Тема A'],
        ['2024/02/01', 15, 'Тема B'],
        ['2024/02/01', 35, 'Тема C'],
        ['2024/03/01', 30, 'Тема A'],
        ['2024/03/01', 25, 'Тема B'],
        ['2024/03/01', 20, 'Тема C']
      ]
    }
  ]
};
```

---

## 18. PictorialBar (Картинки-столбцы)

**Когда использовать:** Инфографика, наглядные сравнения с символами.

**Тип серии:** `type: 'pictorialBar'`

```javascript
option = {
  xAxis: {
    data: ['Кот', 'Собака', 'Попугай'],
    axisTick: { show: false },
    axisLine: { show: false }
  },
  yAxis: { splitLine: { show: false } },
  series: [
    {
      type: 'pictorialBar',
      barCategoryGap: '-130%',
      symbol: 'path://M0,10 L10,10 C5.5,10 5.5,5 5,0 C4.5,5 4.5,10 0,10 z',
      itemStyle: { opacity: 0.5 },
      emphasis: { itemStyle: { opacity: 1 } },
      data: [123, 60, 25],
      z: 10
    }
  ]
};
```

---

## 19. Calendar (Календарная тепловая карта)

**Когда использовать:** Ежедневная активность, паттерны по дням/неделям.

**Координатная система:** `calendar`

```javascript
// Генерация данных за год
function getVirtualData(year) {
  const date = +echarts.time.parse(year + '-01-01');
  const end = +echarts.time.parse(+year + 1 + '-01-01');
  const data = [];
  for (let d = date; d < end; d += 3600 * 24 * 1000) {
    data.push([echarts.time.format(d, '{yyyy}-{MM}-{dd}', false), Math.floor(Math.random() * 10000)]);
  }
  return data;
}

option = {
  visualMap: {
    min: 0,
    max: 10000,
    type: 'piecewise',
    orient: 'horizontal',
    left: 'center',
    top: 65
  },
  calendar: {
    top: 120,
    left: 30,
    right: 30,
    cellSize: ['auto', 13],
    range: '2024',
    itemStyle: { borderWidth: 0.5 },
    yearLabel: { show: false }
  },
  series: {
    type: 'heatmap',
    coordinateSystem: 'calendar',
    data: getVirtualData('2024')
  }
};
```

---

## 20. Chord (Хордовая диаграмма) — v6.0.0+

**Когда использовать:** Взаимные связи, миграция между группами, корреляции.

**Тип серии:** `type: 'chord'`

```javascript
option = {
  series: [{
    type: 'chord',
    data: [
      { name: 'Группа A' },
      { name: 'Группа B' },
      { name: 'Группа C' },
      { name: 'Группа D' }
    ],
    links: [
      { source: 'Группа A', target: 'Группа B', value: 100 },
      { source: 'Группа A', target: 'Группа C', value: 50 },
      { source: 'Группа B', target: 'Группа C', value: 80 },
      { source: 'Группа C', target: 'Группа D', value: 70 },
      { source: 'Группа D', target: 'Группа A', value: 60 }
    ]
  }]
};
```

---

## 21. Matrix (Матрица) — v6.0.0+

**Когда использовать:** Корреляционные матрицы, confusion matrix, scatter matrix.

**Координатная система:** `matrix`

```javascript
option = {
  matrix: {
    data: ['Переменная 1', 'Переменная 2', 'Переменная 3']
  },
  series: [
    {
      type: 'scatter',
      coordinateSystem: 'matrix',
      data: [/* scatter data */]
    }
  ]
};
```

---

## 22. Custom Series (Пользовательские серии)

**Когда использовать:** Нестандартные визуализации: Gantt, Error Bars, Profiles, Hexbin.

**Тип серии:** `type: 'custom'`

```javascript
option = {
  xAxis: { type: 'category', data: ['A', 'B', 'C', 'D'] },
  yAxis: {},
  series: [{
    type: 'custom',
    renderItem: function (params, api) {
      const categoryIndex = api.value(0);
      const start = api.coord([categoryIndex, api.value(1)]);
      const end = api.coord([categoryIndex, api.value(2)]);
      const height = end[1] - start[1];
      const width = api.size([0, 1])[0] * 0.6;
      return {
        type: 'rect',
        shape: echarts.graphic.clipRectByRect(
          { x: start[0] - width / 2, y: start[1], width: width, height: height },
          { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height }
        ),
        style: api.style()
      };
    },
    data: [[0, 10, 20], [1, 15, 30], [2, 8, 25], [3, 12, 35]]
  }]
};
```

---

## Общие компоненты ECharts

Эти компоненты применимы к любому типу виджета:

### Tooltip

```javascript
tooltip: {
  trigger: 'axis',        // 'item' для pie/scatter, 'axis' для line/bar
  axisPointer: { type: 'shadow' },  // 'line' | 'shadow' | 'cross'
  formatter: '{b}: {c}'   // Шаблон или function
}
```

### Legend

```javascript
legend: {
  type: 'scroll',         // 'plain' | 'scroll' (для множества элементов)
  orient: 'vertical',     // 'horizontal' | 'vertical'
  left: 'left',
  data: ['Серия 1', 'Серия 2']
}
```

### Grid (область построения)

```javascript
grid: {
  left: '3%',
  right: '4%',
  bottom: '3%',
  top: '10%',
  containLabel: true       // Включает подписи осей в границы
}
```

### DataZoom (масштабирование)

```javascript
dataZoom: [
  { type: 'inside', start: 0, end: 100 },   // Скролл мышью
  { type: 'slider', start: 0, end: 100 }     // Ползунок
]
```

### VisualMap (цветовая шкала)

```javascript
visualMap: {
  min: 0,
  max: 100,
  calculable: true,
  inRange: {
    color: ['#50a3ba', '#eac736', '#d94e5d']
  }
}
```

### Toolbox (панель инструментов)

```javascript
toolbox: {
  feature: {
    saveAsImage: {},
    dataView: { readOnly: false },
    restore: {},
    dataZoom: {},
    magicType: { type: ['line', 'bar', 'stack'] }
  }
}
```

### Dataset (управление данными)

```javascript
dataset: {
  source: [
    ['product', '2021', '2022', '2023'],
    ['Матча', 41.1, 30.4, 65.1],
    ['Молоко', 86.5, 92.1, 85.7],
    ['Сыр', 24.1, 67.2, 79.5]
  ]
},
xAxis: { type: 'category' },
yAxis: {},
series: [
  { type: 'bar' },
  { type: 'bar' },
  { type: 'bar' }
]
```

---

## Матрица выбора типов виджетов

Для помощи WidgetCodexAgent в выборе правильного типа графика:

| Задача                        | Рекомендуемые типы  | series.type                |
| ----------------------------- | ------------------- | -------------------------- |
| Тренд во времени              | Line, Area          | `'line'`                   |
| Сравнение категорий           | Bar, Horizontal Bar | `'bar'`                    |
| Доли целого                   | Pie, Doughnut       | `'pie'`                    |
| Корреляция двух переменных    | Scatter, Bubble     | `'scatter'`                |
| Многомерное сравнение         | Radar               | `'radar'`                  |
| Одиночная метрика / KPI       | Gauge               | `'gauge'`                  |
| Финансовые данные             | Candlestick         | `'candlestick'`            |
| Статистическое распределение  | Boxplot             | `'boxplot'`                |
| Плотность / паттерны          | Heatmap             | `'heatmap'`                |
| Связи и сети                  | Graph               | `'graph'`                  |
| Потоки ресурсов               | Sankey              | `'sankey'`                 |
| Конверсия / этапы             | Funnel              | `'funnel'`                 |
| Иерархическое дерево          | Tree                | `'tree'`                   |
| Иерархические пропорции       | Treemap, Sunburst   | `'treemap'` / `'sunburst'` |
| Многопараметрический анализ   | Parallel            | `'parallel'`               |
| Изменение долей во времени    | ThemeRiver          | `'themeRiver'`             |
| Ежедневная активность         | Calendar + Heatmap  | `'heatmap'` + `calendar`   |
| Взаимные связи между группами | Chord               | `'chord'`                  |
| Инфографика с символами       | PictorialBar        | `'pictorialBar'`           |
| Нестандартная визуализация    | Custom              | `'custom'`                 |

---

## Комбинированные виджеты

ECharts позволяет комбинировать несколько серий на одном графике:

### Line + Bar

```javascript
option = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['Продажи', 'Прибыль'] },
  xAxis: { type: 'category', data: ['Янв', 'Фев', 'Мар', 'Апр', 'Май'] },
  yAxis: [
    { type: 'value', name: 'Продажи' },
    { type: 'value', name: 'Прибыль %' }
  ],
  series: [
    { name: 'Продажи', type: 'bar', data: [200, 300, 250, 400, 350] },
    { name: 'Прибыль', type: 'line', yAxisIndex: 1, data: [15, 20, 18, 25, 22] }
  ]
};
```

### Scatter + effectScatter (выделение точек)

```javascript
option = {
  xAxis: { scale: true },
  yAxis: { scale: true },
  series: [
    {
      type: 'scatter',
      data: [[161.2, 51.6], [167.5, 59.0], [159.5, 49.2]]
    },
    {
      type: 'effectScatter',
      symbolSize: 20,
      data: [[172.7, 105.2]],  // Выделенные аномалии
      rippleEffect: { brushType: 'stroke' }
    }
  ]
};
```

### Pie + центральная статистика

```javascript
option = {
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 30, fontWeight: 'bold' }
      },
      data: [
        { value: 1048, name: 'A' },
        { value: 735, name: 'B' },
        { value: 580, name: 'C' }
      ]
    }
  ],
  graphic: [{
    type: 'text',
    left: 'center',
    top: 'center',
    style: {
      text: 'Всего\n2363',
      textAlign: 'center',
      fontSize: 24,
      fontWeight: 'bold'
    }
  }]
};
```

---

## Темизация и стилизация

### Встроенные темы

```javascript
// Тёмная тема
const chart = echarts.init(document.getElementById('chart'), 'dark');
```

### Цветовая палитра

```javascript
option = {
  color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'],
  // ... series
};
```

### Dark mode (адаптивная)

```javascript
option = {
  backgroundColor: '#1a1a2e',
  textStyle: { color: '#e0e0e0' },
  // Для осей
  xAxis: { axisLine: { lineStyle: { color: '#444' } } },
  yAxis: { axisLine: { lineStyle: { color: '#444' } }, splitLine: { lineStyle: { color: '#333' } } }
};
```

---

## Шаблон промпта для WidgetCodexAgent

При генерации виджета WidgetCodexAgent должен:

1. **Определить тип данных** из ContentNode (временные ряды? категории? иерархия? связи?)
2. **Выбрать тип графика** из матрицы выбора выше
3. **Сгенерировать option** на основе шаблонов из этого документа
4. **Обернуть в HTML** по шаблону из раздела "Общая структура"
5. **Добавить tooltip, legend, grid** для интерактивности
6. **Использовать адаптивный resize** `window.addEventListener('resize', ...)`
7. **Подставить реальные данные** из ContentNode вместо placeholder

### Формат данных из ContentNode

```javascript
// Данные приходят как объект:
const nodeData = {
  columns: ['date', 'sales', 'profit'],
  rows: [
    { date: '2024-01-01', sales: 100, profit: 15 },
    { date: '2024-02-01', sales: 200, profit: 30 },
    // ...
  ]
};

// Преобразование для ECharts dataset:
option = {
  dataset: {
    dimensions: nodeData.columns,
    source: nodeData.rows
  },
  xAxis: { type: 'category' },
  yAxis: {},
  series: [{ type: 'bar' }]
};
```

---

## Ссылки

- [Официальные примеры ECharts](https://echarts.apache.org/examples/en/index.html)
- [API Reference](https://echarts.apache.org/en/option.html)
- [ECharts Handbook](https://echarts.apache.org/handbook/en/get-started)
- [GitHub: apache/echarts](https://github.com/apache/echarts)
