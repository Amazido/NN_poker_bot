# Фронт Одесского покера — макеты 3 экранов + стек (sub-project A)

## Контекст

Бэкенд (`backend/`) уже реализован: FastAPI + Postgres + Redis, чистый движок
раунда, REST-контракт, Telegram-авторизация, Centrifugo заложен, но не
включён наружу (см. `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`). Есть
черновой vanilla-JS тестер `frontend/index.html`, который он заменит.

Полная задача («сделать весь фронт») слишком велика для одной спеки. Разбита
на подпроекты:

- **A (эта спека)** — стек, TS-контракт, макеты 3 экранов (ожидание / торги /
  сброс) на фейковых данных.
- **B (следующая спека)** — реальное подключение: авторизация, поллинг,
  wiring экранов к API, деплой на замену `frontend/index.html`.
- **C (позже)** — оставшиеся экраны (итоги раздачи, конец матча, ошибки/
  реконнект) — после того как прояснятся открытые вопросы к бэку (см. ниже).

Эта спека закрывает только A.

## Стек

React + TypeScript + Vite. Деплоится как статическая сборка тем же nginx-
контейнером `frontend` из `docker-compose.yml`, что и сейчас.

Обоснование: Telegram Mini Apps экосистема (SDK, примеры) в первую очередь
ориентирована на React; TS-типы страхуют от ошибок при слабом опыте во
фронтенде; компонент = экран/виджет — простая для понимания структура.

## Архитектура

```
src/
  api/            — HTTP-клиент, обмен Telegram initData → JWT,
                    хук useGameView(roomId) (поллинг, см. "Открытые вопросы")
  types/game.ts   — TS-типы контракта (см. ниже)
  screen-resolver.ts — чистая функция resolveScreen(view): AppScreen
  screens/        — WaitingScreen, BiddingScreen, PlayingScreen
  components/     — Table, PlayerSeat, Card, Hand, BidPad, TrickArea
  App.tsx         — поллит через useGameView, резолвит экран, рендерит
```

`resolveScreen` — вся "стейт-машина" фронта на v1, без сторонних библиотек
(YAGNI; если ветвление разрастётся в sub-project B/C — пересмотреть):

```ts
function resolveScreen(view: GameView): AppScreen {
  if (view.status === 'lobby') return { type: 'waiting', view };
  if (view.round?.phase === 'bidding') return { type: 'bidding', view };
  if (view.round?.phase === 'playing') return { type: 'playing', view };
  return { type: 'unsupported', view }; // scoring/finished — sub-project C
}
```

Получение данных сейчас — REST-поллинг (см. "Открытые вопросы"), спрятан за
одним хуком `useGameView`, чтобы замена на Centrifugo (WebSocket push от
сервера, канал `room:{id}` для публичного состояния и `user#{id}` для
личного) в будущем не потребовала переписывать экраны.

## TS-контракт

Смёржен из реальных `public_view` / `private_view` бэка
(`backend/app/poker/state.py`):

```ts
type CardCode = string; // "AS", "TD", "XR" (красный джокер), "XB" (чёрный)

interface Seat { seat: number; user_id: string; username: string; score: number }

interface RoundPublic {
  cards_count: number;
  dealer_seat: number;
  first_seat: number;
  trump_card: CardCode;
  trump_suit: string | null;   // null если no_trump
  no_trump: boolean;
  phase: 'bidding' | 'playing' | 'scoring' | 'finished';
  bids: Record<string, number>;       // ключ — seat как строка
  bid_turn: number | null;
  tricks_won: Record<string, number>;
  trick_number: number;
  current_trick: {
    lead_seat: number;
    lead_suit: string | null;
    turn: number;
    plays: { seat: number; card: CardCode }[];
  } | null;
  last_trick: {
    plays: { seat: number; card: CardCode }[];
    winner: number;
  } | null;
  result: Record<string, { bid: number; won: number; delta: number; total: number }> | null;
  hand_counts: Record<string, number>; // чужие руки — только количество карт
}

interface PublicView {
  room_id: string;
  status: 'lobby' | 'playing' | 'finished';
  match_over: boolean;
  seats: Seat[];
  n_players: number;
  max_players?: number;  // присутствует только в lobby-ветке
  join_code?: string;    // присутствует только в lobby-ветке
  round_index: number;
  rounds_total?: number;
  round: RoundPublic | null;
  turn: { kind: 'bid' | 'play' | null; seat: number | null };
}

interface PrivateView {
  seat: number;
  hand: CardCode[];
  your_turn: boolean;
  available_actions:
    | { type: 'bid'; options: number[] }
    | { type: 'play'; cards: CardCode[] }
    | null;
}

// Результат мёржа GET /rooms/{id} + GET /rooms/{id}/hand на фронте.
interface GameView extends PublicView { me: PrivateView | null }
```

