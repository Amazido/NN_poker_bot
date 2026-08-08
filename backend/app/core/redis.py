"""Redis-клиент с graceful degradation и self-healing reconnect.

Ключи префиксуются REDIS_KEY_PREFIX для изоляции dev/prod на общем Redis.
"""
import asyncio
import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import REDIS_KEY_PREFIX, REDIS_URL
from app.logger import get_logger

log = get_logger("REDIS")

_redis_client: Optional[aioredis.Redis] = None

RECONNECT_MIN_INTERVAL_SEC = 10
RECONNECT_MAX_INTERVAL_SEC = 60


def _prefixed(key: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{key}"


async def _try_connect() -> Optional[aioredis.Redis]:
    if not REDIS_URL:
        return None
    try:
        client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        await client.ping()
        return client
    except Exception as e:  # noqa: BLE001
        log.error("Redis connect failed: {}", e)
        return None


async def init_redis() -> Optional[aioredis.Redis]:
    global _redis_client
    if not REDIS_URL:
        log.warning("REDIS_URL not set, Redis features disabled")
        return None
    client = await _try_connect()
    _redis_client = client
    if client:
        log.info("Redis connected (prefix={})", REDIS_KEY_PREFIX)
    else:
        log.error("Initial Redis connection failed; reconnect task will keep retrying")
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
        except Exception as e:  # noqa: BLE001
            log.warning("Error closing Redis: {}", e)
        _redis_client = None


def get_redis() -> Optional[aioredis.Redis]:
    return _redis_client


async def redis_reconnect_task() -> None:
    """Фоновая задача: держит клиент живым, переподключается при сбое."""
    global _redis_client
    if not REDIS_URL:
        return
    backoff = RECONNECT_MIN_INTERVAL_SEC
    while True:
        try:
            await asyncio.sleep(backoff)
            if _redis_client is None:
                new = await _try_connect()
                if new is not None:
                    _redis_client = new
                    log.info("Redis reconnected")
                    backoff = RECONNECT_MIN_INTERVAL_SEC
                else:
                    backoff = min(backoff * 2, RECONNECT_MAX_INTERVAL_SEC)
                continue
            try:
                await _redis_client.ping()
                backoff = RECONNECT_MIN_INTERVAL_SEC
            except Exception:  # noqa: BLE001
                stale, _redis_client = _redis_client, None
                try:
                    await stale.close()
                except Exception:  # noqa: BLE001
                    pass
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            log.error("reconnect task error: {}", e)
            backoff = min(backoff * 2, RECONNECT_MAX_INTERVAL_SEC)


# === Безопасные операции (никогда не бросают) ===

async def safe_get(key: str) -> Optional[str]:
    if not _redis_client:
        return None
    try:
        return await _redis_client.get(_prefixed(key))
    except Exception as e:  # noqa: BLE001
        log.warning("GET {} failed: {}", key, e)
        return None


async def safe_set(key: str, value: str, ex: Optional[int] = None) -> bool:
    if not _redis_client:
        return False
    try:
        await _redis_client.set(_prefixed(key), value, ex=ex)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("SET {} failed: {}", key, e)
        return False


async def safe_delete(key: str) -> bool:
    if not _redis_client:
        return False
    try:
        await _redis_client.delete(_prefixed(key))
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("DELETE {} failed: {}", key, e)
        return False


async def safe_setex(key: str, seconds: int, value: str) -> bool:
    if not _redis_client:
        return False
    try:
        await _redis_client.setex(_prefixed(key), seconds, value)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("SETEX {} failed: {}", key, e)
        return False


async def safe_exists(key: str) -> bool:
    if not _redis_client:
        return False
    try:
        return bool(await _redis_client.exists(_prefixed(key)))
    except Exception as e:  # noqa: BLE001
        log.warning("EXISTS {} failed: {}", key, e)
        return False


# === JSON-хелперы ===

async def get_json(key: str) -> Optional[Any]:
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def set_json(key: str, data: Any, ex: Optional[int] = None) -> bool:
    return await safe_set(key, json.dumps(data, default=str), ex=ex)
