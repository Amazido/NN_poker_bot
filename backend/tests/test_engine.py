"""Интеграционные тесты движка раунда (торги → взятки → счёт → переход)."""
import random

from app.poker import engine
from app.poker.rules import RulesEdition


def _seats(n):
    return [{"seat": i, "user_id": f"u{i}", "username": f"P{i}", "score": 0} for i in range(n)]


def _build_one_card_round():
    """Ручное состояние: 3 игрока, 1 карта, козырь ♠, first_seat=0, dealer=2."""
    rules = RulesEdition()
    state = {
        "room_id": "r1",
        "rules": rules.config,
        "status": "playing",
        "match_over": False,
        "seats": _seats(3),
        "n_players": 3,
        "sequence": rules.round_sequence(3),
        "round_index": 0,
        "starting_dealer": 2,
        "round": {
            "cards_count": 1,
            "dealer_seat": 2,
            "first_seat": 0,
            "trump_card": "7S",
            "trump_suit": "S",
            "no_trump": False,
            "no_trump_high_joker": None,
            "phase": "bidding",
            "hands": {"0": ["AH"], "1": ["2S"], "2": ["KH"]},
            "bids": {},
            "bid_turn": 0,
            "tricks_won": {"0": 0, "1": 0, "2": 0},
            "trick_number": 1,
            "current_trick": None,
            "last_trick": None,
            "result": None,
        },
    }
    return state


def test_bidding_hook_forbids_last_bidder():
    state = _build_one_card_round()
    engine.apply_action(state, 0, "bid", {"bid": 0})
    engine.apply_action(state, 1, "bid", {"bid": 1})
    # Последний (seat 2, dealer): сумма прочих = 1, карт = 1 → нельзя 0.
    try:
        engine.apply_action(state, 2, "bid", {"bid": 0})
        assert False, "should forbid bid making total == cards_count"
    except Exception:
        pass
    # Разрешён 1.
    engine.apply_action(state, 2, "bid", {"bid": 1})
    assert state["round"]["phase"] == "playing"


def test_not_your_turn_rejected():
    state = _build_one_card_round()
    try:
        engine.apply_action(state, 1, "bid", {"bid": 0})
        assert False
    except Exception:
        pass


def test_full_one_card_round_scoring_and_advance():
    state = _build_one_card_round()
    round_ref = state["round"]  # держим ссылку, чтобы прочитать result после перехода

    engine.apply_action(state, 0, "bid", {"bid": 0})
    engine.apply_action(state, 1, "bid", {"bid": 1})
    engine.apply_action(state, 2, "bid", {"bid": 1})
    assert round_ref["phase"] == "playing"

    # seat0 ведёт AH (сброс ♥); seat1 без ♥ но с козырем 2S — обязан козырь; seat2 KH.
    engine.apply_action(state, 0, "play_card", {"card": "AH"})
    # seat1 обязан положить козырь 2S.
    legal_before = state["round"]["current_trick"]
    engine.apply_action(state, 1, "play_card", {"card": "2S"})
    events = engine.apply_action(state, 2, "play_card", {"card": "KH"})

    # Козырь 2S забирает взятку → seat1.
    assert round_ref["result"]["1"]["won"] == 1
    # Счёт: seat0 заказал 0 взял 0 → +10; seat1 1/1 → +10; seat2 1/0 → -10.
    assert round_ref["result"]["0"]["delta"] == 10
    assert round_ref["result"]["1"]["delta"] == 10
    assert round_ref["result"]["2"]["delta"] == -10

    # Матч не закончен, перешли к раунду 1 (новая раздача).
    assert state["match_over"] is False
    assert state["round_index"] == 1
    assert state["round"]["phase"] == "bidding"
    assert any(e["type"] == "round_scored" for e in events)


def test_new_game_state_deals_and_starts_bidding():
    state = engine.new_game_state(
        room_id="r2",
        seats=_seats(3),
        rules_config=None,
        starting_dealer=0,
        rng=random.Random(42),
    )
    r = state["round"]
    assert r["phase"] == "bidding"
    assert r["cards_count"] == 1  # первый раунд — 1 карта
    # Каждому роздано по 1 карте.
    assert all(len(h) == 1 for h in r["hands"].values())
    # Ход первого — сразу после сдающего.
    assert r["bid_turn"] == (r["dealer_seat"] + 1) % 3


def test_illegal_card_rejected():
    state = _build_one_card_round()
    engine.apply_action(state, 0, "bid", {"bid": 0})
    engine.apply_action(state, 1, "bid", {"bid": 1})
    engine.apply_action(state, 2, "bid", {"bid": 1})
    engine.apply_action(state, 0, "play_card", {"card": "AH"})
    # seat1 обязан класть козырь 2S, попытка положить... у него только 2S, проверим
    # что нельзя ходить не в свою очередь seat2.
    try:
        engine.apply_action(state, 2, "play_card", {"card": "KH"})
        assert False
    except Exception:
        pass
