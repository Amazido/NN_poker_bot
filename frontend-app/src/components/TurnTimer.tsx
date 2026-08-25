import { useEffect, useState } from 'react';

// Ход обычного игрока — 30с (дефолт правил); у покинувших/ботов дедлайн короче
// (см. LEFT_SEAT_TIMEOUT_SEC на бэке) — тогда кольцо просто быстро промотает круг.
const ASSUMED_TOTAL_MS = 30_000;

function useCountdownMs(deadline: string | null): number | null {
  const [msLeft, setMsLeft] = useState<number | null>(() => (deadline ? Date.parse(deadline) - Date.now() : null));

  useEffect(() => {
    if (!deadline) {
      setMsLeft(null);
      return;
    }
    const tick = () => setMsLeft(Math.max(0, Date.parse(deadline) - Date.now()));
    tick();
    const id = setInterval(tick, 200);
    return () => clearInterval(id);
  }, [deadline]);

  return msLeft;
}

export function TurnTimer({ deadline, size = 30, invert = false }: { deadline: string | null; size?: number; invert?: boolean }) {
  const msLeft = useCountdownMs(deadline);
  if (msLeft === null) return null;

  const frac = Math.min(1, Math.max(0, msLeft / ASSUMED_TOTAL_MS));
  const r = size / 2 - 2.5;
  const circumference = 2 * Math.PI * r;
  const seconds = Math.ceil(msLeft / 1000);
  const track = invert ? 'rgba(255,255,255,0.35)' : 'var(--line)';
  const stroke = frac < 0.25 ? 'var(--bad)' : invert ? '#fff' : 'var(--accent)';
  const fill = invert ? '#fff' : 'var(--ink)';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block', flexShrink: 0 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth="2.5" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={stroke}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray={`${circumference * frac} ${circumference}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 0.2s linear' }}
      />
      <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle" fontSize={size * 0.4} fontWeight="700" fill={fill}>
        {seconds}
      </text>
    </svg>
  );
}
