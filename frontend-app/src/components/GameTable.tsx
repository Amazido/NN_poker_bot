import { STAGE_W, TABLE_BUBBLE_H, seatTablePositions } from '../lib/layout';
import type { GameView, RoundScoreEvent, Seat } from '../types/game';
import { Card } from './Card';
import styles from './Table.module.css';

function badgeClass(kind: 'turn' | 'waiting' | 'done') {
  return `${styles.oppBadge} ${styles[kind]}`;
}

function TrickLine({ won, bid }: { won: number; bid: number | undefined }) {
  return (
    <div className={styles.oppMeta}>
      взял <b>{won}</b>/{bid ?? '—'}
    </div>
  );
}

function BiddingBadge({ view, seat }: { view: GameView; seat: number }) {
  const r = view.round!;
  const bid = r.bids[seat];
  if (bid !== undefined) return null;
  if (r.bid_turn === seat) return <span className={badgeClass('turn')}>Думает…</span>;
  return <span className={badgeClass('waiting')}>Ожидает</span>;
}

function OpponentSeat({
  view,
  seat,
  mode,
  point,
  scoreDelta,
}: {
  view: GameView;
  seat: Seat;
  mode: 'bidding' | 'playing';
  point: { x: number; y: number };
  scoreDelta: number | null;
}) {
  const r = view.round!;
  const isTurn = mode === 'bidding' ? r.bid_turn === seat.seat : r.current_trick?.turn === seat.seat;
  const hasLeft = view.left_seats?.includes(seat.seat) ?? false;
  const isDealer = r.dealer_seat === seat.seat;
  const bid = r.bids[seat.seat];
  const won = r.tricks_won[seat.seat] ?? 0;

  return (
    <div className={`${styles.oppSeat} ${isTurn ? styles.turn : ''}`} style={{ left: point.x, top: point.y }}>
      <div className={styles.avatarWrap}>
        <div className={`${styles.avatar} ${styles.oppAvatar}`} style={hasLeft ? { opacity: 0.5 } : undefined}>
          {seat.username[0]}
        </div>
        {isDealer && (
          <span className={styles.dealerChip} title="Сдаёт">
            Д
          </span>
        )}
        {scoreDelta !== null && (
          <span className={`${styles.scorePop} ${scoreDelta >= 0 ? styles.scorePopGood : styles.scorePopBad}`}>
            {scoreDelta >= 0 ? `+${scoreDelta}` : scoreDelta}
          </span>
        )}
      </div>
      <div className={styles.oppName}>{seat.username}</div>
      {bid !== undefined && <TrickLine won={won} bid={bid} />}
      {hasLeft ? (
        <span className={badgeClass('waiting')}>Вышел · авто-ход</span>
      ) : mode === 'bidding' ? (
        <BiddingBadge view={view} seat={seat.seat} />
      ) : (
        isTurn && <span className={badgeClass('turn')}>Ходит</span>
      )}
    </div>
  );
}

function SelfSeat({
  view,
  point,
  mode,
}: {
  view: GameView;
  point: { x: number; y: number };
  mode: 'bidding' | 'playing';
}) {
  const r = view.round!;
  const me = view.me!;
  const isTurn = mode === 'bidding' ? r.bid_turn === me.seat : r.current_trick?.turn === me.seat;
  const isDealer = r.dealer_seat === me.seat;

  return (
    <div className={`${styles.oppSeat} ${isTurn ? styles.turn : ''}`} style={{ left: point.x, top: point.y }}>
      <div className={styles.avatarWrap}>
        <div className={`${styles.avatar} ${styles.oppAvatar}`}>{view.seats.find((s) => s.seat === me.seat)?.username[0] ?? 'В'}</div>
        {isDealer && (
          <span className={styles.dealerChip} title="Сдаёшь">
            Д
          </span>
        )}
      </div>
      <div className={styles.oppName}>вы</div>
    </div>
  );
}

function LastTrick({ view }: { view: GameView }) {
  const last = view.round!.last_trick;
  if (!last) return null;
  return (
    <div className={styles.lastTrick}>
      <div className={styles.lastTrickLabel}>Прошлая взятка</div>
      <div className={styles.trickCards}>
        {last.plays.map((p) => {
          const name = view.seats.find((s) => s.seat === p.seat)?.username ?? '';
          const isWinner = p.seat === last.winner;
          return (
            <div key={p.seat} className={styles.trickSlot}>
              <div className={isWinner ? styles.winnerCard : undefined}>
                <Card code={p.card} size="sm" />
              </div>
              <div className={`${styles.who} ${isWinner ? styles.whoWinner : ''}`}>{isWinner ? `✓ ${name}` : name}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CenterZone({ view, mode }: { view: GameView; mode: 'bidding' | 'playing' }) {
  const r = view.round!;
  if (mode === 'bidding') {
    return (
      <div className={styles.centerZone}>
        <div className={styles.centerHint}>Идут торги</div>
      </div>
    );
  }
  if (!r.current_trick || r.current_trick.plays.length === 0) {
    return (
      <div className={styles.centerZone}>
        <div className={styles.centerHint}>Взятка №{r.trick_number}</div>
        <LastTrick view={view} />
      </div>
    );
  }
  return (
    <div className={styles.centerZone}>
      <div className={styles.centerHint}>Взятка №{r.trick_number}</div>
      <div className={styles.trickCards}>
        {r.current_trick.plays.map((p) => {
          const name = view.seats.find((s) => s.seat === p.seat)?.username ?? '';
          return (
            <div key={p.seat} className={styles.trickSlot}>
              <Card code={p.card} size="sm" />
              <div className={styles.who}>{name}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function GameTable({
  view,
  mode,
  lastRoundScore,
}: {
  view: GameView;
  mode: 'bidding' | 'playing';
  lastRoundScore?: RoundScoreEvent | null;
}) {
  const meSeat = view.me!.seat;
  const points = seatTablePositions(Math.max(view.n_players, view.seats.length), STAGE_W, TABLE_BUBBLE_H, meSeat);
  const opponents = view.seats.filter((s) => s.seat !== meSeat);

  return (
    <div className={styles.tableWrap}>
      <div className={styles.tableOval} />
      {opponents.map((seat) => (
        <OpponentSeat
          key={seat.seat}
          view={view}
          seat={seat}
          mode={mode}
          point={points[seat.seat]}
          scoreDelta={lastRoundScore?.result[seat.seat]?.delta ?? null}
        />
      ))}
      <SelfSeat view={view} point={points[meSeat]} mode={mode} />
      <CenterZone view={view} mode={mode} />
    </div>
  );
}
