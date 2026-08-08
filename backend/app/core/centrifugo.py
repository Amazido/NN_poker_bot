"""Server-side клиент Centrifugo с graceful degradation.

Каналы (префикс = CENTRIFUGO_CHANNEL_PREFIX для изоляции окружений):
  {prefix}:room:{room_id}   - публичный канал комнаты (публичный стейт, фазы, вскрытие)
  {prefix}:user#{user_id}   - личный канал игрока (приватная рука, доступные действия)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as pyjwt

from app.config import CENTRIFUGO_CHANNEL_PREFIX
from app.logger import get_logger

log = get_logger("CENTRIFUGO")

_client = None
_P = CENTRIFUGO_CHANNEL_PREFIX


def ch_room(room_id: str) -> str:
    """Публичный канал комнаты."""
    return f"{_P}:room:{room_id}"


def ch_user(user_id: str) -> str:
    """Личный канал пользователя (user-limited)."""
    return f"{_P}:user#{user_id}"


async def init_centrifugo() -> None:
    global _client
    import app.config as cfg

    if not cfg.CENTRIFUGO_API_URL or not cfg.CENTRIFUGO_API_KEY:
        log.warning("Centrifugo not configured. Real-time disabled.")
        return
    try:
        from cent import AsyncClient

        _client = AsyncClient(api_url=cfg.CENTRIFUGO_API_URL, api_key=cfg.CENTRIFUGO_API_KEY)
        log.info("Centrifugo client initialized (prefix={})", _P)
    except Exception as e:  # noqa: BLE001
        log.error("Failed to init Centrifugo: {}", e)
        _client = None


async def close_centrifugo() -> None:
    global _client
    if _client is None:
        return
    try:
        close = getattr(_client, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:  # noqa: BLE001
        log.warning("Error closing Centrifugo client: {}", e)
    finally:
        _client = None


def get_centrifugo_client():
    return _client


async def publish(channel: str, data: dict) -> bool:
    if not _client:
        return False
    try:
        from cent import PublishRequest

        await _client.publish(PublishRequest(channel=channel, data=data))
        return True
    except Exception as e:  # noqa: BLE001
        log.error("publish to {} failed: {}", channel, e)
        return False


async def safe_publish(channel: str, data: dict) -> None:
    """Fire-and-forget публикация: логирует ошибки, но не бросает."""
    await publish(channel, data)


def generate_connection_token(user_id: str = "", expire_minutes: int = 60) -> Optional[str]:
    """JWT для подключения клиента к Centrifugo (sub = user_id, "" = аноним)."""
    import app.config as cfg

    secret = cfg.CENTRIFUGO_TOKEN_SECRET
    if not secret:
        log.warning("CENTRIFUGO_TOKEN_SECRET not set")
        return None
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id) if user_id is not None else "",
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        "iat": int(now.timestamp()),
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")
