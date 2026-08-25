import type { ReactNode } from 'react';
import { AppHeader, StatusBar } from '../components/AppHeader';
import styles from './MatchLayout.module.css';

export function MatchLayout({
  roomCode,
  onLeave,
  onShowScores,
  status,
  table,
  controls,
}: {
  roomCode: string;
  onLeave?: () => void;
  onShowScores?: () => void;
  status: ReactNode;
  table: ReactNode;
  controls: ReactNode;
}) {
  return (
    <div className={styles.match}>
      <AppHeader roomCode={roomCode} onLeave={onLeave} onShowScores={onShowScores} />
      <StatusBar>{status}</StatusBar>
      <div className={styles.tableBubble}>{table}</div>
      <div className={styles.controlBubble}>{controls}</div>
    </div>
  );
}
