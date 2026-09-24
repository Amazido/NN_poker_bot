"""Стейт-движок в Redis: хранение полного состояния + публичный/приватный views.

Полное состояние (включая руки) — источник истины, лежит в Redis:
  poker:room:{room_id}:state

Клиентам руки других игроков не отдаём:
  - public_view  — общий вид для канала комнаты (руки скрыты, только счётчики);
  - private_view — личный вид игрока (его рука + доступные действия).
"""
from typing import Any, Dict, List, Optional

from app.config import REDIS_KEY_PREFIX
from app.core.redis import get_json, get_redis, safe_delete, set_json
from app.poker import cards as C
from app.poker.engine import GameState
from app.poker.rules import RulesEdition

# TTL стейта комнаты в Redis (сек). Обновляется при каждом сохранении.
STATE_TTL_SEC = 24 * 3600

# Набор id активных комнат (для фонового таймера хода).
_ACTIVE_SET = f"{REDIS_KEY_PREFIX}:poker:active_rooms"


def _state_key(room_id: str) -> str:
    return f"poker:room:{room_id}:state"


async def load_state(room_id: str) -> Optional[GameState]:
    return await get_json(_state_key(room_id))


async def save_state(room_id: str, state: GameState) -> None:
    await set_json(_state_key(room_id), state, ex=STATE_TTL_SEC)


async def delete_state(room_id: str) -> None:
    await safe_delete(_state_key(room_id))


# === Набор активных комнат (для таймера хода) ===

async def add_active_room(room_id: str) -> None:
    r = get_redis()
    if r:
        try:
            await r.sadd(_ACTIVE_SET, room_id)
        except Exception:  # noqa: BLE001
            pass


async def remove_active_room(room_id: str) -> None:
    r = get_redis()
    if r:
        try:
            await r.srem(_ACTIVE_SET, room_id)
        except Exception:  # noqa: BLE001
            pass


async def list_active_rooms() -> list[str]:
    r = get_redis()
    if not r:
        return []
    try:
        return list(await r.smembers(_ACTIVE_SET))
    except Exception:  # noqa: BLE001
        return []


def rules_view(config: Optional[dict], code: str = "", name: str = "") -> Dict[str, Any]:
    """Правила стола для клиента: чем эта редакция отличается, коротко.

    Игрок должен видеть, по каким правилам сел играть, — редакций теперь несколько.
    """
    rules = RulesEdition(config)
    return {
        "code": code,
        "name": name,
        "summary": rules.summary(),
        # Числом, а не фразой из summary: экран заказа показывает надбавку на кнопке.
        "blind_bonus": int(rules.config["scoring"]["blind_bonus"]) if rules.blind_allowed else 0,
    }


def public_view(state: GameState) -> Dict[str, Any]:
    """Публичный вид комнаты — без чужих рук."""
    r = state.get("round")
    round_public: Optional[dict] = None
    if r is not None:
        round_public = {
            "cards_count": r["cards_count"],
            "dealer_seat": r["dealer_seat"],
            "first_seat": r["first_seat"],
            "trump_card": r["trump_card"],
            "trump_suit": r["trump_suit"],
            "no_trump": r["no_trump"],
            "phase": r["phase"],
            "bids": r["bids"],
            "bid_turn": r["bid_turn"],
            "tricks_won": r["tricks_won"],
            "trick_number": r["trick_number"],
            "current_trick": r["current_trick"],
            "last_trick": r["last_trick"],
            "result": r["result"],
            "hand_counts": {seat: len(hand) for seat, hand in r["hands"].items()},
            # Кто заказал вслепую — видно всем: это часть публичной интриги.
            "blind_bids": r.get("blind_bids", {}),
        }

    kind, seat = _turn(state)
    return {
        "room_id": state["room_id"],
        "status": state["status"],
        "match_over": state["match_over"],
        "seats": state["seats"],
        "n_players": state["n_players"],
        "round_index": state["round_index"],
        "rounds_total": len(state["sequence"]),
        "round": round_public,
        "rules": rules_view(
            state.get("rules"),
            code=(state.get("rules_meta") or {}).get("code", ""),
            name=(state.get("rules_meta") or {}).get("name", ""),
        ),
        "turn": {"kind": kind, "seat": seat},
        "left_seats": state.get("left_seats", []),
        "turn_deadline": state.get("turn_deadline"),
    }


def private_view(state: GameState, seat: int) -> Dict[str, Any]:
    """Личный вид игрока: его рука + доступные действия, если сейчас его ход."""
    r = state.get("round")
    hand: List[str] = []
    available: Optional[dict] = None
    hand_hidden = False
    hand_count = 0
    can_open_hand = False

    if r is not None:
        hand = list(r["hands"].get(str(seat), []))
        hand_count = len(hand)
        rules = RulesEdition(state["rules"])
        n = state["n_players"]

        # «Тёмная»: до открытия игрок не видит и собственных карт — иначе слепой
        # заказ ничего не стоит.
        if not r.get("hand_open", {}).get(str(seat), True):
            hand_hidden = True
            hand = []
            can_open_hand = r["phase"] == "bidding" and str(seat) not in r["bids"]

        if r["phase"] == "bidding" and r["bid_turn"] == seat:
            others_sum = sum(r["bids"].values())
            is_last = len(r["bids"]) == n - 1
            options = rules.allowed_bids(r["cards_count"], is_last, others_sum)
            available = {"type": "bid", "options": options}
        elif r["phase"] == "playing" and r["current_trick"] and r["current_trick"]["turn"] == seat:
            legal = C.legal_moves(hand, r["current_trick"]["lead_suit"], r["trump_suit"])
            available = {"type": "play", "cards": legal}

    return {
        # Личный канал у игрока один на все комнаты, поэтому приватный вид обязан
        # сам говорить, к какой комнате он относится: недоигранный матч иначе
        # перебивает руку в текущем (см. журнал 2026-08-25).
        "room_id": state["room_id"],
        "seat": seat,
        "hand": hand,
        "hand_hidden": hand_hidden,
        "hand_count": hand_count,
        "can_open_hand": can_open_hand,
        "your_turn": available is not None,
        "available_actions": available,
        # Публичный и приватный вид приходят отдельными WS-сообщениями — фронт
        # сверяет их с одноимёнными полями в public_view, чтобы не показать
        # смесь новой раздачи/фазы со старой рукой (см. useGameView.ts).
        "round_index": state["round_index"],
        "phase": r["phase"] if r is not None else None,
    }


def _turn(state: GameState):
    r = state.get("round")
    if not r or state.get("match_over"):
        return None, None
    if r["phase"] == "bidding":
        return "bid", r["bid_turn"]
    if r["phase"] == "playing" and r["current_trick"]:
        return "play", r["current_trick"]["turn"]
    return None, None
