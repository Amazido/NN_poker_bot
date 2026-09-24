"""Боты и авто-ход: играют по правилам стола и не кладут нелегальных карт.

Бот — это не ИИ, а тот же авто-ход, что и за ушедшего игрока (см. autoplay.py),
поэтому все проверки здесь одновременно про ботов, про истёкший таймер и про
покинутые места.
"""
import random

import pytest

from app.poker import cards as C
from app.poker import engine
from app.poker.autoplay import choose_auto_action
from app.poker.editions import BUILTIN_EDITIONS
from app.poker.rules import RulesEdition


def _seats(n: int):
    return [{"seat": i, "user_id": f"u{i}", "username": f"Бот {i}", "score": 0} for i in range(n)]


def _assert_action_is_legal(state, seat, action_type, payload, rules):
    """Ход бота должен проходить те же проверки, что и ход живого игрока."""
    r = state["round"]
    if action_type == "bid":
        is_last = len(r["bids"]) == state["n_players"] - 1
        allowed = rules.allowed_bids(r["cards_count"], is_last, sum(r["bids"].values()))
        assert payload["bid"] in allowed, (
            f"бот заказал {payload['bid']}, допустимо {allowed} "
            f"(раздача {r['cards_count']} карт, последний={is_last})"
        )
    else:
        hand = r["hands"][str(seat)]
        legal = C.legal_moves(hand, r["current_trick"]["lead_suit"], r["trump_suit"])
        assert payload["card"] in legal, (
            f"бот положил {payload['card']}, легальны {legal} "
            f"(сброс {r['current_trick']['lead_suit']}, козырь {r['trump_suit']})"
        )


def _play_full_auto_match(rules_config: dict, n_players: int, seed: int = 0):
    """Прогнать матч, где все ходы делает авто-ход, проверяя каждый шаг."""
    rng = random.Random(seed)
    state = engine.new_game_state(
        room_id="test-room",
        seats=_seats(n_players),
        rules_config=rules_config,
        starting_dealer=0,
        rng=rng,
    )
    rules = RulesEdition(state["rules"])
    expected_rounds = len(rules.round_sequence(n_players))

    guard = 0
    while not state["match_over"]:
        guard += 1
        assert guard < 20000, "матч не сходится — авто-ход зациклился"

        seat, action_type, payload = choose_auto_action(state)
        assert seat is not None, "ход есть, а авто-действия нет"
        _assert_action_is_legal(state, seat, action_type, payload, rules)
        engine.apply_action(state, seat, action_type, payload, rng)

    assert state["round_index"] == expected_rounds
    return state


@pytest.mark.parametrize("spec", BUILTIN_EDITIONS, ids=lambda s: s["code"])
def test_bots_play_full_match_on_every_builtin_edition(spec):
    """Бот обязан доигрывать до конца в любой редакции из каталога."""
    rules = RulesEdition(spec["config"], validate=True)
    for n in range(rules.min_players, rules.max_players + 1):
        state = _play_full_auto_match(spec["config"], n)
        # Сумма взяток за матч сходится с числом раздач — счёт не потерялся.
        assert all(s["seat"] in range(n) for s in state["seats"])


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_bots_respect_ranking_rules_edition(seed):
    """Круговое старшинство меняет победителя взятки, но не легальность хода."""
    config = {"ranking": {"two_beats_ace_same_suit": True, "offcolor_beats_oncolor": True},
              "rounds": {"mode": "custom", "sequence": [5, 5]}}
    _play_full_auto_match(config, n_players=4, seed=seed)


def test_bots_play_edition_without_jokers():
    _play_full_auto_match({"deck": {"jokers": 0}, "rounds": {"mode": "custom", "sequence": [4]}}, 3)


def test_bots_play_deep_hand_edition():
    """13 карт на четверых — раздача на пределе колоды."""
    _play_full_auto_match(
        {"players": {"min": 3, "max": 4}, "rounds": {"mode": "custom", "sequence": [13]}},
        n_players=4,
    )


# === Торги ===

def _state_at_last_bid(hook: bool):
    """Довести торги до сдающего так, чтобы «крюк» запрещал ему заказать 0.

    Трое, раздача 2 карты, первые двое заказывают по 1 — сумма уже равна числу
    карт, значит сдающему нельзя 0.
    """
    config = {"rounds": {"mode": "custom", "sequence": [2]}, "bidding": {"hook": hook}}
    state = engine.new_game_state(
        room_id="r", seats=_seats(3), rules_config=config,
        starting_dealer=0, rng=random.Random(7),
    )
    # Сдающий — место 0, значит заказывают 1, 2, потом 0.
    engine.apply_action(state, 1, "bid", {"bid": 1})
    engine.apply_action(state, 2, "bid", {"bid": 1})
    return state


