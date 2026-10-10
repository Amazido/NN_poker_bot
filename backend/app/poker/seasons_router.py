"""REST-роутер сезона: рейтинг, лидерборд и метрики по матчам.

Экранов для этого пока нет — ручки нужны, чтобы смотреть собранные метрики и
понять по ним, какой должна быть настоящая формула рейтинга (текущая заведомо
временная, см. `poker/rating.py`).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.db.models import UserModel
from app.dependencies import get_season_repo
from app.poker.schemas import (
    LeaderboardRow,
    MatchPlayerRow,
    MatchRow,
    MyRatingResponse,
    RatingEventRow,
    SeasonResponse,
)
from app.repositories.pg import SeasonRepository

router = APIRouter(prefix="/seasons", tags=["seasons"])


def _username(user: Optional[UserModel]) -> str:
    if not user:
        return "—"
    return user.telegram_username or f"user-{str(user.id)[:8]}"


def _match_row(match, highlight_user: Optional[uuid.UUID] = None) -> MatchRow:
    players = sorted(match.players, key=lambda p: p.place)
    return MatchRow(
        match_id=str(match.id),
        finished_at=match.finished_at,
        outcome=match.outcome,
        rated=match.rated,
        unrated_reason=match.unrated_reason,
        n_players=match.n_players,
        rounds_played=match.rounds_played,
        rounds_total=match.rounds_total,
        players=[
            MatchPlayerRow(
                user_id=str(p.user_id),
                username=_username(p.user),
                is_me=highlight_user is not None and p.user_id == highlight_user,
                seat_index=p.seat_index,
                score=p.score,
                place=p.place,
                is_bot=p.is_bot,
                left_match=p.left_match,
                rating_before=p.rating_before,
                rating_delta=p.rating_delta,
                rating_after=p.rating_after,
            )
            for p in players
        ],
    )


async def _active_season(repo: SeasonRepository):
    season = await repo.get_active_season()
    if not season:
        raise HTTPException(status_code=404, detail="Активного сезона нет")
    return season


@router.get("/current", response_model=SeasonResponse, summary="Текущий сезон и сводка по матчам")
async def current_season(
    repo: SeasonRepository = Depends(get_season_repo),
    user: UserModel = Depends(get_current_user),
):
    season = await _active_season(repo)
    stats = await repo.season_stats(season.id)
    return SeasonResponse(
        code=season.code,
        name=season.name,
        status=season.status,
        initial_rating=season.initial_rating,
        starts_at=season.starts_at,
        ends_at=season.ends_at,
        **stats,
    )


@router.get(
    "/current/leaderboard",
    response_model=List[LeaderboardRow],
    summary="Лидерборд сезона",
)
async def leaderboard(
    limit: int = Query(100, ge=1, le=500),
    repo: SeasonRepository = Depends(get_season_repo),
    user: UserModel = Depends(get_current_user),
):
    season = await _active_season(repo)
    rows = await repo.leaderboard(season, limit=limit)
    out: List[LeaderboardRow] = []
    place = 0
    prev_rating: Optional[int] = None
    for i, (player, rating_value, matches) in enumerate(rows, start=1):
        # Равный рейтинг — равное место, как и равный счёт в матче.
        if rating_value != prev_rating:
            place = i
            prev_rating = rating_value
        out.append(
            LeaderboardRow(
                place=place,
                user_id=str(player.id),
                username=_username(player),
                rating=rating_value,
                matches=matches,
                is_me=player.id == user.id,
            )
        )
    return out


@router.get("/current/me", response_model=MyRatingResponse, summary="Мой рейтинг и его история")
async def my_rating(
    repo: SeasonRepository = Depends(get_season_repo),
    user: UserModel = Depends(get_current_user),
):
    season = await _active_season(repo)
    ratings = await repo.ratings_of(season.id, [user.id], season.initial_rating)
    events = await repo.rating_events_of(season.id, user.id)
    matches = await repo.matches_of_user(user.id, limit=20)
    return MyRatingResponse(
        rating=ratings.get(user.id, season.initial_rating),
        matches=sum(1 for e in events if e.match_id is not None),
        events=[
            RatingEventRow(
                created_at=e.created_at,
                kind=e.kind,
                delta=e.delta,
                rating_before=e.rating_before,
                rating_after=e.rating_after,
                note=e.note,
                match_id=str(e.match_id) if e.match_id else None,
            )
            for e in events
        ],
        recent_matches=[_match_row(m, highlight_user=user.id) for m in matches],
    )


@router.get(
    "/current/matches",
    response_model=List[MatchRow],
    summary="Последние матчи сезона (метрики)",
)
async def season_matches(
    limit: int = Query(50, ge=1, le=200),
    all_seasons: bool = Query(False, description="Включая матчи вне сезона"),
    repo: SeasonRepository = Depends(get_season_repo),
    user: UserModel = Depends(get_current_user),
):
    """Матчи как они записаны: с местами, рейтингами на момент матча, отметками
    «вышел» и причиной, по которой матч не пошёл в зачёт."""
    season_id: Optional[uuid.UUID] = None
    if not all_seasons:
        season_id = (await _active_season(repo)).id
    matches = await repo.recent_matches(season_id=season_id, limit=limit)
    return [_match_row(m, highlight_user=user.id) for m in matches]
