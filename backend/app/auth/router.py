"""Роутер авторизации: Telegram WebApp + dev, /me, /logout, centrifugo-token."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import (
    add_token_to_blacklist,
    create_jwt_token,
    get_current_token,
    get_current_user,
)
from app.auth.utils import verify_telegram_webapp_data
from app.config import DEBUG, TELEGRAM_BOT_TOKEN, TELEGRAM_INITIAL_BALANCE
from app.core.exceptions import InvalidCredentials
from app.db.models import UserModel, UserType
from app.dependencies import get_user_repo
from app.logger import auth_log
from app.repositories.pg import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., description="initData от Telegram WebApp")


class UserResponse(BaseModel):
    id: str
    user_type: str
    telegram_id: int | None = None
    telegram_username: str | None = None
    balance: float


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class DevAuthRequest(BaseModel):
    username: str = Field(default="TestPlayer", description="Имя dev-пользователя")


class LogoutResponse(BaseModel):
    success: bool
    message: str


class CentrifugoTokenResponse(BaseModel):
    token: str


def _to_user_response(user: UserModel) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        user_type=user.user_type,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        balance=float(user.balance),
    )


@router.post("/telegram", response_model=AuthResponse, summary="Авторизация через Telegram WebApp")
async def auth_telegram(
    request: TelegramAuthRequest,
    user_repo: UserRepository = Depends(get_user_repo),
):
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not configured")
    try:
        data = verify_telegram_webapp_data(request.init_data, TELEGRAM_BOT_TOKEN)
    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    telegram_id = data.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing user id in Telegram data")

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        user = await user_repo.create(
            user_type=UserType.TELEGRAM,
            telegram_id=telegram_id,
            telegram_username=data.get("username"),
            balance=TELEGRAM_INITIAL_BALANCE,
        )
        auth_log.info("New TG user {} registered", user.id)

    token = create_jwt_token(str(user.id), user_type=UserType.TELEGRAM)
    return AuthResponse(token=token, user=_to_user_response(user))


@router.post("/dev", response_model=AuthResponse, summary="[DEBUG] Dev-авторизация без Telegram")
async def auth_dev(
    request: DevAuthRequest = DevAuthRequest(),
    user_repo: UserRepository = Depends(get_user_repo),
):
    if not DEBUG:
        raise HTTPException(status_code=403, detail="Dev auth available only in DEBUG mode")

    user = await user_repo.get_dev_by_username(request.username)
    if not user:
        user = await user_repo.create(
            user_type=UserType.DEV,
            telegram_username=request.username,
            balance=1000.0,
        )
        auth_log.info("New dev user {} ({})", user.id, request.username)

    token = create_jwt_token(str(user.id), user_type=UserType.DEV)
    return AuthResponse(token=token, user=_to_user_response(user))


@router.get("/me", response_model=UserResponse, summary="Текущий пользователь")
async def get_me(user: UserModel = Depends(get_current_user)):
    return _to_user_response(user)


@router.post("/logout", response_model=LogoutResponse, summary="Выход (инвалидация токена)")
async def logout(
    token: str = Depends(get_current_token),
    user: UserModel = Depends(get_current_user),
):
    add_token_to_blacklist(token)
    return LogoutResponse(success=True, message=f"User {user.id} logged out")


@router.get("/centrifugo-token", response_model=CentrifugoTokenResponse, summary="Токен подключения к Centrifugo")
async def centrifugo_token(user: UserModel = Depends(get_current_user)):
    from app.core.centrifugo import generate_connection_token

    token = generate_connection_token(user_id=str(user.id))
    if not token:
        raise HTTPException(status_code=503, detail="Real-time service not configured")
    return CentrifugoTokenResponse(token=token)
