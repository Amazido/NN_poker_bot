"""Тесты редакции правил: последовательность раундов, счёт, ограничение крюка."""
import pytest

from app.poker.rules import RulesEdition


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


def test_round_sequence_capped_by_deck():
    # Гипотетически 8 игроков: пик 10 невозможен (10*8+1=81 > 54) → усечение.
    rules = RulesEdition()
    seq = rules.round_sequence(8)
    max_cards = (54 - 1) // 8
    assert max(seq) <= max_cards
