import { useEffect, useState } from 'react';
import { AppHeader } from '../components/AppHeader';
import { getRulesEditions } from '../api/rooms';
import type { RulesEditionOption } from '../types/game';
import styles from './EntryScreen.module.css';

export interface EntryScreenProps {
  onCreate: (rulesCode?: string) => void;
  onJoin: (code: string) => void;
  busy?: boolean;
  error?: string | null;
}

export function EntryScreen({ onCreate, onJoin, busy, error }: EntryScreenProps) {
  const [tab, setTab] = useState<'create' | 'join'>('create');
  const [code, setCode] = useState('');
  const [editions, setEditions] = useState<RulesEditionOption[]>([]);
  const [rulesCode, setRulesCode] = useState<string | null>(null);

  // Каталог редакций не критичен для входа: не загрузился — создаём стол на
  // редакции по умолчанию, как было до выбора правил.
  useEffect(() => {
    getRulesEditions()
      .then((list) => {
        setEditions(list);
        setRulesCode((prev) => prev ?? list[0]?.code ?? null);
      })
      .catch(() => setEditions([]));
  }, []);

  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div>
          <div className={styles.title}>Одесский покер</div>
          <div className={styles.subtitle}>Собери стол или войди по коду друга</div>
        </div>

        <div className={styles.tabs}>
          <button type="button" className={tab === 'create' ? styles.tabActive : styles.tab} onClick={() => setTab('create')}>
            Создать
          </button>
          <button type="button" className={tab === 'join' ? styles.tabActive : styles.tab} onClick={() => setTab('join')}>
            Присоединиться
          </button>
        </div>

        <div className={styles.card}>
          {tab === 'create' ? (
            <>
              {editions.length > 1 && (
                <>
                  <div className={styles.rulesLabel}>Правила стола</div>
                  <div className={styles.editions}>
                    {editions.map((e) => (
                      <button
                        key={e.code}
                        type="button"
                        className={e.code === rulesCode ? styles.editionActive : styles.edition}
                        onClick={() => setRulesCode(e.code)}
                      >
                        <span className={styles.editionName}>{e.name}</span>
                        <span className={styles.editionDesc}>{e.description}</span>
                        <span className={styles.editionDesc}>
                          {e.min_players}–{e.max_players} игроков · {e.rounds_total_hint} раздач
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              <button className={styles.btnWide} disabled={busy} onClick={() => onCreate(rulesCode ?? undefined)}>
                Создать стол
              </button>
            </>
          ) : (
            <>
              <input
                className={styles.input}
                placeholder="Код комнаты"
                value={code}
                maxLength={12}
                onChange={(e) => setCode(e.target.value)}
              />
              <button className={styles.btnWide} disabled={busy || !code.trim()} onClick={() => onJoin(code)}>
                Войти
              </button>
            </>
          )}
        </div>

        {error && <div className={styles.error}>{error}</div>}
      </div>
    </>
  );
}
