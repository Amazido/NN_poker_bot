import { parseCard, rankDisplay, cardIsRed, suitInner, jokerInner } from '../lib/cards';
import type { CardCode } from '../types/game';
import styles from './Card.module.css';

function Pip({ code, ink }: { code: CardCode; ink: string }) {
  const c = parseCard(code);
  const inner = c.joker ? jokerInner(ink) : suitInner(c.suit!, ink);
  // eslint-disable-next-line react/no-danger -- inner is built from our own fixed shape primitives, not user input
  return <svg viewBox="0 0 100 100" dangerouslySetInnerHTML={{ __html: inner }} />;
}

export interface CardProps {
  code: CardCode;
  size?: 'md' | 'sm';
  playable?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

export function Card({ code, size = 'md', playable, disabled, onClick }: CardProps) {
  const c = parseCard(code);
  const red = cardIsRed(code);
  const ink = red ? 'var(--card-red)' : 'var(--card-ink)';
  const rankTxt = c.joker ? '' : rankDisplay(c.rank!);
  const cls = [styles.card, size === 'sm' ? styles.sm : '', playable ? styles.playable : '', disabled ? styles.disabled : '']
    .filter(Boolean)
    .join(' ');
  const suitCls = [styles.miniSuit, c.joker ? styles.joker : ''].filter(Boolean).join(' ');

  return (
    <div className={cls} onClick={playable ? onClick : undefined}>
      <div className={styles.corner}>
        {rankTxt && (
          <span className={styles.rank} style={{ color: ink }}>
            {rankTxt}
          </span>
        )}
        <span className={suitCls}>
          <Pip code={code} ink={ink} />
        </span>
      </div>
      <div className={styles.cornerBr}>
        {rankTxt && (
          <span className={styles.rank} style={{ color: ink }}>
            {rankTxt}
          </span>
        )}
        <span className={suitCls}>
          <Pip code={code} ink={ink} />
        </span>
      </div>
      <div className={styles.pipCenter}>
        <Pip code={code} ink={ink} />
      </div>
    </div>
  );
}

export function CardBack({ size = 'md' }: { size?: 'md' | 'sm' }) {
  if (size === 'sm') return <div className={styles.backSm} />;
  return (
    <div className={styles.back}>
      <svg viewBox="0 0 100 100" dangerouslySetInnerHTML={{ __html: suitInner('D', 'var(--card-back-mark)') }} />
    </div>
  );
}
