"""Фикстуры для e2e-тестов API.

Поднимаем приложение поверх реального Postgres (отдельная БД odessa_test),
live-стейт (Redis) подменяем in-memory, публикацию в Centrifugo оставляем no-op
(клиент не сконфигурирован). Каждый тест получает чистую схему.
"""
import copy
import os

os.environ.setdefault("DEBUG", "true")

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

PG_HOST = os.getenv("E2E_PG_HOST", "localhost")
PG_PORT = int(os.getenv("E2E_PG_PORT", "5432"))
PG_USER = os.getenv("E2E_PG_USER", "postgres")
PG_PASS = os.getenv("E2E_PG_PASS", "postgres")
TEST_DB_NAME = os.getenv("E2E_DB_NAME", "odessa_test")
TEST_DB_URL = f"postgresql+asyncpg://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"

# Короткая редакция правил для быстрого, но полноценного матча:
# раунды по 1, 2, 1 карте (торги + розыгрыш нескольких взяток + подсчёт + переход).
E2E_RULES_CODE = "e2e"
E2E_RULES_CONFIG = {
    "rounds": {"mode": "custom", "sequence": [1, 2, 1]},
    "players": {"min": 3, "max": 5},
    "turn_timeout_sec": 30,
}


async def _ensure_database() -> None:
    """Создать тестовую БД, если её ещё нет."""
    conn = await asyncpg.connect(
        user=PG_USER, password=PG_PASS, host=PG_HOST, port=PG_PORT, database="postgres"
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


def _mem_state_store(monkeypatch) -> None:
    """Подменить Redis-стейт in-memory словарём (эмуляция сериализации через deepcopy)."""
    mem: dict = {}
    active: set = set()

    async def _load(room_id):
        v = mem.get(room_id)
        return copy.deepcopy(v) if v is not None else None

    async def _save(room_id, state):
        mem[room_id] = copy.deepcopy(state)

    async def _delete(room_id):
        mem.pop(room_id, None)

    async def _add(room_id):
        active.add(room_id)

    async def _remove(room_id):
        active.discard(room_id)

    async def _list():
        return list(active)

    import app.poker.state as st

    monkeypatch.setattr(st, "load_state", _load)
    monkeypatch.setattr(st, "save_state", _save)
    monkeypatch.setattr(st, "delete_state", _delete)
    monkeypatch.setattr(st, "add_active_room", _add)
    monkeypatch.setattr(st, "remove_active_room", _remove)
    monkeypatch.setattr(st, "list_active_rooms", _list)


@pytest_asyncio.fixture
async def client(monkeypatch):
    """HTTP-клиент поверх приложения с чистой тестовой БД и in-memory стейтом."""
    await _ensure_database()

    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)

    import app.db.models  # noqa: F401  — регистрация таблиц на Base
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    _mem_state_store(monkeypatch)

    from app.dependencies import get_db_session
    from app.main import app

    async def _override_session():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_session

    # Сид короткой редакции правил.
    from app.repositories.pg import RulesEditionRepository

    async with TestSession() as session:
        repo = RulesEditionRepository(session)
        await repo.create(
            code=E2E_RULES_CODE,
            version=1,
            name="E2E короткая редакция",
            config=E2E_RULES_CONFIG,
            meta={"author": "e2e"},
            is_active=True,
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://e2e.local") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()
