import { Pill, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand } from '../components/Hand';
import { PlayHint, WaitingTurnNote } from '../components/BidPad';
import { ScoreboardModal, useScoreboard } from '../components/Scoreboard';
import { sortHand } from '../lib/cards';
import type { CardCode, GameView, RoundScoreEvent } from '../types/game';
import { MatchLayout } from './MatchLayout';
import matchStyles from './MatchLayout.module.css';

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
          <Pill>{r.cards_count} карт</Pill>
        </>
      }
      table={<GameTable view={view} mode="playing" lastRoundScore={lastRoundScore} />}
      controls={
        <>
          <div className={matchStyles.controlTop}>
            {me.your_turn ? (
              <PlayHint deadline={view.turn_deadline}>Сбрось карту</PlayHint>
            ) : (
              <WaitingTurnNote deadline={view.turn_deadline}>
                Ходит: <b>{turnName}</b>
              </WaitingTurnNote>
            )}
          </div>
          <Hand cards={sortHand(me.hand, r.trump_suit)} legal={legal} onPlay={onPlay} scoreDelta={myDelta} />
        </>
      }
      />
      {scoreboard.open && <ScoreboardModal seats={view.seats} onClose={scoreboard.hide} />}
    </>
  );
}
