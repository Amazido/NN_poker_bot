import { useEffect, useState } from 'react';
import { AppHeader } from '../components/AppHeader';
import { ApiError } from '../api/http';
import { getCurrentSeason, getSeasonLeaderboard } from '../api/seasons';
import type { LeaderboardRow, SeasonSummary } from '../types/game';
import styles from './SeasonScreen.module.css';

export interface SeasonData {
  season: SeasonSummary;
  rows: LeaderboardRow[];
}

export interface SeasonScreenProps {
  onBack: () => void;
  /** Дев-стенд подставляет данные сам — ходить в API оттуда некуда. */
  data?: SeasonData | null;
}

/** Таблица участников сезона с рейтингами. Доступна всем, кто вошёл в игру:
 * смотреть лидерборд можно, даже не играя в сезоне. */
export function SeasonScreen({ onBack, data: given }: SeasonScreenProps) {
  const [data, setData] = useState<SeasonData | null>(given ?? null);
  // Три разных исхода, и путать их нельзя: грузим, сезона нет, запрос упал.
  const [state, setState] = useState<'loading' | 'ready' | 'no-season' | 'error'>(
    given ? 'ready' : 'loading',
  );

  useEffect(() => {
    if (given) return;
    let alive = true;
    Promise.all([getCurrentSeason(), getSeasonLeaderboard()])
      .then(([season, rows]) => {
        if (!alive) return;
        setData({ season, rows });
        setState('ready');
      })
      .catch((e) => {
        if (!alive) return;
        setState(e instanceof ApiError && e.status === 404 ? 'no-season' : 'error');
      });
    return () => {
      alive = false;
    };
  }, [given]);

  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div className={styles.head}>
          <div>
            <div className={styles.title}>Результаты сезона</div>
            {data && <div className={styles.subtitle}>{data.season.name}</div>}
          </div>
          <button className={styles.backBtn} onClick={onBack}>
            Назад
          </button>
        </div>

        {state === 'loading' && <div className={styles.note}>Загружаем таблицу…</div>}
        {state === 'no-season' && <div className={styles.note}>Сезон пока не открыт.</div>}
        {state === 'error' && <div className={styles.error}>Не удалось загрузить таблицу сезона.</div>}

        {state === 'ready' && data && (
          <div className={styles.card}>
            {data.rows.length === 0 ? (
              <div className={styles.note}>
                Зачётных матчей в сезоне ещё не было — таблица наполнится после первых игр.
              </div>
            ) : (
              <>
                <div className={styles.headRow}>
                  <span className={styles.place}>#</span>
                  <span className={styles.name}>Игрок</span>
                  <span className={styles.matches}>Матчи</span>
                  <span className={styles.rating}>Рейтинг</span>
                </div>
                {data.rows.map((r) => (
                  <div key={r.user_id} className={r.is_me ? styles.rowMe : styles.row}>
                    <span className={styles.place}>{r.place}</span>
                    <span className={styles.name}>{r.username}</span>
                    <span className={styles.matches}>{r.matches}</span>
                    <span className={styles.rating}>{r.rating}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
