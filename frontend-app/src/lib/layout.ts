export interface Point {
  x: number;
  y: number;
}

/** Ширина рабочей колонки. Совпадает с --stage-w. */
export const STAGE_W = 360;
/** Высота бабла стола в матче. Совпадает с --table-bubble-h. */
export const TABLE_BUBBLE_H = 300;

/** «Я» всегда внизу стола (в экранных координатах y растёт вниз). */
const ME_DEG = 90;

/**
 * Места вокруг стола: `meIndex` сидит снизу, остальные — по часовой.
 * Для 4 игроков это лево / верх / право + «вы» снизу; для 5 — ещё нижние углы.
 */
export function seatTablePositions(count: number, width: number, height: number, meIndex = 0): Point[] {
  if (count <= 0) return [];
  const cx = width / 2;
  const cy = height / 2;
  const rx = width * 0.38;
  const ry = height * 0.34;
  const step = 360 / count;
  const origin = ((meIndex % count) + count) % count;
  return Array.from({ length: count }, (_, i) => {
    const rel = (i - origin + count) % count;
    const rad = ((ME_DEG + rel * step) * Math.PI) / 180;
    return { x: cx + rx * Math.cos(rad), y: cy + ry * Math.sin(rad) };
  });
}

/** @deprecated используй seatTablePositions; оставлено для лобби без «я». */
export function seatArcPositions(count: number, width: number, height: number): Point[] {
  return seatTablePositions(count, width, height, 0);
}
