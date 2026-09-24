import { buildDeck, legalMoves } from './cards';
import type { CardCode, GameView, Seat } from '../types/game';

const ODESSA_NAMES = ['Аркадий', 'Софа', 'Моня', 'Циля', 'Жора', 'Бэла'];

const FIXTURE_RULES = {
  code: 'odessa_season_1',
  name: 'Сезон 1',
  summary: [
    'Раздачи от 1 до 10 карт',
    'Игроков 3–5',
    'Двойка бьёт туза своей масти',
    'Некозырной джокер бьёт козырного',
    'Можно заказать вслепую: +5 за точный заказ',
    'Очки: +10 за взятку при точном заказе, -5 за перебор, -5 за недобранную',
  ],
  blind_bonus: 5,
};

function shuffled(arr: CardCode[], seed: number): CardCode[] {
  const a = arr.slice();
  let s = seed;
  for (let i = a.length - 1; i > 0; i--) {
    s = (s * 9301 + 49297) % 233280;
    const j = Math.floor((s / 233280) * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export type FixtureScreen = 'waiting' | 'bidding' | 'bidding-blind' | 'playing';

/** Фейковые данные в форме реального GameView — для разработки экранов без бэка (sub-project A). */
export function makeFixture(screenType: FixtureScreen, n: number): GameView {
  const meSeat = n - 1;
  const names = ODESSA_NAMES.slice(0, n);
  const seats: Seat[] = names.map((username, seat) => ({ seat, user_id: `u${seat}`, username, score: ((seat * 7) % 23) - 6 }));
  const deck = shuffled(buildDeck(), 42 + n);
  const cardsCount = Math.min(7, Math.max(3, n + 2));
  const dealerSeat = 0;
  const trumpCard = deck[deck.length - 1];
  const trumpSuit = trumpCard[0] === 'X' ? null : trumpCard.slice(-1);
  const noTrump = trumpCard[0] === 'X';

  const hands: Record<number, CardCode[]> = {};
  let cursor = 0;
  for (let s = 0; s < n; s++) {
    hands[s] = deck.slice(cursor, cursor + cardsCount);
    cursor += cardsCount;
  }
  const handCounts: Record<string, number> = {};
  for (let s = 0; s < n; s++) handCounts[s] = hands[s].length;

  if (screenType === 'waiting') {
    const joined = Math.max(1, n - 1);
    return {
      status: 'lobby',
      room_id: 'r1',
      join_code: '7F3K9Q',
      match_over: false,
      seats: seats.slice(0, joined),
      n_players: joined,
      max_players: n,
      round_index: 0,
      rules: FIXTURE_RULES,
      round: null,
      turn: { kind: null, seat: null },
      left_seats: [],
      turn_deadline: null,
      me: null,
    };
  }

  if (screenType === 'bidding' || screenType === 'bidding-blind') {
    const blind = screenType === 'bidding-blind';
    const bidTurnIdx = meSeat;
    const bids: Record<string, number> = {};
    const blindBids: Record<string, boolean> = {};
    for (let i = 0; i < bidTurnIdx; i++) {
      bids[i] = i % (cardsCount + 1);
      blindBids[i] = blind && i % 2 === 0;
    }
    const myTurn = bidTurnIdx === meSeat;
    const othersSum = Object.values(bids).reduce((a, b) => a + b, 0);
    const isLast = Object.keys(bids).length === n - 1;
    const options = Array.from({ length: cardsCount + 1 }, (_, i) => i);
    let forbidden: number | null = null;
    if (isLast) {
      forbidden = cardsCount - othersSum;
      if (forbidden < 0 || forbidden > cardsCount) forbidden = null;
    }
    return {
      status: 'playing',
      room_id: 'r1',
      match_over: false,
      seats,
      n_players: n,
      round_index: 3,
      rounds_total: 18 + n,
      rules: FIXTURE_RULES,
      round: {
        cards_count: cardsCount,
        dealer_seat: dealerSeat,
        first_seat: (dealerSeat + 1) % n,
        trump_card: trumpCard,
        trump_suit: trumpSuit,
        no_trump: noTrump,
        phase: 'bidding',
        bids,
        bid_turn: bidTurnIdx,
        tricks_won: {},
        trick_number: 1,
        current_trick: null,
        last_trick: null,
        result: null,
        hand_counts: handCounts,
        blind_bids: blindBids,
      },
      turn: { kind: 'bid', seat: bidTurnIdx },
      left_seats: [],
      turn_deadline: null,
      me: {
        room_id: 'r1',
        seat: meSeat,
        hand: blind ? [] : hands[meSeat],
        hand_hidden: blind,
        hand_count: cardsCount,
        can_open_hand: blind,
        your_turn: myTurn,
        available_actions: myTurn
          ? { type: 'bid', options: forbidden === null ? options : options.filter((o) => o !== forbidden) }
          : null,
        round_index: 3,
        phase: 'bidding',
      },
    };
  }

  // playing
  const bids: Record<string, number> = {};
  for (let i = 0; i < n; i++) bids[i] = (i + 2) % (cardsCount + 1);
  const tricksWon: Record<string, number> = {};
  for (let i = 0; i < n; i++) tricksWon[i] = 0;
  const winnerOfLast = (dealerSeat + 1) % n;
  tricksWon[winnerOfLast] = 1;
  const trickTurnStart = winnerOfLast;
  const playsSoFar = Math.min(n - 1, Math.ceil(n / 2));
  const plays = [];
  for (let i = 0; i < playsSoFar; i++) {
    const seat = (trickTurnStart + i) % n;
    plays.push({ seat, card: hands[seat].pop()! });
  }
  for (let s = 0; s < n; s++) handCounts[s] = hands[s].length;
  const currentTurnSeat = (trickTurnStart + playsSoFar) % n;
  const leadSuit = plays.length ? (plays[0].card[0] === 'X' ? null : plays[0].card.slice(-1)) : null;
  const myTurn = currentTurnSeat === meSeat && !plays.some((p) => p.seat === meSeat);

  return {
    status: 'playing',
    room_id: 'r1',
    match_over: false,
    seats,
    n_players: n,
    round_index: 3,
    rounds_total: 18 + n,
    rules: FIXTURE_RULES,
    round: {
      cards_count: cardsCount,
      dealer_seat: dealerSeat,
      first_seat: (dealerSeat + 1) % n,
      trump_card: trumpCard,
      trump_suit: trumpSuit,
      no_trump: noTrump,
      phase: 'playing',
      bids,
      bid_turn: null,
      tricks_won: tricksWon,
      trick_number: 2,
      current_trick: { lead_seat: trickTurnStart, lead_suit: leadSuit, turn: currentTurnSeat, plays },
      last_trick: { plays: [{ seat: dealerSeat, card: 'AS' }], winner: winnerOfLast },
      result: null,
      hand_counts: handCounts,
      blind_bids: {},
    },
    turn: { kind: 'play', seat: currentTurnSeat },
    left_seats: [],
    turn_deadline: null,
    me: {
      room_id: 'r1',
      seat: meSeat,
      hand: hands[meSeat],
      hand_hidden: false,
      hand_count: hands[meSeat].length,
      can_open_hand: false,
      your_turn: myTurn,
      available_actions: myTurn ? { type: 'play', cards: legalMoves(hands[meSeat], leadSuit, trumpSuit) } : null,
      round_index: 3,
      phase: 'playing',
    },
  };
}
