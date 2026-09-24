"""Репозиторий редакций правил."""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RulesEditionModel


class RulesEditionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, edition_id: str) -> Optional[RulesEditionModel]:
        try:
            eid = uuid.UUID(edition_id)
        except (ValueError, TypeError):
            return None
        res = await self.session.execute(
            select(RulesEditionModel).where(RulesEditionModel.id == eid)
        )
        return res.scalar_one_or_none()

    async def get_active_by_code(self, code: str) -> Optional[RulesEditionModel]:
        """Активная редакция с наибольшей версией для данного code."""
        res = await self.session.execute(
            select(RulesEditionModel)
            .where(RulesEditionModel.code == code, RulesEditionModel.is_active.is_(True))
            .order_by(RulesEditionModel.version.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_active(self) -> List[RulesEditionModel]:
        """Активные редакции, по одной (наибольшей) версии на каждый code."""
        res = await self.session.execute(
            select(RulesEditionModel)
            .where(RulesEditionModel.is_active.is_(True))
            .order_by(RulesEditionModel.code, RulesEditionModel.version.desc())
        )
        latest: dict[str, RulesEditionModel] = {}
        for edition in res.scalars():
            latest.setdefault(edition.code, edition)
        return list(latest.values())

    async def get_default(self) -> Optional[RulesEditionModel]:
        """Любая активная редакция (приоритет — наибольшая версия)."""
        res = await self.session.execute(
            select(RulesEditionModel)
            .where(RulesEditionModel.is_active.is_(True))
            .order_by(RulesEditionModel.version.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def create(
        self, *, code: str, version: int, name: str, config: dict, meta: dict, is_active: bool = True
    ) -> RulesEditionModel:
        edition = RulesEditionModel(
            id=uuid.uuid4(),
            code=code,
            version=version,
            name=name,
            config=config,
            meta=meta,
            is_active=is_active,
        )
        self.session.add(edition)
        await self.session.commit()
        await self.session.refresh(edition)
        return edition
