"""Тесты рейтинга сезона: шкала прибавок, места по счёту, отбор зачётных матчей."""
from app.poker import rating as R


# === Шкала прибавок ===

def test_scale_matches_the_agreed_numbers():
    """Договорённая шкала первого касания."""
    assert R.rating_deltas(3) == [1, 0, -1]
    assert R.rating_deltas(4) == [2, 1, -1, -2]
    assert R.rating_deltas(5) == [2, 1, 0, -1, -2]


def test_scale_is_zero_sum_and_symmetric():
    """Сколько рейтинга наверху прибыло, столько внизу убыло."""
    for n in range(1, 9):
        deltas = R.rating_deltas(n)
        assert len(deltas) == n
        assert sum(deltas) == 0
        assert deltas == sorted(deltas, reverse=True), "шкала должна убывать от первого места"
        assert deltas == [-d for d in reversed(deltas)]


def test_even_tables_have_no_zero_in_the_scale():
    """При чётном числе игроков стол делится пополам, «ничьей» в шкале нет."""
    for n in (2, 4, 6, 8):
        assert 0 not in R.rating_deltas(n)


def test_odd_tables_have_exactly_one_zero():
    for n in (3, 5, 7):
        assert R.rating_deltas(n).count(0) == 1


def test_delta_for_place():
    assert R.delta_for_place(1, 5) == 2
    assert R.delta_for_place(3, 5) == 0
    assert R.delta_for_place(5, 5) == -2
    assert R.delta_for_place(1, 4) == 2
    assert R.delta_for_place(3, 4) == -1


# === Места по счёту ===

def test_places_by_score():
    places = R.places_by_score({0: 120, 1: 75, 2: -10, 3: 200})
    assert places == {3: 1, 0: 2, 1: 3, 2: 4}


def test_equal_scores_share_the_place():
    """Равный счёт — равное место, следующее место пропускается (1, 2, 2, 4)."""
    places = R.places_by_score({0: 100, 1: 100, 2: 50, 3: 10})
    assert places == {0: 1, 1: 1, 2: 3, 3: 4}


def test_all_equal_scores_are_all_first():
    places = R.places_by_score({0: 0, 1: 0, 2: 0})
    assert places == {0: 1, 1: 1, 2: 1}


def test_negative_scores_are_ordered_normally():
    """Счёт матча бывает отрицательным — на местах это не должно сказываться."""
    places = R.places_by_score({0: -50, 1: -10, 2: -200})
    assert places == {1: 1, 0: 2, 2: 3}


def test_shared_place_shares_the_delta():
    """Поделившие место делят прибавки за занятые позиции шкалы."""
    places = R.places_by_score({0: 100, 1: 100, 2: 50})
    # Двое заняли позиции (+1, 0) → по нулю каждому, третий получает −1.
    assert R.deltas_by_seat(places, 3) == {0: 0, 1: 0, 2: -1}


def test_full_draw_gives_nobody_anything():
    """Ничья всем столом не должна печатать рейтинг из ничего."""
    places = R.places_by_score({0: 0, 1: 0, 2: 0})
    assert R.deltas_by_seat(places, 3) == {0: 0, 1: 0, 2: 0}


def test_deltas_without_ties_follow_the_scale():
    places = R.places_by_score({0: 50, 1: 100, 2: 10, 3: 70})
    assert R.deltas_by_seat(places, 4) == {1: 2, 3: 1, 0: -1, 2: -2}
    assert sum(R.deltas_by_seat(places, 4).values()) == 0


def test_ties_never_inflate_the_table():
    """Округление вниз: при ничьей сумма по столу не бывает больше нуля."""
    cases = [
        {0: 10, 1: 10, 2: 5, 3: 0},
        {0: 10, 1: 10, 2: 10, 3: 0},
        {0: 10, 1: 5, 2: 5, 3: 5},
        {0: 7, 1: 7, 2: 7, 3: 7},
    ]
    for scores in cases:
        places = R.places_by_score(scores)
        assert sum(R.deltas_by_seat(places, len(scores)).values()) <= 0, scores


def test_shared_place_keeps_the_old_scale_untouched():
    """`delta_for_place` остаётся шкалой «место → прибавка», без учёта ничьих."""
    scores = {0: 100, 1: 100, 2: 50}
    places = R.places_by_score(scores)
    total = sum(R.delta_for_place(places[seat], 3) for seat in scores)
    assert total == 1  # +1, +1, -1 вместо нуля


# === Отбор зачётных матчей ===

def _elig(**kw):
    base = dict(
        season_edition_id="season-edition",
        room_edition_id="season-edition",
        human_players=3,
        bot_players=0,
    )
    base.update(kw)
    return R.eligibility(**base)


def test_season_table_with_three_humans_is_rated():
    assert _elig() == R.Eligibility(True, None)


def test_no_active_season_means_unrated():
    e = _elig(season_edition_id=None)
    assert not e.rated and e.reason == R.UnratedReason.NO_SEASON


def test_house_rules_table_is_unrated():
    """Стол со своими правилами (у комнаты нет редакции) в зачёт не идёт."""
    e = _elig(room_edition_id=None)
    assert not e.rated and e.reason == R.UnratedReason.HOUSE_RULES


def test_other_edition_is_unrated():
    e = _elig(room_edition_id="odessa-classic")
    assert not e.rated and e.reason == R.UnratedReason.HOUSE_RULES


def test_single_bot_makes_the_whole_match_unrated():
    e = _elig(human_players=4, bot_players=1)
    assert not e.rated and e.reason == R.UnratedReason.BOTS


def test_two_humans_are_not_enough():
    e = _elig(human_players=2)
    assert not e.rated and e.reason == R.UnratedReason.TOO_FEW_PLAYERS


def test_reason_reported_is_the_most_general_one():
    """Причин может быть несколько — объясняем самую общую."""
    e = _elig(season_edition_id=None, room_edition_id=None, human_players=1, bot_players=2)
    assert e.reason == R.UnratedReason.NO_SEASON
    e2 = _elig(room_edition_id=None, human_players=1, bot_players=2)
    assert e2.reason == R.UnratedReason.HOUSE_RULES
