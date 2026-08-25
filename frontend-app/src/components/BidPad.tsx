import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { TurnTimer } from './TurnTimer';
import styles from './ActionPanel.module.css';

export function BidPad({
  maxBid,
  options,
  onBid,
  deadline,
}: {
  maxBid: number;
  options: number[];
  onBid: (n: number) => void;
  deadline: string | null;
}) {
  const allowed = useMemo(() => new Set(options), [options]);
  const [value, setValue] = useState(0);

  useEffect(() => {
    setValue(0);
  }, [maxBid]);

  const canConfirm = allowed.has(value);

  return (
    <div className={styles.panel}>
      <div className={styles.title}>
        <span>Сколько взяток заказываешь?</span>
      </div>
      <div className={styles.stepper}>
        <button type="button" className={styles.stepBtn} disabled={value <= 0} onClick={() => setValue((v) => v - 1)}>
          −
        </button>
        <div className={`${styles.stepValue} ${canConfirm ? '' : styles.stepForbidden}`}>{value}</div>
        <button type="button" className={styles.stepBtn} disabled={value >= maxBid} onClick={() => setValue((v) => v + 1)}>
          +
        </button>
      </div>
      <button type="button" className={styles.confirm} disabled={!canConfirm} onClick={() => onBid(value)}>
        <TurnTimer deadline={deadline} size={22} invert />
        {canConfirm ? 'Заказать' : 'Нельзя'}
      </button>
    </div>
  );
}

export function WaitingTurnNote({ deadline, children }: { deadline: string | null; children: ReactNode }) {
  return (
    <div className={styles.panel}>
      <div className={styles.waitingNote}>
        <TurnTimer deadline={deadline} size={22} />
        {children}
      </div>
    </div>
  );
}

export function PlayHint({ deadline, children }: { deadline: string | null; children: ReactNode }) {
  return (
    <div className={styles.panel}>
      <div className={styles.playHint}>
        <TurnTimer deadline={deadline} size={22} />
        {children}
      </div>
    </div>
  );
}
