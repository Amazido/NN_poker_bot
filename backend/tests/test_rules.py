"""Тесты редакции правил: последовательность раздач, счёт, крюк, схема конфига."""
import pytest

from app.poker import cards as C
from app.poker.editions import BUILTIN_EDITIONS
from app.poker.rules import SCHEMA_VERSION, RulesConfigError, RulesEdition


def test_round_sequence_length_18_plus_n():
    rules = RulesEdition()
    for n in (3, 4, 5):
        seq = rules.round_sequence(n)
        assert len(seq) == 18 + n
        # 1..9, затем 10 повторяется n раз, затем 9..1
        assert seq[:9] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert seq[9:9 + n] == [10] * n
        assert seq[9 + n:] == [9, 8, 7, 6, 5, 4, 3, 2, 1]


def test_scoring_exact():
    rules = RulesEdition()
    assert rules.score(bid=3, tricks_won=3) == 30
    assert rules.score(bid=1, tricks_won=1) == 10


def test_scoring_zero_exact_bonus():
    rules = RulesEdition()
    assert rules.score(bid=0, tricks_won=0) == 10  # фикс +10


def test_scoring_over_is_flat():
    rules = RulesEdition()
    assert rules.score(bid=1, tricks_won=3) == -5
    assert rules.score(bid=0, tricks_won=2) == -5


def test_scoring_under_per_trick():
    rules = RulesEdition()
    assert rules.score(bid=3, tricks_won=1) == -20  # -10 * 2
    assert rules.score(bid=2, tricks_won=0) == -20


def test_forbidden_last_bid():
    rules = RulesEdition()
    # 3 карты, другие заказали суммарно 1 → последний не может заказать 2 (сумма=3).
    assert rules.forbidden_last_bid(cards_count=3, others_bid_sum=1) == 2
    allowed = rules.allowed_bids(cards_count=3, is_last_bidder=True, others_bid_sum=1)
    assert 2 not in allowed
    assert set(allowed) == {0, 1, 3}


def test_allowed_bids_non_last_has_no_restriction():
    rules = RulesEdition()
    allowed = rules.allowed_bids(cards_count=3, is_last_bidder=False, others_bid_sum=1)
    assert set(allowed) == {0, 1, 2, 3}


def test_round_sequence_raises_when_deck_too_small():
    # 8 игроков по 10 карт — это 81 карта при колоде в 54. Раньше молча урезалось
    # до 6 карт, то есть игра шла не по тем правилам, что заказали.
    rules = RulesEdition()
    with pytest.raises(RulesConfigError, match="не влезает"):
        rules.round_sequence(8)


def test_round_sequence_respects_start():
    rules = RulesEdition({"rounds": {"start": 5, "peak": 8}})
    seq = rules.round_sequence(4)
    assert seq == [5, 6, 7] + [8] * 4 + [7, 6, 5]


def test_round_sequence_custom_mode():
    rules = RulesEdition({"rounds": {"mode": "custom", "sequence": [3, 5, 3]}})
    assert rules.round_sequence(4) == [3, 5, 3]


# === Схема и валидация ===

def test_legacy_v1_config_upgraded():
    """Редакции схемы v1 лежат в БД, снапшоты идущих матчей — в Redis."""
    v1 = {
        "deck": {"cards": 54, "jokers": 2},
        "jokers": {"two_beats_ace_same_suit": True, "offcolor_beats_oncolor": True},
        "rounds": {"mode": "up_plateau_down", "peak": 10},
    }
    rules = RulesEdition(v1)
    assert rules.config["schema_version"] == SCHEMA_VERSION
    assert rules.ranking["two_beats_ace_same_suit"] is True
    assert rules.ranking["offcolor_beats_oncolor"] is True
    assert "cards" not in rules.config["deck"]
    rules.validate()  # поднятый конфиг обязан быть валидным


def test_validate_rejects_unknown_key():
    with pytest.raises(RulesConfigError, match="неизвестные ключи"):
        RulesEdition({"scoring": {"exact_per_trik": 10}}, validate=True)


def test_validate_rejects_hand_that_does_not_fit():
    # Пятеро по 13 карт — 66 карт при колоде 54.
    with pytest.raises(RulesConfigError, match="не влезает"):
        RulesEdition({"rounds": {"peak": 13}, "players": {"min": 3, "max": 5}}, validate=True)


def test_validate_accepts_big_hand_for_fewer_players():
    # Те же 13 карт, но максимум четверо: 13*4+1 = 53 <= 54.
    RulesEdition({"rounds": {"peak": 13}, "players": {"min": 3, "max": 4}}, validate=True)


def test_deck_without_jokers():
    rules = RulesEdition({"deck": {"jokers": 0}}, validate=True)
    assert rules.deck_size == 52
    assert len(C.build_deck(rules.jokers_count)) == 52


def test_hook_can_be_disabled():
    rules = RulesEdition({"bidding": {"hook": False}})
    assert rules.forbidden_last_bid(cards_count=3, others_bid_sum=1) is None
    assert set(rules.allowed_bids(3, is_last_bidder=True, others_bid_sum=1)) == {0, 1, 2, 3}


def test_scoring_is_configurable():
    rules = RulesEdition({"scoring": {"under_per_trick": -5}})
    assert rules.score(bid=3, tricks_won=1) == -10  # -5 * 2


# === Встроенный каталог ===

@pytest.mark.parametrize("spec", BUILTIN_EDITIONS, ids=lambda s: s["code"])
def test_builtin_edition_is_playable(spec):
    """Редакция из каталога должна играться при любом допустимом числе игроков.

    Самую большую раздачу реально раздаём: проверка длины последовательности
    не поймает нехватку карт, а `deal` — поймает.
    """
    rules = RulesEdition(spec["config"], validate=True)
    for n in range(rules.min_players, rules.max_players + 1):
        seq = rules.round_sequence(n)
        assert seq
        hands, trump = C.deal(n, max(seq), jokers=rules.jokers_count)
        assert len(hands) == n
        assert all(len(h) == max(seq) for h in hands)
        assert trump


def test_builtin_edition_codes_are_unique():
    codes = [s["code"] for s in BUILTIN_EDITIONS]
    assert len(codes) == len(set(codes))


def test_summary_mentions_enabled_ranking_rules():
    rules = RulesEdition({"ranking": {"two_beats_ace_same_suit": True}})
    assert any("Двойка бьёт туза" in line for line in rules.summary())
    assert not any("джокер" in line for line in rules.summary())
