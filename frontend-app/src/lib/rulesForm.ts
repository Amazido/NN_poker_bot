/** Помощники формы создания стола: границы, запасные значения, длина матча. */
import type { RulesFormLimits, TableRulesSettings } from '../types/game';

/** Чем работать, если каталог не ответил: собрать стол должно быть можно всё равно.
 *
 * Значения совпадают с эталоном сезона — самый разумный стол по умолчанию. */
export const FALLBACK_SETTINGS: TableRulesSettings = {
  rounds_start: 1,
  rounds_peak: 10,
  two_beats_ace: true,
  offcolor_beats_oncolor: true,
  blind_allowed: true,
  blind_bonus: 5,
  infinite_deck: false,
  pass_reward: 10,
  trick_reward: 10,
  overtrick_penalty: 5,
  undertrick_penalty: 5,
};

/** Дублирует пределы бэка (`rules.max_peak_finite`, `MAX_PEAK_INFINITE`) —
 * используется, только пока настоящие не приехали. */
export const FALLBACK_LIMITS: RulesFormLimits = {
  min_start: 1,
  max_peak_one_deck: 10,
  max_peak_infinite: 20,
};

/** Сколько карт максимум можно раздать. Безлимитная колода поднимает потолок. */
export function maxPeak(settings: TableRulesSettings, limits: RulesFormLimits): number {
  return settings.infinite_deck ? limits.max_peak_infinite : limits.max_peak_one_deck;
}

function clampInt(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(Math.round(value), max));
}

/** Удержать поля в допустимых границах.
 *
 * Порядок «начало ≤ пик» здесь не чиним: правка на лету мешала бы набирать
 * число. Это проверяет `settingsError` и блокирует кнопку. */
export function clampSettings(settings: TableRulesSettings, limits: RulesFormLimits): TableRulesSettings {
  const top = maxPeak(settings, limits);
  return {
    ...settings,
    rounds_start: clampInt(settings.rounds_start, limits.min_start, top),
    rounds_peak: clampInt(settings.rounds_peak, limits.min_start, top),
    blind_bonus: clampInt(settings.blind_bonus, 0, 999),
    pass_reward: clampInt(settings.pass_reward, 0, 999),
    trick_reward: clampInt(settings.trick_reward, 0, 999),
    overtrick_penalty: clampInt(settings.overtrick_penalty, 0, 999),
    undertrick_penalty: clampInt(settings.undertrick_penalty, 0, 999),
  };
}

/** Что не так с настройками, человеческим языком. null — всё в порядке. */
export function settingsError(settings: TableRulesSettings): string | null {
  if (settings.rounds_peak < settings.rounds_start) {
    return 'Последняя раздача не может быть меньше первой';
  }
  return null;
}

/** Сколько раздач выйдет в матче на players игроков.
 *
 * Матч идёт от первой раздачи к самой большой и обратно, а на пике задерживается:
 * «пик» повторяется по разу на каждого сдающего. */
export function roundsTotal(settings: TableRulesSettings, players: number): number {
  return 2 * (settings.rounds_peak - settings.rounds_start) + players;
}
