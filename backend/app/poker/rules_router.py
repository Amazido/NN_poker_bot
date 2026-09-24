"""REST-роутер правил: каталог редакций и заготовки для формы создания стола."""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_rules_repo
from app.poker.rules import (
    MAX_PEAK_INFINITE,
    RulesEdition,
    max_peak_finite,
    settings_from_config,
)
from app.poker.schemas import TableRulesSettings
from app.repositories.pg import RulesEditionRepository

router = APIRouter(prefix="/rules", tags=["rules"])

# Эталон сезона. Форма открывается на нём: по умолчанию человек собирает
# сезонный стол, а не случайный набор правил.
SEASON_EDITION_CODE = "odessa_season_1"


class RulesEditionResponse(BaseModel):
    code: str
    version: int
    name: str
    description: str = ""
    min_players: int
    max_players: int
    rounds_total_hint: int = Field(
        description="Сколько раздач в матче при минимальном числе игроков"
    )
    summary: List[str] = Field(description="Отличия редакции короткими фразами — для UI")


@router.get("/editions", response_model=List[RulesEditionResponse], summary="Доступные редакции правил")
async def list_editions(repo: RulesEditionRepository = Depends(get_rules_repo)):
    out: List[RulesEditionResponse] = []
    for edition in await repo.list_active():
        rules = RulesEdition(edition.config)
        try:
            rounds_hint = len(rules.round_sequence(rules.min_players))
        except ValueError:
            # Редакцию завели до появления валидации и по ней нельзя играть.
            # Показываем её, но без подсказки о длине матча.
            rounds_hint = 0
        out.append(
            RulesEditionResponse(
                code=edition.code,
                version=edition.version,
                name=edition.name,
                description=(edition.meta or {}).get("description", ""),
                min_players=rules.min_players,
                max_players=rules.max_players,
                rounds_total_hint=rounds_hint,
                summary=rules.summary(),
            )
        )
    return out


class RulesPreset(BaseModel):
    code: str
    name: str
    description: str = ""
    settings: TableRulesSettings


class RulesFormLimits(BaseModel):
    min_start: int = Field(description="Минимальный размер первой раздачи")
    max_peak_one_deck: int = Field(description="Потолок раздачи при одной колоде")
    max_peak_infinite: int = Field(description="Потолок раздачи при безлимитной колоде")


class RulesPresetsResponse(BaseModel):
    season: Optional[RulesPreset] = Field(
        description="Эталон сезона: им форма заполняется по умолчанию"
    )
    presets: List[RulesPreset] = Field(description="Быстрые заготовки для формы")
    limits: RulesFormLimits


@router.get("/presets", response_model=RulesPresetsResponse, summary="Заготовки для формы стола")
async def list_presets(repo: RulesEditionRepository = Depends(get_rules_repo)):
    """Значения полей формы создания стола: эталон сезона и быстрые заготовки.

    Отдаём именно поля формы, а не конфиги: фронту не приходится знать, как
    настройки раскладываются по блокам конфига и где у штрафов меняется знак.
    Редакции, формой не выражаемые (свой список раздач, посадка уже 3–5),
    в заготовки не попадают — подставленные поля соврали бы о том, что на кнопке.
    """
    season: Optional[RulesPreset] = None
    presets: List[RulesPreset] = []

    for edition in await repo.list_active():
        settings = settings_from_config(edition.config)
        if settings is None:
            continue
        preset = RulesPreset(
            code=edition.code,
            name=edition.name,
            description=(edition.meta or {}).get("description", ""),
            settings=TableRulesSettings(**settings),
        )
        if edition.code == SEASON_EDITION_CODE:
            season = preset
        else:
            presets.append(preset)

    return RulesPresetsResponse(
        season=season,
        presets=presets,
        limits=RulesFormLimits(
            min_start=1,
            max_peak_one_deck=max_peak_finite(),
            max_peak_infinite=MAX_PEAK_INFINITE,
        ),
    )
