import type { GameView } from './types/game';

export type AppScreen =
  | { type: 'waiting'; view: GameView }
  | { type: 'bidding'; view: GameView }
  | { type: 'playing'; view: GameView }
  | { type: 'loading' }
  | { type: 'finished'; view: GameView }
  | { type: 'unsupported'; view: GameView }; // scoring между раздачами — sub-project C

export function resolveScreen(view: GameView): AppScreen {
  if (view.status === 'lobby') return { type: 'waiting', view };
  if (view.match_over || view.status === 'finished') return { type: 'finished', view };
  // Публичный и приватный вид прилетают отдельными push-сообщениями (не одним
  // REST-ответом) — на короткое окно фаза уже сменилась, а своя рука ещё не
  // подъехала. Ждём, пока подъедут обе половины, а не рендерим экран с me=null.
  // Важно: только для bidding/playing — у finished/scoring me законно отсутствует
  // (private view для них не запрашивается), это не «ещё не подъехало».
  if (view.round?.phase === 'bidding') return view.me ? { type: 'bidding', view } : { type: 'loading' };
  if (view.round?.phase === 'playing') return view.me ? { type: 'playing', view } : { type: 'loading' };
  return { type: 'unsupported', view };
}
