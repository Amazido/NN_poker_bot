"""Репозиторий раздач (rounds) и журнала действий."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameRoundModel, RoundActionModel


class RoundRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_from_state(
        self, room_id: uuid.UUID, round_index: int, round_state: dict
    ) -> GameRoundModel:
        model = GameRoundModel(
            id=uuid.uuid4(),
            room_id=room_id,
            round_index=round_index,
            cards_count=round_state["cards_count"],
            dealer_seat=round_state["dealer_seat"],
            trump_card=round_state["trump_card"],
            trump_suit=round_state["trump_suit"],
            no_trump=round_state["no_trump"],
            phase=round_state["phase"],
            bids=round_state.get("bids", {}),
            tricks_won=round_state.get("tricks_won", {}),
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_room_index(self, room_id: uuid.UUID, round_index: int) -> Optional[GameRoundModel]:
        res = await self.session.execute(
            select(GameRoundModel).where(
                GameRoundModel.room_id == room_id,
                GameRoundModel.round_index == round_index,
            )
        )
        return res.scalar_one_or_none()

    async def sync_from_state(self, round_id: uuid.UUID, round_state: dict) -> None:
        """Обновить строку раздачи из live-состояния движка."""
        ended_at = None
        if round_state["phase"] == "finished":
            ended_at = datetime.now(timezone.utc)
        await self.session.execute(
            update(GameRoundModel)
            .where(GameRoundModel.id == round_id)
            .values(
                phase=round_state["phase"],
                bids=round_state.get("bids", {}),
                tricks_won=round_state.get("tricks_won", {}),
                result=round_state.get("result"),
                trump_card=round_state["trump_card"],
                trump_suit=round_state["trump_suit"],
                no_trump=round_state["no_trump"],
                ended_at=ended_at,
            )
        )
        await self.session.commit()

    async def next_seq(self, round_id: uuid.UUID) -> int:
        res = await self.session.execute(
            select(func.coalesce(func.max(RoundActionModel.seq), 0)).where(
                RoundActionModel.round_id == round_id
            )
        )
        return int(res.scalar() or 0) + 1

    async def append_action(
        self,
        *,
        round_id: uuid.UUID,
        room_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        seat: int,
        phase: str,
        action_type: str,
        payload: dict,
        seq: int,
    ) -> None:
        action = RoundActionModel(
            id=uuid.uuid4(),
            round_id=round_id,
            room_id=room_id,
            user_id=user_id,
            seat=seat,
            phase=phase,
            action_type=action_type,
            payload=payload,
            seq=seq,
        )
        self.session.add(action)
        await self.session.commit()
