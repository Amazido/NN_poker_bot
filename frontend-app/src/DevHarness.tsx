import { useMemo, useState } from 'react';
import styles from './App.module.css';
import { makeFixture, type FixtureScreen } from './lib/fixtures';
import { resolveScreen } from './screen-resolver';
import { WaitingScreen } from './screens/WaitingScreen';
import { BiddingScreen } from './screens/BiddingScreen';
import { PlayingScreen } from './screens/PlayingScreen';

const SCREENS: { id: FixtureScreen; label: string }[] = [
  { id: 'waiting', label: 'Ожидание' },
  { id: 'bidding', label: 'Торги' },
  { id: 'playing', label: 'Сброс' },
];
const PLAYER_COUNTS = [2, 3, 4, 5, 6];
const THEMES = [
  { id: 'auto', label: 'Системная' },
  { id: 'light', label: 'Светлая' },
  { id: 'dark', label: 'Тёмная' },
] as const;
type ThemeId = (typeof THEMES)[number]['id'];

function Segmented<T extends string | number>({ items, active, onPick }: { items: { id: T; label: string }[]; active: T; onPick: (id: T) => void }) {
  return (
    <div className={styles.seg}>
      {items.map((it) => (
        <button key={it.id} className={it.id === active ? styles.active : ''} onClick={() => onPick(it.id)}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState<FixtureScreen>('waiting');
  const [players, setPlayers] = useState(4);
  const [theme, setTheme] = useState<ThemeId>('auto');

  const view = useMemo(() => makeFixture(screen, players), [screen, players]);
  const resolved = resolveScreen(view);

  if (theme === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', theme);

  return (
    <div className={styles.page}>
      <div className={styles.meta}>
        <div className={styles.metaTop}>
          <span className={styles.metaTitle}>Одесский покер · дев-стенд экранов</span>
          <span className={styles.metaBadge}>Вымышленные данные</span>
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Экран</span>
          <Segmented items={SCREENS} active={screen} onPick={setScreen} />
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Игроков</span>
          <Segmented items={PLAYER_COUNTS.map((n) => ({ id: n, label: String(n) }))} active={players} onPick={setPlayers} />
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Тема</span>
          <Segmented items={THEMES as unknown as { id: ThemeId; label: string }[]} active={theme} onPick={setTheme} />
        </div>
      </div>

      <div className={styles.stage}>
        <div className={styles.phone}>
          {resolved.type === 'waiting' && (
            <WaitingScreen
              view={resolved.view}
              myUserId={resolved.view.seats[0]?.user_id ?? ''}
              onStart={() => console.log('start')}
              onLeave={() => console.log('leave')}
            />
          )}
          {resolved.type === 'bidding' && <BiddingScreen view={resolved.view} onBid={(n) => console.log('bid', n)} />}
          {resolved.type === 'playing' && <PlayingScreen view={resolved.view} onPlay={(c) => console.log('play', c)} />}
          {resolved.type === 'unsupported' && <p>Экран для этой фазы ещё не спроектирован (sub-project C).</p>}
        </div>
      </div>

      <p className={styles.note}>
        Панель сверху — инструмент разработки, в реальном приложении её не будет. Данные фиксированы фикстурой{' '}
        <code>makeFixture</code> — в sub-project B она заменится на реальный поллинг API.
      </p>
    </div>
  );
}
