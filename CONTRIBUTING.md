# Contributing to GigaBoard

Спасибо за интерес к проекту GigaBoard! Мы приветствуем любые вклады — от исправления опечаток до новых функций.

## 🚀 Как начать

### 1. Fork и клонирование

```bash
# Fork репозиторий через GitHub UI
# Затем клонируйте ваш fork
git clone https://github.com/YOUR_USERNAME/gigaboard.git
cd gigaboard
```

### 2. Настройка окружения

```bash
# Frontend dependencies
npm install

# Backend dependencies (using uv)
cd apps/backend
uv sync
cd ../..

# Настройте .env файл
cp apps/backend/.env.example apps/backend/.env
# Отредактируйте .env с вашими настройками
```

### 3. Создайте feature branch

```bash
git checkout -b feature/AmazingFeature
```

## 📝 Правила разработки

### Стиль кода

**Backend (Python):**
- Используйте `uv` для управления зависимостями
- Следуйте PEP 8
- Используйте type hints
- Документируйте функции docstrings

**Frontend (TypeScript/React):**
- Используйте TypeScript для всех компонентов
- Следуйте существующей структуре проекта
- Используйте функциональные компоненты с hooks
- Именуйте компоненты в PascalCase

### Структура коммитов

Следуйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавить поддержку Excel файлов в FileExtractor
fix: исправить memory leak в WebSocket соединении
docs: обновить README с примерами использования
refactor: переработать TransformationAgent для лучшей производительности
test: добавить unit тесты для SourceNodeService
```

### Тестирование

**Backend:**
```bash
cd apps/backend
uv run pytest
```

**Frontend:**
```bash
npm run test
```

## 📚 Документация

При добавлении новых функций:

1. Обновите соответствующие файлы в папке `docs/`
2. Добавьте JSDoc/docstrings к коду
3. Обновите API документацию в [docs/API.md](docs/API.md) (если применимо)
4. Проверьте [docs/DEVELOPER_CHECKLIST.md](docs/DEVELOPER_CHECKLIST.md)

**Важно:** Следуйте инструкциям в [.github/copilot-instructions.md](.github/copilot-instructions.md) при работе над проектом.

## 🔍 Pull Request процесс

1. Убедитесь, что ваш код проходит все тесты
2. Обновите документацию
3. Создайте Pull Request с чётким описанием изменений
4. Свяжите PR с соответствующим issue (если есть)
5. Дождитесь code review

### PR Checklist

- [ ] Код соответствует стилю проекта
- [ ] Проведён self-review
- [ ] Добавлены/обновлены тесты
- [ ] Обновлена документация
- [ ] Все тесты проходят
- [ ] Нет новых warnings
- [ ] Commit messages следуют Conventional Commits

## 🐛 Сообщения об ошибках

Используйте GitHub Issues с шаблоном Bug Report:
- Чёткое описание проблемы
- Шаги для воспроизведения
- Ожидаемое vs фактическое поведение
- Информация об окружении
- Скриншоты (если применимо)

## 💡 Предложения функций

Используйте GitHub Issues с шаблоном Feature Request:
- Опишите проблему, которую решает фича
- Предложите решение
- Опишите альтернативы
- Добавьте контекст (скриншоты, примеры)

## 🏗️ Приоритеты разработки

Проверьте:
1. [docs/ROADMAP.md](docs/ROADMAP.md) — текущие приоритеты
2. [.vscode/CURRENT_FOCUS.md](.vscode/CURRENT_FOCUS.md) — текущая фаза
3. GitHub Issues с меткой `good first issue` — для начинающих

## 🤝 Code Review

При review чужих PR:
- Будьте конструктивны и вежливы
- Проверяйте соответствие архитектуре в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Тестируйте изменения локально
- Оставляйте чёткие комментарии

## 📞 Связь

- GitHub Issues — для багов и фич
- GitHub Discussions — для вопросов и обсуждений
- Pull Requests — для code review

## 📄 Лицензия

Внося вклад в проект, вы соглашаетесь с тем, что ваш код будет лицензирован под MIT License.

---

Спасибо за вклад в GigaBoard! 🚀