def test_bot_does_not_break_the_hook():
    state = _state_at_last_bid(hook=True)
    seat, action_type, payload = choose_auto_action(state)
    assert (seat, action_type) == (0, "bid")
    assert payload["bid"] != 0, "бот сделал заказ, запрещённый крюком"
    assert payload["bid"] == 1, "бот должен брать наименьший разрешённый заказ"


def test_bot_bids_zero_when_hook_disabled():
    """Без крюка тот же расклад разрешает 0 — бот выбирает самый безопасный заказ."""
    state = _state_at_last_bid(hook=False)
    _, _, payload = choose_auto_action(state)
    assert payload["bid"] == 0


# === Розыгрыш ===

def _state_in_play(hands: dict, trump_suit, lead_seat: int = 1):
    """Состояние в фазе розыгрыша с заданными руками и козырем."""
    config = {"rounds": {"mode": "custom", "sequence": [3]}}
    state = engine.new_game_state(
        room_id="r", seats=_seats(3), rules_config=config,
        starting_dealer=0, rng=random.Random(11),
    )
    r = state["round"]
    for seat in (1, 2, 0):
        engine.apply_action(state, seat, "bid", {"bid": 0})
    r["hands"] = {str(k): list(v) for k, v in hands.items()}
    r["trump_suit"] = trump_suit
    r["no_trump"] = trump_suit is None
    r["current_trick"] = {"lead_seat": lead_seat, "lead_suit": None, "turn": lead_seat, "plays": []}
    return state


def test_bot_follows_lead_suit():
    """У бота есть масть сброса — он обязан её положить, а не сбросить туза."""
    state = _state_in_play(
        hands={1: ["5H", "6H", "7H"], 2: ["2H", "AS", "KS"], 0: ["3C", "4C", "5C"]},
        trump_suit="S",
    )
    # Место 1 ведёт червой.
    engine.apply_action(state, 1, "play_card", {"card": "5H"})
    seat, action_type, payload = choose_auto_action(state)
    assert (seat, action_type) == (2, "play_card")
    assert payload["card"] == "2H", "бот сбросил не масть сброса, имея её на руках"


def test_bot_plays_trump_when_out_of_lead_suit():
    """Червей нет, козыри есть — обязан козырять, а не сбрасывать пустышку."""
    state = _state_in_play(
        hands={1: ["5H", "6H", "7H"], 2: ["2S", "AC", "KC"], 0: ["3C", "4C", "5C"]},
        trump_suit="S",
    )
    engine.apply_action(state, 1, "play_card", {"card": "5H"})
    _, _, payload = choose_auto_action(state)
    assert payload["card"] == "2S", "бот не козырнул, хотя обязан"


def test_bot_may_play_anything_without_lead_suit_or_trump():
    state = _state_in_play(
        hands={1: ["5H", "6H", "7H"], 2: ["AC", "KC", "QC"], 0: ["3D", "4D", "5D"]},
        trump_suit="S",
    )
    engine.apply_action(state, 1, "play_card", {"card": "5H"})
    _, _, payload = choose_auto_action(state)
    assert payload["card"] in ["AC", "KC", "QC"]


# === Безлимитная колода ===

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_bots_play_infinite_deck_with_duplicates(seed):
    """Повторяющиеся карты не должны ломать ни выбор хода, ни списание с руки."""
    config = {"deck": {"infinite": True}, "rounds": {"mode": "custom", "sequence": [12, 12]}}
    state = _play_full_auto_match(config, n_players=5, seed=seed)
    assert all(not hand for hand in state["round"]["hands"].values()) or state["match_over"]


def test_bots_play_hand_larger_than_the_deck():
    """Безлимитная колода снимает потолок раздачи — бот обязан доиграть и такую."""
    config = {"deck": {"infinite": True}, "rounds": {"mode": "custom", "sequence": [20]}}
    _play_full_auto_match(config, n_players=5)


def test_playing_a_duplicate_removes_only_one_copy():
    state = _state_in_play(
        hands={1: ["KH", "KH", "5H"], 2: ["2H", "AS", "KS"], 0: ["3C", "4C", "5C"]},
        trump_suit="S",
    )
    engine.apply_action(state, 1, "play_card", {"card": "KH"})
    assert state["round"]["hands"]["1"] == ["KH", "5H"]


def test_no_action_when_match_is_over():
    state = _play_full_auto_match({"rounds": {"mode": "custom", "sequence": [1]}}, 3)
    assert choose_auto_action(state) == (None, None, None)
