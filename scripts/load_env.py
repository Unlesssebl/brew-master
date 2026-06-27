import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path, чтобы можно было импортировать config.py и модули src
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Вручную загружаем переменные из .env, так как при запуске из папки scripts/ pydantic-settings не найдет .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from config import settings
BOT_TOKEN = settings.BOT_TOKEN
