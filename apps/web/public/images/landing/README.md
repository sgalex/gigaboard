# Landing Page Images

Эта папка содержит изображения для лендинга GigaBoard.

## Структура

- `hero-background.png` (2400x1200px) - Фоновое изображение Hero секции
- `data-pipeline.png` (1600x900px) - Иллюстрация Data Pipeline для Core Features
- `real-time-streaming.png` (1400x1000px) - Визуализация Real-Time Streaming
- `use-case-product-manager.png` (800x1000px) - Product Manager сценарий
- `use-case-data-scientist.png` (800x1000px) - Data Scientist сценарий
- `use-case-devops.png` (800x1000px) - DevOps Engineer сценарий
- `use-case-student.png` (800x1000px) - Student/Researcher сценарий

## Генерация изображений

Промпты для генерации всех изображений находятся в:
`docs/LANDING_PAGE_IMAGE_PROMPTS.md`

Используйте NanoBanana для генерации изображений по этим промптам.

## Использование в коде

Изображения из папки `public/` доступны напрямую по URL:

```tsx
<img src="/images/landing/hero-background.png" alt="Hero Background" />
```

## Требования к изображениям

- **Формат**: PNG с поддержкой прозрачности (где применимо)
- **Оптимизация**: Сжатие для веб (под 500KB на файл)
- **Цветовая схема**: Sber Green (#21A038) как основной цвет
- **Стиль**: Профессиональная tech-иллюстрация

## Текущий статус

- [ ] hero-background.png - **Placeholder** (Unsplash)
- [ ] data-pipeline.png - **Placeholder** (Unsplash)
- [ ] real-time-streaming.png - **Placeholder** (Unsplash)
- [ ] use-case-product-manager.png - **Placeholder** (Unsplash)
- [ ] use-case-data-scientist.png - **Placeholder** (Unsplash)
- [ ] use-case-devops.png - **Placeholder** (Unsplash)
- [ ] use-case-student.png - **Placeholder** (Unsplash)

После генерации изображений с помощью NanoBanana, замените placeholder URL в `LandingPage.tsx` на локальные пути.
