"""Лёгкие структуры для входных данных движка.

Сам игровой стейт движок хранит как обычный dict (сериализуемый в JSON для
Redis) — см. engine.py. Здесь только вход: список игроков за столом.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class SeatInput:
    """Игрок за столом на момент старта матча."""
    seat: int
    user_id: str
    username: str


def seats_payload(seats: List[SeatInput]) -> List[dict]:
    return [{"seat": s.seat, "user_id": s.user_id, "username": s.username, "score": 0} for s in seats]
