import type { ReactNode } from 'react';
import styles from './ActionPanel.module.css';

export function BidPad({ maxBid, options, onBid }: { maxBid: number; options: number[]; onBid: (n: number) => void }) {
  const allowed = new Set(options);
  const values = Array.from({ length: maxBid + 1 }, (_, i) => i);
  return (
    <div className={styles.panel}>
      <div className={styles.title}>
        <span>Сколько взяток заказываешь?</span>
      </div>
      <div className={styles.bidPad}>
        {values.map((n) => {
          const forbidden = !allowed.has(n);
          return (
            <button key={n} className={forbidden ? styles.forbidden : ''} disabled={forbidden} onClick={() => onBid(n)}>
              {n}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function WaitingTurnNote({ children }: { children: ReactNode }) {
  return (
    <div className={styles.panel}>
      <div className={styles.waitingNote}>{children}</div>
    </div>
  );
}
