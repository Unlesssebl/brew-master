# Brew-master 🍺

Экономическая стратегия с элементами RPG, менеджмента и асинхронного PvP в формате Telegram-бота. 

---

## 🛠️ Стек технологий

- **Язык**: Python 3.13+
- **Пакетный менеджер**: [uv](https://github.com/astral-sh/uv) (быстрая и современная альтернатива pip/poetry)
- **Telegram Bot API**: [aiogram 3.x](https://github.com/aiogram/aiogram) (асинхронный фреймворк)
- **База данных**: [PostgreSQL](https://www.postgresql.org/)
- **ORM / БД Драйвер**: [SQLAlchemy 2.x](https://www.sqlalchemy.org/) + [asyncpg](https://github.com/MagicStack/asyncpg) (полностью асинхронная работа)
- **Миграции**: [Alembic](https://alembic.sqlalchemy.org/)
- **Валидация данных**: [Pydantic v2](https://docs.pydantic.dev/) & `pydantic-settings`
- **ИИ-слой (Game Master)**: [google-genai](https://github.com/googleapis/google-genai) (Gemini SDK)
- **Линтер и форматирование**: [Ruff](https://github.com/astral-sh/ruff)

---

## 📂 Структура проекта

Основа проекта спроектирована по модульному принципу:

```text
brew-master/
│
├── .gemini/               # Внутренние правила AI-ассистентов
├── docs/                  # Документация проекта (GDD, Архитектура, БД, Экономика, AI)
│   ├── 01_gdd.md          # Game Design Document — механики, геймплей, концепция
│   ├── 02_architecture.md # Архитектура системы — структура проекта, паттерны
│   ├── 03_database.md     # Схема БД — таблицы, связи, поля
│   ├── 04_math_and_economy.md # Математика и экономика — формулы, балансировка
│   ├── 05_ai_pipelines.md # AI пайплайны — агенты, процессы
│   ├── 06_llm_config.md   # Конфигурация LLM — настройки генерации и промпты
│   └── 07_telegram_native_game_dev.md # База знаний по TG Bot API
│
├── infrastructure/        # docker-compose.yml, скрипты развертывания
│
├── src/                   # Весь исходный код
│   ├── __init__.py
│   ├── config.py          # Конфигурация проекта (загрузка и валидация .env)
│   │
│   ├── bot/               # Изолированный клиент Telegram
│   │   ├── __init__.py
│   │   ├── handlers/      # Обработка команд (напр., /brew 40 30 20 10)
│   │   ├── keyboards/     # Инлайн-кнопки и меню
│   │   └── middlewares/   # Проверки сессий и антиспам
│   │
│   ├── core/              # Математика и бизнес-правила (Pure Functions)
│   │   ├── crafting.py    # Математика статов пива (без зависимостей)
│   │   ├── economy.py     # Логика расчета налогов и демпинга
│   │   ├── pvp.py         # Расчет PvP механик (диверсии, защита, шпионаж)
│   │   └── expeditions.py # Расчет событий в рогалик-экспедициях
│   │
│   ├── database/          # Слой хранения и доступа к данным
│   │   ├── alembic/       # Миграции структуры БД
│   │   ├── models/        # SQLAlchemy модели дата-классов
│   │   └── repositories/  # Классы с транзакциями (player_repo, queue_repo)
│   │
│   ├── llm_engine/        # Невидимый Гейм-мастер
│   │   ├── prompts.py     # Шаблоны системных промптов
│   │   ├── schemas.py     # Pydantic-схемы для LLM (GameEvent)
│   │   └── generator.py   # Логика вызова API и система Fallback
│   │
│   └── workers/           # Фоновые процессы (PostgreSQL IPC)
│       ├── royalty.py     # Скрипт начисления роялти из логов (FOR UPDATE SKIP LOCKED)
│       └── rival_ceo.py   # ИИ-конкуренты на рынке
│
├── tests/                 # Модульные и интеграционные тесты (pytest)
│
├── .env.template          # Шаблон переменных окружения
├── .gitignore             # Игнорируемые файлы Git
├── alembic.ini            # Настройки Alembic
├── pyproject.toml         # Зависимости проекта (uv)
├── ruff.toml              # Правила линтера Ruff
└── README.md              # Документация разработчика (этот файл)
```

---

## 🚀 Быстрый старт

### 1. Подготовка окружения и установка зависимостей

Убедитесь, что у вас установлен [uv](https://github.com/astral-sh/uv).

Выполните команду для автоматического создания виртуального окружения и установки всех зависимостей (включая инструменты разработки):

```bash
uv sync
```

### 2. Настройка конфигурации

Создайте файл `.env` на основе шаблона `.env.template`:

```bash
cp .env.template .env
```

Заполните переменные в `.env` (токен Telegram-бота, реквизиты PostgreSQL и ключ Gemini API).

### 3. Применение миграций базы данных

Для применения миграций и создания таблиц в базе данных выполните команду:

```bash
uv run alembic upgrade head
```

При добавлении новых SQLAlchemy моделей в `src/database/models/` создайте автомиграцию:

```bash
uv run alembic revision --autogenerate -m "description"
```

### 4. Линтинг и форматирование кода

Для проверки кода на соответствие стандартам:

```bash
uv run ruff check .
```

Для автоматического исправления ошибок форматирования и сортировки импортов:

```bash
uv run ruff format .
```

---

## 📝 Разработка фич

Перед началом реализации новых игровых механик, изменений баланса или API обязательно ознакомьтесь с проектными правилами в `.gemini/rules/project.md` и документами в директории `docs/`.
