import type { CardCode } from '../types/game';
import { STAGE_W } from '../lib/layout';
import { Card } from './Card';
import styles from './Hand.module.css';

const CARD_W = 56;
const TRAY_INNER = STAGE_W - 32;

function overlapPx(count: number): number {
  if (count <= 1) return 0;
  const needed = CARD_W * count - TRAY_INNER;
  return Math.max(12, needed / (count - 1));
}

export interface HandProps {
  cards: CardCode[];
  legal?: Set<CardCode> | null;
  onPlay?: (code: CardCode) => void;
  /** Изменение счёта за только что законченную раздачу — показать пару секунд. */
  scoreDelta?: number | null;
}

export function Hand({ cards, legal, onPlay, scoreDelta }: HandProps) {
  const overlap = overlapPx(cards.length);
  return (
    <div className={styles.tray}>
      {scoreDelta != null && (
        <span className={`${styles.scorePop} ${scoreDelta >= 0 ? styles.scorePopGood : styles.scorePopBad}`}>
          {scoreDelta >= 0 ? `+${scoreDelta}` : scoreDelta}
        </span>
      )}
      <div className={styles.row}>
        {cards.map((code, i) => {
          const playable = legal ? legal.has(code) : false;
          const disabled = legal ? !legal.has(code) : false;
          return (
            <div key={`${code}-${i}`} className={styles.slot} style={{ marginLeft: i === 0 ? 0 : -overlap }}>
              <Card code={code} playable={playable} disabled={disabled} onClick={() => onPlay?.(code)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
