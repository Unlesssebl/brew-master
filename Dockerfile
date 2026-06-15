FROM python:3.11-slim

# Предотвращение записи pyc-файлов на диск и буферизации вывода
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Установка системных зависимостей, необходимых для сборки бинарных пакетов (например, asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование структуры проекта
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY main.py config.py alembic.ini ./

# Применение миграций Alembic и запуск главного оркестратора
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
