"""Заказ вслепую («тёмная»): рука закрыта до заказа, надбавка только за попадание.

Разделение понятий (см. docs/BACKLOG.md): «заказ вслепую» — это две фазы внутри
торгов (открыть руку или заказать, не глядя). «Одновременные заказы» — отдельное
правило, здесь не затрагивается.
"""
import random

import pytest

from app.poker import engine, state as state_store
from app.poker.autoplay import choose_auto_action
from app.poker.rules import RulesEdition

BLIND = {
    "bidding": {"blind_allowed": True},
    "scoring": {"blind_bonus": 5},
    "rounds": {"mode": "custom", "sequence": [3]},
}


def _seats(n):
    return [{"seat": i, "user_id": f"u{i}", "username": f"P{i}", "score": 0} for i in range(n)]


def _new_state(config=None, n=3, seed=5, dealer=0):
    return engine.new_game_state(
        room_id="r", seats=_seats(n), rules_config=config or BLIND,
        starting_dealer=dealer, rng=random.Random(seed),
    )


# === Конфигурация ===

def test_blind_is_off_by_default():
    rules = RulesEdition()
    assert rules.blind_allowed is False
    assert rules.score(2, 2, blind=True) == rules.score(2, 2), "надбавка без правила"


def test_blind_bonus_only_on_exact_bid():
    rules = RulesEdition(BLIND)
    assert rules.score(2, 2, blind=True) == 25   # 2*10 + 5
    assert rules.score(0, 0, blind=True) == 15   # пас +10, надбавка +5
    assert rules.score(2, 3, blind=True) == rules.score(2, 3), "перебор: скидок за риск нет"
    assert rules.score(2, 1, blind=True) == rules.score(2, 1), "недобор: минус в полном объёме"


# === Движок ===

def test_hand_is_hidden_from_its_owner_until_opened():
    state = _new_state()
    view = state_store.private_view(state, 1)
    assert view["hand"] == [], "слепой заказ ничего не стоит, если игрок видит карты"
    assert view["hand_hidden"] is True
    assert view["hand_count"] == 3, "сколько карт на руке — не секрет"
    assert view["can_open_hand"] is True


def test_opening_hand_reveals_it_without_taking_the_turn():
    state = _new_state()
    before = state["round"]["bid_turn"]
    engine.apply_action(state, 1, "open_hand", {})
    view = state_store.private_view(state, 1)
    assert len(view["hand"]) == 3
    assert view["hand_hidden"] is False
    assert view["can_open_hand"] is False
    assert state["round"]["bid_turn"] == before, "открытие руки не должно двигать очередь"


def test_hand_can_be_opened_before_your_turn():
    """Ждать очереди, чтобы просто взглянуть на карты, незачем."""
    state = _new_state()
    not_on_turn = (state["round"]["bid_turn"] + 1) % 3
    engine.apply_action(state, not_on_turn, "open_hand", {})
    assert state["round"]["hand_open"][str(not_on_turn)] is True


def test_bid_with_closed_hand_is_blind():
    state = _new_state()
    seat = state["round"]["bid_turn"]
    events = engine.apply_action(state, seat, "bid", {"bid": 1})
    assert state["round"]["blind_bids"][str(seat)] is True
    assert events[0]["blind"] is True


def test_bid_after_opening_is_not_blind():
    state = _new_state()
    seat = state["round"]["bid_turn"]
    engine.apply_action(state, seat, "open_hand", {})
    engine.apply_action(state, seat, "bid", {"bid": 1})
    assert state["round"]["blind_bids"][str(seat)] is False


def test_cannot_open_hand_after_bidding():
    state = _new_state()
    seat = state["round"]["bid_turn"]
    engine.apply_action(state, seat, "bid", {"bid": 1})
    with pytest.raises(engine.InvalidMove):
        engine.apply_action(state, seat, "open_hand", {})


def test_cannot_open_hand_twice():
    state = _new_state()
    engine.apply_action(state, 1, "open_hand", {})
    with pytest.raises(engine.InvalidMove):
        engine.apply_action(state, 1, "open_hand", {})


def test_cannot_open_hand_without_the_rule():
    state = _new_state({"rounds": {"mode": "custom", "sequence": [3]}})
    with pytest.raises(engine.InvalidMove):
        engine.apply_action(state, 1, "open_hand", {})


def test_all_hands_open_once_bidding_ends():
    """«Тёмная» касается только заказа — играют все с открытыми картами."""
    state = _new_state()
    for seat in _bid_order(state):
        engine.apply_action(state, seat, "bid", {"bid": 0})
    assert state["round"]["phase"] == "playing"
    assert all(state["round"]["hand_open"].values())
    assert len(state_store.private_view(state, 0)["hand"]) == 3


def test_blind_bonus_lands_in_the_round_result():
    """Один заказал вслепую, другой — открывшись; оба угадали, надбавка одному."""
    state = _new_state(dealer=2)
    order = _bid_order(state)
    engine.apply_action(state, order[1], "open_hand", {})
    for seat in order:
        engine.apply_action(state, seat, "bid", {"bid": 0})

    result = _play_out(state)
    for seat in order:
        entry = result[str(seat)]
        assert entry["blind"] is (seat != order[1])
        if entry["won"]:
            assert entry["delta"] == -5, "перебор: скидок за риск нет"
        else:
            assert entry["delta"] == (15 if entry["blind"] else 10)


def test_blind_flag_is_public():
    state = _new_state()
    seat = state["round"]["bid_turn"]
    engine.apply_action(state, seat, "bid", {"bid": 1})
    assert state_store.public_view(state)["round"]["blind_bids"][str(seat)] is True


# === Авто-ход ===

def test_auto_move_bids_blind_pass():
    """Отошёл — пас вслепую: не глядя в карты, безопаснее всего ничего не обещать."""
    state = _new_state()
    seat, action_type, payload = choose_auto_action(state)
    assert action_type == "bid" and payload["bid"] == 0
    engine.apply_action(state, seat, action_type, payload)
    assert state["round"]["blind_bids"][str(seat)] is True, "авто-ход открыл руку без нужды"


def test_auto_move_bids_one_blind_when_hook_forbids_zero():
    """Крюк запрещает пас — минимальный разрешённый заказ, по-прежнему вслепую."""
    config = dict(BLIND, rounds={"mode": "custom", "sequence": [2]})
    state = _new_state(config, dealer=0)
    engine.apply_action(state, 1, "bid", {"bid": 1})
    engine.apply_action(state, 2, "bid", {"bid": 1})

    seat, _, payload = choose_auto_action(state)
    assert (seat, payload["bid"]) == (0, 1)
    engine.apply_action(state, seat, "bid", payload)
    assert state["round"]["blind_bids"]["0"] is True


def test_auto_move_after_player_opened_hand_is_not_blind():
    """Игрок успел открыться и отошёл — авто-ход не может вернуть «тёмную»."""
    state = _new_state()
    seat = state["round"]["bid_turn"]
    engine.apply_action(state, seat, "open_hand", {})
    s2, action_type, payload = choose_auto_action(state)
    assert s2 == seat
    engine.apply_action(state, s2, action_type, payload)
    assert state["round"]["blind_bids"][str(seat)] is False


def _bid_order(state):
    n = state["n_players"]
    first = state["round"]["first_seat"]
    return [(first + i) % n for i in range(n)]


def _play_out(state):
    """Доиграть текущую раздачу авто-ходом и вернуть её результат."""
    r = state["round"]
    while r["result"] is None:
        seat, action_type, payload = choose_auto_action(state)
        engine.apply_action(state, seat, action_type, payload)
    return r["result"]
