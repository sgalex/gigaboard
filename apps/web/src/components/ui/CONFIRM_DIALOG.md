# ConfirmDialog - Универсальный компонент диалогов подтверждения

Централизованный компонент для всех диалоговых окон подтверждения в GigaBoard.

## Использование

```tsx
import { useState } from 'react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

function MyComponent() {
    const [isOpen, setIsOpen] = useState(false)
    const [isLoading, setIsLoading] = useState(false)

    const handleDelete = async () => {
        setIsLoading(true)
        try {
            await deleteItem()
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <>
            <Button onClick={() => setIsOpen(true)}>Удалить</Button>
            
            <ConfirmDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title="Удалить элемент?"
                description="Это действие нельзя отменить. Все данные будут удалены."
                variant="danger"
                onConfirm={handleDelete}
                loading={isLoading}
                confirmText="Удалить"
                cancelText="Отмена"
            />
        </>
    )
}
```

## Props

| Prop           | Type                              | Default         | Описание                         |
| -------------- | --------------------------------- | --------------- | -------------------------------- |
| `open`         | `boolean`                         | —               | Открыт ли диалог                 |
| `onOpenChange` | `(open: boolean) => void`         | —               | Callback при изменении состояния |
| `title`        | `string`                          | —               | Заголовок диалога                |
| `description`  | `string`                          | —               | Описание/предупреждение          |
| `confirmText`  | `string`                          | `'Подтвердить'` | Текст кнопки подтверждения       |
| `cancelText`   | `string`                          | `'Отмена'`      | Текст кнопки отмены              |
| `variant`      | `'danger' \| 'warning' \| 'info'` | `'info'`        | Вариант стиля                    |
| `onConfirm`    | `() => void \| Promise<void>`     | —               | Callback при подтверждении       |
| `loading`      | `boolean`                         | `false`         | Состояние загрузки               |

## Варианты (Variants)

### `danger` - Опасные действия
Используйте для необратимых действий (удаление).

```tsx
<ConfirmDialog
    variant="danger"
    title="Удалить доску?"
    description="Все данные будут безвозвратно удалены."
    confirmText="Удалить"
/>
```

### `warning` - Предупреждения
Используйте для действий требующих внимания.

```tsx
<ConfirmDialog
    variant="warning"
    title="Перезаписать данные?"
    description="Существующие данные будут заменены."
    confirmText="Перезаписать"
/>
```

### `info` - Информационные
Используйте для обычных подтверждений.

```tsx
<ConfirmDialog
    variant="info"
    title="Сохранить изменения?"
    description="Изменения будут применены к текущему проекту."
    confirmText="Сохранить"
/>
```

## Примеры использования

### Удаление доски (ProjectOverviewPage)

```tsx
const [boardToDelete, setBoardToDelete] = useState<Board | null>(null)
const [isDeleting, setIsDeleting] = useState(false)

const handleDelete = async () => {
    if (!boardToDelete) return
    setIsDeleting(true)
    try {
        await deleteBoard(boardToDelete.id)
    } finally {
        setIsDeleting(false)
        setBoardToDelete(null)
    }
}

return (
    <>
        <Button onClick={() => setBoardToDelete(board)}>
            Удалить
        </Button>
        
        <ConfirmDialog
            open={!!boardToDelete}
            onOpenChange={(open) => !open && setBoardToDelete(null)}
            title="Удалить доску?"
            description={`Вы уверены, что хотите удалить доску "${boardToDelete?.name}"?`}
            variant="danger"
            onConfirm={handleDelete}
            loading={isDeleting}
        />
    </>
)
```

## Стиль и доступность

- ✅ Автоматическое закрытие по ESC
- ✅ Управление фокусом (trap focus)
- ✅ Блокировка прокрутки фона
- ✅ Анимация появления/исчезновения
- ✅ Responsive дизайн
- ✅ Поддержка клавиатуры (Enter/Esc)
- ✅ Состояние loading (disabled buttons)

## Стандарты

Все диалоги подтверждения в GigaBoard должны использовать этот компонент для:
- Единообразия UX
- Централизованного управления стилями
- Легкости обновления дизайна
- Соответствия accessibility стандартам