## Экраны

### Ожидание игроков (`status === 'lobby'`)

- Код комнаты крупно + кнопка «поделиться» (Telegram share).
- Места по кругу/списком до `max_players`: занятые — имя игрока, пустые —
  «ждём игрока».
- Кнопка «Начать игру» — видна только хосту комнаты. **Блокер**: бэк сейчас
  не отдаёт признак хоста в lobby-виде (см. "Открытые вопросы", п.2) — до
  уточнения кнопка мокается видимой всегда в макете, реальная логика видимости
  — в sub-project B.

### Торги (`round.phase === 'bidding'`)

- Заголовок: раунд X из `rounds_total`, `cards_count`, козырь (иконка масти
  или «без козыря»), кто сдаёт (`dealer_seat`).
- Вокруг стола: у каждого места — уже сделанный заказ (`bids`) или «думает…»
  для ожидающих; подсветка текущего бидера (`bid_turn`).
- Своя рука снизу (`me.hand`) — видна, не кликабельна на этом экране.
- Если `me.your_turn && me.available_actions.type === 'bid'` — панель кнопок
  из `available_actions.options` (крюк уже вычислен бэком).

### Розыгрыш / сброс (`round.phase === 'playing'`)

- Заголовок как в торгах + номер взятки (`trick_number`).
- У каждого места: заказ vs текущее число взятых (`tricks_won`).
- Центр стола: карты текущей взятки (`current_trick.plays`), привязанные к
  позиции игрока.
- Последняя взятка (`last_trick`) — компактный индикатор (кто её забрал).
- Своя рука снизу: карты не из `available_actions.cards` визуально притушены
  и некликабельны; клик по разрешённой карте = ход.

Раскладка стола — не фиксированная сетка на 4, а функция от `n_players`
(2–6, произвольно) — компонент `Table` располагает N мест равномерно по дуге/
кругу вне зависимости от точного числа.

## Визуальный стиль и ассеты

Флэт/минимализм, без внешних ассетов и CDN-шрифтов (лишние внешние ресурсы в
Telegram WebView — источник проблем). Всё рисуется SVG/CSS внутри проекта:

- `<Card rank suit />` — скруглённый прямоугольник, крупный ранг в углу,
  SVG-иконка масти по центру. Джокеры — отдельная простая иконка (красная/
  чёрная).
- Чужие карты — рубашки; их количество берётся из `hand_counts` (сами карты
  соперников бэк не отдаёт вообще).
- Стол — плоский цвет/лёгкий градиент, без текстур.

## Процесс макетирования

1. Один самодостаточный HTML/CSS/JS файл (артефакт) с переключателем экрана
   (Ожидание / Торги / Сброс) и переключателем числа игроков (2 / 4 / 6) на
   фейковых данных формы `GameView` — проверить раскладку на границах
   диапазона игроков до вложений в сборку проекта.
2. После апрува макета — перенос разметки/стилей в реальные React-компоненты
   Vite-проекта с теми же fixture-данными (отдельный dev-роут с селектором
   сценария вместо Storybook — YAGNI).

## Открытые вопросы к бэку (не блокируют макеты, блокируют sub-project B)

1. **Диапазон игроков**: дефолтная редакция правил ограничивает 3–5, но
   заявлено 2–6 произвольно. Уточнить у Славы, будет ли отдельная редакция
   правил или дефолт поменяется.
2. **Признак хоста в лобби**: `public_view` в статусе `lobby` не содержит
   `created_by` — фронт не может определить, кому показывать «Начать игру».
   Нужно либо добавить это поле, либо булево `is_host` относительно текущего
   пользователя.
3. **Видимость итогов раздачи**: `_finish_round` (подсчёт, `result`
   заполняется) и `_advance_after_round` (старт следующей раздачи или
   `match_over`) происходят в одном вызове движка — REST-поллинг физически не
   успевает увидеть промежуточное состояние с `result`. Нужно либо поле
   `last_round_result`, персистентное в следующем `public_view`, либо
   опираться на Centrifugo-событие `round_scored` (требует включения
   Centrifugo наружу).
4. **Centrifugo не включён наружу** — v1 фронта строится на REST-поллинге;
   переход на push учтён архитектурно (см. "Архитектура"), но не в scope A/B
   до включения на инфраструктуре.

## Верификация (sub-project A)

Это визуальный макет, не рабочий код — проверка визуальная: просмотр
артефакта/dev-сервера на 2, 4 и 6 игроках для каждого из 3 экранов.
Автоматических тестов на этом этапе нет.
