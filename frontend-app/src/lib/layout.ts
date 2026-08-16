export interface Point {
  x: number;
  y: number;
}

/**
 * Раскладка N мест по дуге стола (2..6 игроков, произвольно).
 * Дуга — верхние 200°..340° эллипса; место "я" всегда снизу, вне этой дуги.
 */
export function seatArcPositions(count: number, width: number, height: number): Point[] {
  if (count <= 0) return [];
  const cx = width / 2;
  const cy = height * 0.42;
  const rx = width * 0.42;
  const ry = height * 0.36;
  const startDeg = 200;
  const endDeg = 340;
  const span = endDeg - startDeg;
  return Array.from({ length: count }, (_, i) => {
    const t = count === 1 ? 0.5 : i / (count - 1);
    const deg = startDeg + span * t;
    const rad = (deg * Math.PI) / 180;
    return { x: cx + rx * Math.cos(rad), y: cy + ry * Math.sin(rad) };
  });
}
