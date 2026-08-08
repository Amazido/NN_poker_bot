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
    """Разослать актуальное состояние: публичное в комнату, приватное — каждому."""
    room_id = state["room_id"]
    await safe_publish(ch_room(room_id), {"type": "state", "state": public_view(state)})

    tasks = []
    for s in state["seats"]:
        view = private_view(state, s["seat"])
        tasks.append(safe_publish(ch_user(s["user_id"]), {"type": "private", "private": view}))
    if tasks:
        await asyncio.gather(*tasks)


async def publish_events(state: GameState, events: List[dict]) -> None:
    """Разослать события раунда в канал комнаты (снапшот шлём отдельно)."""
    if not events:
        return
    await safe_publish(ch_room(state["room_id"]), {"type": "events", "events": events})
