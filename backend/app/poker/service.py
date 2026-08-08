"""Оркестрация комнаты: создание/вход/старт/действие + БД + Redis + Centrifugo.

Redis держит live-стейт (источник истины для розыгрыша). Postgres хранит
раздачи и журнал действий для истории/восстановления. Centrifugo рассылает
обновления в реальном времени.
"""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidMove, NotFound
from app.db.models import GameRoomModel, RoomStatus, UserModel
from app.logger import poker_log
from app.poker import channels, engine
from app.poker import state as state_store
from app.poker.rules import RulesEdition
from app.repositories.pg import (
    RoomRepository,
    RoundRepository,
    RulesEditionRepository,
    UserRepository,
)


def _gen_join_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


class PokerService:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        rules_repo: RulesEditionRepository,
        room_repo: RoomRepository,
        round_repo: RoundRepository,
    ):
        self.session = session
        self.user_repo = user_repo
        self.rules_repo = rules_repo
        self.room_repo = room_repo
        self.round_repo = round_repo

    def _stamp_deadline(self, state: dict) -> None:
        """Проставить дедлайн текущего хода (для фонового авто-хода)."""
        kind, seat = engine.current_turn(state)
        if kind is None:
            state["turn_deadline"] = None
            return
        rules = RulesEdition(state["rules"])
        deadline = datetime.now(timezone.utc) + timedelta(seconds=rules.turn_timeout_sec)
        state["turn_deadline"] = deadline.isoformat()

    # === Комната ===

    async def create_room(
        self, user: UserModel, rules_code: Optional[str] = None, max_players: Optional[int] = None
    ) -> dict:
        edition = (
            await self.rules_repo.get_active_by_code(rules_code)
            if rules_code
            else await self.rules_repo.get_default()
        )
        if not edition:
            raise Conflict("No active rules edition found (seed one first)")

        rules = RulesEdition(edition.config)
        mp = max_players or rules.max_players
        mp = max(rules.min_players, min(mp, rules.max_players))

        # Уникальный join_code.
        for _ in range(10):
            code = _gen_join_code()
            if not await self.room_repo.get_by_join_code(code):
                break
        else:
            raise Conflict("Failed to generate unique join code")

        room = await self.room_repo.create(
            join_code=code,
            rules_edition_id=edition.id,
            max_players=mp,
            created_by=user.id,
        )
        await self.room_repo.add_player(room_id=room.id, user_id=user.id, seat_index=0)
        poker_log.info("Room {} created by {} (rules {})", room.join_code, user.id, edition.code)
        return await self.get_public(str(room.id))

    async def join_room(self, user: UserModel, join_code: str) -> dict:
        room = await self.room_repo.get_by_join_code(join_code.upper())
        if not room:
            raise NotFound("Room not found")
        if room.status != RoomStatus.LOBBY:
            raise Conflict("Match already started")

        existing = await self.room_repo.get_player(room.id, user.id)
        if existing:
            return await self.get_public(str(room.id))

        count = await self.room_repo.count_players(room.id)
        if count >= room.max_players:
            raise Conflict("Room is full")

        await self.room_repo.add_player(room_id=room.id, user_id=user.id, seat_index=count)
        poker_log.info("User {} joined room {} (seat {})", user.id, room.join_code, count)
        return await self.get_public(str(room.id))

    # === Старт матча ===

    async def start_match(self, user: UserModel, room_id: str) -> dict:
        room = await self.room_repo.get(room_id)
        if not room:
            raise NotFound("Room not found")
        if room.created_by != user.id:
            raise Conflict("Only room creator can start the match")
        if room.status != RoomStatus.LOBBY:
            raise Conflict("Match already started")

        players = await self.room_repo.get_players(room.id)
        edition = await self.rules_repo.get(str(room.rules_edition_id))
        rules = RulesEdition(edition.config if edition else None)
        n = len(players)
        if n < rules.min_players:
            raise Conflict(f"Need at least {rules.min_players} players (have {n})")

        seats = []
        for p in players:
            u = await self.user_repo.get(str(p.user_id))
            username = (u.telegram_username if u else None) or f"Player{p.seat_index}"
            seats.append({
                "seat": p.seat_index,
                "user_id": str(p.user_id),
                "username": username,
                "score": 0,
            })

        starting_dealer = random.randrange(n)
        state = engine.new_game_state(
            room_id=str(room.id),
            seats=seats,
            rules_config=edition.config if edition else None,
            starting_dealer=starting_dealer,
        )

        # Персист первой раздачи + прогресс комнаты.
        round_row = await self.round_repo.create_from_state(room.id, 0, state["round"])
        await self.room_repo.set_match_started(
            room.id, starting_dealer_seat=starting_dealer, current_round_id=round_row.id
        )

        self._stamp_deadline(state)
        await state_store.save_state(str(room.id), state)
        await state_store.add_active_room(str(room.id))
        await channels.publish_snapshot(state)
        poker_log.info("Match started in room {} ({} players)", room.join_code, n)
        return state_store.public_view(state)

    # === Игровое действие ===

    async def act(self, user: UserModel, room_id: str, action_type: str, payload: dict) -> dict:
        room = await self.room_repo.get(room_id)
        if not room:
            raise NotFound("Room not found")

        state = await state_store.load_state(room_id)
        if not state:
            raise Conflict("Match is not active")

        seat = engine.seat_of_user(state, str(user.id))
        if seat is None:
            raise Conflict("You are not seated in this room")

        round_index_before = state["round_index"]
        round_before = state["round"]
        phase_before = round_before["phase"]

        round_row = await self.round_repo.get_by_room_index(room.id, round_index_before)
        if not round_row:
            round_row = await self.round_repo.create_from_state(room.id, round_index_before, round_before)

        # Применяем действие (может бросить InvalidMove).
        events = engine.apply_action(state, seat, action_type, payload)

        # Журнал действия (в раздаче, что была активна до применения).
        seq = await self.round_repo.next_seq(round_row.id)
        await self.round_repo.append_action(
            round_id=round_row.id,
            room_id=room.id,
            user_id=user.id,
            seat=seat,
            phase=phase_before,
            action_type=action_type,
            payload=payload,
            seq=seq,
        )
        await self.round_repo.sync_from_state(round_row.id, round_before)

        # Прогресс матча / новая раздача.
        if state.get("match_over"):
            await self.room_repo.set_progress(
                room.id, round_index=state["round_index"], current_round_id=None, status=RoomStatus.FINISHED
            )
        elif state["round_index"] != round_index_before:
            new_round_row = await self.round_repo.create_from_state(
                room.id, state["round_index"], state["round"]
            )
            await self.room_repo.set_progress(
                room.id,
                round_index=state["round_index"],
                current_round_id=new_round_row.id,
                status=RoomStatus.PLAYING,
            )

        await self.room_repo.update_scores(
            room.id, {s["seat"]: s["score"] for s in state["seats"]}
        )

        self._stamp_deadline(state)
        await state_store.save_state(room_id, state)
        if state.get("match_over"):
            await state_store.remove_active_room(room_id)
        await channels.publish_events(state, events)
        await channels.publish_snapshot(state)
        return state_store.public_view(state)

    # === Чтение состояния ===

    async def get_public(self, room_id: str) -> dict:
        state = await state_store.load_state(room_id)
        if state:
            return state_store.public_view(state)

        # Лобби (матч ещё не стартовал) — собираем вид из БД.
        room = await self.room_repo.get(room_id)
        if not room:
            raise NotFound("Room not found")
        players = await self.room_repo.get_players(room.id)
        seats = []
        for p in players:
            u = await self.user_repo.get(str(p.user_id))
            username = (u.telegram_username if u else None) or f"Player{p.seat_index}"
            seats.append({
                "seat": p.seat_index,
                "user_id": str(p.user_id),
                "username": username,
                "score": p.score,
            })
        return {
            "room_id": str(room.id),
            "join_code": room.join_code,
            "status": room.status,
            "match_over": room.status == RoomStatus.FINISHED,
            "seats": seats,
            "n_players": len(seats),
            "max_players": room.max_players,
            "round_index": room.round_index,
            "round": None,
            "turn": {"kind": None, "seat": None},
        }

    async def get_private(self, user: UserModel, room_id: str) -> dict:
        state = await state_store.load_state(room_id)
        if not state:
            raise Conflict("Match is not active")
        seat = engine.seat_of_user(state, str(user.id))
        if seat is None:
            raise Conflict("You are not seated in this room")
        return state_store.private_view(state, seat)
