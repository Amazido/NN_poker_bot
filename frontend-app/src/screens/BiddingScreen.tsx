import { AppHeader, Pill, StatusBar, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand } from '../components/Hand';
import { BidPad, WaitingTurnNote, YourTurnBanner } from '../components/BidPad';
import { ScoreboardModal, useScoreboard } from '../components/Scoreboard';
import { sortHand } from '../lib/cards';
import type { GameView, RoundScoreEvent } from '../types/game';

export interface BiddingScreenProps {
  view: GameView;
  onBid: (n: number) => void;
  onLeave?: () => void;
  lastRoundScore?: RoundScoreEvent | null;
  /** Короткий код комнаты — после старта матча бэк его в GameView уже не отдаёт. */
  roomCode?: string;
}

export function BiddingScreen({ view, onBid, onLeave, lastRoundScore, roomCode }: BiddingScreenProps) {
  const r = view.round!;
  const me = view.me!;
  const bidderName = view.seats.find((s) => s.seat === r.bid_turn)?.username ?? '';
  const myDelta = lastRoundScore?.result[me.seat]?.delta;
  const scoreboard = useScoreboard();

  function handleLeave() {
    if (onLeave && window.confirm('Покинуть матч? За тебя начнут доигрывать автоматически до конца.')) onLeave();
  }

  return (
    <>
      <AppHeader roomCode={roomCode ?? view.room_id} onLeave={onLeave ? handleLeave : undefined} onShowScores={scoreboard.show} />
      <StatusBar>
        {view.rounds_total && (
          <Pill>
            Раздача {view.round_index + 1}/{view.rounds_total}
          </Pill>
        )}
        <TrumpPill round={r} />
        <Pill>{r.cards_count} карт</Pill>
        {r.dealer_seat === me.seat && <Pill>Ты сдаёшь</Pill>}
      </StatusBar>
      <GameTable view={view} mode="bidding" lastRoundScore={lastRoundScore} />
      {me.your_turn && me.available_actions?.type === 'bid' ? (
        <>
          <YourTurnBanner deadline={view.turn_deadline} />
          <BidPad maxBid={r.cards_count} options={me.available_actions.options} onBid={onBid} />
        </>
      ) : (
        <WaitingTurnNote>
          Ход заказа: <b>{bidderName}</b>
        </WaitingTurnNote>
      )}
      <Hand cards={sortHand(me.hand, r.trump_suit)} scoreDelta={myDelta} />
      {scoreboard.open && <ScoreboardModal seats={view.seats} onClose={scoreboard.hide} />}
    </>
  );
}
