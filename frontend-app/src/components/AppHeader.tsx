import type { ReactNode } from 'react';
import type { RoundPublic } from '../types/game';
import { suitInner } from '../lib/cards';
import styles from './AppHeader.module.css';

export function AppHeader({
  roomCode,
  onLeave,
  onShowScores,
  status,
}: {
  roomCode: string;
  onLeave?: () => void;
  onShowScores?: () => void;
  status?: ReactNode;
}) {
  return (
    <div className={styles.header}>
      <div className={styles.headerTop}>
        <div className={styles.brand}>
          Одесский покер
          <small>стол №{roomCode}</small>
        </div>
        <div className={styles.headerActions}>
          {onShowScores && (
            <button className={styles.scoresBtn} onClick={onShowScores}>
              Счёт
            </button>
          )}
          {onLeave && (
            <button className={styles.leaveBtn} onClick={onLeave}>
              Выйти
            </button>
          )}
        </div>
      </div>
      {status && <div className={styles.statusBar}>{status}</div>}
    </div>
  );
}

export function StatusBar({ children }: { children: ReactNode }) {
  return <div className={styles.statusBar}>{children}</div>;
}

export function Pill({ children, trump }: { children: ReactNode; trump?: boolean }) {
  return <span className={[styles.pill, trump ? styles.pillTrump : ''].filter(Boolean).join(' ')}>{children}</span>;
}

export function TrumpPill({ round }: { round: RoundPublic }) {
  if (round.no_trump) return <Pill trump>Без козыря</Pill>;
  const color = round.trump_suit === 'D' || round.trump_suit === 'H' ? 'var(--card-red)' : 'currentColor';
  return (
    <Pill trump>
      <svg viewBox="0 0 100 100" dangerouslySetInnerHTML={{ __html: suitInner(round.trump_suit as 'C' | 'D' | 'H' | 'S', color) }} />
      Козырь
    </Pill>
  );
}
