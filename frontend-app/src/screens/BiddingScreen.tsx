import { MyTrickPill, Pill, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand, HiddenHand } from '../components/Hand';
import { BidPad, OpenHandRow, WaitingTurnNote } from '../components/BidPad';
import { ScoreboardModal, useScoreboard } from '../components/Scoreboard';
import { sortHand } from '../lib/cards';
import type { GameView, RoundScoreEvent } from '../types/game';
import { MatchLayout } from './MatchLayout';
import matchStyles from './MatchLayout.module.css';

export interface BiddingScreenProps {
  view: GameView;
  onBid: (n: number) => void;
  /** «Тёмная»: отказаться от слепого заказа и посмотреть карты. */
  onOpenHand?: () => void;
  onLeave?: () => void;
  lastRoundScore?: RoundScoreEvent | null;
  /** Короткий код комнаты — после старта матча бэк его в GameView уже не отдаёт. */
  roomCode?: string;
}

export function BiddingScreen({ view, onBid, onOpenHand, onLeave, lastRoundScore, roomCode }: BiddingScreenProps) {
  const r = view.round!;
  const me = view.me!;
  const blindBonus = view.rules?.blind_bonus ?? 0;
  const bidderName = view.seats.find((s) => s.seat === r.bid_turn)?.username ?? '';
  const scoreboard = useScoreboard();

  function handleLeave() {
    if (onLeave && window.confirm('Покинуть матч? За тебя начнут доигрывать автоматически до конца.')) onLeave();
  }

  return (
    <>
      <MatchLayout
      roomCode={roomCode ?? view.room_id}
      onLeave={onLeave ? handleLeave : undefined}
      onShowScores={scoreboard.show}
      status={
        <>
          {view.rounds_total && (
            <Pill>
              Кон {view.round_index + 1}/{view.rounds_total}
            </Pill>
          )}
          <TrumpPill round={r} />
          <MyTrickPill round={r} seat={me.seat} />
          <Pill>{r.cards_count} карт</Pill>
        </>
      }
      table={<GameTable view={view} mode="bidding" lastRoundScore={lastRoundScore} />}
      controls={
        <>
          <div className={matchStyles.controlTop}>
            {me.can_open_hand && onOpenHand && <OpenHandRow bonus={blindBonus} onOpen={onOpenHand} />}
            {me.your_turn && me.available_actions?.type === 'bid' ? (
              <BidPad
                maxBid={r.cards_count}
                options={me.available_actions.options}
                onBid={onBid}
                deadline={view.turn_deadline}
                blind={me.hand_hidden ? { bonus: blindBonus } : undefined}
              />
            ) : (
              <WaitingTurnNote deadline={view.turn_deadline}>
                Ход заказа: <b>{bidderName}</b>
              </WaitingTurnNote>
            )}
          </div>
          {me.hand_hidden ? <HiddenHand count={me.hand_count} /> : <Hand cards={sortHand(me.hand, r.trump_suit)} />}
        </>
      }
      />
      {scoreboard.open && <ScoreboardModal seats={view.seats} rules={view.rules} onClose={scoreboard.hide} />}
    </>
  );
}
