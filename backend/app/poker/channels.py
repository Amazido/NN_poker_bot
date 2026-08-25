"""Публикация игрового состояния в Centrifugo.

  - публичный снапшот → канал комнаты (для всех за столом);
  - приватный вид (рука + доступные действия) → личный канал каждого игрока;
  - события раунда → канал комнаты (для анимаций/ленты).
"""
import asyncio
from typing import List

from app.core.centrifugo import ch_room, ch_user, safe_publish
from app.poker.engine import GameState
from app.poker.state import private_view, public_view


async def publish_snapshot(state: GameState) -> None:
    """Разослать актуальное состояние: публичное в комнату, приватное — за столом.

    Приватку не шлём на места из `left_seats` (ушедшие игроки и боты): руку
    в комнате, которую человек покинул, ему смотреть незачем, а его личный канал
    может слушать уже другая комната.
    """
    room_id = state["room_id"]
    await safe_publish(ch_room(room_id), {"type": "state", "state": public_view(state)})

    left = set(state.get("left_seats", []))
    tasks = []
    for s in state["seats"]:
        if s["seat"] in left:
            continue
        view = private_view(state, s["seat"])
        tasks.append(safe_publish(ch_user(s["user_id"]), {"type": "private", "private": view}))
    if tasks:
        await asyncio.gather(*tasks)


async def publish_events(state: GameState, events: List[dict]) -> None:
    """Разослать события раунда в канал комнаты (снапшот шлём отдельно)."""
    if not events:
        return
    await safe_publish(ch_room(state["room_id"]), {"type": "events", "events": events})


async def publish_lobby(public: dict) -> None:
    """Разослать состояние лобби в канал комнаты (матч ещё не стартовал).

    Live-стейта в Redis для лобби нет, поэтому шлём готовый публичный вид из БД:
    подключившиеся к каналу комнаты увидят, кто сел за стол.
    """
    room_id = public.get("room_id")
    if not room_id:
        return
    await safe_publish(ch_room(room_id), {"type": "lobby", "state": public})
