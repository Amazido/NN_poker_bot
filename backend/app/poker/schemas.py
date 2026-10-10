"""Схемы, общие для роутеров покера.

`TableRulesSettings` — контракт формы создания стола. Он один и тот же в обе
стороны: форма отправляет эти поля в `POST /rooms`, а `GET /rules/presets`
возвращает готовые значения тех же полей. Держать две похожие модели нельзя —
разъедутся, и заготовка начнёт заполнять форму не тем, что потом отправится.
"""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TableRulesSettings(BaseModel):
    """Правила стола в виде полей формы.

    Штрафы задаются положительным числом («штраф 5»), знак ставит сервер при
    сборке конфига (`rules.config_from_settings`).
    """

    rounds_start: int = Field(ge=1, description="Сколько карт в первой раздаче")
    rounds_peak: int = Field(ge=1, description="Сколько карт в самой большой раздаче")
    two_beats_ace: bool = Field(description="Двойка бьёт туза своей масти")
    offcolor_beats_oncolor: bool = Field(description="Некозырной джокер бьёт козырного джокера")
    blind_allowed: bool = Field(description="Можно заказать, не открывая руку")
    blind_bonus: int = Field(default=0, ge=0, description="Надбавка за точный заказ вслепую")
    infinite_deck: bool = Field(description="Безлимитная колода: карты повторяются")
    pass_reward: int = Field(ge=0, description="Награда за пас (заказал 0 и взял 0)")
    trick_reward: int = Field(ge=0, description="Награда за каждую взятку при точном заказе")
    overtrick_penalty: int = Field(ge=0, description="Штраф за перебор, положительным числом")
    undertrick_penalty: int = Field(
        ge=0, description="Штраф за каждую недобранную взятку, положительным числом"
    )


# === Сезон, рейтинг и метрики по матчам ===

class SeasonResponse(BaseModel):
    code: str
    name: str
    status: str
    initial_rating: int = Field(description="Рейтинг, с которого игрок входит в сезон")
    starts_at: datetime
    ends_at: Optional[datetime] = None
    matches_rated: int = Field(description="Матчей пошло в зачёт")
    matches_unrated: int = Field(description="Матчей не пошло в зачёт")
    unrated_by_reason: Dict[str, int] = Field(
        description="Почему матчи не пошли в зачёт: house_rules, bots, too_few_players, no_season"
    )
    matches_abandoned: int = Field(description="Матчей брошено (все вышли до конца)")


class LeaderboardRow(BaseModel):
    place: int
    user_id: str
    username: str
    rating: int
    matches: int = Field(description="Сколько зачётных матчей сыграно")
    is_me: bool = False


class MatchPlayerRow(BaseModel):
    user_id: str
    username: str
    is_me: bool = False
    seat_index: int
    score: int = Field(description="Финальный счёт матча")
    place: int
    is_bot: bool
    left_match: bool = Field(description="Покинул матч, доигрывал авто-ход")
    rating_before: Optional[int] = Field(
        default=None, description="Рейтинг на момент матча; null, если сезона не было"
    )
    rating_delta: Optional[int] = Field(default=None, description="null у нерейтингового матча")
    rating_after: Optional[int] = None


class MatchRow(BaseModel):
    match_id: str
    finished_at: datetime
    outcome: str = Field(description="completed — доиграли, abandoned — все вышли")
    rated: bool
    unrated_reason: Optional[str] = None
    n_players: int
    rounds_played: int
    rounds_total: int
    players: List[MatchPlayerRow]


class RatingEventRow(BaseModel):
    created_at: datetime
    kind: str = Field(description="match, seed, adjustment, recalc")
    delta: int
    rating_before: int
    rating_after: int
    note: str
    match_id: Optional[str] = None


class MyRatingResponse(BaseModel):
    rating: int
    matches: int
    events: List[RatingEventRow] = Field(description="История изменений рейтинга, свежие сверху")
    recent_matches: List[MatchRow]
