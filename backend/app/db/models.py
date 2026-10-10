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
    text,
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


class SeasonStatus:
    UPCOMING = "upcoming"  # заведён, но ещё не начался
    ACTIVE = "active"      # идёт; ровно один такой (см. partial unique index)
    CLOSED = "closed"      # закончился, результаты заморожены


class MatchOutcome:
    COMPLETED = "completed"  # доиграли все раздачи
    ABANDONED = "abandoned"  # все вышли; финальным стал счёт на момент выхода


class RatingEventKind:
    SEED = "seed"              # вход в сезон с начальным рейтингом
    MATCH = "match"            # результат матча
    ADJUSTMENT = "adjustment"  # правка руками
    RECALC = "recalc"          # пересчёт по новой формуле


class RoundPhase:
    BIDDING = "bidding"     # торги
    PLAYING = "playing"     # розыгрыш взяток
    SCORING = "scoring"     # подсчёт
    FINISHED = "finished"


class ActionType:
    BID = "bid"            # заказ взяток
    PLAY_CARD = "play_card"  # ход картой
    OPEN_HAND = "open_hand"  # раскрыть руку до заказа (отказ от «тёмной»)


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
    # Стол играет либо по редакции из каталога, либо по собственным правилам,
    # которые хозяин собрал при создании. Заполнено ровно одно из двух полей:
    # ссылка на редакцию нужна, чтобы сезон мог отличить «свой» стол от
    # эталонного, а не только по совпадению конфигов.
    rules_edition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules_editions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rules_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
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

    rules_edition: Mapped[Optional["RulesEditionModel"]] = relationship(back_populates="rooms")
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


class SeasonModel(Base):
    """Сезон: отрезок времени, в котором считается рейтинг.

    Живёт отдельно от редакции правил, потому что у них разные жизненные циклы:
    редакция неизменяема и вечна (на неё ссылаются сыгранные матчи), а сезон
    начинается, идёт и закрывается. `rules_edition_id` — эталон лиги: матч
    зачётный, если стол играл именно по этой редакции.
    """
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rules_edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules_editions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=SeasonStatus.ACTIVE, nullable=False, index=True)
    # Рейтинг, с которого игрок входит в сезон. Хранится у сезона, а не в коде:
    # прошлые сезоны должны читаться своими числами и после смены формулы.
    initial_rating: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        # Двух активных сезонов быть не может: иначе непонятно, в какой зачёт
        # идёт матч и чей рейтинг показывать. Сторожит база, а не код.
        Index(
            "uq_one_active_season",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Season {self.code} ({self.status})>"


class MatchModel(Base):
    """Завершённый матч — факт, живущий дольше комнаты.

    Комната остаётся живым объектом (её состояние чистится, Redis-стейт живёт
    сутки), а матч нужен для истории и рейтинга, поэтому его итог фиксируется
    отдельной записью в момент завершения. `rated` отвечает на вопрос «пошёл ли
    матч в зачёт», `unrated_reason` — почему нет (см. `poker/rating.py`).
    """
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # RESTRICT, а не CASCADE: результат матча не должен исчезнуть вместе со столом.
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_rooms.id", ondelete="RESTRICT"),
        unique=True, nullable=False, index=True,
    )
    # Сезон, который шёл в момент матча, — контекст, а не признак зачёта:
    # нерейтинговые матчи тоже нужны в метриках сезона.
    season_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rules_edition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules_editions.id", ondelete="RESTRICT"), nullable=True
    )
    rated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    unrated_reason: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), default=MatchOutcome.COMPLETED, nullable=False)
    n_players: Mapped[int] = mapped_column(Integer, nullable=False)
    # Сколько раздач успели сыграть и сколько было в плане: у брошенного матча
    # это главный признак «доиграли почти всё» против «вышли на первом кону».
    rounds_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rounds_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    players: Mapped[List["MatchPlayerModel"]] = relationship(back_populates="match")

    def __repr__(self) -> str:
        return f"<Match {self.id} ({self.outcome}, rated={self.rated})>"


class MatchPlayerModel(Base):
    """Результат одного игрока в матче плюс его рейтинг на момент матча.

    `rating_before` пишется и у нерейтингового матча: «с каким рейтингом люди
    садились» — метрика сама по себе, независимо от того, пошёл ли зачёт.
    У рейтингового матча заполнены все три поля рейтинга, у остальных — только
    `rating_before` (и то лишь если сезон вообще шёл).
    """
    __tablename__ = "match_players"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    place: Mapped[int] = mapped_column(Integer, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Покинул матч по своей воле (за него доигрывал авто-ход). Результат всё
    # равно идёт в зачёт — иначе выход стал бы способом не портить рейтинг.
    left_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rating_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating_delta: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    match: Mapped["MatchModel"] = relationship(back_populates="players")
    user: Mapped["UserModel"] = relationship()

    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_match_user"),
        UniqueConstraint("match_id", "seat_index", name="uq_match_seat"),
    )

    def __repr__(self) -> str:
        return f"<MatchPlayer match={self.match_id} seat={self.seat_index} place={self.place}>"


class RatingEventModel(Base):
    """Append-only журнал изменений рейтинга: по нему рейтинг и считается.

    Текущего рейтинга отдельной таблицей нет намеренно: он выводится как
    `season.initial_rating + SUM(delta)`. Пока игроков десятки, это дешевле, чем
    держать второе место правды, которое может разойтись с журналом. А главное —
    формулу собираются менять: пересчёт тогда будет перезаписью журнала, и
    «почему у меня такой рейтинг» останется на что ответить.
    """
    __tablename__ = "rating_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default=RatingEventKind.MATCH, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_before: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # Чем объясняем запись человеку: место в матче, правка руками, пересчёт.
    note: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    __table_args__ = (
        # Один матч меняет рейтинг игрока ровно один раз. Запись результата
        # идемпотентна и по этому ограничению тоже — сторожит база.
        UniqueConstraint("match_id", "user_id", name="uq_rating_event_match_user"),
        Index("ix_rating_events_season_user", "season_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<RatingEvent {self.kind} user={self.user_id} {self.delta:+d}>"


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
