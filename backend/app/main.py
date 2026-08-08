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
from app.poker import cards as C
from app.poker import engine
from app.poker import state as state_store
from app.poker.router import router as poker_router
from app.poker.rules import RulesEdition


async def ensure_default_rules() -> None:
    """Создать дефолтную редакцию правил odessa_classic v1, если её ещё нет."""
    from app.db.base import async_session_maker
    from app.poker.rules import DEFAULT_CONFIG
    from app.repositories.pg import RulesEditionRepository

    async with async_session_maker() as session:
        repo = RulesEditionRepository(session)
        existing = await repo.get_active_by_code("odessa_classic")
        if existing:
            startup_log.info("Rules edition odessa_classic v{} present", existing.version)
            return
        await repo.create(
            code="odessa_classic",
            version=1,
            name="Одесский покер — классическая редакция",
            config=DEFAULT_CONFIG,
            meta={
                "description": "Колода 54, 3-5 игроков, раунды 1..10..1 (18+n), "
                "джокеры по цвету козыря, крюк на последнем заказе.",
                "author": "system",
            },
            is_active=True,
        )
        startup_log.info("Seeded rules edition odessa_classic v1")


def _auto_action(state: dict):
    """Выбрать действие по умолчанию при истечении таймера хода."""
    kind, seat = engine.current_turn(state)
    if kind is None:
        return None, None, None
    r = state["round"]
    rules = RulesEdition(state["rules"])
    if kind == "bid":
        n = state["n_players"]
        others_sum = sum(r["bids"].values())
        is_last = len(r["bids"]) == n - 1
        allowed = rules.allowed_bids(r["cards_count"], is_last, others_sum)
        bid = 0 if 0 in allowed else allowed[0]
        return seat, "bid", {"bid": bid}
    hand = r["hands"][str(seat)]
    legal = C.legal_moves(hand, r["current_trick"]["lead_suit"], r["trump_suit"])
    return seat, "play_card", {"card": legal[0]}


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

                seat, action_type, payload = _auto_action(state)
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
    await ensure_default_rules()
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
