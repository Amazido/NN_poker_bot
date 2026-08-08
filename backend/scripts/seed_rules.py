"""Ручной сидинг редакций правил.

Запуск: python -m scripts.seed_rules
(дефолтную редакцию также создаёт приложение при старте — см. main.ensure_default_rules)
"""
import asyncio

from app.db.base import async_session_maker
from app.poker.rules import DEFAULT_CONFIG
from app.repositories.pg import RulesEditionRepository


async def main() -> None:
    async with async_session_maker() as session:
        repo = RulesEditionRepository(session)
        existing = await repo.get_active_by_code("odessa_classic")
        if existing:
            print(f"odessa_classic v{existing.version} already exists")
            return
        edition = await repo.create(
            code="odessa_classic",
            version=1,
            name="Одесский покер — классическая редакция",
            config=DEFAULT_CONFIG,
            meta={"description": "Дефолтная редакция", "author": "system"},
        )
        print(f"Created rules edition {edition.code} v{edition.version} ({edition.id})")


if __name__ == "__main__":
    asyncio.run(main())
