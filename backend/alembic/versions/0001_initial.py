"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("user_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "rules_editions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("meta", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", "version", name="uq_rules_code_version"),
    )
    op.create_index("ix_rules_editions_code", "rules_editions", ["code"])
    op.create_index("ix_rules_editions_is_active", "rules_editions", ["is_active"])

    op.create_table(
        "game_rooms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("join_code", sa.String(length=12), nullable=False),
        sa.Column("rules_edition_id", UUID(as_uuid=True), sa.ForeignKey("rules_editions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("starting_dealer_seat", sa.Integer(), nullable=True),
        sa.Column("current_round_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_game_rooms_join_code", "game_rooms", ["join_code"], unique=True)
    op.create_index("ix_game_rooms_rules_edition_id", "game_rooms", ["rules_edition_id"])
    op.create_index("ix_game_rooms_status", "game_rooms", ["status"])

    op.create_table(
        "room_players",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("room_id", "seat_index", name="uq_room_seat"),
        sa.UniqueConstraint("room_id", "user_id", name="uq_room_user"),
    )
    op.create_index("ix_room_players_room_id", "room_players", ["room_id"])
    op.create_index("ix_room_players_user_id", "room_players", ["user_id"])

    op.create_table(
        "game_rounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("cards_count", sa.Integer(), nullable=False),
        sa.Column("dealer_seat", sa.Integer(), nullable=False),
        sa.Column("trump_card", sa.String(length=4), nullable=True),
        sa.Column("trump_suit", sa.String(length=1), nullable=True),
        sa.Column("no_trump", sa.Boolean(), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("bids", JSONB(), nullable=False),
        sa.Column("tricks_won", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("room_id", "round_index", name="uq_room_round_index"),
    )
    op.create_index("ix_game_rounds_room_id", "game_rounds", ["room_id"])
    op.create_index("ix_game_rounds_phase", "game_rounds", ["phase"])
    op.create_index("ix_rounds_room_phase", "game_rounds", ["room_id", "phase"])

    op.create_table(
        "round_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("round_id", UUID(as_uuid=True), sa.ForeignKey("game_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("round_id", "seq", name="uq_round_action_seq"),
    )
    op.create_index("ix_round_actions_round_id", "round_actions", ["round_id"])
    op.create_index("ix_round_actions_room_id", "round_actions", ["room_id"])
    op.create_index("ix_actions_round_seq", "round_actions", ["round_id", "seq"])


def downgrade() -> None:
    op.drop_table("round_actions")
    op.drop_table("game_rounds")
    op.drop_table("room_players")
    op.drop_table("game_rooms")
    op.drop_table("rules_editions")
    op.drop_table("users")
