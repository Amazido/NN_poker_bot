import type { GameView } from './types/game';

export type AppScreen =
  | { type: 'waiting'; view: GameView }
  | { type: 'bidding'; view: GameView }
  | { type: 'playing'; view: GameView }
  | { type: 'loading' }
  | { type: 'finished'; view: GameView }
  | { type: 'unsupported'; view: GameView }; // scoring между раздачами — sub-project C

/**
 * Публичный и приватный вид прилетают отдельными push-сообщениями (не одним
 * REST-ответом) — на короткое окно после смены раздачи/фазы новый round_index
 * или phase уже видны в публичном виде, а своя рука ещё старая. Сверяем их,
 * а не просто "me не null", иначе можно отрисовать смесь новой раздачи со
 * старой рукой (см. открытые вопросы в спеке — ровно тот баг с "не тем числом карт").
 */
function isMeFresh(view: GameView): boolean {
  if (!view.me) return false;
  return view.me.round_index === view.round_index && view.me.phase === (view.round?.phase ?? null);
}

export function resolveScreen(view: GameView): AppScreen {
  if (view.status === 'lobby') return { type: 'waiting', view };
  if (view.match_over || view.status === 'finished') return { type: 'finished', view };
  if (view.round?.phase === 'bidding') return isMeFresh(view) ? { type: 'bidding', view } : { type: 'loading' };
  if (view.round?.phase === 'playing') return isMeFresh(view) ? { type: 'playing', view } : { type: 'loading' };
  return { type: 'unsupported', view };
}
