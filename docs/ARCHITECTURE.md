# Odessa Poker — архитектура

Документ описывает систему в актуальной редакции. История смысловых изменений —
в [CHANGELOG.md](./CHANGELOG.md).

## Обзор

Одесский покер — многопользовательская пошаговая взяточная игра с заказами,
козырем и джокерами. Хостится на сервере, упаковывается в Docker, играется
внутри Telegram WebApp. Логин — только через Telegram. Быстрый обмен игровыми
событиями — через WebSocket (Centrifugo).

## Стек

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic.
- **БД**: PostgreSQL (JSONB для конфигов правил, снапшотов раздач, журнала).
- **Live-стейт**: Redis — источник истины для розыгрыша (руки, ход, доступные действия).
- **Realtime**: Centrifugo (server API publish + JWT для подключения клиентов).
- **Инфраструктура**: Docker Compose (dev — только БД/Redis/Centrifugo; prod — плюс app).

## Слои и модули (`backend/app`)

- `config.py` — конфиг из ENV/.env.
- `core/` — `redis.py` (клиент + reconnect), `centrifugo.py` (publish + токены), `exceptions.py`.
- `db/` — `base.py` (async engine/session), `models.py` (ORM).
- `auth/` — проверка Telegram initData (HMAC-SHA256), JWT, dependency текущего пользователя.
- `poker/` — доменное ядро:
  - `cards.py` — колода 54, кодировка карт, **старшинство во взятке**.
  - `rules.py` — `RulesEdition` (конфиг варианта, последовательность раундов, счёт, «крюк»).
  - `engine.py` — **чистый конечный автомат раунда** над dict-состоянием.
  - `state.py` — Redis-хранилище стейта + `public_view`/`private_view` + набор активных комнат.
  - `channels.py` — публикация снапшотов/событий в Centrifugo.
  - `service.py` — оркестрация (создать/войти/старт/действие) + БД + Redis + Centrifugo.
  - `router.py` — REST.
- `repositories/pg/` — доступ к БД (user, rules_edition, room, round + журнал действий).

## Данные (PostgreSQL)

- `users` — игроки (telegram_id/username, тип, баланс).
- `rules_editions` — редакция правил + мета, версионируется по `(code, version)`; `config` (JSONB).
- `game_rooms` — комната/стол: статус, `join_code`, редакция правил, `round_index`,
  стартовый сдающий, текущая раздача.
- `room_players` — посадка: место (`seat_index`), накопленный счёт матча.
- `game_rounds` — раздача: количество карт, сдающий, козырь, фаза, заказы, взятки, итог.
- `round_actions` — append-only журнал ходов (для истории/восстановления).

Live-стейт (полное состояние, включая руки) хранится в Redis:
`poker:room:{room_id}:state`. Postgres — история и восстановление.

## Правила (дефолтная редакция `odessa_classic v1`)

- Колода 54 (52 + 2 джокера красный/чёрный).
- Игроков 3–5. Раундов `18 + n`: `1..9`, затем `10` повторяется `n` раз (каждый
  игрок сдаёт «десятку» по разу), затем `9..1`.
- Козырь = масть вскрытой ведущей карты колоды; джокер как ведущий → раунд без козыря.
- Фазы раздачи: **торги** (каждый заказывает число взяток) → **розыгрыш** → **счёт**.
- **Крюк**: последний в заказе (= сдающий) не может сделать сумму заказов равной числу карт.
- Порядок: первым заказывает и первым ходит игрок после сдающего; далее взятку ведёт
  победитель предыдущей. Сдающий сменяется по кругу каждую раздачу (стартовый — случайный).
- Обязанность масти: масть сброса → иначе козырь → иначе любая (пустышка, не берёт).
  Джокеров можно класть всегда. Джокер, ведущий взятку, масти не задаёт.
- **Старшинство во взятке (с козырем)**: козырный джокер > козыри > масть сброса >
  пустышки. **Некозырной джокер** берёт масть сброса только если её цвет совпадает с
  цветом джокера; против чужого цвета он пустышка; если ведёт взятку — берёт её, но
  проигрывает любому козырю (контекстное правило, см. журнал 2026-08-09).
