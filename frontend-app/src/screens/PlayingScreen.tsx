import { AppHeader, Pill, StatusBar, TrumpPill } from '../components/AppHeader';
import { GameTable } from '../components/GameTable';
import { Hand } from '../components/Hand';
import { WaitingTurnNote } from '../components/BidPad';
import type { CardCode, GameView } from '../types/game';

export interface PlayingScreenProps {
  view: GameView;
  onPlay: (code: CardCode) => void;
  onLeave?: () => void;
  /** Короткий код комнаты — после старта матча бэк его в GameView уже не отдаёт. */
  roomCode?: string;
}

export function PlayingScreen({ view, onPlay, onLeave, roomCode }: PlayingScreenProps) {
  const r = view.round!;
  const me = view.me!;
  const dealerName = view.seats.find((s) => s.seat === r.dealer_seat)?.username ?? '';
  const turnName = view.seats.find((s) => s.seat === r.current_trick?.turn)?.username ?? '';
  const legal = me.your_turn && me.available_actions?.type === 'play' ? new Set(me.available_actions.cards) : null;

  function handleLeave() {
    if (onLeave && window.confirm('Покинуть матч? За тебя начнут доигрывать автоматически до конца.')) onLeave();
  }

  return (
    <>
      <AppHeader roomCode={roomCode ?? view.room_id} onLeave={onLeave ? handleLeave : undefined} />
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
      <GameTable view={view} mode="playing" />
      {!me.your_turn && (
        <WaitingTurnNote>
          Ходит: <b>{turnName}</b>
        </WaitingTurnNote>
      )}
      <Hand cards={me.hand} legal={legal} onPlay={onPlay} />
    </>
  );
}
