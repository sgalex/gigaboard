# GigaBoard Design System

## Обзор

GigaBoard использует современный дизайн-систему на основе **shadcn/ui** и **Tailwind CSS** с расширенной семантической цветовой палитрой. Все компоненты и стили управляются через CSS-переменные, что позволяет просто переключать темы и поддерживать консистентность интерфейса.

---

## Архитектура

### Слои стилей

1. **CSS-переменные** (`src/index.css`)
   - Семантические токены цветов (primary, secondary, accent, success, warning, info, destructive)
   - Поддержка light/dark режимов через `.dark` класс
   - Токены типографики и отступов (через Tailwind)

2. **Tailwind CSS** (`tailwind.config.js`)
   - Расширенная палитра на основе CSS-переменных
   - Кастомные утилиты для border radius и font family
   - Dark mode: `class`-based (управляется через `ThemeProvider`)

3. **shadcn/ui компоненты** (`src/components/ui/`)
   - Button, Card, Input, Label и др.
   - Используют CSS-переменные для цветов
   - Поддерживают варианты (`variant`, `size`)

---

## Цветовая палитра

### Семантические токены

#### Light Mode (`:root`)
| Токен           | HSL               | Назначение                |
| --------------- | ----------------- | ------------------------- |
| `--background`  | 210 40% 98%       | Основной фон              |
| `--foreground`  | 222.2 84% 4.9%    | Основной текст            |
| `--card`        | 0 0% 100%         | Фон карточек              |
| `--primary`     | 221.2 83.2% 53.3% | Основной цвет (синий)     |
| `--secondary`   | 210 40% 96.1%     | Вторичный (светлый)       |
| `--accent`      | 188 100% 50%      | Акцент (голубой)          |
| `--success`     | 142 76.2% 36.3%   | Успех (зелёный)           |
| `--warning`     | 38.6 92.1% 50.2%  | Предупреждение (жёлтый)   |
| `--info`        | 217.2 91.2% 59.8% | Информация (голубой)      |
| `--destructive` | 0 84.2% 60.2%     | Ошибка/Удаление (красный) |
| `--muted`       | 210 40% 96.1%     | Приглушённый (серый)      |
| `--border`      | 214.3 31.8% 91.4% | Границы                   |

#### Dark Mode (`.dark`)
- Инвертированные фоны (background → nearly-black, card → slightly-lighter)
- Более насыщенные accent цвета для контраста
- Success/Warning/Info адаптированы для видимости

### Использование в Tailwind

```tsx
// Фоны
<div className="bg-background">            {/* основной фон */}
<div className="bg-card">                 {/* фон карточки */}
<div className="bg-primary">              {/* синий фон */}
<div className="bg-success">              {/* зелёный фон */}

// Текст
<p className="text-foreground">           {/* основной текст */}
<p className="text-muted-foreground">     {/* приглушённый текст */}
<p className="text-primary">              {/* синий текст */}

// Бордеры
<div className="border border-border">    {/* стандартный бордер */}
<div className="border border-primary">   {/* цветной бордер */}
```

---

## Компоненты

### Button

```tsx
import { Button } from '@/components/ui/button'

// Варианты
<Button variant="default">Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="destructive">Delete</Button>

// Размеры
<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
<Button size="icon">✓</Button>
```

### Card

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'

<Card>
  <CardHeader>
    <CardTitle>Заголовок</CardTitle>
    <CardDescription>Описание</CardDescription>
  </CardHeader>
  <CardContent>
    Содержимое
  </CardContent>
  <CardFooter>
    Footer
  </CardFooter>
</Card>
```

### Input & Label

```tsx
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

<div className="space-y-2">
  <Label htmlFor="email">Email</Label>
  <Input
    id="email"
    type="email"
    placeholder="name@example.com"
    className="bg-background border-border"
  />
</div>
```

---

## Тема (Light/Dark)

### Использование `ThemeProvider`

```tsx
import { ThemeProvider } from '@/components/ThemeProvider'

<ThemeProvider defaultTheme="system" storageKey="gigaboard-theme">
  <App />
</ThemeProvider>
```

### Переключатель темы

```tsx
import { ThemeToggle } from '@/components/ThemeToggle'

<ThemeToggle />  // Автоматически переключает light ↔ dark
```

### Управление темой из компонента

```tsx
import { useTheme } from '@/components/ThemeProvider'

function MyComponent() {
  const { theme, setTheme } = useTheme()
  
  return (
    <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
      Переключить тему
    </button>
  )
}
```

---

## Лучшие практики

### ✅ Делайте

1. **Используйте семантические токены вместо hardcoded цветов**
   ```tsx
   // Хорошо
   <div className="bg-card text-foreground border border-border" />
   
   // Плохо
   <div style={{ backgroundColor: '#ffffff', color: '#000000' }} />
   ```

2. **Используйте компоненты из `ui/`**
   ```tsx
   // Хорошо
   <Button variant="primary">Send</Button>
   
   // Плохо
   <button className="bg-blue-500 text-white">Send</button>
   ```

3. **Применяйте Tailwind утилиты для spacing/sizing**
   ```tsx
   // Хорошо
   <div className="p-6 space-y-4 rounded-lg" />
   
   // Плохо
   <div style={{ padding: '24px', gap: '16px', borderRadius: '8px' }} />
   ```

4. **Используйте `space-y` / `space-x` для отступов между элементами**
   ```tsx
   <div className="space-y-4">
     <Input />
     <Input />
     <Button>Send</Button>
   </div>
   ```

### ❌ Избегайте

1. **Hardcoded цвета и styles**
   ```tsx
   // ❌ Плохо
   <div style={{ backgroundColor: '#f0f0f0', color: '#333' }} />
   ```

2. **Использование neutral цветов (gray-500, slate-500, zinc-500)**
   ```tsx
   // ❌ Плохо
   <p className="text-gray-500">Comment</p>
   
   // ✅ Хорошо
   <p className="text-muted-foreground">Comment</p>
   ```

3. **Инлайн стили вместо Tailwind**
   ```tsx
   // ❌ Плохо
   <div style={{ display: 'flex', gap: '8px' }} />
   
   // ✅ Хорошо
   <div className="flex gap-2" />
   ```

---

## Расширение палитры

Если нужно добавить новый цвет:

1. **Добавьте CSS-переменную в `src/index.css`**
   ```css
   :root {
       --brand: 260 100% 50%;
   }
   
   .dark {
       --brand: 260 100% 60%;
   }
   ```

2. **Подключите в `tailwind.config.js`**
   ```js
   colors: {
       brand: {
           DEFAULT: "hsl(var(--brand))",
           foreground: "hsl(var(--brand-foreground))",
       },
   }
   ```

3. **Используйте в компонентах**
   ```tsx
   <Button className="bg-brand text-brand-foreground">Custom</Button>
   ```

---

## Ресурсы

- [Tailwind CSS Documentation](https://tailwindcss.com)
- [shadcn/ui Components](https://ui.shadcn.com)
- [HSL Color Reference](https://en.wikipedia.org/wiki/HSL_and_HSV)
- [Contrast Checker](https://webaim.org/resources/contrastchecker/)

---

**Последнее обновление:** January 23, 2026
