import { AppHeader } from '../components/AppHeader';
import type { GameView } from '../types/game';
import styles from './FinishedScreen.module.css';

export function FinishedScreen({ view, onLeave }: { view: GameView; onLeave: () => void }) {
  const sorted = [...view.seats].sort((a, b) => b.score - a.score);
  const topScore = sorted[0]?.score;

  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div className={styles.title}>Матч завершён 🏁</div>
        <div className={styles.board}>
          {sorted.map((s, i) => (
            <div key={s.seat} className={`${styles.row} ${s.score === topScore ? styles.winner : ''}`}>
              <span className={styles.place}>{i + 1}</span>
              <span className={styles.name}>{s.username}</span>
              <span className={styles.score}>{s.score}</span>
            </div>
          ))}
        </div>
        <button className={styles.leaveBtn} onClick={onLeave}>
          Выйти в меню
        </button>
      </div>
    </>
  );
}
