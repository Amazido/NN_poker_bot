"""Движок раунда Одесского покера — чистые функции над dict-состоянием.

Состояние (GameState) полностью сериализуемо в JSON и хранится в Redis как
источник истины (включая руки игроков — они приватны и вырезаются при отдаче
клиентам, см. state.py). Движок не знает про БД, Redis и Centrifugo.

Действия:
  apply_action(state, seat, "bid", {"bid": n})
  apply_action(state, seat, "play_card", {"card": "AS"})

Каждый вызов возвращает список событий (dict) для публикации.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import InvalidMove
from app.poker import cards as C
from app.poker.rules import RulesEdition

GameState = Dict[str, Any]
Event = Dict[str, Any]


def _next_seat(seat: int, n: int) -> int:
    return (seat + 1) % n


# === Инициализация матча ===

def new_game_state(
    room_id: str,
    seats: List[dict],
    rules_config: Optional[dict],
    starting_dealer: int,
    rng: Optional[random.Random] = None,
) -> GameState:
    """Создать состояние матча и раздать первый раунд.

    seats — список {"seat","user_id","username","score"} (score можно 0).
    """
    rules = RulesEdition(rules_config)
    seats_sorted = sorted(seats, key=lambda s: s["seat"])
    n = len(seats_sorted)
    for s in seats_sorted:
        s.setdefault("score", 0)

    state: GameState = {
        "room_id": room_id,
        "rules": rules.config,
        "status": "playing",
        "match_over": False,
        "seats": seats_sorted,
        "n_players": n,
        "sequence": rules.round_sequence(n),
        "round_index": 0,
        "starting_dealer": starting_dealer % n,
        "round": None,
    }
    start_round(state, rng)
    return state


def start_round(state: GameState, rng: Optional[random.Random] = None) -> List[Event]:
    """Начать текущую раздачу (по round_index): сдать карты, вскрыть козырь, торги."""
    rules = RulesEdition(state["rules"])
    n = state["n_players"]
    idx = state["round_index"]
    cards_count = state["sequence"][idx]

    dealer_seat = (state["starting_dealer"] + idx) % n
    first_seat = _next_seat(dealer_seat, n)

    hands, trump_card = C.deal(n, cards_count, rng)
    trump_suit, no_trump = C.determine_trump(trump_card)

    round_state = {
        "cards_count": cards_count,
        "dealer_seat": dealer_seat,
        "first_seat": first_seat,
        "trump_card": trump_card,
        "trump_suit": trump_suit,
        "no_trump": no_trump,
        "no_trump_high_joker": trump_card if no_trump else None,
        "phase": "bidding",
        "hands": {str(seat): hands[seat] for seat in range(n)},
        "bids": {},
        "bid_turn": first_seat,
        "tricks_won": {str(seat): 0 for seat in range(n)},
        "trick_number": 1,
        "current_trick": None,
        "last_trick": None,
        "result": None,
    }
    state["round"] = round_state
    return [{
        "type": "round_started",
        "round_index": idx,
        "cards_count": cards_count,
        "dealer_seat": dealer_seat,
        "first_seat": first_seat,
        "trump_card": trump_card,
        "trump_suit": trump_suit,
        "no_trump": no_trump,
        "phase": "bidding",
        "bid_turn": first_seat,
    }]


# === Диспетчер действий ===

def apply_action(
    state: GameState,
    seat: int,
    action_type: str,
    payload: dict,
    rng: Optional[random.Random] = None,
) -> List[Event]:
    if state.get("match_over"):
        raise InvalidMove("Match is over")
    if action_type == "bid":
        return _apply_bid(state, seat, int(payload["bid"]))
    if action_type == "play_card":
        return _apply_play(state, seat, str(payload["card"]), rng)
    raise InvalidMove(f"Unknown action: {action_type}")


# === Торги ===

def _apply_bid(state: GameState, seat: int, bid: int) -> List[Event]:
    r = state["round"]
    if r["phase"] != "bidding":
        raise InvalidMove("Not in bidding phase")
    if r["bid_turn"] != seat:
        raise InvalidMove("Not your turn to bid")

    rules = RulesEdition(state["rules"])
    n = state["n_players"]
    cards_count = r["cards_count"]
    others_sum = sum(r["bids"].values())
    is_last = len(r["bids"]) == n - 1

    allowed = rules.allowed_bids(cards_count, is_last, others_sum)
    if bid not in allowed:
        raise InvalidMove(f"Bid {bid} not allowed (allowed: {allowed})")

    r["bids"][str(seat)] = bid
    events: List[Event] = [{"type": "bid_made", "seat": seat, "bid": bid}]

    if len(r["bids"]) == n:
        # Торги закончены → фаза розыгрыша, первую взятку ведёт first_seat.
        r["bid_turn"] = None
        r["phase"] = "playing"
        r["current_trick"] = {
            "lead_seat": r["first_seat"],
            "lead_suit": None,
            "turn": r["first_seat"],
            "plays": [],
        }
        events.append({
            "type": "bidding_finished",
            "bids": dict(r["bids"]),
            "phase": "playing",
            "turn": r["first_seat"],
        })
    else:
        r["bid_turn"] = _next_seat(seat, n)
        events.append({"type": "bid_turn", "seat": r["bid_turn"]})
    return events


# === Розыгрыш взяток ===

def _apply_play(
    state: GameState, seat: int, card: str, rng: Optional[random.Random]
) -> List[Event]:
    r = state["round"]
    if r["phase"] != "playing":
        raise InvalidMove("Not in playing phase")
    ct = r["current_trick"]
    if ct["turn"] != seat:
        raise InvalidMove("Not your turn to play")

    hand = r["hands"][str(seat)]
    if card not in hand:
        raise InvalidMove("Card not in hand")

    legal = C.legal_moves(hand, ct["lead_suit"], r["trump_suit"])
    if card not in legal:
        raise InvalidMove(f"Illegal card {card} (must follow suit)")

    hand.remove(card)
    if not ct["plays"]:
        ct["lead_seat"] = seat
        ct["lead_suit"] = C.lead_suit_of_play(card)
    ct["plays"].append({"seat": seat, "card": card})

    n = state["n_players"]
    events: List[Event] = [{"type": "card_played", "seat": seat, "card": card}]

    if len(ct["plays"]) < n:
        ct["turn"] = _next_seat(seat, n)
        events.append({"type": "play_turn", "seat": ct["turn"]})
        return events

    # Взятка собрана — определяем победителя.
    rules = RulesEdition(state["rules"])
    plays_tuples: List[Tuple[int, str]] = [(p["seat"], p["card"]) for p in ct["plays"]]
    winner = C.trick_winner(
        plays_tuples,
        trump_suit=r["trump_suit"],
        lead_suit=ct["lead_suit"],
        no_trump_high_joker=r["no_trump_high_joker"],
        flags=rules.flags,
    )
    r["tricks_won"][str(winner)] += 1
    r["last_trick"] = {
        "trick_number": r["trick_number"],
        "plays": list(ct["plays"]),
        "lead_suit": ct["lead_suit"],
        "winner": winner,
    }
    events.append({
        "type": "trick_won",
        "trick_number": r["trick_number"],
        "winner": winner,
        "plays": list(ct["plays"]),
    })
    r["trick_number"] += 1

    hands_empty = all(len(h) == 0 for h in r["hands"].values())
    if hands_empty:
        events.extend(_finish_round(state))
        events.extend(_advance_after_round(state, rng))
    else:
        r["current_trick"] = {
            "lead_seat": winner,
            "lead_suit": None,
            "turn": winner,
            "plays": [],
        }
        events.append({"type": "play_turn", "seat": winner})
    return events


# === Подсчёт и переход к следующей раздаче ===

def _finish_round(state: GameState) -> List[Event]:
    r = state["round"]
    rules = RulesEdition(state["rules"])
    r["phase"] = "scoring"

    result: Dict[str, dict] = {}
    seat_score = {s["seat"]: s for s in state["seats"]}
    for seat in range(state["n_players"]):
        bid = r["bids"].get(str(seat), 0)
        won = r["tricks_won"].get(str(seat), 0)
        delta = rules.score(bid, won)
        seat_score[seat]["score"] += delta
        result[str(seat)] = {
            "bid": bid,
            "won": won,
            "delta": delta,
            "total": seat_score[seat]["score"],
        }
    r["result"] = result
    r["phase"] = "finished"
    return [{
        "type": "round_scored",
        "round_index": state["round_index"],
        "result": result,
        "scores": {s["seat"]: s["score"] for s in state["seats"]},
    }]


def _advance_after_round(state: GameState, rng: Optional[random.Random]) -> List[Event]:
    state["round_index"] += 1
    if state["round_index"] < len(state["sequence"]):
        return start_round(state, rng)
    state["match_over"] = True
    state["status"] = "finished"
    winner_seat = max(state["seats"], key=lambda s: s["score"])["seat"]
    return [{
        "type": "match_over",
        "scores": {s["seat"]: s["score"] for s in state["seats"]},
        "winner_seat": winner_seat,
    }]


# === Вспомогательные геттеры (для таймера/сервиса) ===

def current_turn(state: GameState) -> Tuple[Optional[str], Optional[int]]:
    """Кто сейчас ходит: ("bid"|"play", seat) либо (None, None)."""
    r = state.get("round")
    if not r or state.get("match_over"):
        return None, None
    if r["phase"] == "bidding":
        return "bid", r["bid_turn"]
    if r["phase"] == "playing":
        return "play", r["current_trick"]["turn"]
    return None, None


def seat_of_user(state: GameState, user_id: str) -> Optional[int]:
    for s in state["seats"]:
        if s["user_id"] == user_id:
            return s["seat"]
    return None
