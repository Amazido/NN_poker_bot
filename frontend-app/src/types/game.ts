export type CardCode = string; // "AS", "TD", "XR" (красный джокер), "XB" (чёрный)

export interface Seat {
  seat: number;
  user_id: string;
  username: string;
  score: number;
  is_bot?: boolean;
}

export interface TrickPlay {
  seat: number;
  card: CardCode;
}

export interface CurrentTrick {
  lead_seat: number;
  lead_suit: string | null;
  turn: number;
  plays: TrickPlay[];
}

export interface LastTrick {
  plays: TrickPlay[];
  winner: number;
}

export interface RoundResult {
  bid: number;
  won: number;
  delta: number;
  total: number;
}

export interface RoundPublic {
  cards_count: number;
  dealer_seat: number;
  first_seat: number;
  trump_card: CardCode;
  trump_suit: string | null; // null если no_trump
  no_trump: boolean;
  phase: 'bidding' | 'playing' | 'scoring' | 'finished';
  bids: Record<string, number>; // ключ — seat как строка
  bid_turn: number | null;
  tricks_won: Record<string, number>;
  trick_number: number;
  current_trick: CurrentTrick | null;
  last_trick: LastTrick | null;
  result: Record<string, RoundResult> | null;
  hand_counts: Record<string, number>; // чужие руки — только количество карт
}

export interface PublicView {
  room_id: string;
  status: 'lobby' | 'playing' | 'finished';
  match_over: boolean;
  seats: Seat[];
  n_players: number;
  max_players?: number; // только в lobby-ветке
  join_code?: string; // только в lobby-ветке
  round_index: number;
  rounds_total?: number;
  round: RoundPublic | null;
  turn: { kind: 'bid' | 'play' | null; seat: number | null };
  /** Места, чей игрок вышел посреди матча — за них доигрывает авто-ход. */
  left_seats: number[];
}

export type AvailableActions =
  | { type: 'bid'; options: number[] }
  | { type: 'play'; cards: CardCode[] };

export interface PrivateView {
  seat: number;
  hand: CardCode[];
  your_turn: boolean;
  available_actions: AvailableActions | null;
}

// Результат мёржа GET /rooms/{id} + GET /rooms/{id}/hand на фронте.
export interface GameView extends PublicView {
  me: PrivateView | null;
}
