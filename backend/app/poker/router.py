"""REST-роутер комнат Одесского покера.

Realtime-обновления идут через Centrifugo (каналы room:{id} и user#{id}).
Эти эндпоинты — управляющие команды и чтение состояния (fallback к REST).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.exceptions import Conflict, InvalidMove, NotFound
from app.db.models import UserModel
from app.dependencies import get_poker_service

router = APIRouter(prefix="/rooms", tags=["poker"])


class CreateRoomRequest(BaseModel):
    rules_code: Optional[str] = Field(default=None, description="Код редакции правил (по умолчанию активная)")
    max_players: Optional[int] = Field(default=None, description="Максимум игроков за столом")


class JoinRoomRequest(BaseModel):
    join_code: str = Field(..., description="Код для входа в комнату")


class ActionRequest(BaseModel):
    action_type: str = Field(..., description="bid | play_card")
    payload: dict = Field(default_factory=dict, description='{"bid": n} или {"card": "AS"}')


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (Conflict, InvalidMove)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post("", summary="Создать комнату")
async def create_room(
    request: CreateRoomRequest = CreateRoomRequest(),
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.create_room(user, rules_code=request.rules_code, max_players=request.max_players)
    except (NotFound, Conflict, InvalidMove) as e:
        raise _handle(e) from e


@router.post("/join", summary="Войти в комнату по коду")
async def join_room(
    request: JoinRoomRequest,
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.join_room(user, request.join_code)
    except (NotFound, Conflict, InvalidMove) as e:
        raise _handle(e) from e


@router.post("/{room_id}/start", summary="Начать матч (только создатель)")
async def start_match(
    room_id: str,
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.start_match(user, room_id)
    except (NotFound, Conflict, InvalidMove) as e:
        raise _handle(e) from e


@router.post("/{room_id}/action", summary="Игровое действие (заказ / ход картой)")
async def action(
    room_id: str,
    request: ActionRequest,
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.act(user, room_id, request.action_type, request.payload)
    except (NotFound, Conflict, InvalidMove) as e:
        raise _handle(e) from e


@router.get("/{room_id}", summary="Публичное состояние комнаты")
async def get_state(
    room_id: str,
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.get_public(room_id)
    except (NotFound, Conflict) as e:
        raise _handle(e) from e


@router.get("/{room_id}/hand", summary="Моя рука и доступные действия")
async def get_hand(
    room_id: str,
    user: UserModel = Depends(get_current_user),
    service=Depends(get_poker_service),
):
    try:
        return await service.get_private(user, room_id)
    except (NotFound, Conflict) as e:
        raise _handle(e) from e
