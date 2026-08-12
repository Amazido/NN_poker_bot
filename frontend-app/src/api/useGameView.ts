import { useEffect, useState } from 'react';
import { getPrivateView, getPublicView } from './rooms';
import { ApiError } from './http';
import { chRoom, chUser, connectRealtime, subscribeChannel } from './realtime';
import type { GameView, PrivateView, PublicView } from '../types/game';

const POLL_MS = 1200;

interface RoomPublication {
  type: 'state' | 'lobby' | 'events';
  state?: PublicView;
}
interface UserPublication {
  type: 'private';
  private?: PrivateView;
}

export function useGameView(roomId: string | null, myUserId: string | null) {
  const [view, setView] = useState<GameView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setView(null);
    setError(null);
    if (!roomId || !myUserId) return;

    let stopped = false;
    let pollId: ReturnType<typeof setInterval> | null = null;
    let unsubRoom: (() => void) | null = null;
    let unsubUser: (() => void) | null = null;

    async function hydrate() {
      try {
        const pub = await getPublicView(roomId!);
        const me = pub.status === 'playing' ? await getPrivateView(roomId!).catch(() => null) : null;
        if (stopped) return;
        setView({ ...pub, me });
        setError(null);
      } catch (e) {
        if (!stopped) setError(e instanceof ApiError ? e.message : 'Не удалось связаться с сервером');
      }
    }

    function startPolling() {
      if (pollId) return;
      hydrate();
      pollId = setInterval(hydrate, POLL_MS);
    }

    async function startRealtime() {
      await hydrate(); // начальный снимок — WS отдаёт только новые публикации, не историю
      if (stopped) return;
      try {
        await connectRealtime();
        if (stopped) return;
        unsubRoom = subscribeChannel(chRoom(roomId!), (data) => {
          const msg = data as RoomPublication;
          if ((msg.type === 'state' || msg.type === 'lobby') && msg.state) {
            const pub = msg.state;
            setView((prev) => ({ ...(prev ?? {}), ...pub, me: prev?.me ?? null }) as GameView);
          }
        });
        unsubUser = subscribeChannel(chUser(myUserId!), (data) => {
          const msg = data as UserPublication;
          if (msg.type === 'private') {
            setView((prev) => (prev ? { ...prev, me: msg.private ?? null } : prev));
          }
        });
      } catch {
        if (!stopped) startPolling(); // WS не поднялся — не бросаем человека без обновлений
      }
    }

    startRealtime();

    return () => {
      stopped = true;
      if (pollId) clearInterval(pollId);
      unsubRoom?.();
      unsubUser?.();
    };
  }, [roomId, myUserId]);

  return { view, error };
}
