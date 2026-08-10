import { seatArcPositions } from '../lib/layout';
import { useElementSize } from '../lib/useElementSize';
import type { Seat } from '../types/game';
import styles from './Table.module.css';

// используются, пока ResizeObserver ещё не измерил реальный контейнер
const FALLBACK_W = 358;
const FALLBACK_H = 300;

export function LobbySeats({ seats, maxPlayers, meSeat }: { seats: Seat[]; maxPlayers: number; meSeat: number }) {
  const [wrapRef, size] = useElementSize<HTMLDivElement>();
  const slots: (Seat | null)[] = Array.from({ length: maxPlayers }, (_, i) => seats[i] ?? null);
  const points = seatArcPositions(slots.length, size.width || FALLBACK_W, size.height || FALLBACK_H);

  return (
    <div className={styles.seatsWrap} ref={wrapRef}>
      {slots.map((seat, i) => {
        const p = points[i];
        if (!seat) {
          return (
            <div key={i} className={`${styles.seatChip} ${styles.empty}`} style={{ left: p.x, top: p.y }}>
              <div className={styles.avatar}>?</div>
              <div className={styles.seatName}>Место {i + 1}</div>
              <div className={styles.seatSub}>ждём игрока</div>
            </div>
          );
        }
        const isMe = i === meSeat;
        return (
          <div key={i} className={`${styles.seatChip} ${isMe ? styles.me : ''}`} style={{ left: p.x, top: p.y }}>
            <div className={styles.avatar}>{seat.username[0]}</div>
            <div className={styles.seatName}>
              {seat.username}
              {isMe ? ' (ты)' : ''}
            </div>
            <div className={styles.seatSub}>{i === 0 ? 'хост' : 'за столом'}</div>
          </div>
        );
      })}
    </div>
  );
}
