import { useState } from 'react';
import type { Seat } from '../types/game';
import styles from './Scoreboard.module.css';

function ScoreboardModal({ seats, onClose }: { seats: Seat[]; onClose: () => void }) {
  const sorted = [...seats].sort((a, b) => b.score - a.score);
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <div className={styles.title}>Счёт</div>
        {sorted.map((s, i) => (
          <div key={s.seat} className={styles.row}>
            <span className={styles.place}>{i + 1}</span>
            <span className={styles.name}>{s.username}</span>
            <span className={styles.score}>{s.score}</span>
          </div>
        ))}
        <button className={styles.closeBtn} onClick={onClose}>
          Закрыть
        </button>
      </div>
    </div>
  );
}

export function useScoreboard() {
  const [open, setOpen] = useState(false);
  return { open, show: () => setOpen(true), hide: () => setOpen(false) };
}

export { ScoreboardModal };
