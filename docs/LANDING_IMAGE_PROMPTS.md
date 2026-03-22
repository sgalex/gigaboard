# Промпты для иллюстраций лендинга GigaBoard

Единый визуальный стиль для всех изображений ниже — см. блок **«Базовый стиль»**. Файлы кладите в `apps/web/public/images/landing/` (имена файлов указаны у каждого промпта). Формат: **JPG или WebP**, ширина **1600–2400 px** по длинной стороне, сжатие под веб.

---

## Базовый стиль (добавляйте в начало каждого промпта)

```
Professional editorial tech illustration, dark UI theme, deep charcoal and black background (#0f1419 feel), subtle depth and soft gradients, accent color Sber green #21A038 used sparingly for highlights and connection lines, clean isometric or slight 3D perspective, no text on image, no logos, no watermarks, crisp vector-like shapes, soft studio lighting, modern fintech / data analytics aesthetic, 8k, high detail.
```

**Негативный хинт (при необходимости):** `no people faces, no readable text, no brand logos, no cluttered wireframes, no neon cyberpunk, no stock photo office`

---

## 1. Ценность — «Всё на одном экране»

**Файл:** `value-canvas.jpg`  
**Соотношение:** ~16:10

**Промпт:**  
*(Базовый стиль)* + `Abstract data pipeline on an infinite dark canvas: rounded nodes connected by glowing green (#21A038) lines, small chart and table silhouettes, sense of one unified workspace, minimal icons for database and chart, airy composition, hero illustration for analytics product.`

---

## 2. Ценность — «ИИ рядом с вами»

**Файл:** `value-ai-dialog.jpg`  
**Соотношение:** ~16:10

**Промпт:**  
*(Базовый стиль)* + `Side panel chat UI in dark mode next to a blurred data canvas: message bubbles as soft glassmorphism shapes, subtle sparkle or neural motif in green accent only, suggestion of AI assisting without showing text, calm collaborative vibe.`

---

## 3. Ценность — «Дашборды для презентаций»

**Файл:** `value-dashboard.jpg`  
**Соотношение:** ~16:10

**Промпт:**  
*(Базовый стиль)* + `Presentation dashboard mockup on dark background: KPI cards, one simple line chart and a text block as abstract shapes, grid alignment, export-ready layout feel, green accent on one chart series, elegant and minimal.`

---

## 4. Процесс — обзор трёх шагов

**Файл:** `how-process-overview.jpg`  
**Соотношение:** ~21:9 (широкий баннер)

**Промпт:**  
*(Базовый стиль)* + `Wide horizontal banner: left to right flow — data sources (file, cloud, API as simple icons) → central AI assist node (soft glow) → charts and insight cards on the right, three visual zones connected by a single green path (#21A038), storytelling left-to-right, no labels.`

---

## 5. Сценарий — менеджер продукта

**Файл:** `story-product.jpg`  
**Соотношение:** ~4:3

**Промпт:**  
*(Базовый стиль)* + `Product manager workspace vibe without people: laptop silhouette, floating metric charts and retention curve as abstract graphics, coffee cup subtle, deadline calm, green accent on one key metric, soft vignette.`

---

## 6. Сценарий — аналитик / исследователь

**Файл:** `story-analyst.jpg`  
**Соотношение:** ~4:3

**Промпт:**  
*(Базовый стиль)* + `Research analytics theme: two overlapping segment charts or Venn-like abstract shapes, hypothesis A/B as subtle dual panels, magnifying glass or compare motif very minimal, green highlights on insight areas, scientific but friendly.`

---

## 7. Сценарий — команда на встрече

**Файл:** `story-team.jpg`  
**Соотношение:** ~4:3

**Промпт:**  
*(Базовый стиль)* + `Team collaboration around data: abstract silhouettes of three figures as soft shapes without faces, shared screen with same chart duplicated as “synced” copies, sync / live pulse in green (#21A038), meeting table minimal, warm professional.`

---

## Чеклист файлов

| Файл | Секция |
|------|--------|
| `value-canvas.jpg` | Зачем — карточка 1 |
| `value-ai-dialog.jpg` | Зачем — карточка 2 |
| `value-dashboard.jpg` | Зачем — карточка 3 |
| `how-process-overview.jpg` | Как работает — под заголовком |
| `story-product.jpg` | Кому — карточка 1 |
| `story-analyst.jpg` | Кому — карточка 2 |
| `story-team.jpg` | Кому — карточка 3 |

После генерации положите файлы в `public/images/landing/`. Если файла нет, на лендинге показывается плейсхолдер с именем файла.
