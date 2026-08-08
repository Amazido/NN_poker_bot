"""Репозиторий пользователей."""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserModel, UserStatus, UserType


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: str) -> Optional[UserModel]:
        try:
            uid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return None
        res = await self.session.execute(select(UserModel).where(UserModel.id == uid))
        return res.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserModel]:
        res = await self.session.execute(
            select(UserModel).where(UserModel.telegram_id == telegram_id)
        )
        return res.scalar_one_or_none()

    async def get_dev_by_username(self, username: str) -> Optional[UserModel]:
        res = await self.session.execute(
            select(UserModel).where(
                UserModel.telegram_username == username,
                UserModel.user_type == UserType.DEV,
            )
        )
        return res.scalar_one_or_none()

    async def create(
        self,
        *,
        user_type: str,
        telegram_id: Optional[int] = None,
        telegram_username: Optional[str] = None,
        balance: float = 0.0,
    ) -> UserModel:
        user = UserModel(
            id=uuid.uuid4(),
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            user_type=user_type,
            status=UserStatus.ACTIVE,
            balance=Decimal(str(balance)),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
