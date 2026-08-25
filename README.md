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

## Фронт (`frontend-app`)

React + TypeScript, сборка Vite; realtime через `centrifuge-js`.

```bash
cd frontend-app
npm install
npm run dev          # адреса API/WS — в .env.development
npm run build        # типы + прод-сборка в dist/
```

Дев-стенд экранов на фикстурах, без бэка и авторизации: `?mock=1`.

## Тесты

```bash
cd backend
pytest

# Живые проверки против стенда
python scripts/stand_check.py        # публичный путь: HTTPS + WSS + push
python scripts/repro_cross_room.py   # личный канал не смешивает комнаты
```

```bash
cd frontend-app
npm run build && npm run lint
```

## Прод (Docker Compose)

```bash
docker compose up -d --build   # поднимает app + postgres + redis + centrifugo, применяет миграции
```
