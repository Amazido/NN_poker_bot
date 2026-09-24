# Odessa Poker — деплой и эксплуатация

Документ описывает прод в актуальной редакции. История смысловых изменений —
в [CHANGELOG.md](./CHANGELOG.md). Устройство самой системы — в
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Что и где крутится

| | |
|---|---|
| Публичный адрес | `https://odessky.win` |
| Сервер | `5.188.21.132`, Ubuntu 24.04, FastVPS |
| Ресурсы | 2 ГБ RAM (без свопа), диск 8 ГБ |
| Доступ | SSH по паролю, пользователь `root`, порт 22 |
| Репозиторий на сервере | `/opt/odessa/repo`, ветка `main`, remote — GitHub `Amazido/NN_poker_bot` |
| Стек | Docker Compose, проект `odessa-poker` |
| Боевой фронт | `/var/www/odessky_win_usr/data/www/odessky.win` (вне репозитория) |

Трафик идёт **браузер → Cloudflare (TLS) → nginx FastPanel → контейнеры**.
Фронт отдаётся статикой из корня сайта, API и WebSocket проксируются внутрь.

Контейнеры проекта: `app` (FastAPI, `:8000`), `postgres`, `redis`,
`centrifugo` (`127.0.0.1:8001`), `frontend` (nginx `:3000` со старым отладочным
тестером `frontend/index.html` — к боевому фронту отношения не имеет).

Конфиги nginx лежат на сервере отдельно от основного конфига FastPanel, чтобы
панель их не перетирала. Копии — в репозитории (`deploy/nginx/`):

| В репозитории | На сервере |
|---|---|
| `deploy/nginx/odessa_api.conf` | `/etc/nginx/snippets/odessa_api.conf` |
| `deploy/nginx/odessa_ws.conf` | `/etc/nginx/snippets/odessa_ws.conf` |
| `deploy/nginx/odessky.win.includes` | `/etc/nginx/fastpanel2-sites/odessky_win_usr/odessky.win.includes` |

Маршруты в `odessky.win.includes` перечислены **поимённо**, а не одним префиксом.
Новый корневой путь в API (например `/rules`) через домен не заработает, пока его
туда не добавили и не перечитали nginx:

```bash
python deploy/ssh_exec.py --put deploy/nginx/odessky.win.includes /etc/nginx/fastpanel2-sites/odessky_win_usr/odessky.win.includes
python deploy/ssh_exec.py "nginx -t && systemctl reload nginx"
```

## Доступ к серверу

Команды гоняются через `deploy/ssh_exec.py` — он не требует установленного
SSH-клиента и стримит вывод. Нужен `paramiko` (`pip install paramiko`).

Креды берутся из переменных окружения, в репозиторий не коммитятся:

```powershell
$env:DEPLOY_HOST='5.188.21.132'
$env:DEPLOY_PORT='22'
$env:DEPLOY_USER='root'
$env:DEPLOY_PASSWORD='<пароль>'
```

```bash
python deploy/ssh_exec.py "docker ps"              # выполнить команду
python deploy/ssh_exec.py --put local.txt /tmp/x   # залить файл
python deploy/ssh_exec.py --putdir dist /remote    # залить папку рекурсивно
```

Оболочка на сервере — bash. Из PowerShell команду удобнее заворачивать в
двойные кавычки, а кавычки внутри SQL и подобного — в одинарные.

## Секреты

Боевые значения живут только в `/opt/odessa/repo/.env` на сервере. В git этот
файл не попадает (`.gitignore`), локальных копий нет. Состав:

