import { useState } from 'react';
import { AppHeader } from '../components/AppHeader';
import styles from './EntryScreen.module.css';

export interface EntryScreenProps {
  onCreate: () => void;
  onJoin: (code: string) => void;
  busy?: boolean;
  error?: string | null;
}

export function EntryScreen({ onCreate, onJoin, busy, error }: EntryScreenProps) {
  const [tab, setTab] = useState<'create' | 'join'>('create');
  const [code, setCode] = useState('');

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
            <button className={styles.btnWide} disabled={busy} onClick={onCreate}>
              Создать стол
            </button>
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
