"""Репозиторий комнат и посадки игроков."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameRoomModel, RoomPlayerModel, RoomPlayerStatus


class RoomRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, *, join_code: str, rules_edition_id: uuid.UUID, max_players: int, created_by: uuid.UUID
    ) -> GameRoomModel:
        room = GameRoomModel(
            id=uuid.uuid4(),
            join_code=join_code,
            rules_edition_id=rules_edition_id,
            max_players=max_players,
            created_by=created_by,
        )
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(room)
        return room

    async def get(self, room_id: str) -> Optional[GameRoomModel]:
        try:
            rid = uuid.UUID(room_id)
        except (ValueError, TypeError):
            return None
        res = await self.session.execute(select(GameRoomModel).where(GameRoomModel.id == rid))
        return res.scalar_one_or_none()

    async def get_by_join_code(self, join_code: str) -> Optional[GameRoomModel]:
        res = await self.session.execute(
            select(GameRoomModel).where(GameRoomModel.join_code == join_code)
        )
        return res.scalar_one_or_none()

    async def add_player(
        self, *, room_id: uuid.UUID, user_id: uuid.UUID, seat_index: int
    ) -> RoomPlayerModel:
        player = RoomPlayerModel(
            id=uuid.uuid4(),
            room_id=room_id,
            user_id=user_id,
            seat_index=seat_index,
            status=RoomPlayerStatus.ACTIVE,
        )
        self.session.add(player)
        await self.session.commit()
        await self.session.refresh(player)
        return player

    async def get_players(self, room_id: uuid.UUID) -> List[RoomPlayerModel]:
        res = await self.session.execute(
            select(RoomPlayerModel)
            .where(RoomPlayerModel.room_id == room_id)
            .order_by(RoomPlayerModel.seat_index.asc())
        )
        return list(res.scalars().all())

    async def get_player(self, room_id: uuid.UUID, user_id: uuid.UUID) -> Optional[RoomPlayerModel]:
        res = await self.session.execute(
            select(RoomPlayerModel).where(
                RoomPlayerModel.room_id == room_id,
                RoomPlayerModel.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    async def count_players(self, room_id: uuid.UUID) -> int:
        res = await self.session.execute(
            select(func.count(RoomPlayerModel.id)).where(RoomPlayerModel.room_id == room_id)
        )
        return res.scalar() or 0

    async def update_scores(self, room_id: uuid.UUID, scores_by_seat: dict) -> None:
        """Синхронизировать накопленный счёт матча из движка в БД."""
        for seat, score in scores_by_seat.items():
            await self.session.execute(
                update(RoomPlayerModel)
                .where(RoomPlayerModel.room_id == room_id, RoomPlayerModel.seat_index == int(seat))
                .values(score=int(score))
            )
        await self.session.commit()

    async def set_match_started(
        self, room_id: uuid.UUID, *, starting_dealer_seat: int, current_round_id: uuid.UUID
    ) -> None:
        await self.session.execute(
            update(GameRoomModel)
            .where(GameRoomModel.id == room_id)
            .values(
                status="playing",
                starting_dealer_seat=starting_dealer_seat,
                round_index=0,
                current_round_id=current_round_id,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

    async def set_progress(
        self,
        room_id: uuid.UUID,
        *,
        round_index: int,
        current_round_id: Optional[uuid.UUID],
        status: str,
    ) -> None:
        await self.session.execute(
            update(GameRoomModel)
            .where(GameRoomModel.id == room_id)
            .values(
                round_index=round_index,
                current_round_id=current_round_id,
                status=status,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()
