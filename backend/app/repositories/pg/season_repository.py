"""Репозиторий сезонов, результатов матчей и рейтинга.

Рейтинг нигде не хранится готовым числом: он выводится из журнала
`rating_events` как `season.initial_rating + SUM(delta)`. Второго места правды
нет намеренно — формулу собираются менять, и пересчёт должен быть перезаписью
журнала, а не правкой чисел в двух местах.
"""
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MatchModel,
    MatchOutcome,
    MatchPlayerModel,
    RatingEventKind,
    RatingEventModel,
    SeasonModel,
    SeasonStatus,
    UserModel,
    UserType,
)


class SeasonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # === Сезон ===

    async def get_active_season(self) -> Optional[SeasonModel]:
        res = await self.session.execute(
            select(SeasonModel).where(SeasonModel.status == SeasonStatus.ACTIVE).limit(1)
        )
        return res.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[SeasonModel]:
        res = await self.session.execute(select(SeasonModel).where(SeasonModel.code == code))
        return res.scalar_one_or_none()

    async def create_season(
        self,
        *,
        code: str,
        name: str,
        rules_edition_id: uuid.UUID,
        initial_rating: int,
        status: str = SeasonStatus.ACTIVE,
        meta: Optional[dict] = None,
    ) -> SeasonModel:
        season = SeasonModel(
            id=uuid.uuid4(),
            code=code,
            name=name,
            rules_edition_id=rules_edition_id,
            initial_rating=initial_rating,
            status=status,
            meta=meta or {},
        )
        self.session.add(season)
        await self.session.commit()
        await self.session.refresh(season)
        return season

    # === Рейтинг (считается по журналу) ===

    async def ratings_of(
        self, season_id: uuid.UUID, user_ids: Sequence[uuid.UUID], initial_rating: int
    ) -> Dict[uuid.UUID, int]:
        """Текущий рейтинг перечисленных игроков в сезоне.

        Игрок без единой записи в журнале ещё не играл — у него начальный
        рейтинг сезона, а не отсутствие рейтинга.
        """
        if not user_ids:
            return {}
        res = await self.session.execute(
            select(RatingEventModel.user_id, func.coalesce(func.sum(RatingEventModel.delta), 0))
            .where(
                RatingEventModel.season_id == season_id,
                RatingEventModel.user_id.in_(list(user_ids)),
            )
            .group_by(RatingEventModel.user_id)
        )
        sums = {uid: int(total) for uid, total in res.all()}
        return {uid: initial_rating + sums.get(uid, 0) for uid in user_ids}

    async def leaderboard(
        self, season: SeasonModel, limit: int = 100
    ) -> List[Tuple[UserModel, int, int]]:
        """Лидерборд сезона: (игрок, рейтинг, сыграно зачётных матчей).

        Боты в выборку не попадают: по правилам сезона бот за столом делает матч
        нерейтинговым, так что рейтинга у них нет по построению. Фильтр оставлен
        явным — чтобы случайная ручная запись в журнал не вынесла бота в таблицу.
        """
        res = await self.session.execute(
            select(
                UserModel,
                func.coalesce(func.sum(RatingEventModel.delta), 0),
                func.count(RatingEventModel.match_id.distinct()),
            )
            .join(RatingEventModel, RatingEventModel.user_id == UserModel.id)
            .where(
                RatingEventModel.season_id == season.id,
                UserModel.user_type != UserType.BOT,
            )
            .group_by(UserModel.id)
            .order_by(func.coalesce(func.sum(RatingEventModel.delta), 0).desc())
            .limit(limit)
        )
        return [
            (user, season.initial_rating + int(total), int(matches))
            for user, total, matches in res.all()
        ]

    async def rating_events_of(
        self, season_id: uuid.UUID, user_id: uuid.UUID, limit: int = 50
    ) -> List[RatingEventModel]:
        res = await self.session.execute(
            select(RatingEventModel)
            .where(
                RatingEventModel.season_id == season_id,
                RatingEventModel.user_id == user_id,
            )
            .order_by(RatingEventModel.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    # === Результаты матчей ===

    async def match_by_room(self, room_id: uuid.UUID) -> Optional[MatchModel]:
        res = await self.session.execute(select(MatchModel).where(MatchModel.room_id == room_id))
        return res.scalar_one_or_none()

    async def record_match(
        self,
        *,
        room_id: uuid.UUID,
        season: Optional[SeasonModel],
        rules_edition_id: Optional[uuid.UUID],
        rated: bool,
        unrated_reason: Optional[str],
        outcome: str,
        rounds_played: int,
        rounds_total: int,
        players: List[dict],
    ) -> MatchModel:
        """Записать итог матча одной транзакцией.

        `players` — по строке на место: `user_id`, `seat_index`, `score`,
        `place`, `is_bot`, `left_match`, `rating_before`, `rating_delta`.
        Записи журнала рейтинга создаются только для зачётного матча.
        """
        match = MatchModel(
            id=uuid.uuid4(),
            room_id=room_id,
            season_id=season.id if season else None,
            rules_edition_id=rules_edition_id,
            rated=rated,
            unrated_reason=unrated_reason,
            outcome=outcome,
            n_players=len(players),
            rounds_played=rounds_played,
            rounds_total=rounds_total,
        )
        self.session.add(match)

        for p in players:
            before = p.get("rating_before")
            delta = p.get("rating_delta") if rated else None
            after = (before + delta) if (rated and before is not None and delta is not None) else None
            self.session.add(
                MatchPlayerModel(
                    id=uuid.uuid4(),
                    match_id=match.id,
                    user_id=p["user_id"],
                    seat_index=p["seat_index"],
                    score=p["score"],
                    place=p["place"],
                    is_bot=bool(p.get("is_bot")),
                    left_match=bool(p.get("left_match")),
                    rating_before=before,
                    rating_delta=delta,
                    rating_after=after,
                )
            )
            if rated and season is not None and before is not None and delta is not None:
                self.session.add(
                    RatingEventModel(
                        id=uuid.uuid4(),
                        season_id=season.id,
                        user_id=p["user_id"],
                        match_id=match.id,
                        kind=RatingEventKind.MATCH,
                        delta=delta,
                        rating_before=before,
                        rating_after=after,
                        note=f"{p['place']} место из {len(players)}",
                    )
                )

        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def recent_matches(
        self, *, season_id: Optional[uuid.UUID] = None, limit: int = 50
    ) -> List[MatchModel]:
        """Последние матчи с участниками — это и есть «метрики» для разбора."""
        from sqlalchemy.orm import selectinload

        stmt = (
            select(MatchModel)
            .options(selectinload(MatchModel.players).selectinload(MatchPlayerModel.user))
            .order_by(MatchModel.finished_at.desc())
            .limit(limit)
        )
        if season_id is not None:
            stmt = stmt.where(MatchModel.season_id == season_id)
        res = await self.session.execute(stmt)
        return list(res.scalars())

    async def matches_of_user(self, user_id: uuid.UUID, limit: int = 50) -> List[MatchModel]:
        from sqlalchemy.orm import selectinload

        res = await self.session.execute(
            select(MatchModel)
            .join(MatchPlayerModel, MatchPlayerModel.match_id == MatchModel.id)
            .where(MatchPlayerModel.user_id == user_id)
            .options(selectinload(MatchModel.players).selectinload(MatchPlayerModel.user))
            .order_by(MatchModel.finished_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def season_stats(self, season_id: uuid.UUID) -> dict:
        """Сводка по сезону: сколько матчей дошло до зачёта и почему отвалились
        остальные. Первая метрика, которую захочется посмотреть."""
        res = await self.session.execute(
            select(MatchModel.rated, MatchModel.unrated_reason, MatchModel.outcome, func.count())
            .where(MatchModel.season_id == season_id)
            .group_by(MatchModel.rated, MatchModel.unrated_reason, MatchModel.outcome)
        )
        rated = 0
        unrated_by_reason: Dict[str, int] = {}
        abandoned = 0
        for is_rated, reason, outcome, count in res.all():
            if is_rated:
                rated += count
            else:
                unrated_by_reason[reason or "unknown"] = unrated_by_reason.get(reason or "unknown", 0) + count
            if outcome == MatchOutcome.ABANDONED:
                abandoned += count
        return {
            "matches_rated": rated,
            "matches_unrated": sum(unrated_by_reason.values()),
            "unrated_by_reason": unrated_by_reason,
            "matches_abandoned": abandoned,
        }
