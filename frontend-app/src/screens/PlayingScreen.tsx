import { AppHeader, Pill, StatusBar, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand } from '../components/Hand';
import { WaitingTurnNote, YourTurnBanner } from '../components/BidPad';
import { ScoreboardModal, useScoreboard } from '../components/Scoreboard';
import { sortHand } from '../lib/cards';
import type { CardCode, GameView, RoundScoreEvent } from '../types/game';

export interface PlayingScreenProps {
  view: GameView;
  onPlay: (code: CardCode) => void;
  onLeave?: () => void;
  lastRoundScore?: RoundScoreEvent | null;
  /** Короткий код комнаты — после старта матча бэк его в GameView уже не отдаёт. */
  roomCode?: string;
}

export function PlayingScreen({ view, onPlay, onLeave, lastRoundScore, roomCode }: PlayingScreenProps) {
  const r = view.round!;
  const me = view.me!;
  const turnName = view.seats.find((s) => s.seat === r.current_trick?.turn)?.username ?? '';
  const legal = me.your_turn && me.available_actions?.type === 'play' ? new Set(me.available_actions.cards) : null;
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
      <GameTable view={view} mode="playing" lastRoundScore={lastRoundScore} />
      {me.your_turn ? (
        <YourTurnBanner deadline={view.turn_deadline} />
      ) : (
        <WaitingTurnNote>
          Ходит: <b>{turnName}</b>
        </WaitingTurnNote>
      )}
      <Hand cards={sortHand(me.hand, r.trump_suit)} legal={legal} onPlay={onPlay} scoreDelta={myDelta} />
      {scoreboard.open && <ScoreboardModal seats={view.seats} onClose={scoreboard.hide} />}
    </>
  );
}
