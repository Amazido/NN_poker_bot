"""FastAPI-приложение Одесского покера."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.config import CORS_ORIGINS
from app.core.exceptions import NotAuthenticated
from app.logger import startup_log, task_log
from app.poker import state as state_store
from app.poker.autoplay import choose_auto_action
from app.poker.router import router as poker_router
from app.poker.rules import RulesEdition
from app.poker.rules_router import router as rules_router


async def ensure_builtin_rules() -> None:
    """Досидить встроенные редакции правил, которых ещё нет в БД.

    Существующие не трогаем: у них своя история комнат, а конфиг мог быть
    поправлен руками. Изменение правил выпускается новой версией.
    """
    from app.db.base import async_session_maker
    from app.poker.editions import BUILTIN_EDITIONS
    from app.repositories.pg import RulesEditionRepository

    async with async_session_maker() as session:
        repo = RulesEditionRepository(session)
        for spec in BUILTIN_EDITIONS:
            existing = await repo.get_active_by_code(spec["code"])
            if existing:
                continue
            # Негодный конфиг лучше поймать на старте, чем в середине матча.
            RulesEdition(spec["config"], validate=True)
            await repo.create(
                code=spec["code"],
                version=spec["version"],
                name=spec["name"],
                config=spec["config"],
                meta={"description": spec["description"], "author": "system"},
                is_active=True,
            )
            startup_log.info("Seeded rules edition {} v{}", spec["code"], spec["version"])


async def turn_timeout_task() -> None:
    """Фоновый таймер: авто-ход за игрока, который не успел походить."""
    from app.db.base import async_session_maker
    from app.poker.service import PokerService
    from app.repositories.pg import (
        RoomRepository,
        RoundRepository,
        RulesEditionRepository,
        UserRepository,
    )

    task_log.info("Turn timeout task started")
    while True:
        try:
            await asyncio.sleep(2)
            room_ids = await state_store.list_active_rooms()
            for room_id in room_ids:
                state = await state_store.load_state(room_id)
                if not state or state.get("match_over"):
                    await state_store.remove_active_room(room_id)
                    continue
                deadline = state.get("turn_deadline")
                if not deadline:
                    continue
                if datetime.now(timezone.utc) < datetime.fromisoformat(deadline):
                    continue

                seat, action_type, payload = choose_auto_action(state)
                if seat is None:
                    continue
                user_id = next(
                    (s["user_id"] for s in state["seats"] if s["seat"] == seat), None
                )
                if not user_id:
                    continue

                async with async_session_maker() as session:
                    user_repo = UserRepository(session)
                    user = await user_repo.get(user_id)
                    if not user:
                        continue
                    service = PokerService(
                        session=session,
                        user_repo=user_repo,
                        rules_repo=RulesEditionRepository(session),
                        room_repo=RoomRepository(session),
                        round_repo=RoundRepository(session),
                    )
                    try:
                        await service.act(user, room_id, action_type, payload)
                        task_log.info("Auto-move in room {}: seat {} {}", room_id, seat, action_type)
                    except Exception as e:  # noqa: BLE001
                        task_log.warning("Auto-move failed in {}: {}", room_id, e)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            task_log.error("turn_timeout_task error: {}", e)
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.centrifugo import close_centrifugo, init_centrifugo
    from app.core.redis import close_redis, init_redis, redis_reconnect_task
    from app.db.base import close_db

    startup_log.info("Starting Odessa Poker...")
    await init_redis()
    reconnect_task = asyncio.create_task(redis_reconnect_task())
    await init_centrifugo()
    await ensure_builtin_rules()
    timeout_task = asyncio.create_task(turn_timeout_task())
    startup_log.success("Application started")

    yield

    startup_log.info("Stopping application...")
    for task in (reconnect_task, timeout_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await close_centrifugo()
    await close_db()
    await close_redis()
    startup_log.info("Application stopped")


app = FastAPI(
    title="Odessa Poker API",
    description="Одесский покер: Telegram WebApp, real-time через Centrifugo.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return JSONResponse(status_code=401, content={"detail": str(exc)})


app.include_router(auth_router)
app.include_router(poker_router)
app.include_router(rules_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "odessa-poker"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    from sqlalchemy import text

    from app.core.redis import get_redis
    from app.db.base import async_session_maker

    checks = {}
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:  # noqa: BLE001
        checks["database"] = f"error: {e}"

    redis = get_redis()
    if redis:
        try:
            await redis.ping()
            checks["redis"] = "connected"
        except Exception as e:  # noqa: BLE001
            checks["redis"] = f"error: {e}"
    else:
        checks["redis"] = "not_configured"

    ok = all(v in ("connected", "not_configured") for v in checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "not_ready", "checks": checks},
    )
