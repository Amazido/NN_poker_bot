# Odessa Poker

Многопользовательский «Одесский покер» для Telegram WebApp. Бэкенд на FastAPI,
Postgres + Redis + Centrifugo, упаковка в Docker.

Полное описание — в [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).
История решений — в [docs/CHANGELOG.md](./docs/CHANGELOG.md).

## Быстрый старт (локально)

```bash
# 1) Инфраструктура (Postgres, Redis, Centrifugo)
cd backend
docker compose -f docker-compose.dev.yml up -d

# 2) Зависимости
python -m venv .venv
. .venv/Scripts/activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3) Переменные окружения
copy .env.example .env        # bash: cp .env.example .env

# 4) Миграции
alembic upgrade head

# 5) Запуск API (при старте создаётся дефолтная редакция правил)
uvicorn app.main:app --reload
```

Swagger: http://localhost:8000/docs

## Тесты

```bash
cd backend
pytest
```

## Прод (Docker Compose)

```bash
docker compose up -d --build   # поднимает app + postgres + redis + centrifugo, применяет миграции
```