`DEBUG`, `TELEGRAM_BOT_TOKEN`, `JWT_SECRET`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB`, `CORS_ORIGINS`, `CENTRIFUGO_API_KEY`,
`CENTRIFUGO_TOKEN_SECRET`.

`docker-compose.yml` подставляет их с дефолтами вида `${JWT_SECRET:-change-me-in-prod}`,
поэтому потеря `.env` не уронит стек, а тихо поднимет его с dev-секретами.
При правке `.env` это стоит держать в голове.

Одни и те же `CENTRIFUGO_API_KEY` и `CENTRIFUGO_TOKEN_SECRET` читают и `app`,
и `centrifugo` — менять только парой.

## Выкатка бэкенда

Код на сервер приходит через `git pull`, сборка образа — на месте.

```bash
python deploy/ssh_exec.py "cd /opt/odessa/repo && git pull && docker compose up -d --build app"
```

Миграции применяются сами: команда контейнера — `alembic upgrade head`, затем
`uvicorn`. Дефолтная редакция правил сидится при старте приложения.

Проверка после выкатки:

```bash
python deploy/ssh_exec.py "docker ps; cd /opt/odessa/repo && docker compose logs --tail 30 app"
curl https://odessky.win/health   # {"status":"ok"}
curl https://odessky.win/ready    # database + redis connected
```

Сборка образа на 2 ГБ памяти без свопа проходит, но это самая тяжёлая операция
на машине — не стоит запускать её параллельно с чем-то ещё.

## Выкатка фронта

Node на сервере **нет**: сборка делается локально, результат заливается по SFTP.

```bash
cd frontend-app
npm run build
cd ..
python deploy/ssh_exec.py --putdir frontend-app/dist /var/www/odessky_win_usr/data/www/odessky.win
```

`index.html` ссылается на файлы в `assets/` с хешем в имени, поэтому выкатка
атомарна по смыслу: старые бандлы продолжают работать у тех, кто уже открыл
страницу. Обратная сторона — `--putdir` ничего не удаляет, и старые сборки
накапливаются (на сентябрь 2026 — около десятка бандлов, ~3 МБ). Чистить
вручную, сверяясь с тем, что упомянуто в текущем `index.html`.

Проверка: открыть `https://odessky.win` и убедиться, что в `index.html`
подставлено имя свежего бандла.

## Наблюдение и разбор проблем

```bash
# статус контейнеров
python deploy/ssh_exec.py "docker ps"

# логи приложения
python deploy/ssh_exec.py "cd /opt/odessa/repo && docker compose logs --tail 100 app"

# ресурсы машины
python deploy/ssh_exec.py "df -h /; free -h; uptime"

# база (пользователь и БД — odessa)
python deploy/ssh_exec.py "cd /opt/odessa/repo && docker compose exec -T postgres psql -U odessa -d odessa -tAc 'select count(*) from users'"
```

Живые проверки снаружи — скриптами из `backend/scripts/`:
`stand_check.py` (HTTPS + WSS + push), `repro_cross_room.py` (изоляция личного
канала) и `blind_stand_check.py` (заказ вслепую: рука закрыта, `open_hand`
работает). Все логинятся через `POST /auth/dev`, то есть **зависят от
`DEBUG=true`** на стенде.

## Откат

Образ собирается из исходников, отдельного реестра нет, поэтому откат — это
откат кода:

```bash
python deploy/ssh_exec.py "cd /opt/odessa/repo && git log --oneline -10"
python deploy/ssh_exec.py "cd /opt/odessa/repo && git checkout <commit> && docker compose up -d --build app"
```

Миграции назад не откатываются автоматически: если в откатываемом релизе была
`alembic upgrade`, сначала нужен `alembic downgrade` вручную.

Фронт откатывается заливкой предыдущей локальной сборки тем же `--putdir`.

## Известные риски

Приняты осознанно, не закрыты на сентябрь 2026.

**Порты 8000 и 3000 открыты всему интернету.** Docker публикует их на `0.0.0.0`,
файрвола на машине нет (`ufw` не установлен, цепочка `DOCKER-USER` пуста).
`http://5.188.21.132:8000` и `:3000` отвечают напрямую, в обход Cloudflare;
Swagger на `/docs` тоже доступен. В логах `app` видны обращения посторонних
сканеров. Лечится привязкой публикации портов к `127.0.0.1` в
`docker-compose.yml` — как уже сделано для Centrifugo.

**`DEBUG=true` на проде.** Включает `POST /auth/dev` — вход без Telegram, любой
желающий заводит игрока и садится за стол. Держится сознательно: на нём
работают `stand_check.py` и `repro_cross_room.py`. Все dev-аккаунты в базе
(`probe`, `rt1`, `rt2`, `cross_p_*`, `cross_q_*`) созданы нашими же скриптами,
посторонних на сентябрь 2026 нет. Выключение `DEBUG` потребует другого способа
логина для живых проверок.

**`CORS_ORIGINS` не содержит домена** — там остались `http://5.188.21.132:3000`
и `http://localhost:3000`. Сейчас безвредно, потому что фронт ходит к API
same-origin, но сломается, если фронт съедет на другой хост.

**Пароль root как единственный способ входа.** SSH-ключей не заведено,
`ssh_exec.py` умеет только пароль (`look_for_keys=False`).

**Нет бэкапов Postgres.** Том `postgres_data` живёт только на этой машине,
снапшотов и выгрузок не настроено.
