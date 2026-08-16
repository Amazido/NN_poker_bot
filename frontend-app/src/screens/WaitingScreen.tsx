import { AppHeader } from '../components/AppHeader';
import { LobbySeats } from '../components/LobbySeats';
import type { GameView } from '../types/game';
import styles from './WaitingScreen.module.css';

export interface WaitingScreenProps {
  view: GameView;
  myUserId: string;
  onStart: () => void;
  onLeave: () => void;
  onAddBot: () => void;
  starting?: boolean;
  startError?: string | null;
}

export function WaitingScreen({ view, myUserId, onStart, onLeave, onAddBot, starting, startError }: WaitingScreenProps) {
  const meSeat = view.seats.findIndex((s) => s.user_id === myUserId);
  // Место 0 всегда достаётся создателю комнаты (service.create_room сажает его первым) —
  // временная эвристика, пока бэк не отдаёт явный признак хоста (см. открытые вопросы в спеке).
  const isHost = view.seats.find((s) => s.seat === 0)?.user_id === myUserId;
  const maxPlayers = view.max_players ?? view.n_players;
  const isFull = view.n_players >= maxPlayers;

  return (
    <>
      <AppHeader roomCode={view.join_code ?? '—'} />
      <div className={styles.body}>
        <div className={styles.roomCodeCard}>
          <div className={styles.codeCol}>
            <div className={styles.lbl}>Код комнаты</div>
            <div className={styles.code}>{view.join_code}</div>
          </div>
          <button className={styles.shareBtn}>Поделиться</button>
        </div>
        <LobbySeats seats={view.seats} maxPlayers={maxPlayers} meSeat={meSeat} />
        <div className={styles.hostPanel}>
          {isHost ? (
            <>
              <button className={styles.primaryBtn} disabled={view.n_players < 2 || starting} onClick={onStart}>
                {starting ? 'Запускаем…' : 'Начать игру'}
              </button>
              {!isFull && (
                <button className={styles.secondaryBtn} disabled={starting} onClick={onAddBot}>
                  Добавить бота
                </button>
              )}
              <div className={styles.hostHint}>
                {startError ?? (view.n_players < 2 ? 'Нужно минимум 2 игрока' : `Собрано ${view.n_players} из ${maxPlayers}`)}
              </div>
            </>
          ) : (
            <div className={styles.turnNote}>Ждём, пока хост начнёт игру</div>
          )}
          <button className={styles.leaveBtn} onClick={onLeave}>
            Покинуть комнату
          </button>
        </div>
      </div>
    </>
  );
}
