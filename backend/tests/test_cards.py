"""Тесты колоды и старшинства во взятке."""
from app.poker import cards as C


def test_deck_is_54_unique():
    deck = C.build_deck()
    assert len(deck) == 54
    assert len(set(deck)) == 54
    assert "XR" in deck and "XB" in deck


def test_on_color_joker_beats_everything():
    # Козырь ♠ (чёрный) → чёрный джокер XB старше всего.
    plays = [(0, "AS"), (1, "XB"), (2, "XR")]
    w = C.trick_winner(plays, trump_suit="S", lead_suit="S")
    assert w == 1


def test_off_color_joker_beats_ordinary_but_loses_to_trump():
    # Козырь ♠. Некозырной (красный XR) бьёт масть сброса, но проигрывает козырю.
    # Здесь козыря среди карт нет → XR должен взять.
    plays = [(0, "AH"), (1, "KH"), (2, "XR")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit="H") == 2
    # А тут есть козырь 2S → он бьёт некозырного джокера.
    plays2 = [(0, "XR"), (1, "2S"), (2, "AH")]
    assert C.trick_winner(plays2, trump_suit="S", lead_suit=None) == 1


def test_trump_beats_lead_suit():
    plays = [(0, "AH"), (1, "2S"), (2, "KH")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit="H") == 1


def test_empty_cannot_win():
    # Козырь ♠, сброс ♥. Клуб — пустышка, не берёт даже будучи тузом.
    plays = [(0, "3H"), (1, "AC"), (2, "2H")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit="H") == 0


def test_highest_lead_wins_without_trump_in_trick():
    plays = [(0, "5H"), (1, "KH"), (2, "9H")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit="H") == 1


def test_no_trump_high_joker():
    # Без козыря: старший джокер — тот, что вскрыт (XR). Он бьёт второго джокера.
    plays = [(0, "XB"), (1, "XR"), (2, "AS")]
    w = C.trick_winner(plays, trump_suit=None, lead_suit=None, no_trump_high_joker="XR")
    assert w == 1


def test_legal_moves_must_follow_lead():
    hand = ["AH", "KH", "2S", "XR"]
    legal = C.legal_moves(hand, lead_suit="H", trump_suit="S")
    assert set(legal) == {"AH", "KH", "XR"}  # масть сброса + джокер


def test_legal_moves_must_trump_when_no_lead():
    hand = ["2S", "AC", "XB"]
    legal = C.legal_moves(hand, lead_suit="H", trump_suit="S")
    assert set(legal) == {"2S", "XB"}  # нет ♥ → обязан козырь (+джокер)


def test_legal_moves_any_when_no_lead_no_trump():
    hand = ["AC", "KD"]
    legal = C.legal_moves(hand, lead_suit="H", trump_suit="S")
    assert set(legal) == {"AC", "KD"}  # нет ни ♥, ни козыря → любая


def test_two_beats_ace_same_suit_flag():
    plays = [(0, "AH"), (1, "2H")]
    # По умолчанию туз старше двойки.
    assert C.trick_winner(plays, trump_suit="S", lead_suit="H") == 0
    # С флагом двойка бьёт туза своей масти.
    assert C.trick_winner(
        plays, trump_suit="S", lead_suit="H", flags={"two_beats_ace_same_suit": True}
    ) == 1


def test_offcolor_joker_is_dummy_vs_foreign_color_lead():
    # Козырь ♠ (чёрный). Масть сброса ♣ (чёрная, не козырь) — чужой цвет для
    # красного джокера → XR пустышка, берёт старшая ♣.
    plays = [(0, "KC"), (1, "XR"), (2, "2C")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit="C") == 0


def test_offcolor_joker_takes_lead_of_own_color():
    # Козырь ♣ (чёрный). Масть сброса ♦ (красная) = цвет XR → джокер берёт,
    # даже если есть более старшая чужая пустышка ♠.
    plays = [(0, "AD"), (1, "XR"), (2, "KS")]
    assert C.trick_winner(plays, trump_suit="C", lead_suit="D") == 1


def test_offcolor_joker_leads_and_wins_without_trump_in_trick():
    # Козырь ♠. XR ведёт (масть сброса не задана). Козырей во взятке нет →
    # джокер берёт независимо от цвета остальных карт.
    plays = [(0, "XR"), (1, "AH"), (2, "KD")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit=None) == 0


def test_trump_beats_offcolor_joker_leading():
    # Козырь ♠. XR ведёт, но кто-то кладёт козырь → козырь берёт.
    plays = [(0, "XR"), (1, "AH"), (2, "2S")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit=None) == 2


def test_oncolor_joker_beats_offcolor_joker_by_default():
    # Козырь ♠ (чёрный): XB (козырный) старше XR (некозырного).
    plays = [(0, "XB"), (1, "XR")]
    assert C.trick_winner(plays, trump_suit="S", lead_suit=None) == 0


def test_offcolor_beats_oncolor_flag():
    # Редакция «некозырной джокер берёт козырного»: XR становится старшим.
    plays = [(0, "XB"), (1, "XR")]
    assert C.trick_winner(
        plays, trump_suit="S", lead_suit=None, flags={"offcolor_beats_oncolor": True}
    ) == 1
