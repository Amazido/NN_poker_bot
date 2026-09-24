"""Ручной сидинг встроенных редакций правил.

Запуск: python -m scripts.seed_rules
(то же самое делает приложение при старте — см. main.ensure_builtin_rules)
"""
import asyncio

from app.db.base import async_session_maker
from app.poker.editions import BUILTIN_EDITIONS
from app.poker.rules import RulesEdition
from app.repositories.pg import RulesEditionRepository


async def main() -> None:
    async with async_session_maker() as session:
        repo = RulesEditionRepository(session)
        for spec in BUILTIN_EDITIONS:
            existing = await repo.get_active_by_code(spec["code"])
            if existing:
                print(f"{spec['code']} v{existing.version} already exists")
                continue
            RulesEdition(spec["config"], validate=True)
            edition = await repo.create(
                code=spec["code"],
                version=spec["version"],
                name=spec["name"],
                config=spec["config"],
                meta={"description": spec["description"], "author": "system"},
            )
            print(f"Created {edition.code} v{edition.version} ({edition.id})")


if __name__ == "__main__":
    asyncio.run(main())