- **Счёт**: точный заказ `+10 × взятки`; заказал 0 и взял 0 → `+10`; перебор → `−5`
  (фикс); недобор → `−10` за каждую недобранную.
- Флаги редакции (по умолчанию off): `offcolor_beats_oncolor`, `two_beats_ace_same_suit`.

### Допущение (нет в исходных правилах)

В раунде **без козыря** старшим джокером считается тот, что вскрыт ведущим колоду;
второй джокер — следующий по силе; оба бьют любые обычные карты. Подлежит уточнению.

## Realtime (Centrifugo)

- **Каналы** (`prefix` = `CENTRIFUGO_CHANNEL_PREFIX`, в prod `prod`):
  - `{prefix}:room:{room_id}` — публичный канал комнаты;
  - `{prefix}:user#{user_id}` — личный (user-limited) канал игрока.
- **Что публикуется** (сервер, `channels.py`):
  - `create`/`join` → `{"type":"lobby","state":<public>}` в канал комнаты;
  - `start` → `{"type":"state",...}` в комнату + `{"type":"private",...}` каждому;
  - `action` → `{"type":"events",...}` (лента) + `{"type":"state",...}` в комнату
    и приватные руки игрокам.
- **Токен подключения**: `GET /auth/centrifugo-token` (JWT `sub = user_id`, HMAC).
- **Транспорт наружу**: браузер → `wss://odessky.win/connection/websocket` →
  Cloudflare → origin nginx (`location /connection/`) → контейнер Centrifugo
  (`127.0.0.1:8001`, наружу напрямую не публикуется).
- **Конфиг Centrifugo**: `backend/centrifugo.prod.json` (namespace `prod` с
  `allow_user_limited_channels`, `allowed_origins: https://odessky.win`, admin off).
  Секреты (`http_api.key`, `client.token.hmac_secret_key`) приходят из ENV
  (`CENTRIFUGO_API_KEY`, `CENTRIFUGO_TOKEN_SECRET`) — в файле их нет. App и Centrifugo
  используют одни и те же значения из серверного `.env`.
- **Проверка**: детерминированно — pytest (`test_realtime_publishes_on_transitions`,
  перехват публикаций); вживую — `backend/scripts/ws_smoke.py` (подписка по WS +
  публикация через API, проверка доставки).
- **Фронт на WS** (`centrifuge-js`) пока не подключён — клиент обновляется REST-поллингом
  (следующая итерация).

## API (кратко)

- `POST /auth/telegram`, `POST /auth/dev` (DEBUG), `GET /auth/me`, `POST /auth/logout`,
  `GET /auth/centrifugo-token`.
- `POST /rooms` (создать), `POST /rooms/join`, `POST /rooms/{id}/start`,
  `POST /rooms/{id}/action` (`bid` / `play_card`), `GET /rooms/{id}` (публичный стейт),
  `GET /rooms/{id}/hand` (моя рука + доступные действия).

## Таймер хода

Фоновая задача сканирует активные комнаты (Redis-set) и при истечении дедлайна
хода делает авто-действие (минимальный допустимый заказ / первая легальная карта).

## Локальный запуск / проверка

1. `docker compose -f backend/docker-compose.dev.yml up -d` (Postgres, Redis, Centrifugo).
2. `alembic upgrade head` (из `backend/`).
3. `uvicorn app.main:app --reload` — при старте создаётся дефолтная редакция правил.
4. Через `POST /auth/dev` завести игроков, `POST /rooms` + `join` + `start`, играть
   через `POST /rooms/{id}/action`, наблюдая руки и доступные действия.

### Тесты

- Юнит + e2e: `pytest` (из `backend/`). E2E поднимает приложение поверх реального
  Postgres (отдельная БД `odessa_test`), live-стейт in-memory, Centrifugo no-op —
  прогоняет полный матч на короткой редакции правил (см. `tests/conftest.py`).
- Живой realtime-смоук: `python scripts/ws_smoke.py` (по умолчанию против dev
  Centrifugo `localhost:8001`).

Prod-стек (`docker-compose.yml`) монтирует `backend/centrifugo.prod.json` и
публикует Centrifugo только на `127.0.0.1:8001` (наружу — через nginx).
