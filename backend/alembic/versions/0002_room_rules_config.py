"""own rules per table

Стол может играть по собственному набору правил, собранному при создании,
а не только по редакции из каталога. Поэтому у комнаты появляется `rules_config`,
а ссылка на редакцию перестаёт быть обязательной: заполнено ровно одно из двух.

Revision ID: 0002_room_rules_config
Revises: 0001_initial
Create Date: 2026-09-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002_room_rules_config"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("game_rooms", sa.Column("rules_config", JSONB(), nullable=True))
    op.alter_column("game_rooms", "rules_edition_id", existing_type=UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    # У столов со своими правилами редакции нет и взять её неоткуда, поэтому
    # откат их удаляет (история уходит каскадом) — иначе NOT NULL не поставить.
    op.execute("DELETE FROM game_rooms WHERE rules_edition_id IS NULL")
    op.alter_column("game_rooms", "rules_edition_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.drop_column("game_rooms", "rules_config")
