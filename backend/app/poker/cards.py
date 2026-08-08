"""Карты, колода и правила старшинства во взятке (Одесский покер).

Кодировка карты — строка:
  - обычная карта: <ранг><масть>, напр. "AS" (туз пик), "TD" (10 бубён), "2C".
    ранги: 2 3 4 5 6 7 8 9 T J Q K A ; масти: C(♣) D(♦) H(♥) S(♠)
  - джокеры: "XR" (красный джокер), "XB" (чёрный джокер).

Цвета: ♦♥ — красные, ♣♠ — чёрные.

Старшинство во взятке (сверху вниз), КОГДА ЕСТЬ КОЗЫРЬ:
  1. Козырный джокер (цвет совпадает с цветом козыря) — бьёт всё.
  2. Козыри (по рангу).
  3. Некозырной джокер — бьёт все обычные карты любой масти, но проигрывает
     козырю и козырному джокеру («второй сверху»).
  4. Карты масти сброса (по рангу).
  5. Пустышки (прочие масти) — во взятке не участвуют.

БЕЗ КОЗЫРЯ (колоду ведёт джокер): оба джокера бьют любые обычные карты,
старшим считается тот джокер, что был вскрыт ведущим колоду.

Флаги редакции правил:
  offcolor_beats_oncolor  — некозырной джокер берёт козырного (тогда он старший).
  two_beats_ace_same_suit — двойка бьёт туза своей масти, если оба в одном сбросе.
"""
import random
from typing import Dict, List, Optional, Tuple

SUITS = ["C", "D", "H", "S"]
RANK_CODES = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
RANK_VALUE = {code: i for i, code in enumerate(RANK_CODES, start=2)}  # 2..14

RED_SUITS = {"D", "H"}
BLACK_SUITS = {"C", "S"}

JOKER_RED = "XR"
JOKER_BLACK = "XB"
JOKERS = (JOKER_RED, JOKER_BLACK)


def is_joker(card: str) -> bool:
    return card[0] == "X"


def joker_color(card: str) -> str:
    """'red' или 'black' для джокера."""
    return "red" if card[1] == "R" else "black"


def suit_of(card: str) -> Optional[str]:
    """Масть обычной карты; None для джокера."""
    if is_joker(card):
        return None
    return card[-1]


def rank_of(card: str) -> Optional[int]:
    """Числовой ранг обычной карты (2..14); None для джокера."""
    if is_joker(card):
        return None
    return RANK_VALUE[card[:-1]]


def color_of_suit(suit: str) -> str:
    return "red" if suit in RED_SUITS else "black"


def build_deck() -> List[str]:
    """Полная колода 54 карты (52 + 2 джокера)."""
    deck = [f"{r}{s}" for s in SUITS for r in RANK_CODES]
    deck.extend(JOKERS)
    return deck


def deal(
    n_players: int, cards_count: int, rng: Optional[random.Random] = None
) -> Tuple[List[List[str]], str]:
    """Раздать по cards_count карт каждому и вскрыть ведущую колоду карту (козырь).

    Returns:
        (hands, trump_card) — hands[i] рука игрока i, trump_card — вскрытая карта.
    Raises:
        ValueError: если в колоде не хватает карт.
    """
    needed = n_players * cards_count + 1
    deck = build_deck()
    if needed > len(deck):
        raise ValueError(
            f"Deck too small: need {needed} for {n_players}x{cards_count}, have {len(deck)}"
        )
    rng = rng or random.Random()
    rng.shuffle(deck)

    hands: List[List[str]] = [[] for _ in range(n_players)]
    idx = 0
    for _ in range(cards_count):
        for p in range(n_players):
            hands[p].append(deck[idx])
            idx += 1
    trump_card = deck[idx]
    return hands, trump_card


def determine_trump(trump_card: str) -> Tuple[Optional[str], bool]:
    """По вскрытой карте определить козырную масть.

    Returns:
        (trump_suit, no_trump). Если вскрыт джокер — (None, True).
    """
    if is_joker(trump_card):
        return None, True
    return suit_of(trump_card), False


