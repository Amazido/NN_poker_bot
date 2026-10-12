import { apiFetch } from './http';
import type { LeaderboardRow, SeasonSummary } from '../types/game';

/** Идущий сезон. 404, если активного сезона нет — это нормальное состояние. */
export function getCurrentSeason(): Promise<SeasonSummary> {
  return apiFetch<SeasonSummary>('/seasons/current');
}

/** Лидерборд сезона. В выборку попадают только те, у кого есть зачётные матчи. */
export function getSeasonLeaderboard(): Promise<LeaderboardRow[]> {
  return apiFetch<LeaderboardRow[]>('/seasons/current/leaderboard');
}
