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
  const [code, setCode] = useState('');

  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div>
          <div className={styles.title}>Одесский покер</div>
          <div className={styles.subtitle}>Собери стол или войди по коду друга</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardTitle}>Новый стол</div>
          <button className={styles.btnWide} disabled={busy} onClick={onCreate}>
            Создать стол
          </button>
        </div>

        <div className={styles.card}>
          <div className={styles.cardTitle}>Уже есть код</div>
          <div className={styles.row}>
            <input
              className={styles.input}
              placeholder="Код комнаты"
              value={code}
              maxLength={12}
              onChange={(e) => setCode(e.target.value)}
            />
            <button className={styles.btn} disabled={busy || !code.trim()} onClick={() => onJoin(code)}>
              Войти
            </button>
          </div>
        </div>

        {error && <div className={styles.error}>{error}</div>}
      </div>
    </>
  );
}