def _effective_rank(card: str, present: List[str], two_beats_ace: bool) -> int:
    """Ранг карты с учётом правила «двойка бьёт туза своей масти в одном сбросе»."""
    r = rank_of(card)
    if r is None:
        return 0
    if two_beats_ace and r == 2:
        ace_same = f"A{suit_of(card)}"
        if ace_same in present:
            return 15  # выше туза
    return r


def _strength(
    card: str,
    *,
    trump_suit: Optional[str],
    lead_suit: Optional[str],
    no_trump_high_joker: Optional[str],
    present: List[str],
    flags: Dict[str, bool],
) -> Tuple[int, int]:
    """Ключ силы карты во взятке: (категория, ранг). Больше — сильнее.

    Категории:
      7 — некозырной джокер при offcolor_beats_oncolor (старший)
      6 — козырный джокер / старший джокер без козыря
      5 — козырь / второй джокер без козыря
      4 — некозырной джокер (обычная редакция)
      3 — масть сброса
      0 — пустышка
    """
    two_beats_ace = flags.get("two_beats_ace_same_suit", False)

    if is_joker(card):
        if trump_suit is not None:
            trump_color = color_of_suit(trump_suit)
            if joker_color(card) == trump_color:
                return (6, 0)  # козырный джокер
            # некозырной джокер
            if flags.get("offcolor_beats_oncolor", False):
                return (7, 0)
            return (4, 0)
        # без козыря
        if card == no_trump_high_joker:
            return (6, 0)
        return (5, 0)

    # обычная карта
    if trump_suit is not None and suit_of(card) == trump_suit:
        return (5, _effective_rank(card, present, two_beats_ace))
    if lead_suit is not None and suit_of(card) == lead_suit:
        return (3, _effective_rank(card, present, two_beats_ace))
    return (0, 0)  # пустышка


def trick_winner(
    plays: List[Tuple[int, str]],
    *,
    trump_suit: Optional[str],
    lead_suit: Optional[str],
    no_trump_high_joker: Optional[str] = None,
    flags: Optional[Dict[str, bool]] = None,
) -> int:
    """Определить место (seat) победителя взятки.

    plays — список (seat, card) в порядке хода. lead_suit — масть сброса
    (масть первой карты; None, если первым вышел джокер → сброс без масти).
    """
    flags = flags or {}
    present = [c for _, c in plays]
    best_seat = plays[0][0]
    best_key = _strength(
        plays[0][1],
        trump_suit=trump_suit,
        lead_suit=lead_suit,
        no_trump_high_joker=no_trump_high_joker,
        present=present,
        flags=flags,
    )
    for seat, card in plays[1:]:
        key = _strength(
            card,
            trump_suit=trump_suit,
            lead_suit=lead_suit,
            no_trump_high_joker=no_trump_high_joker,
            present=present,
            flags=flags,
        )
        if key > best_key:
            best_key = key
            best_seat = seat
    return best_seat


def lead_suit_of_play(card: str) -> Optional[str]:
    """Масть сброса, задаваемая ведущей картой (None, если это джокер)."""
    return None if is_joker(card) else suit_of(card)


def legal_moves(hand: List[str], lead_suit: Optional[str], trump_suit: Optional[str]) -> List[str]:
    """Какие карты игрок вправе положить.

    Правила: обязан класть масть сброса; если её нет — козыря; если нет ни того,
    ни другого — любую карту (пустышка). Джокеров можно класть всегда.
    """
    jokers = [c for c in hand if is_joker(c)]

    if lead_suit is None:
        # Ведущий ход (или сброс без масти) — можно любую карту.
        return list(hand)

    has_lead = any(not is_joker(c) and suit_of(c) == lead_suit for c in hand)
    if has_lead:
        return [c for c in hand if not is_joker(c) and suit_of(c) == lead_suit] + jokers

    if trump_suit is not None:
        has_trump = any(not is_joker(c) and suit_of(c) == trump_suit for c in hand)
        if has_trump:
            return [c for c in hand if not is_joker(c) and suit_of(c) == trump_suit] + jokers

    return list(hand)
