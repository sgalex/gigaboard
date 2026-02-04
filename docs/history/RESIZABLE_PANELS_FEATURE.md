# Resizable Side Panels

## Описание

Боковые панели (левая - Project Explorer, правая - AI Assistant) теперь поддерживают изменение размера с сохранением состояния в localStorage.

## Функциональность

### Изменение размера
- **Перетаскивание**: Наведите курсор на разделитель между панелью и основным контентом, появится визуальный индикатор. Зажмите и перетащите для изменения размера.
- **Диапазон размеров**: От 200px до 800px
- **Плавность**: Используется `requestAnimationFrame` для оптимизации производительности

### Сброс размера
- **Двойной клик**: Дважды кликните на разделитель для сброса размера панели к значению по умолчанию
- **По умолчанию**:
  - Левая панель: 320px
  - Правая панель: 384px

### Сохранение состояния
- Размеры панелей автоматически сохраняются в `localStorage`
- Ключи хранения:
  - `gigaboard-left-panel-width` - ширина левой панели
  - `gigaboard-right-panel-width` - ширина правой панели
- При следующем открытии приложения размеры восстанавливаются

## Компоненты

### ResizableHandle
**Файл**: `apps/web/src/components/layout/ResizableHandle.tsx`

Компонент разделителя с поддержкой drag-and-drop.

**Props**:
- `onResize: (delta: number) => void` - callback для изменения размера
- `onReset?: () => void` - callback для сброса размера (вызывается при двойном клике)
- `side: 'left' | 'right'` - сторона панели
- `className?: string` - дополнительные CSS классы

**Особенности**:
- Предотвращение выделения текста во время перетаскивания
- Визуальная индикация при наведении и перетаскивании
- Оптимизация производительности через `requestAnimationFrame`

### AppLayout
**Файл**: `apps/web/src/components/layout/AppLayout.tsx`

Обновлен для поддержки resizable панелей.

**Изменения**:
- Использование динамической ширины вместо фиксированных классов Tailwind
- Интеграция `ResizableHandle` компонентов
- Callbacks для изменения и сброса размеров панелей

### UIStore
**Файл**: `apps/web/src/store/uiStore.ts`

Добавлены новые состояния и действия для управления размерами панелей.

**Новые поля состояния**:
- `leftPanelWidth: number` - ширина левой панели
- `rightPanelWidth: number` - ширина правой панели

**Новые действия**:
- `setLeftPanelWidth(width: number)` - установить ширину левой панели
- `setRightPanelWidth(width: number)` - установить ширину правой панели

**Utility функции**:
- `loadPanelWidth(key, defaultValue)` - загрузка из localStorage
- `savePanelWidth(key, width)` - сохранение в localStorage

## UX улучшения

1. **Визуальная обратная связь**:
   - Изменение цвета при наведении
   - Более яркая подсветка при перетаскивании
   - Изменение курсора на `col-resize`

2. **Плавность**:
   - Smooth transitions при открытии/закрытии панелей
   - Оптимизированные обновления через RAF

3. **Подсказки**:
   - Title атрибут на разделителе с инструкцией по использованию

## Техническая реализация

### localStorage
```typescript
// Ключи
const STORAGE_KEYS = {
    LEFT_PANEL_WIDTH: 'gigaboard-left-panel-width',
    RIGHT_PANEL_WIDTH: 'gigaboard-right-panel-width',
}

// Валидация при загрузке
- Проверка на NaN
- Диапазон от 200px до 800px
- Fallback на значение по умолчанию
```

### Обработка событий
```typescript
// Drag handling
1. onMouseDown - начало перетаскивания
2. mousemove (document) - обновление позиции через RAF
3. mouseup (document) - завершение перетаскивания

// Reset handling
- onDoubleClick - сброс к значению по умолчанию
```

### Производительность
- Использование `requestAnimationFrame` вместо прямых обновлений
- Cancellation предыдущих RAF при новых событиях
- Cleanup в useEffect return

## Совместимость

- ✅ React 18+
- ✅ TypeScript
- ✅ Zustand state management
- ✅ Tailwind CSS
- ✅ Современные браузеры с поддержкой localStorage

## Будущие улучшения

- [ ] Поддержка touch events для мобильных устройств
- [ ] Анимация при сбросе размера
- [ ] Контекстное меню на разделителе с дополнительными опциями
- [ ] Keyboard shortcuts для изменения размера
- [ ] Preset размеров (S, M, L, XL)
