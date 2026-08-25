import type { ReactNode } from 'react';
import type { RoundPublic } from '../types/game';
import { jokerInner, parseCard, rankDisplay, suitInner, type Suit } from '../lib/cards';
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

function suitColor(suit: Suit | undefined, jokerRed?: boolean): string {
  if (jokerRed === true || suit === 'D' || suit === 'H') return 'var(--card-red)';
  return 'var(--card-ink)';
}

export function TrumpPill({ round }: { round: RoundPublic }) {
  const parsed = parseCard(round.trump_card);
  const color = parsed.joker ? suitColor(undefined, parsed.color === 'red') : suitColor(parsed.suit);
  const glyph = parsed.joker ? jokerInner(color) : suitInner(parsed.suit!, color);

  return (
    <Pill trump>
      <span className={styles.trumpFace}>
        {!parsed.joker && parsed.rank && (
          <span className={styles.trumpRank} style={{ color }}>
            {rankDisplay(parsed.rank)}
          </span>
        )}
        <svg viewBox="0 0 100 100" dangerouslySetInnerHTML={{ __html: glyph }} />
      </span>
      {round.no_trump ? 'Без козыря' : 'Козырь'}
    </Pill>
  );
}
