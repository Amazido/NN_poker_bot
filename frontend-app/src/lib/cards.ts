import type { CardCode } from '../types/game';

export type Suit = 'C' | 'D' | 'H' | 'S';

const RANK_DISPLAY: Record<string, string> = { T: '10' };

export interface ParsedCard {
  joker: boolean;
  color?: 'red' | 'black'; // только для джокера
  rank?: string;
  suit?: Suit;
}

export function parseCard(code: CardCode): ParsedCard {
  if (code[0] === 'X') return { joker: true, color: code[1] === 'R' ? 'red' : 'black' };
  return { joker: false, rank: code.slice(0, -1), suit: code.slice(-1) as Suit };
}

export function rankDisplay(rank: string): string {
  return RANK_DISPLAY[rank] ?? rank;
}

export function cardIsRed(code: CardCode): boolean {
  const c = parseCard(code);
  return c.joker ? c.color === 'red' : c.suit === 'D' || c.suit === 'H';
}

/** Масти/джокер построены из circle/rect/polygon — без ручных bezier-путей. */
export function suitInner(suit: Suit, color: string): string {
  if (suit === 'D') return `<rect x="32" y="32" width="36" height="36" fill="${color}" transform="rotate(45 50 50)"/>`;
  if (suit === 'C')
    return `
    <circle cx="50" cy="34" r="18" fill="${color}"/>
    <circle cx="33" cy="58" r="18" fill="${color}"/>
    <circle cx="67" cy="58" r="18" fill="${color}"/>
    <polygon points="44,66 56,66 53,90 47,90" fill="${color}"/>`;
  if (suit === 'H')
    return `
    <circle cx="34" cy="38" r="19" fill="${color}"/>
    <circle cx="66" cy="38" r="19" fill="${color}"/>
    <rect x="31" y="31" width="38" height="38" fill="${color}" transform="rotate(45 50 54)"/>`;
  // 'S'
  return `
    <g transform="rotate(180 50 50)">
      <circle cx="34" cy="38" r="19" fill="${color}"/>
      <circle cx="66" cy="38" r="19" fill="${color}"/>
      <rect x="31" y="31" width="38" height="38" fill="${color}" transform="rotate(45 50 54)"/>
    </g>
    <polygon points="44,66 56,66 53,90 47,90" fill="${color}"/>`;
}

function starPoints(cx: number, cy: number, rOuter: number, rInner: number, n: number): string {
  const pts: string[] = [];
  for (let i = 0; i < n * 2; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const a = (Math.PI / n) * i - Math.PI / 2;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(' ');
}

export function jokerInner(color: string): string {
  return `<polygon points="${starPoints(50, 50, 42, 18, 5)}" fill="${color}"/>`;
}

const SUITS: Suit[] = ['C', 'D', 'H', 'S'];
const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'];

export function buildDeck(): CardCode[] {
  const deck: CardCode[] = [];
  for (const s of SUITS) for (const r of RANKS) deck.push(r + s);
  deck.push('XR', 'XB');
  return deck;
}

/** Обязана масть сброса → иначе козырь → иначе любая; джокеров можно класть всегда. */
export function legalMoves(hand: CardCode[], leadSuit: string | null, trumpSuit: string | null): CardCode[] {
  if (!leadSuit) return hand.slice();
  const jokers = hand.filter((c) => c[0] === 'X');
  const haveLead = hand.filter((c) => c[0] !== 'X' && c.slice(-1) === leadSuit);
  if (haveLead.length) return haveLead.concat(jokers);
  if (trumpSuit) {
    const haveTrump = hand.filter((c) => c[0] !== 'X' && c.slice(-1) === trumpSuit);
    if (haveTrump.length) return haveTrump.concat(jokers);
  }
  return hand.slice();
}
