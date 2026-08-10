import type { GameView } from './types/game';

export type AppScreen =
  | { type: 'waiting'; view: GameView }
  | { type: 'bidding'; view: GameView }
  | { type: 'playing'; view: GameView }
  | { type: 'unsupported'; view: GameView }; // scoring/finished — sub-project C

export function resolveScreen(view: GameView): AppScreen {
  if (view.status === 'lobby') return { type: 'waiting', view };
  if (view.round?.phase === 'bidding') return { type: 'bidding', view };
  if (view.round?.phase === 'playing') return { type: 'playing', view };
  return { type: 'unsupported', view };
}
