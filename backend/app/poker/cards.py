"""Карты, колода и правила старшинства во взятке (Одесский покер).

Кодировка карты — строка:
  - обычная карта: <ранг><масть>, напр. "AS" (туз пик), "TD" (10 бубён), "2C".
    ранги: 2 3 4 5 6 7 8 9 T J Q K A ; масти: C(♣) D(♦) H(♥) S(♠)
  - джокеры: "XR" (красный джокер), "XB" (чёрный джокер).

Цвета: ♦♥ — красные, ♣♠ — чёрные.

Старшинство во взятке (сверху вниз), КОГДА ЕСТЬ КОЗЫРЬ:
  1. Козырный джокер (цвет совпадает с цветом козыря) — бьёт всё.
  2. Козыри (по рангу).
  3. Некозырной джокер берёт масть сброса ТОЛЬКО если её цвет совпадает с цветом
     джокера; против карт чужого цвета он ведёт себя как пустышка (тогда берёт
     старшая карта масти сброса). Если некозырной джокер ведёт взятку (масть
     сброса не задана) — берёт её, но проигрывает любому козырю.
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

    Некозырной джокер контекстно-зависим (берёт только карты своего цвета),
    поэтому победитель считается по явному порядку приоритетов, а не через
    независимый скаляр силы каждой карты.
    """
    flags = flags or {}
    present = [c for _, c in plays]
    two_beats_ace = flags.get("two_beats_ace_same_suit", False)

    def erank(card: str) -> int:
        return _effective_rank(card, present, two_beats_ace)

    def best_of_suit(suit: str) -> Optional[int]:
        cand = [(s, c) for s, c in plays if not is_joker(c) and suit_of(c) == suit]
        if not cand:
            return None
        return max(cand, key=lambda sc: erank(sc[1]))[0]

    # === БЕЗ КОЗЫРЯ (колоду ведёт джокер) ===
    if trump_suit is None:
        jokers = [(s, c) for s, c in plays if is_joker(c)]
        if jokers:
            for s, c in jokers:
                if c == no_trump_high_joker:
                    return s
            return jokers[0][0]
        if lead_suit is not None:
            w = best_of_suit(lead_suit)
            if w is not None:
                return w
        return plays[0][0]

    # === ЕСТЬ КОЗЫРЬ ===
    trump_color = color_of_suit(trump_suit)
    offcolor_beats = flags.get("offcolor_beats_oncolor", False)
    oncolor_joker = next(
        ((s, c) for s, c in plays if is_joker(c) and joker_color(c) == trump_color), None
    )
    offcolor_joker = next(
        ((s, c) for s, c in plays if is_joker(c) and joker_color(c) != trump_color), None
    )

    # 1. Джокеры высшего порядка.
    if offcolor_beats and offcolor_joker is not None:
        return offcolor_joker[0]  # редакция: некозырной джокер бьёт козырного
    if oncolor_joker is not None:
        return oncolor_joker[0]

    # 2. Козыри.
    w_trump = best_of_suit(trump_suit)
    if w_trump is not None:
        return w_trump

    # 3. Нет козырей и козырного джокера. Некозырной джокер — только свой цвет.
    if lead_suit is not None:
        if offcolor_joker is not None and joker_color(offcolor_joker[1]) == color_of_suit(lead_suit):
            return offcolor_joker[0]  # джокер бьёт масть сброса своего цвета
        w_lead = best_of_suit(lead_suit)
        if w_lead is not None:
            return w_lead  # масть сброса чужого цвета → джокер пустышка
        if offcolor_joker is not None:
            return offcolor_joker[0]
        return plays[0][0]

    # Некозырной джокер ведёт взятку (масть сброса не задана): козыри уже
    # обработаны выше, значит джокер берёт.
    if offcolor_joker is not None:
        return offcolor_joker[0]
    return plays[0][0]


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
