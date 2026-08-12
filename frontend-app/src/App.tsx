import { useEffect, useState, type ReactNode } from 'react';
import styles from './App.module.css';
import { ensureLoggedIn, getMe } from './api/auth';
import { clearToken, ApiError } from './api/http';
import { createRoom, joinRoom, startMatch, bid, playCard, leaveRoomApi } from './api/rooms';
import { useGameView } from './api/useGameView';
import { getTelegramWebApp, getStartParam } from './api/telegram';
import { resolveScreen } from './screen-resolver';
import { EntryScreen } from './screens/EntryScreen';
import { WaitingScreen } from './screens/WaitingScreen';
import { BiddingScreen } from './screens/BiddingScreen';
import { PlayingScreen } from './screens/PlayingScreen';
import { StatusScreen } from './screens/StatusScreen';
import { FinishedScreen } from './screens/FinishedScreen';
import DevHarness from './DevHarness';

const ROOM_KEY = 'op_room_id';
const ROOM_CODE_KEY = 'op_room_code';

function actionErrorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return 'Не удалось выполнить действие';
}

export default function App() {
  const [authError, setAuthError] = useState<string | null>(null);
  const [myUserId, setMyUserId] = useState<string | null>(null);
  const [roomId, setRoomId] = useState<string | null>(() => getStartParam() ?? localStorage.getItem(ROOM_KEY));
  const [roomCode, setRoomCode] = useState<string | null>(() => localStorage.getItem(ROOM_CODE_KEY));
  const [busy, setBusy] = useState(false);
  const [entryError, setEntryError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const tg = getTelegramWebApp();
    tg?.ready();
    tg?.expand();
    (async () => {
      try {
        await ensureLoggedIn();
        const me = await getMe();
        setMyUserId(me.id);
      } catch (e) {
        setAuthError(e instanceof Error ? e.message : 'Не удалось авторизоваться');
      }
    })();
  }, []);

  const { view, error: pollError } = useGameView(roomId, myUserId);

  // join_code бэк отдаёт только в лобби (см. открытые вопросы в спеке) — запоминаем,
  // пока он виден, чтобы показать короткий код и после старта матча.
  useEffect(() => {
    if (view?.join_code && view.join_code !== roomCode) {
      setRoomCode(view.join_code);
      localStorage.setItem(ROOM_CODE_KEY, view.join_code);
    }
  }, [view?.join_code, roomCode]);

  function enterRoom(pub: { room_id: string; join_code?: string }) {
    localStorage.setItem(ROOM_KEY, pub.room_id);
    setRoomId(pub.room_id);
    if (pub.join_code) {
      localStorage.setItem(ROOM_CODE_KEY, pub.join_code);
      setRoomCode(pub.join_code);
    }
  }

  function leaveRoom() {
    // Отписываем на бэке "по-честному" (в лобби — освобождает место, в матче —
    // включает авто-ход за нас), но локальную навигацию не блокируем её результатом:
    // человек должен суметь уйти с экрана, даже если этот запрос не доедет.
    if (roomId) leaveRoomApi(roomId).catch(() => {});
    localStorage.removeItem(ROOM_KEY);
    localStorage.removeItem(ROOM_CODE_KEY);
    setRoomId(null);
    setRoomCode(null);
  }

  async function handleCreate() {
    setBusy(true);
    setEntryError(null);
    try {
      enterRoom(await createRoom());
    } catch (e) {
      setEntryError(actionErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleJoin(code: string) {
    setBusy(true);
    setEntryError(null);
    try {
      enterRoom(await joinRoom(code));
    } catch (e) {
      setEntryError(actionErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    if (!roomId) return;
    setBusy(true);
    setActionError(null);
    try {
      await startMatch(roomId);
    } catch (e) {
      setActionError(actionErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleBid(n: number) {
    if (!roomId) return;
    try {
      await bid(roomId, n);
    } catch (e) {
      setActionError(actionErrorMessage(e));
    }
  }

  async function handlePlay(card: string) {
    if (!roomId) return;
    try {
      await playCard(roomId, card);
    } catch (e) {
      setActionError(actionErrorMessage(e));
    }
  }

  let body: ReactNode;

  if (authError) {
    body = (
      <StatusScreen
        message={authError}
        action={{
          label: 'Повторить',
          onClick: () => {
            setAuthError(null);
            clearToken();
            window.location.reload();
          },
        }}
      />
    );
  } else if (!myUserId) {
    body = <StatusScreen message="Входим…" />;
  } else if (!roomId) {
    body = <EntryScreen onCreate={handleCreate} onJoin={handleJoin} busy={busy} error={entryError} />;
  } else if (pollError) {
    body = <StatusScreen message={pollError} action={{ label: 'Выйти из комнаты', onClick: leaveRoom }} />;
  } else if (!view) {
    body = <StatusScreen message="Загружаем стол…" />;
  } else {
    const resolved = resolveScreen(view);
    if (resolved.type === 'waiting') {
      body = (
        <WaitingScreen
          view={resolved.view}
          myUserId={myUserId}
          onStart={handleStart}
          onLeave={leaveRoom}
          starting={busy}
          startError={actionError}
        />
      );
    } else if (resolved.type === 'bidding') {
      body = <BiddingScreen view={resolved.view} onBid={handleBid} onLeave={leaveRoom} roomCode={roomCode ?? undefined} />;
    } else if (resolved.type === 'playing') {
      body = <PlayingScreen view={resolved.view} onPlay={handlePlay} onLeave={leaveRoom} roomCode={roomCode ?? undefined} />;
    } else if (resolved.type === 'loading') {
      body = <StatusScreen message="Загружаем стол…" />;
    } else if (resolved.type === 'finished') {
      body = <FinishedScreen view={resolved.view} onLeave={leaveRoom} />;
    } else {
      body = <StatusScreen message="Этот момент раздачи фронт пока не умеет показывать (sub-project C)." />;
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.stage}>
        <div className={styles.phone}>{body}</div>
      </div>
    </div>
  );
}

/** ?mock=1 — дев-стенд экранов на фикстурах (см. sub-project A), без бэка и авторизации. */
export function AppOrMock() {
  if (new URLSearchParams(window.location.search).has('mock')) return <DevHarness />;
  return <App />;
}
