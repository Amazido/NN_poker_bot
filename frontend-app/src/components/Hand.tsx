import type { CardCode } from '../types/game';
import { Card } from './Card';
import styles from './Hand.module.css';

export interface HandProps {
  cards: CardCode[];
  legal?: Set<CardCode> | null;
  onPlay?: (code: CardCode) => void;
}

export function Hand({ cards, legal, onPlay }: HandProps) {
  return (
    <div className={styles.tray}>
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
