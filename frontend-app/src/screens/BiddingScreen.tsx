import { AppHeader, Pill, StatusBar, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand } from '../components/Hand';
import { BidPad, WaitingTurnNote } from '../components/BidPad';
import type { GameView } from '../types/game';

export interface BiddingScreenProps {
  view: GameView;
  onBid: (n: number) => void;
  /** Короткий код комнаты — после старта матча бэк его в GameView уже не отдаёт. */
  roomCode?: string;
}

export function BiddingScreen({ view, onBid, roomCode }: BiddingScreenProps) {
  const r = view.round!;
  const me = view.me!;
  const dealerName = view.seats.find((s) => s.seat === r.dealer_seat)?.username ?? '';
  const bidderName = view.seats.find((s) => s.seat === r.bid_turn)?.username ?? '';

  return (
    <>
      <AppHeader roomCode={roomCode ?? view.room_id} />
      <StatusBar>
        {view.rounds_total && (
          <Pill>
            Раздача {view.round_index + 1}/{view.rounds_total}
          </Pill>
        )}
        <TrumpPill round={r} />
        <Pill>{r.cards_count} карт</Pill>
        <Pill>Сдаёт: {dealerName}</Pill>
      </StatusBar>
      <GameTable view={view} mode="bidding" />
      {me.your_turn && me.available_actions?.type === 'bid' ? (
        <BidPad maxBid={r.cards_count} options={me.available_actions.options} onBid={onBid} />
      ) : (
        <WaitingTurnNote>
          Ход заказа: <b>{bidderName}</b>
        </WaitingTurnNote>
      )}
      <Hand cards={me.hand} />
    </>
  );
}
