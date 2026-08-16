"""SQLAlchemy-модели для PostgreSQL.

Игровой live-стейт (руки, текущая взятка, доступные действия) живёт в Redis.
В Postgres храним: пользователей, редакции правил, комнаты, посадку, раздачи
(rounds) и append-only журнал действий (round_actions) — для истории и
восстановления после рестарта.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# === Строковые константы статусов ===

class UserType:
    TELEGRAM = "telegram"
    DEV = "dev"
    BOT = "bot"


class UserStatus:
    ACTIVE = "active"
    ARCHIVED = "archived"


class RoomStatus:
    LOBBY = "lobby"        # ждём игроков
    PLAYING = "playing"    # матч идёт
    FINISHED = "finished"  # матч завершён


class RoomPlayerStatus:
    ACTIVE = "active"
    LEFT = "left"


class RoundPhase:
    BIDDING = "bidding"     # торги
    PLAYING = "playing"     # розыгрыш взяток
    SCORING = "scoring"     # подсчёт
    FINISHED = "finished"


class ActionType:
    BID = "bid"            # заказ взяток
    PLAY_CARD = "play_card"  # ход картой


def _now() -> datetime:
    return datetime.now(timezone.utc)


# === Модели ===

class UserModel(Base):
    """Пользователи платформы."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_type: Mapped[str] = mapped_column(String(20), default=UserType.TELEGRAM, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.id} ({self.user_type})>"


class RulesEditionModel(Base):
    """Редакция правил + мета. Версионируется по (code, version).

    config — параметры варианта (колода, игроки, последовательность раундов,
    подсчёт очков, поведение джокеров, тайминги). meta — описание/автор/заметки.
    """
    __tablename__ = "rules_editions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    rooms: Mapped[List["GameRoomModel"]] = relationship(back_populates="rules_edition")

    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_rules_code_version"),
    )

    def __repr__(self) -> str:
        return f"<RulesEdition {self.code} v{self.version}>"


class GameRoomModel(Base):
    """Игровая комната (стол). Держит матч из последовательности раздач."""
    __tablename__ = "game_rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    join_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    rules_edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules_editions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RoomStatus.LOBBY, nullable=False, index=True)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Индекс текущей раздачи в последовательности матча (0-based).
    round_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Стартовый сдающий матча (случайный). Сдающий раздачи = (starting_dealer + round_index) % n.
    starting_dealer_seat: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_round_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    rules_edition: Mapped["RulesEditionModel"] = relationship(back_populates="rooms")
    players: Mapped[List["RoomPlayerModel"]] = relationship(back_populates="room")
    rounds: Mapped[List["GameRoundModel"]] = relationship(back_populates="room")

    def __repr__(self) -> str:
        return f"<GameRoom {self.join_code} ({self.status})>"


class RoomPlayerModel(Base):
    """Посадка игрока за стол (место + накопленный счёт матча)."""
    __tablename__ = "room_players"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RoomPlayerStatus.ACTIVE, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    room: Mapped["GameRoomModel"] = relationship(back_populates="players")
    user: Mapped["UserModel"] = relationship()

    __table_args__ = (
        UniqueConstraint("room_id", "seat_index", name="uq_room_seat"),
        UniqueConstraint("room_id", "user_id", name="uq_room_user"),
    )

    def __repr__(self) -> str:
        return f"<RoomPlayer room={self.room_id} seat={self.seat_index}>"


class GameRoundModel(Base):
    """Раздача (round) внутри комнаты: сдача → торги → взятки → счёт.

    rules_snapshot фиксирует, какая редакция правил применялась к этой раздаче.
    """
    __tablename__ = "game_rounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cards_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dealer_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    trump_card: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    trump_suit: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    no_trump: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), default=RoundPhase.BIDDING, nullable=False, index=True)
    # {seat: bid}
    bids: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {seat: tricks_won}
    tricks_won: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Итоги раздачи: {seat: {"bid":.., "won":.., "delta":.., "total":..}}
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    room: Mapped["GameRoomModel"] = relationship(back_populates="rounds")
    actions: Mapped[List["RoundActionModel"]] = relationship(back_populates="round")

    __table_args__ = (
        UniqueConstraint("room_id", "round_index", name="uq_room_round_index"),
        Index("ix_rounds_room_phase", "room_id", "phase"),
    )

    def __repr__(self) -> str:
        return f"<GameRound room={self.room_id} #{self.round_index} ({self.phase})>"


class RoundActionModel(Base):
    """Append-only журнал игровых действий (источник истины для истории)."""
    __tablename__ = "round_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # bid: {"bid": n}; play_card: {"card": "SA", "trick": 1}
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    round: Mapped["GameRoundModel"] = relationship(back_populates="actions")

    __table_args__ = (
        UniqueConstraint("round_id", "seq", name="uq_round_action_seq"),
        Index("ix_actions_round_seq", "round_id", "seq"),
    )

    def __repr__(self) -> str:
        return f"<RoundAction {self.action_type} seat={self.seat} seq={self.seq}>"
