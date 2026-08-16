import type { CardCode } from '../types/game';
import { Card } from './Card';
import styles from './Hand.module.css';

export interface HandProps {
  cards: CardCode[];
  legal?: Set<CardCode> | null;
  onPlay?: (code: CardCode) => void;
  /** Изменение счёта за только что законченную раздачу — показать пару секунд. */
  scoreDelta?: number | null;
}

export function Hand({ cards, legal, onPlay, scoreDelta }: HandProps) {
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
            <div key={`${code}-${i}`} className={styles.slot}>
              <Card code={code} playable={playable} disabled={disabled} onClick={() => onPlay?.(code)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
