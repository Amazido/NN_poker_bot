"""seasons, match results and rating journal

Результат матча перестаёт быть свойством живой комнаты и становится отдельным
фактом: `matches` (чем кончился, пошёл ли в зачёт и почему нет) плюс
`match_players` (счёт, место, покинул ли матч, рейтинг на момент матча).
Рейтинг считается по append-only журналу `rating_events` — отдельной таблицы с
текущим значением намеренно нет, см. модель.

Revision ID: 0003_seasons_and_ratings
Revises: 0002_room_rules_config
Create Date: 2026-10-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0003_seasons_and_ratings"
down_revision: Union[str, None] = "0002_room_rules_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "rules_edition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rules_editions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("initial_rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_seasons_code", "seasons", ["code"], unique=True)
    op.create_index("ix_seasons_status", "seasons", ["status"])
    op.create_index("ix_seasons_rules_edition_id", "seasons", ["rules_edition_id"])
    # Активный сезон может быть только один — иначе непонятно, в какой зачёт
    # идёт матч. Частичный уникальный индекс сторожит это на уровне базы.
    op.create_index(
        "uq_one_active_season",
        "seasons",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "room_id",
            UUID(as_uuid=True),
            sa.ForeignKey("game_rooms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "season_id",
            UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "rules_edition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rules_editions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("rated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unrated_reason", sa.String(30), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("n_players", sa.Integer(), nullable=False),
        sa.Column("rounds_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rounds_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_matches_room_id", "matches", ["room_id"], unique=True)
    op.create_index("ix_matches_season_id", "matches", ["season_id"])
    op.create_index("ix_matches_rated", "matches", ["rated"])
    op.create_index("ix_matches_finished_at", "matches", ["finished_at"])

    op.create_table(
        "match_players",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "match_id",
            UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("seat_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("place", sa.Integer(), nullable=False),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("left_match", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rating_before", sa.Integer(), nullable=True),
        sa.Column("rating_delta", sa.Integer(), nullable=True),
        sa.Column("rating_after", sa.Integer(), nullable=True),
        sa.UniqueConstraint("match_id", "user_id", name="uq_match_user"),
        sa.UniqueConstraint("match_id", "seat_index", name="uq_match_seat"),
    )
    op.create_index("ix_match_players_match_id", "match_players", ["match_id"])
    op.create_index("ix_match_players_user_id", "match_players", ["user_id"])

    op.create_table(
        "rating_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "season_id",
            UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False, server_default="match"),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("rating_before", sa.Integer(), nullable=False),
        sa.Column("rating_after", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Один матч меняет рейтинг игрока ровно один раз.
        sa.UniqueConstraint("match_id", "user_id", name="uq_rating_event_match_user"),
    )
    op.create_index("ix_rating_events_season_id", "rating_events", ["season_id"])
    op.create_index("ix_rating_events_user_id", "rating_events", ["user_id"])
    op.create_index("ix_rating_events_match_id", "rating_events", ["match_id"])
    op.create_index("ix_rating_events_created_at", "rating_events", ["created_at"])
    op.create_index("ix_rating_events_season_user", "rating_events", ["season_id", "user_id"])


def downgrade() -> None:
    # Порядок обратный созданию: журнал рейтинга ссылается на матчи и сезоны.
    op.drop_table("rating_events")
    op.drop_table("match_players")
    op.drop_table("matches")
    op.drop_table("seasons")
