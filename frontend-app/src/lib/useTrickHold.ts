import { useEffect, useRef, useState } from 'react';
import type { GameView, LastTrick } from '../types/game';

/** Сколько добитая взятка ещё лежит на столе после последней карты. */
export const TRICK_HOLD_MS = 2000;

/**
 * Держать только что добитую взятку на столе пару секунд.
 *
 * Бэк забирает взятку сразу: как только легла последняя карта, он объявляет
 * победителя и открывает следующую, а при последней взятке кона — сразу и
 * следующий кон. За столом с ботами это мгновенно, и игрок не успевает увидеть,
 * чем закрылись. Задержка живёт на клиенте: движок синхронный и чистый, таймеры
 * ему не нужны, а у каждого игрока своя задержка от момента, когда до него
 * дошёл пуш.
 */
export function useTrickHold(view: GameView | null, holdMs: number = TRICK_HOLD_MS): LastTrick | null {
  const [held, setHeld] = useState<LastTrick | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<LastTrick | null>(null);
  const prev = useRef<{ room: string | null; key: string | null } | null>(null);

  const roomId = view?.room_id ?? null;
  const last = view?.round?.last_trick ?? null;
  const key = last ? `${view!.round_index}:${last.trick_number}` : null;

  // Эффекты срабатывают в порядке объявления, поэтому к моменту проверки ключа
  // снимок уже свежий — а в рендере ref не пишем.
  useEffect(() => {
    latest.current = last;
  }, [last]);

  useEffect(() => {
    const was = prev.current;
    prev.current = { room: roomId, key };
    if (!key) return; // взяток ещё нет либо начался новый кон
    if (!was || was.room !== roomId) return; // первый снимок комнаты — это история, а не ход
    if (was.key === key) return;

    if (timer.current) clearTimeout(timer.current);
    setHeld(latest.current);
    timer.current = setTimeout(() => setHeld(null), holdMs);
    // Таймер намеренно не снимается при смене зависимостей: добив последнюю
    // взятку кона, бэк тут же начинает следующий, `key` становится null — и
    // уборка погасила бы задержку ровно там, где она нужнее всего.
  }, [key, roomId, holdMs]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return held;
}
