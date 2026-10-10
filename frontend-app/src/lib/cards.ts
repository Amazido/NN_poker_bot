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

/** Цвет масти: ♠ чёрная, ♣ тёмно-зелёная, ♥♦ красные.
 *
 * Трефу от пики отличает не только силуэт: значок в углу карты — 10 пикселей,
 * на телефоне форма там не читается вовсе. Пара «красные/чёрные» при этом
 * сохранена — цвет масти в этой игре правило (некозырной джокер берёт масть
 * сброса своего цвета), и зелёная трефа остаётся чёрной по смыслу.
 */
export function suitColor(suit: Suit): string {
  if (suit === 'D' || suit === 'H') return 'var(--card-red)';
  if (suit === 'C') return 'var(--card-club)';
  return 'var(--card-ink)';
}

/** Чернила карты: масть по `suitColor`, джокер — по своему цвету. */
export function cardColor(code: CardCode): string {
  const c = parseCard(code);
  // Чёрный джокер остаётся чёрным: он не трефа, а зелёный сбил бы с толку там,
  // где цвет джокера решает, берёт он взятку или нет.
  if (c.joker) return c.color === 'red' ? 'var(--card-red)' : 'var(--card-ink)';
  return suitColor(c.suit!);
}

/** Масти/джокер построены из circle/rect/polygon — без ручных bezier-путей. */
export function suitInner(suit: Suit, color: string): string {
  if (suit === 'D') return `<rect x="32" y="32" width="36" height="36" fill="${color}" transform="rotate(45 50 50)"/>`;
  // Трефа: три отдельных лепестка и ножка с раструбом. Лепестки мельче, чем у
  // пики, и заходят друг на друга буквально на пару единиц: от касания впритык
  // по стыку остаётся волосяная щель, а большее перекрытие съедает выемки, по
  // которым трефа и узнаётся.
  if (suit === 'C')
    return `
    <circle cx="50" cy="32" r="17" fill="${color}"/>
    <circle cx="34" cy="56" r="17" fill="${color}"/>
    <circle cx="66" cy="56" r="17" fill="${color}"/>
    <polygon points="45,48 55,48 61,90 39,90" fill="${color}"/>`;
  if (suit === 'H')
    return `
    <circle cx="34" cy="38" r="19" fill="${color}"/>
    <circle cx="66" cy="38" r="19" fill="${color}"/>
    <rect x="31" y="31" width="38" height="38" fill="${color}" transform="rotate(45 50 54)"/>`;
  // Пика: острое остриё сверху и сплошные округлые плечи — противоположность
  // трефе, которую раньше от неё отличала только развеска тех же кругов.
  return `
    <polygon points="50,7 87,47 13,47" fill="${color}"/>
    <circle cx="31" cy="52" r="20" fill="${color}"/>
    <circle cx="69" cy="52" r="20" fill="${color}"/>
    <polygon points="42,56 58,56 66,90 34,90" fill="${color}"/>`;
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
const RANK_VALUE: Record<string, number> = Object.fromEntries(RANKS.map((r, i) => [r, i]));

export function buildDeck(): CardCode[] {
  const deck: CardCode[] = [];
  for (const s of SUITS) for (const r of RANKS) deck.push(r + s);
  deck.push('XR', 'XB');
  return deck;
}

/** Своя масть, козырь первым, по возрастанию ранга; джокеры — в конце. */
export function sortHand(cards: CardCode[], trumpSuit?: string | null): CardCode[] {
  const suitOrder = (s: Suit) => (trumpSuit && s === trumpSuit ? -1 : SUITS.indexOf(s));
  return [...cards].sort((a, b) => {
    const pa = parseCard(a);
    const pb = parseCard(b);
    if (pa.joker || pb.joker) {
      if (pa.joker && pb.joker) return a.localeCompare(b);
      return pa.joker ? 1 : -1;
    }
    const suitDiff = suitOrder(pa.suit!) - suitOrder(pb.suit!);
    if (suitDiff !== 0) return suitDiff;
    return RANK_VALUE[pa.rank!] - RANK_VALUE[pb.rank!];
  });
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
