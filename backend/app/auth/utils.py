"""Проверка подписи Telegram WebApp initData.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import parse_qs, unquote

from app.core.exceptions import InvalidCredentials

# Максимальный возраст initData (сек)
MAX_AUTH_AGE_SEC = 86400


def verify_telegram_webapp_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """Проверить подпись initData и вернуть данные пользователя (dict).

    Raises:
        InvalidCredentials: подпись неверна / данные устарели / нет user.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)

    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        raise InvalidCredentials("Missing hash in initData")

    auth_date_str = parsed.get("auth_date", [None])[0]
    if not auth_date_str:
        raise InvalidCredentials("Missing auth_date in initData")
    try:
        auth_date = int(auth_date_str)
    except ValueError as e:
        raise InvalidCredentials("Invalid auth_date format") from e

    if int(time.time()) - auth_date > MAX_AUTH_AGE_SEC:
        raise InvalidCredentials("InitData expired")

    # data_check_string: все пары кроме hash, отсортированные по ключу.
    parts = []
    for key in sorted(parsed.keys()):
        if key == "hash":
            continue
        parts.append(f"{key}={parsed[key][0]}")
    data_check_string = "\n".join(parts)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise InvalidCredentials("Invalid signature")

    user_str = parsed.get("user", [None])[0]
    if not user_str:
        raise InvalidCredentials("Missing user data in initData")
    try:
        return json.loads(unquote(user_str))
    except json.JSONDecodeError as e:
        raise InvalidCredentials("Invalid user data format") from e
