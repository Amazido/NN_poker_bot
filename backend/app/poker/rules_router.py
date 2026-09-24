"""REST-роутер редакций правил: что можно выбрать при создании стола."""
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_rules_repo
from app.poker.rules import RulesEdition
from app.repositories.pg import RulesEditionRepository

router = APIRouter(prefix="/rules", tags=["rules"])


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
