"""Dependency injection для FastAPI."""
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_maker
from app.repositories.pg import (
    RoomRepository,
    RoundRepository,
    RulesEditionRepository,
    UserRepository,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_repo(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return UserRepository(session)


async def get_rules_repo(session: AsyncSession = Depends(get_db_session)) -> RulesEditionRepository:
    return RulesEditionRepository(session)


async def get_room_repo(session: AsyncSession = Depends(get_db_session)) -> RoomRepository:
    return RoomRepository(session)


async def get_round_repo(session: AsyncSession = Depends(get_db_session)) -> RoundRepository:
    return RoundRepository(session)


async def get_poker_service(session: AsyncSession = Depends(get_db_session)):
    from app.poker.service import PokerService

    return PokerService(
        session=session,
        user_repo=UserRepository(session),
        rules_repo=RulesEditionRepository(session),
        room_repo=RoomRepository(session),
        round_repo=RoundRepository(session),
    )
