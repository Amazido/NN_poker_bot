import { useEffect, useRef, useState } from 'react';
import { getPrivateView, getPublicView } from './rooms';
import { ApiError } from './http';
import type { GameView } from '../types/game';

const POLL_MS = 1200;

export function useGameView(roomId: string | null) {
  const [view, setView] = useState<GameView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const viewRef = useRef<GameView | null>(null);

  useEffect(() => {
    setView(null);
    setError(null);
    viewRef.current = null;
    if (!roomId) return;

    let stopped = false;

    async function tick() {
      try {
        const pub = await getPublicView(roomId!);
        const me = pub.status === 'playing' ? await getPrivateView(roomId!).catch(() => null) : null;
        if (stopped) return;
        const next: GameView = { ...pub, me };
        viewRef.current = next;
        setView(next);
        setError(null);
      } catch (e) {
        if (stopped) return;
        setError(e instanceof ApiError ? e.message : 'Не удалось связаться с сервером');
      }
    }

    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [roomId]);

  return { view, error };
}
