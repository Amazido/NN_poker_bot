"""Авто-ход: что делается за игрока, который не походил сам.

Один и тот же механизм обслуживает три случая: истёк таймер хода, место
помечено `left_seats` (игрок ушёл посреди матча) и бот. Отдельного ИИ у ботов
нет — бот ходит ровно так же, как таймер за зазевавшегося: минимальный
допустимый заказ и первая легальная карта.

Выбор обязан считаться с редакцией правил стола: «крюк» может быть выключен,
число карт в раздаче своё, а легальность хода зависит от масти сброса и козыря.
"""
from typing import Optional, Tuple

from app.poker import cards as C
from app.poker import engine
from app.poker.engine import GameState
from app.poker.rules import RulesEdition

AutoAction = Tuple[Optional[int], Optional[str], Optional[dict]]


def choose_auto_action(state: GameState) -> AutoAction:
    """Действие по умолчанию за того, чей сейчас ход.

    Возвращает (seat, action_type, payload) либо (None, None, None), если
    ходить некому.
    """
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
        # Ноль предпочтительнее: не обещать взяток безопаснее всего. Но «крюк»
        # может его запретить — тогда берём наименьший разрешённый.
        bid = 0 if 0 in allowed else allowed[0]
        return seat, "bid", {"bid": bid}

    hand = r["hands"][str(seat)]
    legal = C.legal_moves(hand, r["current_trick"]["lead_suit"], r["trump_suit"])
    return seat, "play_card", {"card": legal[0]}
