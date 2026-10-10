import { useState } from 'react';
import { STAGE_W, TABLE_BUBBLE_H, seatTablePositions } from '../lib/layout';
import type { GameView, LastTrick, RoundScoreEvent, Seat, TrickPlay } from '../types/game';
import { Card } from './Card';
import styles from './Table.module.css';

function badgeClass(kind: 'turn' | 'waiting' | 'done') {
  return `${styles.oppBadge} ${styles[kind]}`;
}

function TrickLine({ won, bid, blind }: { won: number; bid: number | undefined; blind?: boolean }) {
  return (
    <div className={styles.oppMeta}>
      взял <b>{won}</b>/{bid ?? '—'}
      {blind && (
        <span className={styles.blindMark} title="Заказ сделан втёмную">
          втёмную
        </span>
      )}
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
      {bid !== undefined && <TrickLine won={won} bid={bid} blind={r.blind_bids?.[seat.seat]} />}
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
  scoreDelta,
}: {
  view: GameView;
  point: { x: number; y: number };
  mode: 'bidding' | 'playing';
  scoreDelta: number | null;
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
        {scoreDelta !== null && (
          <span className={`${styles.scorePop} ${styles.scorePopBeside} ${scoreDelta >= 0 ? styles.scorePopGood : styles.scorePopBad}`}>
            {scoreDelta >= 0 ? `+${scoreDelta}` : scoreDelta}
          </span>
        )}
      </div>
      <div className={styles.oppName}>вы</div>
    </div>
  );
}

/** Ряд карт взятки с именами; `winner` отмечает забравшего, если он уже известен. */
function TrickRow({ seats, plays, winner }: { seats: Seat[]; plays: TrickPlay[]; winner?: number }) {
  return (
    <div className={styles.trickCards}>
      {plays.map((p) => {
        const name = seats.find((s) => s.seat === p.seat)?.username ?? '';
        const isWinner = p.seat === winner;
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
  );
}

function LastTrickOverlay({ view, trick, onClose }: { view: GameView; trick: LastTrick; onClose: () => void }) {
  const name = view.seats.find((s) => s.seat === trick.winner)?.username ?? '';
  return (
    <div className={styles.trickOverlay} onClick={onClose}>
      <div className={styles.trickOverlayCard} onClick={(e) => e.stopPropagation()}>
        <div className={styles.centerHint}>
          Взятка №{trick.trick_number} · забрал <b>{name}</b>
        </div>
        <TrickRow seats={view.seats} plays={trick.plays} winner={trick.winner} />
        <button className={styles.trickCloseBtn} onClick={onClose}>
          Закрыть
        </button>
      </div>
    </div>
  );
}

function CenterZone({
  view,
  mode,
  heldTrick,
}: {
  view: GameView;
  mode: 'bidding' | 'playing';
  heldTrick?: LastTrick | null;
}) {
  const r = view.round!;

  // Задержанная взятка главнее всего остального: иначе её перекроет либо
  // следующая взятка, либо торги нового кона — бэк открывает их сразу.
  if (heldTrick) {
    const name = view.seats.find((s) => s.seat === heldTrick.winner)?.username ?? '';
    return (
      <div className={styles.centerZone}>
        <div className={styles.centerHint}>
          Взятка №{heldTrick.trick_number} · забрал <b>{name}</b>
        </div>
        <TrickRow seats={view.seats} plays={heldTrick.plays} winner={heldTrick.winner} />
      </div>
    );
  }

  if (mode === 'bidding') {
    return (
      <div className={styles.centerZone}>
        <div className={styles.centerHint}>Идут торги</div>
      </div>
    );
  }

  return (
    <div className={styles.centerZone}>
      <div className={styles.centerHint}>Взятка №{r.trick_number}</div>
      {r.current_trick && r.current_trick.plays.length > 0 && (
        <TrickRow seats={view.seats} plays={r.current_trick.plays} />
      )}
    </div>
  );
}

export function GameTable({
  view,
  mode,
  lastRoundScore,
  heldTrick,
}: {
  view: GameView;
  mode: 'bidding' | 'playing';
  lastRoundScore?: RoundScoreEvent | null;
  /** Добитая взятка, которую ещё держим на столе (см. `useTrickHold`). */
  heldTrick?: LastTrick | null;
}) {
  const meSeat = view.me!.seat;
  const points = seatTablePositions(Math.max(view.n_players, view.seats.length), STAGE_W, TABLE_BUBBLE_H, meSeat);
  const opponents = view.seats.filter((s) => s.seat !== meSeat);
  const lastTrick = view.round?.last_trick ?? null;
  const [lastOpen, setLastOpen] = useState(false);

  return (
    <div className={styles.tableWrap}>
      <div className={styles.tableOval} />
      {lastTrick && (
        <button className={styles.lastTrickBtn} onClick={() => setLastOpen(true)}>
          Прошлая взятка
        </button>
      )}
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
      <SelfSeat view={view} point={points[meSeat]} mode={mode} scoreDelta={lastRoundScore?.result[meSeat]?.delta ?? null} />
      <CenterZone view={view} mode={mode} heldTrick={heldTrick} />
      {lastOpen && lastTrick && <LastTrickOverlay view={view} trick={lastTrick} onClose={() => setLastOpen(false)} />}
    </div>
  );
}
