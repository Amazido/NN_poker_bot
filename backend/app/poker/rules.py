"""Редакция правил: конфиг варианта, последовательность раундов, подсчёт очков.

Конфиг хранится в rules_editions.config (JSONB). RulesEdition ниже — тонкая
обёртка над dict со значениями по умолчанию, чтобы движок не зависел от того,
какие ключи заданы в конкретной редакции.
"""
import copy
from typing import Any, Dict, List, Optional

DECK_SIZE = 54

# Дефолтная редакция «odessa_classic v1».
DEFAULT_CONFIG: Dict[str, Any] = {
    "deck": {"cards": 54, "jokers": 2},
    "players": {"min": 3, "max": 5},
    # up_plateau_down: 1..peak-1, затем peak повторяется n раз (каждый игрок
    # сдаёт «пик» по разу), затем peak-1..1. Всего 2*(peak-1)+n = 18+n при peak=10.
    "rounds": {"mode": "up_plateau_down", "peak": 10},
    "scoring": {
        "exact_per_trick": 10,   # точный заказ: +10 за каждую взятку
        "exact_zero_bonus": 10,  # заказал 0 и взял 0: фикс +10
        "over": -5,              # перебор: фикс -5
        "under_per_trick": -10,  # недобор: -10 за каждую недобранную
    },
    "jokers": {
        "offcolor_beats_oncolor": False,
        "two_beats_ace_same_suit": False,
    },
    "turn_timeout_sec": 30,
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class RulesEdition:
    """Обёртка над config редакции с дефолтами и удобными аксессорами."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = _deep_merge(DEFAULT_CONFIG, config or {})

    # --- Игроки ---
    @property
    def min_players(self) -> int:
        return int(self.config["players"]["min"])

    @property
    def max_players(self) -> int:
        return int(self.config["players"]["max"])

    # --- Джокеры / флаги сравнения ---
    @property
    def flags(self) -> Dict[str, bool]:
        return dict(self.config.get("jokers", {}))

    @property
    def turn_timeout_sec(self) -> int:
        return int(self.config.get("turn_timeout_sec", 30))

    # --- Последовательность раундов ---
    def round_sequence(self, n_players: int) -> List[int]:
        """Список длин раздач (карт на игрока) для матча из n_players."""
        rounds = self.config["rounds"]
        mode = rounds.get("mode", "up_plateau_down")

        if mode == "custom":
            seq = [int(x) for x in rounds.get("sequence", [])]
        elif mode == "up_plateau_down":
            peak = int(rounds.get("peak", 10))
            up = list(range(1, peak))            # 1..peak-1
            plateau = [peak] * n_players         # peak повторяется n раз
            down = list(range(peak - 1, 0, -1))  # peak-1..1
            seq = up + plateau + down
        elif mode == "up_down":
            peak = int(rounds.get("peak", 10))
            seq = list(range(1, peak + 1)) + list(range(peak - 1, 0, -1))
        else:
            raise ValueError(f"Unknown rounds mode: {mode}")

        # Ограничение колоды: c*n + 1 <= DECK_SIZE.
        max_cards = (DECK_SIZE - 1) // n_players
        capped = [min(c, max_cards) for c in seq]
        if any(c < 1 for c in capped):
            raise ValueError("Invalid round sequence (non-positive card count)")
        return capped

    # --- Подсчёт очков раздачи ---
    def score(self, bid: int, tricks_won: int) -> int:
        s = self.config["scoring"]
        if tricks_won == bid:
            if bid == 0:
                return int(s["exact_zero_bonus"])
            return int(s["exact_per_trick"]) * tricks_won
        if tricks_won > bid:
            return int(s["over"])
        return int(s["under_per_trick"]) * (bid - tricks_won)

    # --- Ограничение «крюка» на торгах ---
    def forbidden_last_bid(self, cards_count: int, others_bid_sum: int) -> Optional[int]:
        """Запрещённый заказ для последнего в очереди (сдающего).

        Нельзя сделать сумму заказов равной числу карт в раздаче.
        """
        value = cards_count - others_bid_sum
        if 0 <= value <= cards_count:
            return value
        return None

    def allowed_bids(
        self, cards_count: int, is_last_bidder: bool, others_bid_sum: int
    ) -> List[int]:
        """Доступные значения заказа для игрока."""
        options = list(range(0, cards_count + 1))
        if is_last_bidder:
            forbidden = self.forbidden_last_bid(cards_count, others_bid_sum)
            if forbidden is not None:
                options = [b for b in options if b != forbidden]
        return options
