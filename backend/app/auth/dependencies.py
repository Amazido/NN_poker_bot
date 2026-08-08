"""JWT-логика и dependency для получения текущего пользователя."""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

import jwt
from fastapi import Depends, Header

from app.config import JWT_SECRET
from app.core.exceptions import NotAuthenticated
from app.db.models import UserModel
from app.dependencies import get_user_repo
from app.repositories.pg import UserRepository

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory blacklist (для logout). В Redis дублируется best-effort.
_token_blacklist: Set[str] = set()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def create_jwt_token(
    user_id: str,
    user_type: Optional[str] = None,
    expiration_minutes: Optional[float] = None,
) -> str:
    if expiration_minutes is not None:
        exp = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)
    else:
        exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {"user_id": user_id, "exp": exp, "iat": datetime.now(timezone.utc)}
    if user_type is not None:
        payload["user_type"] = user_type
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    if token in _token_blacklist:
        raise NotAuthenticated("Token has been revoked")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise NotAuthenticated("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise NotAuthenticated(f"Invalid token: {e}") from e
    if not payload.get("user_id"):
        raise NotAuthenticated("Invalid token: missing user_id")
    return payload


def add_token_to_blacklist(token: str) -> None:
    _token_blacklist.add(token)


def extract_token_from_header(authorization: Optional[str]) -> str:
    if not authorization:
        raise NotAuthenticated("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise NotAuthenticated("Invalid Authorization header. Expected: Bearer <token>")
    return parts[1]


async def get_current_user(
    authorization: Optional[str] = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserModel:
    token = extract_token_from_header(authorization)
    payload = verify_jwt_token(token)
    user = await user_repo.get(payload["user_id"])
    if not user:
        raise NotAuthenticated(f"User {payload['user_id']} not found")
    return user


def get_current_token(authorization: Optional[str] = Header(None)) -> str:
    return extract_token_from_header(authorization)


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
) -> Optional[UserModel]:
    if not authorization:
        return None
    try:
        token = extract_token_from_header(authorization)
        payload = verify_jwt_token(token)
        return await user_repo.get(payload["user_id"])
    except Exception:  # noqa: BLE001
        return None
