import type { RulesView } from '../types/game';
import styles from './RulesCard.module.css';

export interface RulesCardProps {
  rules?: RulesView;
  /** Компактный вид — внутри модалки счёта, где места меньше. */
  compact?: boolean;
}

/** Правила стола: во что именно играем. Редакций несколько, по столу их не угадать. */
export function RulesCard({ rules, compact }: RulesCardProps) {
  if (!rules?.summary?.length) return null;
  return (
    <div className={compact ? styles.cardCompact : styles.card}>
      <div className={styles.title}>{rules.name || 'Правила стола'}</div>
      <ul className={styles.list}>
        {rules.summary.map((line) => (
          <li key={line} className={styles.item}>
            {line}
          </li>
        ))}
      </ul>
    </div>
  );
}
