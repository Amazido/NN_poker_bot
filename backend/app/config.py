"""Конфигурация приложения из переменных окружения."""
import os
from pathlib import Path

from dotenv import load_dotenv

# В DEBUG значения из backend/.env перебивают «залипшие» переменные окружения.
_env_path = Path(__file__).resolve().parent.parent / ".env"
_dotenv_override = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
load_dotenv(_env_path, override=_dotenv_override)


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("true", "1", "yes")


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = _flag("DEBUG", "true")
ENV = os.getenv("ENV", "local" if DEBUG else "prod").lower()

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_INITIAL_BALANCE = float(os.getenv("TELEGRAM_INITIAL_BALANCE", "1000"))

# === JWT ===
JWT_SECRET = os.getenv("JWT_SECRET", TELEGRAM_BOT_TOKEN or "dev-secret-key")

# === Database ===
_LOCAL_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/odessa_dev"
DATABASE_URL = os.getenv("DATABASE_URL", _LOCAL_DB_URL if DEBUG else "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required in non-DEBUG mode")

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

# === Redis ===
_redis_url = (os.getenv("REDIS_URL") or "").strip()
REDIS_URL = _redis_url or ("redis://localhost:6379/0" if DEBUG else "")
REDIS_KEY_PREFIX = (os.getenv("REDIS_KEY_PREFIX") or "").strip() or ("dev" if DEBUG else "prod")

# === Centrifugo ===
CENTRIFUGO_API_URL = (os.getenv("CENTRIFUGO_API_URL") or "").strip() or (
    "http://localhost:8001/api" if DEBUG else ""
)
CENTRIFUGO_API_KEY = (os.getenv("CENTRIFUGO_API_KEY") or "").strip() or (
    "dev-centrifugo-api-key" if DEBUG else ""
)
CENTRIFUGO_TOKEN_SECRET = (os.getenv("CENTRIFUGO_TOKEN_SECRET") or "").strip() or (
    "dev-centrifugo-secret" if DEBUG else ""
)
CENTRIFUGO_CHANNEL_PREFIX = (os.getenv("CENTRIFUGO_CHANNEL_PREFIX") or "").strip() or (
    "dev" if DEBUG else "prod"
)

# === CORS ===
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()
]

# === Логи ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO").upper()

# === Игровые тайминги ===
# Таймаут хода игрока по умолчанию (сек) — используется, если в редакции правил не задан.
TURN_TIMEOUT_SEC = int(os.getenv("TURN_TIMEOUT_SEC", "30"))
